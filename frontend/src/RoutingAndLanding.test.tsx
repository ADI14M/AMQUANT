import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./lib/api', async () => {
  const actual = await vi.importActual<typeof import('./lib/api')>('./lib/api')
  return {
    ...actual,
    checkAccessStatus: vi.fn().mockResolvedValue({ authenticated: true }),
    checkApiHealth: vi.fn().mockResolvedValue(true),
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
      breadth_regime: 'BULLISH',
    },
    top_equities: [],
  }),
  getIndiaInstruments: vi.fn().mockResolvedValue([]),
  getIndiaBacktestStrategies: vi.fn().mockResolvedValue([]),
  getIntradayStrategiesCatalog: vi.fn().mockResolvedValue([]),
  getOptionsStrategiesCatalog: vi.fn().mockResolvedValue([]),
  }
})

describe('AMQUANT Root Routing & Landing Page', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('renders the central landing page with both market cards at /', () => {
    window.history.pushState({}, '', '/')
    render(<App />)

    expect(screen.getByRole('heading', { name: 'GLOBAL MARKETS' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'INDIAN MARKETS' })).toBeInTheDocument()
    expect(screen.getByText(/Quantitative Intelligence\. Data-Driven Decisions\./i)).toBeInTheDocument()

    expect(screen.getByRole('button', { name: /Explore Global Markets/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Explore Indian Markets/i })).toBeInTheDocument()
  })

  it('navigates from landing page to Global Markets desk', () => {
    window.history.pushState({}, '', '/')
    render(<App />)

    const globalBtn = screen.getByRole('button', { name: /Explore Global Markets/i })
    fireEvent.click(globalBtn)

    expect(screen.getByRole('heading', { name: /Good morning/i })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/global')
  })

  it('navigates from landing page to Indian Markets platform', async () => {
    window.history.pushState({}, '', '/')
    render(<App />)

    const indiaBtn = screen.getByRole('button', { name: /Explore Indian Markets/i })
    fireEvent.click(indiaBtn)

    expect(window.location.pathname).toBe('/india')
  })

  it('renders the 404 page for unknown routes and allows returning home', () => {
    window.history.pushState({}, '', '/random-unknown-page')
    render(<App />)

    expect(screen.getByText(/404 · ROUTE NOT FOUND/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Page Not Located/i })).toBeInTheDocument()

    const homeBtn = screen.getByRole('button', { name: /AMQUANT Home/i })
    fireEvent.click(homeBtn)

    expect(window.location.pathname).toBe('/')
  })

  it('renders dedicated Indian platform shell at /india', async () => {
    window.history.pushState({}, '', '/india')
    render(<App />)

    expect(screen.getByText('NSE · BSE · DERIVATIVES')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Daily Equity Backtest/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Intraday Backtesting/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Futures Lab/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Options Lab & Payoff/i })).toBeInTheDocument()
    expect(screen.getByText(/© 2026 Aditya M\./i)).toBeInTheDocument()
  })

  it('renders the copyright notice on landing, global and india routes', () => {
    // 1. Landing
    window.history.pushState({}, '', '/')
    const { unmount: unmountLanding } = render(<App />)
    expect(screen.getByText(/© 2026 Aditya M\./i)).toBeInTheDocument()
    unmountLanding()

    // 2. Global
    window.history.pushState({}, '', '/global')
    const { unmount: unmountGlobal } = render(<App />)
    expect(screen.getByText(/© 2026 Aditya M\./i)).toBeInTheDocument()
    unmountGlobal()

    // 3. India
    window.history.pushState({}, '', '/india')
    render(<App />)
    expect(screen.getByText(/© 2026 Aditya M\./i)).toBeInTheDocument()
  })
})
