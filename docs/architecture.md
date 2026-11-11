# AMQUANT Architecture & System Specification

## Overview

AMQUANT is a quantitative finance research platform and learning terminal designed to provide mathematical rigor, computational transparency, and modular separation between presentation layers and pure quantitative algorithms.

```mermaid
flowchart TD
    subgraph Client["Frontend Layer (React + TypeScript + Vite)"]
        UI["Dark Terminal UI Shell"]
        Dashboard["Dashboard & Metrics"]
        RI["AMQUANT Research Intelligence"]
        M1["Financial Foundations"]
        M2["Bayesian Engine"]
        M3["Stochastic Simulator"]
        M4["Options Lab"]
        APIClient["Typed API Client (`postResearch`)"]
    end

    subgraph Service["Backend API Layer (FastAPI)"]
        Router["FastAPI Application & CORS Middleware"]
        HealthRoute["GET /api/health & GET /"]
        RIRoute["POST /api/intelligence/analyze"]
        M1Route["POST /api/foundations/analyze"]
        M2Route["POST /api/bayesian/update"]
        M3Route["POST /api/stochastic/simulate"]
        M4Route["POST /api/options/analyze"]
        LegacyRoute["POST /api/options/black-scholes"]
    end

    subgraph Engine["Pure Quantitative Engine (`quant_engine/`)"]
        Bayes["`bayesian.py`<br/>Beta-Bernoulli Conjugacy"]
        Stoch["`stochastic.py`<br/>ABM, GBM & Monte Carlo"]
        Found["`foundations.py`<br/>CRR Binomial Lattice & Replicating Hedging"]
        Opt["`options.py`<br/>Black–Scholes–Merton & Analytical Greeks"]
        Payoff["`payoffs.py`<br/>Payoff & Net Profit Evaluators"]
    end

    UI --> Dashboard & RI & M1 & M2 & M3 & M4
    RI & M1 & M2 & M3 & M4 --> APIClient
    APIClient -- HTTP JSON --> Router
    Router --> HealthRoute & RIRoute & M1Route & M2Route & M3Route & M4Route & LegacyRoute
    RIRoute --> Bayes & Stoch & Found & Opt
    M1Route --> Found & Payoff
    M2Route --> Bayes
    M3Route --> Stoch
    M4Route --> Opt & Found
```

---

## Architectural Principles & Component Boundaries

1. **Framework-Independent Pure Quant Engine (`quant_engine/`)**:
   - Zero dependencies on HTTP frameworks, ASGI, or UI state.
   - Built with vectorized NumPy, SciPy special functions, and pandas.
   - Deterministic and seed-reproducible calculations.
   - Strict validation: invalid parameter configurations (e.g., arbitrage-violating risk-neutral probabilities, non-positive spot/strike, negative volatility) raise explicit `ValueError` rather than silently clipping or returning degenerate values.

2. **HTTP Service & Contract Layer (`backend/app/routes/`)**:
   - FastAPI routers with Pydantic v2 schemas validating request bounds.
   - Maps domain `ValueError` exceptions to HTTP 422 Unprocessable Entity responses with descriptive error messages.
   - CORS middleware configured via environment variable `CORS_ORIGINS` with secure fallback for local development.

3. **Frontend Application (`frontend/src/`)**:
   - Built on React 18, TypeScript, Vite, and Recharts.
   - Presentational components styled under a Dark Financial Terminal theme.
   - Responsive design adapting from high-resolution multi-monitor desktops to laptop and mobile screens.
   - Explicit distinction between synthetic pedagogical simulations and production market feeds.

---

## Core Quantitative Modules

### 1. Financial Foundations (`quant_engine/foundations.py`)
- **Cox-Ross-Rubinstein (CRR) Binomial Tree**:
  - Up factor: $u = e^{\sigma \sqrt{\Delta t}}$
  - Down factor: $d = \frac{1}{u} = e^{-\sigma \sqrt{\Delta t}}$
  - Growth factor: $a = e^{(r - q)\Delta t}$
  - Risk-neutral probability: $p = \frac{a - d}{u - d}$
  - Discount factor: $e^{-r \Delta t}$
