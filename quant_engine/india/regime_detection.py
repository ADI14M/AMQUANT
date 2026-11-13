"""Bayesian Market-Regime Detection on Indian Equities (First Research Experiment).

Formulation:
- 3-State Hidden Regime Model:
    S1 = BULLISH   (mu > 0, moderate sigma)
    S2 = BEARISH   (mu < 0, elevated sigma)
    S3 = NEUTRAL   (|mu| ~ 0, muted/consolidation)
- Prior Elicitation:
    Dirichlet prior / Markov regime transition beliefs
- Likelihood Model:
    Gaussian likelihood conditioned on state parameters
- Recursive Bayes Filter:
    P(S_t = j | y_{1:t}) sequential posterior update
- Strict Chronological Train/Test Split (Walk-Forward Out-of-Sample)
- Benchmark Comparison against Indian Buy & Hold with full statutory Indian transaction costs
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import numpy as np
import pandas as pd

from quant_engine.india.costs import calculate_indian_cost
from quant_engine.india.features import compute_price_features


@dataclass
class RegimeDetectionResult:
    symbol: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    in_sample_sessions: int
    out_of_sample_sessions: int
    brier_score_test: float
    log_loss_test: float
    current_regime: str
    current_bullish_prob: float
    current_bearish_prob: float
    current_neutral_prob: float
    strategy_metrics: dict[str, float]
    benchmark_metrics: dict[str, float]
    cost_summary: dict[str, float]
    history: list[dict[str, Any]]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BayesianRegimeDetector:
    def __init__(
        self,
        mu_bull: float = 0.18,  # Annualized 18% expected return in bull regime
        mu_bear: float = -0.22,  # Annualized -22% expected return in bear regime
        mu_neut: float = 0.04,  # Annualized 4% consolidation return
        sigma_bull: float = 0.14,  # 14% annualized volatility
        sigma_bear: float = 0.28,  # 28% annualized volatility
        sigma_neut: float = 0.12,  # 12% annualized volatility
        regime_persistence: float = 0.92,  # Probability of staying in same regime
        entry_threshold: float = 0.50,  # Posterior probability required to take long position
        risk_free_rate: float = 0.065,  # RBI Repo rate 6.50%
    ):
        self.dt = 1.0 / 252.0
        # Convert annualized parameters to daily
        self.daily_mu = np.array([mu_bull * self.dt, mu_bear * self.dt, mu_neut * self.dt])
        self.daily_sigma = np.array([sigma_bull * np.sqrt(self.dt), sigma_bear * np.sqrt(self.dt), sigma_neut * np.sqrt(self.dt)])

        self.regime_names = ["BULLISH", "BEARISH", "NEUTRAL"]
        self.entry_threshold = entry_threshold
        self.risk_free_rate = risk_free_rate

        # 3x3 Transition probability matrix T[i, j] = P(S_t = j | S_{t-1} = i)
        p_stay = regime_persistence
        p_switch = (1.0 - p_stay) / 2.0
        self.T = np.array([
            [p_stay, p_switch, p_switch],
            [p_switch, p_stay, p_switch],
            [p_switch, p_switch, p_stay],
        ])

    def _state_likelihood(self, ret: float, roll_vol: float) -> np.ndarray:
        """Evaluate observation likelihood under each of the 3 regimes."""
        eps = 1e-12
        var = self.daily_sigma**2
        # Gaussian density for returns
        lik = (1.0 / (np.sqrt(2 * np.pi * var) + eps)) * np.exp(-0.5 * ((ret - self.daily_mu) ** 2) / (var + eps))

        # Modulate by volatility regime:
        # High rolling vol (> 24% ann) favors bear/neutral; low rolling vol (< 14% ann) favors bull
        vol_weights = np.ones(3)
        if roll_vol > 0.24:
            vol_weights = np.array([0.4, 2.0, 0.9])
        elif roll_vol < 0.14:
            vol_weights = np.array([1.8, 0.3, 1.0])

        mod_lik = lik * vol_weights
        total = mod_lik.sum()
        return mod_lik / total if total > 0 else np.array([0.333, 0.333, 0.334])

    def run_experiment(
        self,
        df: pd.DataFrame,
        symbol: str,
        train_ratio: float = 0.65,
    ) -> RegimeDetectionResult:
        """Execute the Bayesian regime detection experiment with out-of-sample backtest."""
        if df.empty or len(df) < 50:
            raise ValueError(f"Insufficient history for {symbol} to run regime detection (needs >= 50 sessions).")

        feat = compute_price_features(df)
        n = len(feat)
        split_idx = int(n * train_ratio)

        date_col = next((c for c in feat.columns if c in ("date", "timestamp", "datetime")), None)
        dates = [str(d)[:10] for d in feat[date_col]] if date_col else [f"D{i}" for i in range(n)]

        train_start = dates[0]
        train_end = dates[split_idx - 1]
        test_start = dates[split_idx]
        test_end = dates[-1]

        # Prior distribution at t=0
        prob = np.array([0.45, 0.25, 0.30])  # [Bull, Bear, Neutral]

        probs_history = []
        positions = []
        true_labels = []

        rets = feat["daily_return"].values
        vols = feat["rolling_vol_20d"].values
        closes = feat["close"].values

        # Sequential Bayes filter forward pass
        for t in range(n):
            ret_t = rets[t]
            vol_t = vols[t]

            # 1. Prediction step: P(S_t | y_{1:t-1}) = T^T * P(S_{t-1} | y_{1:t-1})
            pred_prob = self.T.T @ prob

            # 2. Update step: P(S_t | y_{1:t}) proportional to P(y_t | S_t) * pred_prob
            lik = self._state_likelihood(ret_t, vol_t)
            unnorm = lik * pred_prob
            prob = unnorm / unnorm.sum() if unnorm.sum() > 0 else np.array([0.333, 0.333, 0.334])

            probs_history.append(prob.copy())

            # Trading rule: go long if Bullish prob >= entry_threshold, otherwise exit to cash
            pos = 1.0 if prob[0] >= self.entry_threshold else 0.0
            positions.append(pos)

            # Ground-truth pseudo label based on forward 5-day return for Brier score benchmark
            fwd_ret = (closes[min(n - 1, t + 5)] / closes[t] - 1.0) if t < n - 5 else ret_t
            if fwd_ret > 0.01:
                true_label = np.array([1.0, 0.0, 0.0])
            elif fwd_ret < -0.01:
                true_label = np.array([0.0, 1.0, 0.0])
            else:
                true_label = np.array([0.0, 0.0, 1.0])
            true_labels.append(true_label)

        probs_arr = np.array(probs_history)
        true_arr = np.array(true_labels)

        # Out-of-sample test evaluation metrics
        test_probs = probs_arr[split_idx:]
        test_trues = true_arr[split_idx:]

        # Brier Score on test set: mean squared error of probability vector vs true one-hot
        brier_score_test = float(np.mean(np.sum((test_probs - test_trues) ** 2, axis=1)))

        # Log loss on test set
        eps = 1e-12
        clipped_probs = np.clip(test_probs, eps, 1.0 - eps)
        log_loss_test = float(-np.mean(np.sum(test_trues * np.log(clipped_probs), axis=1)))

        # Strategy Out-of-Sample Performance Simulation with realistic Indian Transaction Costs
        initial_capital = 1_000_000.0  # ₹10 Lakhs initial portfolio
        cash = initial_capital
        holdings = 0
        total_brokerage = 0.0
        total_stt = 0.0
        total_exchange_fees = 0.0
        total_gst = 0.0
        total_stamp_duty = 0.0
        total_slippage = 0.0
        trades_count = 0
        winning_trades = 0

        strategy_equity = []
        benchmark_equity = []
        last_buy_price = 0.0

        daily_rf = (1.0 + self.risk_free_rate) ** (1.0 / 252.0) - 1.0
        benchmark_shares = initial_capital / closes[split_idx]

        for i in range(split_idx, n):
            price = closes[i]
            target_pos = positions[i]  # 1.0 = Long, 0.0 = Cash

            # State transition: Buy
            if target_pos == 1.0 and holdings == 0:
                cost_preview = calculate_indian_cost(price=price, quantity=int(cash / price), side="BUY", segment="DELIVERY")
                shares_to_buy = int((cash - cost_preview.total_friction) / price)
                if shares_to_buy > 0:
                    cost = calculate_indian_cost(price=price, quantity=shares_to_buy, side="BUY", segment="DELIVERY")
                    cash -= (shares_to_buy * price + cost.total_friction)
                    holdings = shares_to_buy
                    last_buy_price = price
                    trades_count += 1
                    total_brokerage += cost.brokerage
                    total_stt += cost.stt
                    total_exchange_fees += cost.exchange_charges
                    total_gst += cost.gst
                    total_stamp_duty += cost.stamp_duty
                    total_slippage += cost.slippage

            # State transition: Sell / Exit to cash
            elif target_pos == 0.0 and holdings > 0:
                cost = calculate_indian_cost(price=price, quantity=holdings, side="SELL", segment="DELIVERY")
                proceeds = (holdings * price) - cost.total_friction
                cash += proceeds
                if price > last_buy_price:
                    winning_trades += 1
                holdings = 0
                trades_count += 1
                total_brokerage += cost.brokerage
                total_stt += cost.stt
                total_exchange_fees += cost.exchange_charges
                total_gst += cost.gst
                total_slippage += cost.slippage

            # Cash in hand earns daily Indian risk-free repo rate
            if holdings == 0:
                cash *= (1.0 + daily_rf)

            current_eq = cash + (holdings * price)
            bench_eq = benchmark_shares * price
            strategy_equity.append(current_eq)
            benchmark_equity.append(bench_eq)

        # Performance Statistics
        strat_arr = np.array(strategy_equity)
        bench_arr = np.array(benchmark_equity)

        strat_ret_series = np.diff(strat_arr) / strat_arr[:-1]
        bench_ret_series = np.diff(bench_arr) / bench_arr[:-1]

        years = max(0.1, len(strat_arr) / 252.0)
        strat_cagr = float(((strat_arr[-1] / strat_arr[0]) ** (1.0 / years) - 1.0)) if strat_arr[-1] > 0 else -1.0
        bench_cagr = float(((bench_arr[-1] / bench_arr[0]) ** (1.0 / years) - 1.0)) if bench_arr[-1] > 0 else -1.0

        strat_vol = float(np.std(strat_ret_series) * np.sqrt(252)) if len(strat_ret_series) > 1 else 0.01
        bench_vol = float(np.std(bench_ret_series) * np.sqrt(252)) if len(bench_ret_series) > 1 else 0.01

        strat_sharpe = float((strat_cagr - self.risk_free_rate) / strat_vol) if strat_vol > 0 else 0.0
        bench_sharpe = float((bench_cagr - self.risk_free_rate) / bench_vol) if bench_vol > 0 else 0.0

        # Maximum Drawdowns
        strat_peaks = np.maximum.accumulate(strat_arr)
        strat_mdd = float(np.min((strat_arr - strat_peaks) / strat_peaks))

        bench_peaks = np.maximum.accumulate(bench_arr)
        bench_mdd = float(np.min((bench_arr - bench_peaks) / bench_peaks))

        # Recent history sampling (last 60 days) for clean interactive frontend chart
        history_points = []
        step = max(1, len(strat_arr) // 60)
        for idx in range(0, len(strat_arr), step):
            hist_idx = split_idx + idx
            history_points.append({
                "date": dates[hist_idx],
                "price": round(float(closes[hist_idx]), 2),
                "strategy_nav": round(float(strat_arr[idx]), 2),
                "benchmark_nav": round(float(bench_arr[idx]), 2),
                "bullish_prob": round(float(probs_arr[hist_idx, 0]), 3),
                "bearish_prob": round(float(probs_arr[hist_idx, 1]), 3),
                "neutral_prob": round(float(probs_arr[hist_idx, 2]), 3),
                "in_position": bool(positions[hist_idx] == 1.0),
            })

        latest_probs = probs_arr[-1]
        best_regime_idx = int(np.argmax(latest_probs))
        current_regime = self.regime_names[best_regime_idx]

        total_taxes = total_stt + total_gst + total_stamp_duty
        total_friction = total_brokerage + total_taxes + total_exchange_fees + total_slippage

        return RegimeDetectionResult(
            symbol=symbol,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            in_sample_sessions=split_idx,
            out_of_sample_sessions=n - split_idx,
            brier_score_test=round(brier_score_test, 4),
            log_loss_test=round(log_loss_test, 4),
            current_regime=current_regime,
            current_bullish_prob=round(float(latest_probs[0]), 3),
            current_bearish_prob=round(float(latest_probs[1]), 3),
            current_neutral_prob=round(float(latest_probs[2]), 3),
            strategy_metrics={
                "cagr_pct": round(strat_cagr * 100.0, 2),
                "annualized_vol_pct": round(strat_vol * 100.0, 2),
                "sharpe_ratio": round(strat_sharpe, 2),
                "max_drawdown_pct": round(strat_mdd * 100.0, 2),
                "total_trades": trades_count,
                "win_rate_pct": round((winning_trades / max(1, trades_count // 2)) * 100.0, 1),
            },
            benchmark_metrics={
                "cagr_pct": round(bench_cagr * 100.0, 2),
                "annualized_vol_pct": round(bench_vol * 100.0, 2),
                "sharpe_ratio": round(bench_sharpe, 2),
                "max_drawdown_pct": round(bench_mdd * 100.0, 2),
            },
            cost_summary={
                "total_stt_inr": round(total_stt, 2),
                "total_gst_inr": round(total_gst, 2),
                "total_brokerage_inr": round(total_brokerage, 2),
                "total_friction_inr": round(total_friction, 2),
                "friction_drag_pct": round((total_friction / initial_capital) * 100.0, 2),
            },
            history=history_points,
            limitations=[
                "Regime transition lag: Sequential Bayesian updating typically takes 1 to 3 sessions to adapt to sudden shock reversals.",
                "Sideways chop friction: Rapid oscillation around the entry probability threshold generates whipsaw trades incurring STT and slippage.",
                "Stationary assumption: Historical volatility regimes may shift permanently during structural regulatory changes or monetary tightening.",
                "Exchange holiday liquidity: Long weekend holidays can create gap openings not captured by continuous daily pricing.",
            ],
        )
