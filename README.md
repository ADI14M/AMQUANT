# AMQUANT — Quantitative Finance Research Terminal

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11-3776ab.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)
![React](https://img.shields.io/badge/React-18.3-61dafb.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178c6.svg)
![Tests](https://img.shields.io/badge/tests-Pytest%20%7C%20Vitest%20Passing-brightgreen.svg)

**AMQUANT** is an interactive quantitative finance research terminal engineered for rigorous financial computation, parameter uncertainty estimation, stochastic forecasting, and multi-model derivatives valuation.

Built with a strict three-tier architecture separating the **React + TypeScript + Vite** financial-terminal interface, the **FastAPI HTTP service**, and a **pure, framework-independent NumPy/SciPy/pandas quantitative engine**.

---

## Project Objectives

1. **Analytical & Numerical Rigor**: Implement exact closed-form financial models alongside discrete lattices and Monte Carlo estimators with formal mathematical benchmarks.
2. **Unified Research Intelligence**: Provide an end-to-end workflow synthesizing prior belief elicitation, Bayesian signal updates, stochastic path generation, and multi-model derivatives pricing into an executive research memo.
3. **Data Transparency & Educational Integrity**: Strictly differentiate physical real-world forecasting measures ($\mathbb{P}$) from risk-neutral martingale pricing measures ($\mathbb{Q}$), clearly labeling all example data as synthetic and avoiding fabricated live market claims.
4. **Production Engineering Quality**: Enforce 100% automated test coverage across mathematical invariants (Put-Call Parity, BSM benchmarks, moment matching), strict TypeScript typing, and containerized deployment readiness.

---

## Visual Showcase & Screenshots

> **Note**: Below are preview placeholders for repository and portfolio presentation. Replace with captured screenshots after launching locally.

| Research Intelligence Workflow | Multi-Model Valuation & Greeks |
| :---: | :---: |
| `![AMQUANT Research Intelligence](docs/screenshots/research-intelligence.png)`<br/>*(Workflow Stage 01–04: Bayesian Update & Stochastic Paths)* | `![Options Lab & Sensitivities](docs/screenshots/options-lab.png)`<br/>*(Black–Scholes–Merton Greeks & CRR Binomial Comparison)* |

| Financial Foundations & Hedge Tree | Bayesian Engine & Credible Intervals |
| :---: | :---: |
| `![Financial Foundations](docs/screenshots/financial-foundations.png)`<br/>*(CRR Node Replicating Hedge & Payoff Profiles)* | `![Bayesian Engine](docs/screenshots/bayesian-engine.png)`<br/>*(Conjugate Beta–Bernoulli Densities & Sequential Tracking)* |

---

## System Architecture

AMQUANT enforces strict separation of concerns across three decoupled tiers:

```
AMQUANT/
├── quant_engine/            # Pure Python Quantitative Engine (NumPy, SciPy, pandas)
│   ├── foundations.py       # CRR binomial trees, replicating delta/cash schedules
│   ├── bayesian.py          # Conjugate Beta-Bernoulli, credible intervals, marginal likelihood
│   ├── stochastic.py        # Seeded ABM, GBM sample paths, Monte Carlo pricing
│   ├── options.py           # Merton-extended BSM, analytical Greeks, sensitivities
│   └── payoffs.py           # Expiration intrinsic value & net profit evaluators
│
├── backend/                 # FastAPI Service & HTTP Contracts
│   ├── app/
│   │   ├── main.py          # FastAPI application, CORS, health & root endpoints
│   │   ├── auth.py          # Supabase JWT verification (RS256/ES256 JWKS or HS256 secret)
│   │   ├── db.py            # PostgREST RLS data gateway with in-memory test fallback
│   │   └── routes/          # Pydantic v2 schemas and validation routers
│   │       ├── intelligence.py   # AMQUANT Research Intelligence workflow
│   │       ├── foundations.py    # Foundations API
│   │       ├── bayesian.py       # Bayesian API
│   │       ├── stochastic.py     # Stochastic simulation API
│   │       ├── options.py        # Options Lab API
│   │       ├── auth_routes.py    # Profile management (/api/auth/me, /api/auth/profile)
│   │       ├── scenarios.py      # Saved research scenarios (/api/scenarios)
│   │       └── history.py        # Research run audit trail (/api/research-history)
│   └── requirements.txt     # Python dependencies (FastAPI, NumPy, SciPy, pandas, PyJWT[crypto])
│
├── frontend/                # React 18 + TypeScript + Vite Dark Terminal Interface
│   ├── src/
│   │   ├── components/      # Shell, Sidebar, Dashboard, Controls, Charts, AuthModal, SaveModal
│   │   ├── modules/         # Research Intelligence + 4 quantitative workspaces + Personal Workspace
│   │   ├── context/         # AuthContext (Supabase auth, session restoration, profiles)
│   │   ├── lib/             # API client, Supabase client, health polling
│   │   └── styles.css       # Dark Financial Terminal design system
│   ├── package.json         # NPM manifest (@supabase/supabase-js, Lucide, Recharts)
│   └── vite.config.ts       # Vite + Vitest configuration
│
├── supabase/                # PostgreSQL Schema & Row Level Security (RLS) Migrations
│   └── migrations/          # 20261111000000_auth_and_workspaces.sql (profiles, scenarios, history)
│
└── tests/                   # Independent Mathematical & Contract Test Suites
    ├── python/              # Pytest: financial benchmarks, Greeks, API contracts, Auth & RLS
    └── frontend/            # Vitest + React Testing Library UI tests
```

---

## Core Modules & Capabilities

### 1. AMQUANT Research Intelligence (`CORE`)
- **Unified 5-Stage Research Workflow**:
  1. **Asset Setup**: Define underlying spot $S_0$, strike $K$, horizon $T$, risk-free rate $r$, volatility $\sigma$, physical drift $\mu$, and dividend yield $q$.
  2. **Bayesian Evidence**: Elicit $\text{Beta}(\alpha, \beta)$ prior belief on market regime; incorporate sequential binary observations; compute posterior mean, 95% equal-tailed credible range, and natural-language shift explanation.
  3. **Stochastic Simulation**: Generate seed-reproducible Geometric Brownian Motion paths under both Physical Measure $\mathbb{P}$ (real-world forecasting) and Risk-Neutral Measure $\mathbb{Q}$ (martingale pricing measure); benchmark empirical sample moments against theoretical moments.
  4. **Multi-Model Valuation & Greeks**: Compute Black–Scholes–Merton European price, analytical Greeks ($\Delta, \Gamma, \mathcal{V}, \Theta, \rho$), CRR Binomial European and American prices, American early exercise premium, and Risk-Neutral Monte Carlo estimate.
  5. **Research Conclusion Memo**: Automated quantitative synthesis detailing executive summary, primary uncertainty drivers, theoretical model limitations, and compliance notices.

### 2. Financial Foundations
- Cox-Ross-Rubinstein (CRR) binomial lattice pricing for European and American calls/puts.
- Dynamic replicating portfolio schedule at each lattice node: delta shares $\Delta$ and risk-free cash bond $B$.
- Payoff and net profit curves accounting for paid premiums.

### 3. Bayesian Engine
- Beta–Bernoulli conjugate inference for binary regime outcomes.
- Analytical likelihood, prior, and posterior densities evaluated on a 101-point probability grid.
- Sequential belief updating tracking posterior mean after each trial.
- Exact log marginal likelihood calculation via log-gamma functions.

### 4. Stochastic Simulator
- Seeded, reproducible Arithmetic Brownian Motion (ABM) and Geometric Brownian Motion (GBM).
- Monte Carlo terminal distribution metrics: mean, median, standard deviation, and quantile bands.
- Discounted European call/put Monte Carlo valuation with $95\%$ confidence interval.

### 5. Options Lab
- Closed-form Black–Scholes–Merton European option pricing with continuous dividend yield $q$.
- Analytical first- and second-order Greeks:
  - $\Delta$ (Delta): directional exposure per $\$1.00$ underlying move.
  - $\Gamma$ (Gamma): rate of delta change per $\$1.00$ underlying move.
  - $\mathcal{V}$ (Vega): sensitivity per $1.00$ ($100\%$) change in volatility ($0.01 \cdot \mathcal{V}$ per $1\%$).
  - $\Theta$ (Theta): annualized time decay ($\Theta / 365$ per calendar day).
  - $\rho$ (Rho): sensitivity per $1.00$ ($100\%$) change in risk-free interest rate.
- CRR European vs. American lattice comparison.
- One-factor spot ($70\% - 130\%$) and volatility ($40\% - 160\%$) parametric sensitivity sweeps.

### 6. Personal Research Workspace & Supabase Auth (`NEW`)
- **Optional Registration & Login**: Guests have 100% unrestricted public access to all five research modules without logging in.
- **Cryptographic JWT Verification**: Secure FastAPI bearer token validation checking asymmetric JWKS (`RS256`/`ES256`) or symmetric secret (`HS256`), verifying expiration, subject, issuer, and audience (`authenticated`).
- **PostgreSQL Row-Level Security (RLS)**: Zero data leakage with `auth.uid() = user_id` database policies across `profiles`, `saved_scenarios`, and `research_history`.
- **Saved Scenario Management**: Name, inspect, reopen into originating modules with preloaded state, rename, and delete scenarios.
- **Research Execution History**: Automatic, audit-grade calculation tracking recorded in background when authenticated, with entry deletion and bulk clearing.
- **Full Architecture Documentation**: See [`docs/auth_architecture.md`](docs/auth_architecture.md).

---

## Mathematical Formulations

### Black–Scholes–Merton (with Dividend Yield $q$)
$$d_1 = \frac{\ln(S/K) + (r - q + \frac{1}{2}\sigma^2)T}{\sigma \sqrt{T}}, \quad d_2 = d_1 - \sigma \sqrt{T}$$
$$C = S e^{-q T} N(d_1) - K e^{-r T} N(d_2)$$
$$P = K e^{-r T} N(-d_2) - S e^{-q T} N(-d_1)$$

### Cox–Ross–Rubinstein (CRR) Lattice
$$u = e^{\sigma \sqrt{\Delta t}}, \quad d = \frac{1}{u}, \quad p = \frac{e^{(r - q)\Delta t} - d}{u - d}$$
$$\Delta = \frac{V_u - V_d}{S(u - d)}, \quad B = e^{-r\Delta t} \frac{u V_d - d V_u}{u - d}$$

### Beta–Bernoulli Conjugacy
$$\text{Prior}: \theta \sim \text{Beta}(\alpha, \beta) \implies \text{Posterior}: \theta \mid s, f \sim \text{Beta}(\alpha + s, \beta + f)$$
$$\ln m(\mathcal{D}) = \ln \Gamma(\alpha + s) + \ln \Gamma(\beta + f) - \ln \Gamma(\alpha + \beta + s + f) - [\ln \Gamma(\alpha) + \ln \Gamma(\beta) - \ln \Gamma(\alpha + \beta)]$$

### Put-Call Parity
$$C - P = S e^{-q T} - K e^{-r T}$$

---

## Mathematical Benchmark Suite

The automated test suite verifies exact financial invariants and benchmark values:

| Benchmark Case | Inputs | Expected / Theoretical | Verified Status |
| :--- | :--- | :--- | :---: |
| **BSM Call Benchmark** | $S=100, K=100, T=1, r=0.05, \sigma=0.20, q=0$ | $\$10.4506 \pm 0.0005$ | **PASS** |
| **BSM Put Benchmark** | $S=100, K=100, T=1, r=0.05, \sigma=0.20, q=0$ | $\$5.5735 \pm 0.0005$ | **PASS** |
| **Put-Call Parity** | $S=100, K=100, T=1, r=0.05, \sigma=0.20, q=0$ | $C - P = 100(1 - e^{-0.05}) = 4.8771$ | **PASS** |
| **American Call Invariant** | Non-dividend paying American vs. European call | $\text{Price}_{\text{Amer}} \equiv \text{Price}_{\text{Euro}}$ | **PASS** |
| **American Put Early Exercise** | $S=80, K=100, T=1, r=0.05, \sigma=0.25$ | $\text{Price}_{\text{Amer}} > \text{Price}_{\text{Euro}} + 0.50$ | **PASS** |
| **Conjugate Beta Update** | Prior $\text{Beta}(2,2)$ with 4 successes, 2 failures | $\text{Beta}(6,4)$, Mean $= 0.60$ | **PASS** |
| **Seeded Simulation** | Seed $= 123$ across multiple runs | Identical sample trajectories | **PASS** |
| **Monte Carlo SE Scaling** | $N=1,000$ vs. $N=40,000$ paths | $\text{SE}_{\text{ratio}} \approx \sqrt{40} \approx 6.32$ | **PASS** |
| **ABM Moments** | $X_0=0, \mu=0.5, \sigma=0.4, T=2.0$ | $\mathbb{E}[X_T] = 1.0, \text{Std} = 0.4\sqrt{2} \approx 0.5657$ | **PASS** |
| **GBM Moments** | $S_0=100, \mu=0.08, \sigma=0.20, T=1.0$ | $\mathbb{E}[S_T] = 108.33, \text{Std} = 21.89$ | **PASS** |

---

## Installation & Local Development

### Prerequisites
- **Node.js**: v20+ and npm
- **Python**: v3.10+ (tested on Python 3.10 and 3.11)

### 1. Clone & Setup Frontend
```sh
git clone https://github.com/your-username/amquant.git
cd amquant

# Install frontend dependencies
npm install

# Start Vite development server
npm run dev
```
*Frontend runs at:* `http://localhost:5173`

### 2. Setup Backend & Quantitative Engine
In a separate terminal window:
```sh
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python requirements
pip install -r backend/requirements.txt

# Start FastAPI development server with hot reload
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
*API runs at:* `http://127.0.0.1:8000`
*Interactive Swagger Documentation:* `http://127.0.0.1:8000/docs`

---

## Automated Testing & Quality Checks

Run all test suites locally:

```sh
# Run Python Quantitative Engine & API Benchmark Tests
.venv/bin/python -m pytest

# Run Frontend Vitest & React Component Tests
npm test

# Run TypeScript Compilation & Production Build Check
npm run build
```

---

## Production Deployment Preparation

AMQUANT is configured for zero-friction containerized or multi-cloud deployment:

### Docker Deployment
```sh
# Build and run with Docker Compose
docker compose up --build -d

# Check health status
curl http://localhost:8000/api/health
```

### Environment Variables
Configure `.env` or cloud service variables using `.env.example`:

| Variable | Scope | Default | Purpose |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Frontend | `http://localhost:8000` | Frontend backend API URL (`https://amquant-api.onrender.com` in prod) |
| `VITE_SUPABASE_URL` | Frontend | Optional | Supabase project URL (`https://xyz.supabase.co`) |
| `VITE_SUPABASE_ANON_KEY` | Frontend | Optional | Supabase public anonymous API key |
| `CORS_ORIGINS` | Backend | `https://amquant.vercel.app,...` | Comma-separated allowed origins for FastAPI CORS |
| `SUPABASE_URL` | Backend | Optional | Supabase project URL for PostgREST proxy queries |
| `SUPABASE_ANON_KEY` | Backend | Optional | Supabase public anonymous key for PostgREST calls |
| `SUPABASE_JWT_SECRET` | Backend | Optional | Supabase JWT secret (or uses JWKS from Supabase URL) |
| `HOST` | Backend | `0.0.0.0` | Backend bind host |
| `PORT` | Backend | `8000` | Backend bind port |

### Resource Protection & Operational Guardrails

To run reliably on single-instance resource-constrained cloud tiers (e.g. Render 512 MB RAM) without external databases or paid services, AMQUANT implements strict server-side safeguards:

- **Strict Input Validation**: Conservative upper bounds across all endpoints (Monte Carlo paths $\le 10,000$, simulation steps $\le 500$, tree steps $\le 500$, Bayesian observations $\le 5,000$).
- **Request Body Size Limit**: HTTP 413 response for payloads exceeding 64 KB ($65,536$ bytes).
- **Per-Client Rate Limiting**: In-memory sliding window rate limiter enforcing 30 requests/minute per client IP (HTTP 429 with `Retry-After` header), with Render reverse-proxy aware IP extraction and periodic record pruning.
- **Concurrency Throttling**: Concurrency gate limiting simultaneous heavy calculations to 5 tasks via `asyncio.Semaphore` and `run_in_threadpool`, returning HTTP 503 when saturated to protect against OOM crashes.
- **Safe Error Responses**: Unhandled exceptions log tracebacks server-side while returning sanitized HTTP 500 responses with zero client-side leakage of internal paths or stack traces.
- **Frontend Cold-Start Handling**: Friendly UI feedback for Render free-tier cold starts (30–50s spin-up) and retry guidance without broken screens.
- **Health & Readiness Checks**: Lightweight endpoints `/api/health` and `/api/health/ready` (exempt from rate limiting) for continuous uptime monitoring.

---

## Data Transparency & Compliance Notice

- **Synthetic Pedagogical Assumptions**: All simulation paths, performance metrics, and portfolio statistics presented within AMQUANT are generated deterministically or pseudo-randomly using mathematical models. No connection to live external exchange feeds is claimed.
- **Academic & Educational Purpose**: AMQUANT is designed strictly for quantitative research, algorithmic modeling, and pedagogical education. It does not constitute investment advice, financial recommendations, or automated trading signals.

---

## License

Released under the [MIT License](LICENSE).