- **American vs. European Early Exercise**:
  - At each lattice node $(i, j)$, European value: $V_{i,j} = e^{-r\Delta t}[p V_{i+1, j+1} + (1-p)V_{i+1, j}]$
  - American early exercise: $V_{i,j}^{\text{amer}} = \max\left(V_{i,j}^{\text{cont}}, \text{Payoff}(S_{i,j})\right)$
- **Dynamic Replicating Hedge**:
  - Replicating delta: $\Delta_{i,j} = \frac{V_{i+1, j+1} - V_{i+1, j}}{S_{i,j}(u - d)}$
  - Replicating risk-free cash bond: $B_{i,j} = e^{-r\Delta t} \frac{u V_{i+1, j} - d V_{i+1, j+1}}{u - d}$
  - Satisfies no-arbitrage replication: $\Delta S_{i,j} u + B e^{r\Delta t} = V_u$ and $\Delta S_{i,j} d + B e^{r\Delta t} = V_d$.

### 2. Bayesian Engine (`quant_engine/bayesian.py`)
- **Beta-Bernoulli Conjugate Model**:
  - Prior: $\theta \sim \text{Beta}(\alpha, \beta)$ with prior mean $\frac{\alpha}{\alpha + \beta}$.
  - Likelihood for $s$ successes and $f$ failures: $\mathcal{L}(\theta) \propto \theta^s (1 - \theta)^f$.
  - Posterior: $\theta \mid \mathcal{D} \sim \text{Beta}(\alpha + s, \beta + f)$.
  - Equal-tailed 95% Credible Interval: computed via SciPy `beta.ppf([0.025, 0.975], \alpha_{\text{post}}, \beta_{\text{post}})`.
  - Log Marginal Likelihood: closed-form via log-gamma functions:
    $$\ln m(\mathcal{D}) = \ln \Gamma(\alpha + s) + \ln \Gamma(\beta + f) - \ln \Gamma(\alpha + \beta + s + f) - [\ln \Gamma(\alpha) + \ln \Gamma(\beta) - \ln \Gamma(\alpha + \beta)]$$

### 3. Stochastic Simulator (`quant_engine/stochastic.py`)
- **Arithmetic Brownian Motion (ABM)**:
  - $dX_t = \mu dt + \sigma dW_t \implies X_t = X_0 + \mu t + \sigma W_t$.
  - Theoretical moments: $\mathbb{E}[X_T] = \mu T$, $\text{Var}(X_T) = \sigma^2 T$.
- **Geometric Brownian Motion (GBM)**:
  - $dS_t = \mu S_t dt + \sigma S_t dW_t \implies S_t = S_0 \exp\left((\mu - \frac{1}{2}\sigma^2)t + \sigma W_t\right)$.
  - Theoretical moments: $\mathbb{E}[S_T] = S_0 e^{\mu T}$, $\text{Var}(S_T) = S_0^2 e^{2\mu T}(e^{\sigma^2 T} - 1)$.
- **Measure Distinction**:
  - Physical Measure $\mathbb{P}$: uses historical or forecasted physical drift $\mu$.
  - Risk-Neutral Measure $\mathbb{Q}$: uses drift $r - q$ for no-arbitrage discounted expectation pricing.
- **Monte Carlo European Valuation**:
  - $\hat{C}_0 = e^{-r T} \frac{1}{M} \sum_{k=1}^M \max(S_T^{(k)} - K, 0)$
  - Standard error: $\text{SE} = \frac{\hat{\sigma}}{\sqrt{M}}$ with 95% normal confidence interval $\hat{C}_0 \pm 1.96 \cdot \text{SE}$.

