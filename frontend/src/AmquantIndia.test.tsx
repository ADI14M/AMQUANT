import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import AmquantIndia from './modules/AmquantIndia'

afterEach(() => {
  cleanup()
})

// Mock AuthContext
vi.mock('./context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'test-user-123', email: 'trader@amquant.in' },
    session: { access_token: 'mock-token' },
    loading: false,
    openAuthModal: vi.fn(),
  }),
  AuthProvider: ({ children }: any) => children,
}))

// Mock API calls
vi.mock('./lib/api', async () => {
  const actual = await vi.importActual('./lib/api')
  return {
    ...actual,
    getIndiaMarketOverview: vi.fn().mockResolvedValue({
      macro_snapshot: {
        rbi_repo_rate: 6.5,
        india_10y_gsec_yield: 6.82,
        t_bill_91d_yield: 6.65,
        cpi_inflation: 5.12,
        usd_inr_rate: 84.38,
        india_vix: 13.85,
        as_of_date: '2026-11-12',
        provenance_source: 'Reserve Bank of India (RBI)',
      },
      macro_history: [
        { period: '2024-Q3', repo_rate: 6.5, gsec_10y: 6.86, cpi: 3.65, usd_inr: 83.95, vix: 13.2 },
        { period: '2024-Q4', repo_rate: 6.5, gsec_10y: 6.82, cpi: 5.12, usd_inr: 84.38, vix: 13.85 },
      ],
      headline_quotes: [
        { symbol: 'NIFTY 50', ticker: '^NSEI', price: 25299.35, previous_close: 25255.05, change: 44.3, change_pct: 0.18, currency: 'INR', exchange: 'NSE' },
        { symbol: 'SENSEX', ticker: '^BSESN', price: 82500.0, previous_close: 82300.0, change: 200.0, change_pct: 0.24, currency: 'INR', exchange: 'BSE' },
      ],
      market_breadth: {
        total_analyzed: 5,
        advances: 3,
        declines: 2,
        unchanged: 0,
        advance_decline_ratio: 1.5,
        pct_above_50d_sma: 60.0,
        pct_above_200d_sma: 80.0,
      },
    }),
    getIndiaInstruments: vi.fn().mockResolvedValue([
      {
        symbol: 'RELIANCE',
        exchange: 'NSE',
        isin: 'INE002A01018',
        company_name: 'Reliance Industries Ltd.',
        instrument_type: 'EQUITY',
        sector: 'Oil, Gas & Energy',
        market_cap_category: 'LARGE_CAP',
        tick_size: 0.05,
        lot_size: 250,
        has_derivatives: true,
        yahoo_ticker: 'RELIANCE.NS',
      },
      {
        symbol: 'NIFTY 50',
        exchange: 'NSE',
        isin: 'IN9000000001',
        company_name: 'NIFTY 50 Benchmark Index',
        instrument_type: 'INDEX',
        sector: 'Benchmark',
        market_cap_category: 'BROAD_MARKET',
        tick_size: 0.05,
        lot_size: 25,
        has_derivatives: true,
        yahoo_ticker: '^NSEI',
      },
      {
        symbol: 'NIFTYBEES',
        exchange: 'NSE',
        isin: 'INF204KB14I2',
        company_name: 'Nippon India ETF Nifty 50 BeES',
        instrument_type: 'ETF',
        sector: 'Index ETF',
        market_cap_category: 'BROAD_MARKET',
        tick_size: 0.01,
        lot_size: 1,
        has_derivatives: false,
        yahoo_ticker: 'NIFTYBEES.NS',
      },
    ]),
    getIndiaHistory: vi.fn().mockResolvedValue({
      symbol: 'NIFTY 50',
      total_bars: 50,
      start_date: '2024-01-01',
      end_date: '2024-03-01',
      series: [
        { date: '2024-01-01', open: 21500, high: 21600, low: 21450, close: 21550, volume: 50000, turnover_cr: 107.5, daily_return_pct: 0.5, rolling_vol_pct: 12.5, drawdown_pct: 0.0, sma_20: 21500, sma_50: 21400, amihud_illiq: 0.004 },
        { date: '2024-01-02', open: 21550, high: 21700, low: 21500, close: 21650, volume: 60000, turnover_cr: 129.9, daily_return_pct: 0.46, rolling_vol_pct: 12.8, drawdown_pct: 0.0, sma_20: 21520, sma_50: 21410, amihud_illiq: 0.003 },
      ],
    }),
    runBayesianRegimeExperiment: vi.fn().mockResolvedValue({
      symbol: 'NIFTY 50',
      train_start: '2023-01-01',
      train_end: '2023-12-31',
      test_start: '2024-01-01',
      test_end: '2024-11-12',
      in_sample_sessions: 250,
      out_of_sample_sessions: 150,
      brier_score_test: 1.15,
      log_loss_test: 2.34,
      current_regime: 'BULLISH',
      current_bullish_prob: 0.55,
      current_bearish_prob: 0.25,
      current_neutral_prob: 0.2,
      strategy_metrics: { cagr_pct: 14.5, annualized_vol_pct: 12.2, sharpe_ratio: 0.65, max_drawdown_pct: -8.5, total_trades: 6, win_rate_pct: 66.7 },
      benchmark_metrics: { cagr_pct: 12.0, annualized_vol_pct: 14.8, sharpe_ratio: 0.37, max_drawdown_pct: -11.2 },
      cost_summary: { total_stt_inr: 4500.0, total_gst_inr: 81.0, total_brokerage_inr: 120.0, total_friction_inr: 5800.0, friction_drag_pct: 0.58 },
      history: [
        { date: '2024-01-01', price: 21550, strategy_nav: 1000000, benchmark_nav: 1000000, bullish_prob: 0.6, bearish_prob: 0.2, neutral_prob: 0.2, in_position: true },
      ],
      limitations: [
        'Regime transition lag: Sequential Bayesian updating typically takes 1 to 3 sessions to adapt to sudden shock reversals.',
      ],
    }),
    runIndiaBacktest: vi.fn().mockResolvedValue({
      strategy_name: 'SMA Crossover (20/50)',
      symbol: 'NIFTY 50',
      benchmark_symbol: 'NIFTY 50 Benchmark',
      start_date: '2023-01-01',
      end_date: '2024-11-12',
      initial_capital_inr: 1000000,
      ending_capital_inr: 1145000,
      cagr_pct: 13.8,
      annualized_vol_pct: 11.5,
      sharpe_ratio: 0.63,
      sortino_ratio: 0.89,
      max_drawdown_pct: -9.2,
      calmar_ratio: 1.5,
      win_rate_pct: 60.0,
      total_trades: 8,
      annual_turnover_pct: 250.0,
      total_stt_paid_inr: 6200.0,
      total_gst_paid_inr: 95.0,
      total_brokerage_paid_inr: 160.0,
      total_friction_inr: 8100.0,
      benchmark_cagr_pct: 11.4,
      benchmark_sharpe: 0.34,
      benchmark_max_drawdown_pct: -12.5,
      equity_curve: [
        { date: '2023-01-01', strategy_nav: 1000000, benchmark_nav: 1000000, drawdown_pct: 0.0 },
      ],
    }),
    getIndiaDataCoverage: vi.fn().mockResolvedValue({
      status: 'operational',
      storage_engine: 'DuckDB + Apache Parquet',
      duckdb_database: '/data/duckdb/amquant_india.duckdb',
      total_parquet_files: 10,
      total_size_kb: 308.5,
      stages: {
        raw: { file_count: 5, total_size_kb: 142.0, symbols_stored: ['NIFTY 50', 'RELIANCE'] },
        cleaned: { file_count: 5, total_size_kb: 166.5, symbols_stored: ['NIFTY 50', 'RELIANCE'] },
      },
      missing_coverage: [
        { dataset: 'Corporate Announcements & Audio Transcripts', status: 'Available via NSE RSS/API' },
      ],
    }),
    getHistoryManagerCoverage: vi.fn().mockResolvedValue({
      instruments: [
        { symbol: 'RELIANCE', first_date: '2021-11-12', last_date: '2026-11-12', total_sessions: 1236, missing_sessions_estimate: 68, has_adjusted: true, has_total_return: true, file_size_kb: 75.5 },
        { symbol: 'TCS', first_date: '2021-11-12', last_date: '2026-11-11', total_sessions: 1235, missing_sessions_estimate: 69, has_adjusted: true, has_total_return: true, file_size_kb: 76.2 },
      ],
      total_instruments_with_data: 2,
      storage_summary: { total_size_kb: 151.7 },
    }),
    getIndiaUniverseStats: vi.fn().mockResolvedValue({
      total: 108,
      active: 103,
      inactive: 5,
      by_exchange: { BSE: 8, NSE: 100 },
      by_instrument_type: { EQUITY: 81, ETF: 10, INDEX: 17 },
      by_market_cap_category: { BROAD_MARKET: 27, LARGE_CAP: 44, MID_CAP: 17, SMALL_CAP: 20 },
    }),
    startHistoryDownload: vi.fn().mockResolvedValue({
      total_requested: 2,
      successful: 2,
      failed: 0,
      total_records: 2471,
      elapsed_seconds: 4.2,
      results: [
        { symbol: 'RELIANCE', success: true, records: 1236, start_date: '2021-11-12', end_date: '2026-11-12' },
        { symbol: 'TCS', success: true, records: 1235, start_date: '2021-11-12', end_date: '2026-11-11' },
      ],
    }),
    getIndiaCorporateActions: vi.fn().mockResolvedValue({
      symbol: 'RELIANCE',
      total_actions: 35,
      actions: [
        { action_type: 'SPLIT', ex_date: '2017-09-07', ratio: 2.0, source: 'Yahoo Finance', notes: 'Split 2:1' },
      ],
      validation: { is_valid: true, turnover_preserved: true, issues: [] },
    }),
    getIndiaSeriesComparison: vi.fn().mockResolvedValue({
      symbol: 'RELIANCE',
      has_raw: true,
      has_adjusted: true,
      has_total_return: true,
      series: [
        { date: '2024-01-01', value: 2500, series: 'Raw' },
        { date: '2024-01-01', value: 2500, series: 'Adjusted' },
      ],
    }),
    getIndiaBacktestStrategies: vi.fn().mockResolvedValue([
      {
        id: 'SMA_20_50',
        name: 'SMA 20/50 Golden Cross',
        category: 'TREND_FOLLOWING',
        description: 'Classic dual simple moving average trend crossover.',
        entry_rule: 'Buy Day t+1 Open when SMA(20) crosses above SMA(50) at Day t Close.',
        exit_rule: 'Sell Day t+1 Open when SMA(20) crosses below SMA(50) at Day t Close.',
        parameters: [
          { name: 'fast_period', display_name: 'Fast Period', param_type: 'int', default_value: 20, min_value: 5, max_value: 100 },
          { name: 'slow_period', display_name: 'Slow Period', param_type: 'int', default_value: 50, min_value: 20, max_value: 300 },
        ],
      },
      {
        id: 'RSI_MEAN_REVERSION',
        name: 'RSI Mean Reversion (14, 30/70)',
        category: 'MEAN_REVERSION',
        description: 'Contrarian mean-reversion strategy.',
        entry_rule: 'Buy Day t+1 Open when RSI(14) crosses below oversold (30).',
        exit_rule: 'Sell Day t+1 Open when RSI(14) crosses above overbought (70).',
        parameters: [
          { name: 'rsi_period', display_name: 'RSI Period', param_type: 'int', default_value: 14, min_value: 5, max_value: 50 },
          { name: 'oversold', display_name: 'Oversold Level', param_type: 'float', default_value: 30.0, min_value: 10.0, max_value: 45.0 },
          { name: 'overbought', display_name: 'Overbought Level', param_type: 'float', default_value: 70.0, min_value: 55.0, max_value: 90.0 },
        ],
      },
    ]),
    runAdvancedIndiaBacktest: vi.fn().mockResolvedValue({
      config: {
        strategy_name: 'SMA 20/50 Golden Cross',
        symbols: ['RELIANCE'],
        start_date: '2021-11-12',
        end_date: '2026-11-12',
      },
      strategy_id: 'SMA_20_50',
      strategy_name: 'SMA 20/50 Golden Cross',
      parameters: { fast_period: 20, slow_period: 50 },
      start_date: '2021-11-12',
      end_date: '2026-11-12',
      symbols: ['RELIANCE'],
      initial_capital: 1000000,
      ending_capital: 1450200,
      summary_metrics: {
        total_return_net_pct: 45.02,
        total_return_gross_pct: 48.15,
        net_cagr_pct: 12.35,
        gross_cagr_pct: 13.12,
        net_pnl_inr: 450200,
        win_rate_pct: 58.5,
        profit_factor: 1.82,
        max_drawdown_pct: -14.2,
        max_drawdown_duration_days: 64,
        sharpe_ratio: 0.72,
        sortino_ratio: 1.05,
        calmar_ratio: 0.87,
        annualized_vol_pct: 15.2,
        avg_win_inr: 32500,
        avg_loss_inr: -14200,
        avg_win_pct: 5.4,
        avg_loss_pct: -2.3,
        payoff_ratio: 2.29,
        avg_holding_period_days: 18.5,
        total_trades: 28,
        winning_trades: 16,
        losing_trades: 12,
        annual_turnover_pct: 210.0,
        total_transaction_costs_inr: 31300,
      },
      benchmark_comparison: {
        benchmark_symbol: 'NIFTY 50 (^NSEI)',
        benchmark_total_return_pct: 38.4,
        benchmark_cagr_pct: 10.8,
        benchmark_annualized_vol_pct: 14.1,
        benchmark_sharpe: 0.58,
        benchmark_max_drawdown_pct: -16.5,
        alpha_cagr_pct: 1.55,
        beta: 0.88,
      },
      transaction_costs_summary: {
        total_brokerage_inr: 1120,
        total_stt_inr: 21500,
        total_exchange_txn_inr: 720,
        total_sebi_charges_inr: 22,
        total_stamp_duty_inr: 1650,
        total_gst_inr: 340,
        total_slippage_inr: 5948,
        total_friction_inr: 31300,
        friction_drag_on_cagr_pct: 0.77,
      },
      walk_forward_splits: {
        train_start: '2021-11-12',
        train_end: '2025-05-12',
        in_sample_return_pct: 32.4,
        test_start: '2025-05-13',
        test_end: '2026-11-12',
        out_of_sample_return_pct: 12.62,
      },
      equity_curve: [
        { date: '2021-11-12', strategy_nav: 1000000, strategy_gross_nav: 1000000, benchmark_nav: 1000000, drawdown_pct: 0.0, cash: 1000000, positions_value: 0 },
        { date: '2026-11-12', strategy_nav: 1450200, strategy_gross_nav: 1481500, benchmark_nav: 1384000, drawdown_pct: -2.1, cash: 1450200, positions_value: 0 },
      ],
      monthly_returns: [
        { year: 2024, Jan: 2.1, Feb: -1.2, Mar: 3.5, Apr: 0.8, May: -0.5, Jun: 4.2, Jul: 1.1, Aug: -0.2, Sep: 2.0, Oct: -1.5, Nov: 1.8, Dec: 2.5, Year: 15.3 },
      ],
      trades: [
        {
          trade_id: 'TRD-1',
          symbol: 'RELIANCE',
          entry_date: '2024-01-15',
          entry_price: 2450.0,
          shares: 400,
          exit_date: '2024-02-20',
          exit_price: 2620.0,
          gross_pnl_inr: 68000.0,
          net_pnl_inr: 66250.0,
          return_pct: 6.94,
          holding_period_days: 36,
          exit_reason: 'SIGNAL_EXIT',
          friction_inr: 1750.0,
        },
      ],
      warnings: [],
      execution_assumptions: {
        execution_timing: 'Next-session Open (Day t+1)',
        slippage_bps: 5.0,
        stop_loss_pct: 5.0,
        take_profit_pct: 15.0,
        trailing_stop_pct: null,
        position_sizing_rule: 'PERCENT_OF_EQUITY (100%)',
        look_ahead_bias_audit: 'PASSED - zero lookahead bias verified',
      },
    }),
    createSavedScenario: vi.fn().mockResolvedValue({
      id: 'scen-saved-123',
      name: 'Reliance Golden Cross Backtest',
      module_name: 'india',
      created_at: '2026-11-13T12:00:00Z',
    }),
    getIndiaIntradayHistory: vi.fn().mockResolvedValue({
      symbol: 'RELIANCE',
      interval: '5m',
      total_bars: 75,
      series: [
        { datetime: '2024-06-10 09:15:00', datetime_str: '2024-06-10 09:15:00', open: 2950, high: 2960, low: 2945, close: 2955, volume: 25000 },
        { datetime: '2024-06-10 09:20:00', datetime_str: '2024-06-10 09:20:00', open: 2955, high: 2965, low: 2950, close: 2960, volume: 18000 },
      ],
      quality_report: {
        symbol: 'RELIANCE',
        interval: '5m',
        total_bars: 75,
        total_sessions: 1,
        start_timestamp: '2024-06-10 09:15:00',
        end_timestamp: '2024-06-10 15:30:00',
        overall_completeness_pct: 100.0,
        total_missing_bars: 0,
        duplicate_bars_removed: 0,
        out_of_session_bars_filtered: 0,
        provider: 'Yahoo Finance (Free Public Endpoint)',
        sessions_audit: [
          { date: '2024-06-10', bars_found: 75, bars_expected: 75, completeness_pct: 100.0, first_candle_time: '09:15:00', last_candle_time: '15:25:00', is_complete: true, missing_bars_count: 0 },
        ],
      },
    }),
    downloadIndiaIntraday: vi.fn().mockResolvedValue({
      success: true,
      symbol: 'RELIANCE',
      interval: '5m',
      new_records_added: 75,
      total_records: 75,
      metadata: { records_count: 75 },
      quality_report: { overall_completeness_pct: 100.0 },
    }),
    getIndiaDerivativesContracts: vi.fn().mockResolvedValue([
      { symbol: 'NIFTY24DECFUT', underlying_symbol: 'NIFTY 50', exchange: 'NSE', contract_type: 'FUTIDX', expiry_date: '2024-12-26', strike_price: 0, option_type: null, lot_size: 75 },
      { symbol: 'NIFTY24DEC24500CE', underlying_symbol: 'NIFTY 50', exchange: 'NSE', contract_type: 'OPTIDX', expiry_date: '2024-12-26', strike_price: 24500, option_type: 'CE', lot_size: 75 },
    ]),
    getIndiaDerivativesLotSizes: vi.fn().mockResolvedValue({
      underlying: 'NIFTY 50',
      current_lot_size: 75,
      revisions_count: 5,
      history: [
        { underlying: 'NIFTY 50', start_date: '2024-11-20', end_date: 'Present', lot_size: 75 },
      ],
      regulatory_notes: 'SEBI Circular Nov 2024',
    }),
    getIndiaContinuousFutures: vi.fn().mockResolvedValue({
      underlying: 'NIFTY 50',
      method: 'BACK_ADJUSTED_DIFFERENCE',
      is_continuous: true,
      execution_disclaimer: 'Never treat a continuous futures series as an executable contract.',
      total_bars: 250,
      start_date: '2024-01-01',
      end_date: '2024-12-26',
      rollover_events: [
        { roll_date: '2024-10-30', from_contract: 'NIFTY24OCTFUT', to_contract: 'NIFTY24NOVFUT', near_close: 24300, next_close: 24350, roll_spread: 50, ratio: 1.002 },
      ],
      series: [
        { date: '2024-01-01', open: 21500, high: 21600, low: 21400, close: 21550, volume: 50000, open_interest: 800000 },
      ],
    }),
    getIndiaOptionChain: vi.fn().mockResolvedValue({
      underlying: 'NIFTY 50',
      underlying_price: 24520.5,
      as_of_date: '2024-12-01',
      expiry_date: '2024-12-26',
      days_to_expiry: 25,
      pcr_oi: 1.15,
      pcr_volume: 0.98,
      max_pain_strike: 24500,
      total_call_oi: 450000,
      total_put_oi: 517500,
      total_call_volume: 120000,
      total_put_volume: 118000,
      disclaimer: 'Greeks are analytical model estimates',
      strikes: [
        {
          strike: 24500,
          is_atm: true,
          call: { strike: 24500, option_type: 'CE', last_price: 220, close: 220, iv: 13.8, delta: 0.52, gamma: 0.0012, theta: -8.5, vega: 14.2, is_model_estimate: true, volume: 15000, open_interest: 45000 },
          put: { strike: 24500, option_type: 'PE', last_price: 195, close: 195, iv: 14.2, delta: -0.48, gamma: 0.0012, theta: -7.9, vega: 14.2, is_model_estimate: true, volume: 14000, open_interest: 52000 },
        },
      ],
    }),
    getIndiaProviders: vi.fn().mockResolvedValue([
      {
        provider_id: 'yahoo',
        name: 'Yahoo Finance (Free Public Endpoint)',
        auth_requirements: 'None (Public Endpoints)',
        historical_depth_daily: '5 to 10+ years daily OHLCV',
        historical_depth_intraday: '1m: 7 days | 5m: 60 days',
        supported_intervals: ['1m', '5m', '15m', '30m', '60m', '1d'],
        rate_limits: '0.25s throttle (~4 req/s)',
        cost_inr_gbp: '£0 / ₹0 (Zero subscription cost)',
        licensing_restrictions: 'Personal research use only',
        status: 'ACTIVE_FREE',
        notes: 'Primary zero-cost collector',
      },
    ]),
    getIntradayStrategiesCatalog: vi.fn().mockResolvedValue([
      { id: 'VWAP_REVERSION', name: 'VWAP Mean Reversion', description: 'Mean reversion to session VWAP bands', parameters: {}, higher_timeframe_supported: true },
      { id: 'OPENING_RANGE_BREAKOUT', name: 'Opening Range Breakout', description: '15m ORB', parameters: {}, higher_timeframe_supported: false },
    ]),
    runIntradayBacktest: vi.fn().mockResolvedValue({
      config: { strategy_id: 'VWAP_REVERSION', symbol: 'RELIANCE', timeframe: '5m' },
      trades: [
        {
          trade_id: 'IT-001',
          symbol: 'RELIANCE',
          direction: 'BUY',
          entry_time: '2024-01-02 09:30:00',
          entry_price: 2500.0,
          exit_time: '2024-01-02 15:15:00',
          exit_price: 2530.0,
          quantity: 20,
          gross_pnl: 600.0,
          total_costs: 35.5,
          net_pnl: 564.5,
          return_pct: 1.2,
          exit_reason: 'EOD_SQUAREOFF',
          bars_held: 69,
        },
      ],
      total_trades: 1,
      winning_trades: 1,
      losing_trades: 0,
      win_rate: 1.0,
      profit_factor: 16.9,
      gross_pnl: 600.0,
      total_costs: 35.5,
      net_pnl: 564.5,
      return_on_capital: 0.0028,
      max_drawdown_pct: 0.005,
      max_drawdown_amount: 1000.0,
      sharpe_ratio: 2.15,
      sortino_ratio: 3.1,
      calmar_ratio: 1.8,
      average_trade_pnl: 564.5,
      avg_win: 564.5,
      avg_loss: 0.0,
      largest_win: 564.5,
      largest_loss: 0.0,
      equity_curve: [{ datetime: '2024-01-02 15:15:00', equity: 200564.5, cash: 200564.5, drawdown_pct: 0 }],
      walk_forward_metrics: {
        in_sample: { trades: 1, win_rate: 1.0, net_pnl: 564.5 },
        out_of_sample: { trades: 0, win_rate: 0.0, net_pnl: 0 },
        in_sample_bars: 70,
        out_of_sample_bars: 30,
        sharpe_degradation_pct: 5.0,
      },
    }),
    runFuturesBacktest: vi.fn().mockResolvedValue({
      config: { underlying: 'NIFTY', strategy_type: 'TREND_FOLLOWING' },
      trades: [
        {
          contract_symbol: 'NIFTY24JANFUT',
          underlying: 'NIFTY',
          direction: 'BUY',
          entry_date: '2024-01-02',
          entry_price: 21500.0,
          exit_date: '2024-01-25',
          exit_price: 21750.0,
          lot_size: 50,
          num_lots: 1,
          total_quantity: 50,
          gross_pnl: 12500.0,
          total_costs: 420.0,
          net_pnl: 12080.0,
          exit_reason: 'ROLLOVER',
          roll_spread: 45.0,
          basis_at_entry: 30.0,
        },
      ],
      total_trades: 1,
      winning_trades: 1,
      losing_trades: 0,
      win_rate: 1.0,
      profit_factor: 29.7,
      gross_pnl: 12500.0,
      total_costs: 420.0,
      net_pnl: 12080.0,
      total_rollover_costs: 180.0,
      return_on_capital: 0.012,
      max_drawdown_pct: 0.015,
      sharpe_ratio: 1.85,
      equity_curve: [{ date: '2024-01-25', equity: 1012080.0, cash: 850000.0, mtm_pnl: 12080.0, margin_locked: 162000.0 }],
      rollover_log: [
        { date: '2024-01-22', old_contract: 'NIFTY24JANFUT', new_contract: 'NIFTY24FEBFUT', roll_spread: 45.0, roll_cost: 180.0 },
      ],
    }),
    getOptionsStrategiesCatalog: vi.fn().mockResolvedValue([
      { id: 'BULL_CALL_SPREAD', name: 'Bull Call Spread (Debit)', type: 'VERTICAL_SPREAD', description: 'Buy ATM Call + Sell OTM Call', legs: [] },
      { id: 'IRON_CONDOR', name: 'Iron Condor (Delta Neutral)', type: 'RANGE_BOUND', description: 'Wings long, body short', legs: [] },
    ]),
    runOptionsBacktest: vi.fn().mockResolvedValue({
      config: { strategy_id: 'BULL_CALL_SPREAD', underlying: 'NIFTY' },
      legs: [
        {
          action: 'BUY',
          option_type: 'CE',
          strike: 24000,
          entry_premium: 220.0,
          lot_size: 25,
          num_lots: 1,
          total_quantity: 25,
          exit_premium: 350.0,
          implied_volatility: 0.15,
          is_theoretical: false,
          delta: 0.52,
          gamma: 0.001,
          theta: -12.5,
          vega: 18.0,
        },
        {
          action: 'SELL',
          option_type: 'CE',
          strike: 24100,
          entry_premium: 160.0,
          lot_size: 25,
          num_lots: 1,
          total_quantity: 25,
          exit_premium: 270.0,
          implied_volatility: 0.15,
          is_theoretical: false,
          delta: 0.38,
          gamma: 0.0009,
          theta: 9.0,
          vega: -14.0,
        },
      ],
      payoff: {
        spot_price: 24000.0,
        points: [
          { spot: 23500.0, pct_change: -2.08, total_pnl: -1500.0 },
          { spot: 24000.0, pct_change: 0.0, total_pnl: -1500.0 },
          { spot: 24100.0, pct_change: 0.42, total_pnl: 1000.0 },
          { spot: 24500.0, pct_change: 2.08, total_pnl: 1000.0 },
        ],
        max_profit: 1000.0,
        max_loss: -1500.0,
        breakevens: [24060.0],
        risk_reward_ratio: 0.67,
        net_debit_or_credit: -1500.0,
        margin_required: 2500.0,
        net_delta: 0.14,
        net_gamma: 0.0001,
        net_theta: -3.5,
        net_vega: 4.0,
      },
      gross_pnl: 500.0,
      transaction_costs: 45.2,
      net_pnl: 454.8,
      roi_on_capital: 0.0009,
      roi_on_margin: 0.1819,
      margin_required: 2500.0,
      is_theoretical_simulation: false,
      summary: 'Bull Call Spread on NIFTY: Net P&L ₹454.80',
      disclaimer: 'Verified against market quotes',
    }),
  }
})