### 4. Options Lab (`quant_engine/options.py`)
- **Black-Scholes-Merton (1973 / Merton 1973 with Continuous Dividend Yield $q$)**:
  - $d_1 = \frac{\ln(S/K) + (r - q + \frac{1}{2}\sigma^2)T}{\sigma \sqrt{T}}$, $d_2 = d_1 - \sigma \sqrt{T}$
  - Call: $C = S e^{-q T} N(d_1) - K e^{-r T} N(d_2)$
  - Put: $P = K e^{-r T} N(-d_2) - S e^{-q T} N(-d_1)$
- **Analytical Greeks**:
  - Delta ($\Delta$): Call $= e^{-q T} N(d_1)$, Put $= -e^{-q T} N(-d_1)$
  - Gamma ($\Gamma$): $\frac{e^{-q T} N'(d_1)}{S \sigma \sqrt{T}}$
  - Vega ($\mathcal{V}$): $S e^{-q T} N'(d_1)\sqrt{T}$ (reported per $1.00$ volatility change; multiply by $0.01$ for $1\%$ change)
  - Theta ($\Theta$): Annualized time decay
    - Call: $-\frac{S e^{-q T} N'(d_1) \sigma}{2 \sqrt{T}} - r K e^{-r T} N(d_2) + q S e^{-q T} N(d_1)$
    - Put: $-\frac{S e^{-q T} N'(d_1) \sigma}{2 \sqrt{T}} + r K e^{-r T} N(-d_2) - q S e^{-q T} N(-d_1)$
  - Rho ($\rho$): Call $= K T e^{-r T} N(d_2)$, Put $= -K T e^{-r T} N(-d_2)$ (reported per $1.00$ rate change)
- **Put-Call Parity**:
  - $C - P = S e^{-q T} - K e^{-r T}$

---

## AMQUANT Research Intelligence Workflow

The **Research Intelligence** module (`/api/intelligence/analyze` & `ResearchIntelligence.tsx`) unites the entire engine into a structured 5-stage quantitative workflow:

1. **Stage 01 — Setup & Asset Profile**: User defines asset parameters ($S_0, K, T, r, \sigma, \mu, q$) and contract type.
2. **Stage 02 — Bayesian Parameter Inference**: Updates prior belief distribution on regime or outperformance probability with binary evidence; generates predictive distribution, credible interval, and natural language belief shift summary.
3. **Stage 03 — Stochastic Simulation ($\mathbb{P}$ vs. $\mathbb{Q}$)**: Runs seed-reproducible GBM price trajectories under physical drift $\mu$ (forecasting) and risk-neutral drift $r-q$ (martingale pricing measure); displays terminal moments vs. analytical theoretical moments.
4. **Stage 04 — Multi-Model Valuation & Greeks**: Evaluates Black–Scholes–Merton, CRR Binomial European, CRR Binomial American, and Monte Carlo valuations side-by-side; quantifies American early exercise premium; verifies Put-Call Parity; displays replicating portfolio at Node 0; sweeps parametric spot and volatility sensitivities.
5. **Stage 05 — Quantitative Conclusion Memo**: Produces an executive quantitative narrative synthesizing the findings, ranking primary uncertainty drivers (Delta, Gamma, Vega), detailing theoretical model limitations, and displaying an explicit compliance disclaimer.

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service discovery and status metadata |
| `GET` | `/api/health` | Service health status check |
| `POST` | `/api/intelligence/analyze` | Unified Research Intelligence workflow |
| `POST` | `/api/foundations/analyze` | CRR binomial pricing, hedge tree, and payoff curves |
| `POST` | `/api/bayesian/update` | Beta-Bernoulli prior/evidence update and sequential tracking |
| `POST` | `/api/stochastic/simulate` | Brownian / GBM sample path generation & Monte Carlo |
| `POST` | `/api/options/analyze` | BSM pricing, analytical Greeks, binomial comparisons & sensitivity curves |
| `POST` | `/api/options/black-scholes` | Minimal BSM pricing endpoint (backward compatibility) |