describe('AMQUANT INDIA Module Frontend', () => {
  it('renders header, phase 5 badge, and macro indicators', async () => {
    render(<AmquantIndia />)

    expect(screen.getByText('AMQUANT')).toBeInTheDocument()
    expect(screen.getByText('INDIA')).toBeInTheDocument()
    expect(screen.getByText('PHASE 5')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('RBI Policy Repo Rate')).toBeInTheDocument()
      expect(screen.getByText('6.5%')).toBeInTheDocument()
      expect(screen.getByText('91-Day T-Bill (Risk-Free)')).toBeInTheDocument()
      expect(screen.getByText('6.65%')).toBeInTheDocument()
    })
  })

  it('switches to Instrument Universe and filters instruments', async () => {
    render(<AmquantIndia />)

    const universeTab = screen.getByTestId('tab-instruments')
    fireEvent.click(universeTab)

    await waitFor(() => {
      expect(screen.getByText('Reliance Industries Ltd.')).toBeInTheDocument()
      expect(screen.getByText('Nippon India ETF Nifty 50 BeES')).toBeInTheDocument()
    })

    // Filter by search input
    const searchInput = screen.getByPlaceholderText(/Search by symbol, company/)
    fireEvent.change(searchInput, { target: { value: 'Reliance' } })

    expect(screen.getByText('RELIANCE')).toBeInTheDocument()
    expect(screen.queryByText('NIFTYBEES')).not.toBeInTheDocument()
  })

  it('switches to Bayesian Regimes and triggers experiment', async () => {
    render(<AmquantIndia />)

    const regimesTab = screen.getByTestId('tab-regimes')
    fireEvent.click(regimesTab)

    await waitFor(() => {
      expect(screen.getByText('First Research Experiment: Bayesian Market-Regime Detection')).toBeInTheDocument()
      expect(screen.getByText('Brier Score')).toBeInTheDocument()
      expect(screen.getByText('1.15')).toBeInTheDocument()
      expect(screen.getByText('BULLISH')).toBeInTheDocument()
    })
  })

  it('switches to Backtesting and displays Indian statutory taxes', async () => {
    render(<AmquantIndia />)

    const backtestTab = screen.getByTestId('tab-backtest')
    fireEvent.click(backtestTab)

    await waitFor(() => {
      expect(screen.getByText(/Indian Statutory Trading Charges/)).toBeInTheDocument()
      expect(screen.getByText(/Securities Transaction Tax/)).toBeInTheDocument()
      expect(screen.getByText(/Strategy CAGR/)).toBeInTheDocument()
    })
  })

  it('switches to Storage & Coverage audit tab', async () => {
    render(<AmquantIndia />)

    const coverageTab = screen.getByTestId('tab-coverage')
    fireEvent.click(coverageTab)

    await waitFor(() => {
      expect(screen.getByText('Storage Architecture: DuckDB & Apache Parquet')).toBeInTheDocument()
      expect(screen.getByText('Corporate Announcements & Audio Transcripts')).toBeInTheDocument()
    })
  })

  it('switches to Historical Data Manager tab and triggers download and inspection', async () => {
    render(<AmquantIndia />)

    const managerTab = screen.getByTestId('tab-manager')
    fireEvent.click(managerTab)

    await waitFor(() => {
      expect(screen.getByText(/Configurable Historical Data Downloader/i)).toBeInTheDocument()
      expect(screen.getByText('Start Historical Download')).toBeInTheDocument()
      expect(screen.getByText('Parquet Storage Coverage & Health Audit')).toBeInTheDocument()
    })

    // Click Start Historical Download
    const downloadBtn = screen.getByText('Start Historical Download')
    fireEvent.click(downloadBtn)

    await waitFor(() => {
      expect(screen.getByText(/Batch Download Complete/)).toBeInTheDocument()
    })
  })

  it('switches to Backtesting and executes Phase 3 professional strategy simulation', async () => {
    render(<AmquantIndia />)

    const backtestTab = screen.getByTestId('tab-backtest')
    fireEvent.click(backtestTab)

    // Wait for strategy selector to populate
    await waitFor(() => {
      expect(screen.getByText(/Professional Quantitative Strategy/)).toBeInTheDocument()
      expect(screen.getByText('SMA 20/50 Golden Cross')).toBeInTheDocument()
    })

    // Click "Run Professional Backtest"
    const runBtn = screen.getByText('Run Professional Backtest')
    fireEvent.click(runBtn)

    // Verify Phase 3 results display
    await waitFor(() => {
      expect(screen.getByText('12.35%')).toBeInTheDocument() // Net CAGR
      expect(screen.getByText(/Gross CAGR: 13.12%/)).toBeInTheDocument() // Gross CAGR
      expect(screen.getByText('58.5%')).toBeInTheDocument() // Win rate
      expect(screen.getByText('-14.2%')).toBeInTheDocument() // Max Drawdown
      expect(screen.getByText(/PASSED - zero lookahead bias verified/)).toBeInTheDocument()
      expect(screen.getByText('TRD-1')).toBeInTheDocument() // Trade record
    })

    // Click "Save to Workspace"
    const saveBtn = screen.getByText('Save to Workspace')
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(screen.getByText(/saved to your Personal Workspace/i)).toBeInTheDocument()
    })
  })

  it('switches through Phase 4 Data Manager subtabs (Intraday, Futures, Options, Contracts, Providers)', async () => {
    render(<AmquantIndia />)

    const managerTab = screen.getByTestId('tab-manager')
    fireEvent.click(managerTab)

    await waitFor(() => {
      expect(screen.getByTestId('datamanager-subtab-intraday')).toBeInTheDocument()
      expect(screen.getByTestId('datamanager-subtab-futures')).toBeInTheDocument()
      expect(screen.getByTestId('datamanager-subtab-options')).toBeInTheDocument()
      expect(screen.getByTestId('datamanager-subtab-contracts')).toBeInTheDocument()
      expect(screen.getByTestId('datamanager-subtab-providers')).toBeInTheDocument()
    })

    // Click INTRADAY subtab
    fireEvent.click(screen.getByTestId('datamanager-subtab-intraday'))
    await waitFor(() => {
      expect(screen.getByText(/Supports 1m, 5m, 15m, 30m, and 60m/i)).toBeInTheDocument()
      expect(screen.getByText('Fetch History')).toBeInTheDocument()
    })

    // Click FUTURES subtab
    fireEvent.click(screen.getByTestId('datamanager-subtab-futures'))
    await waitFor(() => {
      expect(screen.getByText(/Continuous Series Builder/i)).toBeInTheDocument()
      expect(screen.getByText(/Never treat a continuous futures series as an executable contract/i)).toBeInTheDocument()
    })

    // Click OPTIONS subtab
    fireEvent.click(screen.getByTestId('datamanager-subtab-options'))
    await waitFor(() => {
      expect(screen.getByText(/Analytical Model Greeks/i)).toBeInTheDocument()
      expect(screen.getByText('Put-Call Ratio (OI)')).toBeInTheDocument()
      expect(screen.getByText('Max Pain Strike')).toBeInTheDocument()
    })

    // Click CONTRACTS subtab
    fireEvent.click(screen.getByTestId('datamanager-subtab-contracts'))
    await waitFor(() => {
      expect(screen.getByText(/Historical Lot Size Registry/i)).toBeInTheDocument()
    })

    // Click PROVIDERS subtab
    fireEvent.click(screen.getByTestId('datamanager-subtab-providers'))
    await waitFor(() => {
      expect(screen.getByText(/Data Provider Architecture/i)).toBeInTheDocument()
      expect(screen.getByText('Yahoo Finance (Free Public Endpoint)')).toBeInTheDocument()
    })
  })

  it('switches through Phase 5 Backtest Engines (Intraday, Futures, Options) and executes simulations', async () => {
    render(<AmquantIndia />)

    // Open Backtesting Tab
    const backtestTab = screen.getByTestId('tab-backtest')
    fireEvent.click(backtestTab)

    await waitFor(() => {
      expect(screen.getByTestId('backtest-engine-daily')).toBeInTheDocument()
      expect(screen.getByTestId('backtest-engine-intraday')).toBeInTheDocument()
      expect(screen.getByTestId('backtest-engine-futures')).toBeInTheDocument()
      expect(screen.getByTestId('backtest-engine-options')).toBeInTheDocument()
    })

    // 1. Switch to INTRADAY engine
    fireEvent.click(screen.getByTestId('backtest-engine-intraday'))
    await waitFor(() => {
      expect(screen.getByText(/Intraday Equity Strategy Backtesting Engine/i)).toBeInTheDocument()
      expect(screen.getByTestId('select-intraday-strategy')).toBeInTheDocument()
      expect(screen.getByTestId('select-intraday-timeframe')).toBeInTheDocument()
      expect(screen.getByTestId('run-intraday-backtest')).toBeInTheDocument()
    })

    // Run Intraday backtest
    fireEvent.click(screen.getByTestId('run-intraday-backtest'))
    await waitFor(() => {
      expect(screen.getByText(/NET P&L \(AFTER TAXES\)/i)).toBeInTheDocument()
      expect(screen.getByText(/Zero Look-Ahead Bias Verified/i)).toBeInTheDocument()
      expect(screen.getByText(/Mandatory EOD Square-Off: 15:15 IST/i)).toBeInTheDocument()
      expect(screen.getByText('IT-001')).toBeInTheDocument()
    })

    // 2. Switch to FUTURES engine
    fireEvent.click(screen.getByTestId('backtest-engine-futures'))
    await waitFor(() => {
      expect(screen.getByText(/Indian Index & Stock Futures Backtesting Engine/i)).toBeInTheDocument()
      expect(screen.getByTestId('select-futures-underlying')).toBeInTheDocument()
      expect(screen.getByTestId('run-futures-backtest')).toBeInTheDocument()
    })

    // Run Futures backtest
    fireEvent.click(screen.getByTestId('run-futures-backtest'))
    await waitFor(() => {
      expect(screen.getByText(/Individual Contract Discipline Verified/i)).toBeInTheDocument()
      expect(screen.getByText(/CONTRACTS TRADED/i)).toBeInTheDocument()
      expect(screen.getByText(/Rollover Transition Log/i)).toBeInTheDocument()
    })

    // 3. Switch to OPTIONS engine
    fireEvent.click(screen.getByTestId('backtest-engine-options'))
    await waitFor(() => {
      expect(screen.getByText(/Multi-Leg Options Strategy & Terminal Payoff Engine/i)).toBeInTheDocument()
      expect(screen.getByTestId('select-options-strategy')).toBeInTheDocument()
      expect(screen.getByTestId('run-options-backtest')).toBeInTheDocument()
    })

    // Run Options backtest
    fireEvent.click(screen.getByTestId('run-options-backtest'))
    await waitFor(() => {
      expect(screen.getByText(/PORTFOLIO NET GREEKS AGGREGATION/i)).toBeInTheDocument()
      expect(screen.getByText(/Terminal Payoff Diagram at Expiry/i)).toBeInTheDocument()
      expect(screen.getByText(/Multi-Leg Construction & Greeks Detail/i)).toBeInTheDocument()
      expect(screen.getByText(/Verified against market quotes/i)).toBeInTheDocument()
    })
  })
})
