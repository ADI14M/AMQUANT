import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./lib/api', async () => {
  const actual = await vi.importActual<typeof import('./lib/api')>('./lib/api')
  return {
    ...actual,
    checkAccessStatus: vi.fn().mockResolvedValue({ authenticated: true }),
    checkApiHealth: vi.fn().mockResolvedValue(false),
  }
})

describe('AMQUANT application shell', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })
  beforeEach(() => {
    window.history.pushState({}, '', '/global')
    render(<App />)
  })
  it('renders the research dashboard and labels its example data synthetic', () => {
    expect(screen.getByRole('heading', { name: /Good morning/ })).toBeInTheDocument()
    expect(screen.getByText(/Illustrative simulation · not market data/)).toBeInTheDocument()
  })
  it('navigates to a research module and back to overview', () => {
    fireEvent.click(screen.getByRole('button', { name: /Options Lab/ }))
    expect(screen.getByRole('heading', { name: 'Options Lab' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Overview/ }))
    expect(screen.getByRole('heading', { name: /Good morning/ })).toBeInTheDocument()
  })
  it('changes the selected performance range', () => {
    fireEvent.click(screen.getByRole('button', { name: '1M' }))
    expect(screen.getByRole('button', { name: '1M' })).toHaveAttribute('aria-pressed', 'true')
  })
  it('filters module search and opens a selected result', () => {
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Search modules' }), { target: { value: 'Bayesian' } })
    fireEvent.click(screen.getAllByRole('button', { name: /Bayesian Engine/ })[1])
    expect(screen.getByRole('heading', { name: 'Bayesian Engine' })).toBeInTheDocument()
  })
  it('submits foundation assumptions to the API and displays returned pricing', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ tree: { price: 1.2345, delta: 0.5, hedge_shares: 0.5, hedge_cash: -48.7, risk_neutral_probability: 0.51 }, payoff_curve: [{ spot: 50, intrinsic: 0, profit: -10 }, { spot: 150, intrinsic: 50, profit: 40 }], hedge_explanation: 'Replicating hedge.' }) })
    vi.stubGlobal('fetch', fetchMock)
    fireEvent.click(screen.getByRole('button', { name: /Financial Foundations/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Run calculation' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/foundations/analyze'), expect.objectContaining({ method: 'POST' })))
    expect(await screen.findByText('$1.2345')).toBeInTheDocument()
  })
  it('exposes distinct working inputs for the other research modules', () => {
    fireEvent.click(screen.getByRole('button', { name: /Bayesian Engine/ }))
    expect(screen.getByLabelText('Prior α')).toBeInTheDocument()
    expect(screen.getByLabelText(/Observed outcomes/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Stochastic Simulator/ }))
    expect(screen.getByLabelText('Process')).toBeInTheDocument()
    expect(screen.getByLabelText('Random seed')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Options Lab/ }))
    expect(screen.getByLabelText(/Volatility σ/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Dividend yield q/)).toBeInTheDocument()
  })
  it('navigates to Research Intelligence and executes the integrated research workflow', async () => {
    const mockIntelligence = {
      setup: { asset: 'NVDA', spot: 100, strike: 100, maturity: 1, rate: 0.05, volatility: 0.2, drift: 0.08, dividend_yield: 0, kind: 'call' },
      bayesian: {
        prior: { alpha: 2, beta: 2, mean: 0.5 },
        posterior: { alpha: 7, beta: 4, mean: 0.636, variance: 0.019, predictive_success_probability: 0.636, credible_interval_95: [0.35, 0.87] },
        successes: 5, failures: 2, log_marginal_likelihood: -5.12,
        density: [{ probability: 0.5, prior_density: 1.5, likelihood_relative: 0.6, posterior_density: 1.8 }],
        sequence: [],
        shift_summary: 'Prior belief shifted upward to 63.6% based on observed signals.'
      },
      stochastic: {
        physical: { time: [0, 1], paths: [{ time: 0, path_1: 100 }], terminal_mean: 108.3, terminal_median: 106.1, terminal_std: 21.8, theory_mean: 108.3, theory_std: 21.8, drift_type: 'Physical Drift', drift_value: 0.08 },
        risk_neutral: { time: [0, 1], paths: [{ time: 0, path_1: 100 }], terminal_mean: 105.1, terminal_median: 103.0, terminal_std: 21.2, theory_mean: 105.1, theory_std: 21.2, drift_type: 'Risk-Neutral Drift', drift_value: 0.05 },
        measure_distinction: 'P reflects forecasting drift; Q reflects arbitrage-free pricing drift.'
      },
      valuation: {
        kind: 'call',
        black_scholes: { price: 10.4506, delta: 0.6368, gamma: 0.0187, vega: 37.52, theta: -6.41, rho: 53.23 },
        binomial_european: { price: 10.42, delta: 0.633, hedge_shares: 0.633, hedge_cash: -53.1, up_factor: 1.06, down_factor: 0.94, risk_neutral_probability: 0.52 },
        binomial_american: { price: 10.42, delta: 0.633 },
        early_exercise_premium: 0.0,
        monte_carlo: { price: 10.46, standard_error: 0.15, confidence_interval_95: [10.16, 10.75], paths: 10000 },
        put_call_parity: { call_price: 10.45, put_price: 5.57, parity_difference: 0.000001, holds: true, formula: 'C - P = S - K*exp(-r*T)' },
        models_comparison: [
          { model: 'Black–Scholes–Merton', price: 10.4506, delta: 0.6368, assumptions: 'Lognormal diffusion', divergence: 0.0 }
        ],
        root_hedge: { delta_shares: 0.633, cash_borrowing: -53.1, explanation: 'Replicate with 0.633 shares and $53.1 borrowing.' }
      },
      sensitivities: { spot: [{ input: 100, price: 10.45 }], volatility: [{ input: 0.2, price: 10.45 }] },
      conclusion: {
        executive_summary: 'Comprehensive quantitative analysis for NVDA.',
        uncertainty_drivers: ['Delta exposure: 0.637', 'Vega sensitivity: 37.52'],
        model_limitations: ['Stationary volatility assumed'],
        disclaimer: 'Educational research terminal · Not financial advice.'
      }
    }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => mockIntelligence })
    vi.stubGlobal('fetch', fetchMock)

    fireEvent.click(screen.getByRole('button', { name: /Research Intelligence/ }))
    expect(screen.getByRole('heading', { name: 'AMQUANT Research Intelligence' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Execute Research Workflow' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/intelligence/analyze'), expect.objectContaining({ method: 'POST' })))

    expect(await screen.findByText('Comprehensive quantitative analysis for NVDA.')).toBeInTheDocument()
    expect(screen.getByText('Prior belief shifted upward to 63.6% based on observed signals.')).toBeInTheDocument()
    expect(screen.getByText('Put-Call Parity Verification')).toBeInTheDocument()
  })

  it('handles rate limiting (429) gracefully and displays retry guidance', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: new Headers({ 'Retry-After': '42' }),
      json: async () => ({ detail: 'Rate limit exceeded (maximum 30 requests per minute). Please retry in 42 seconds.' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    fireEvent.click(screen.getByRole('button', { name: /Financial Foundations/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Run calculation' }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/Rate limit exceeded/)).toBeInTheDocument()
    expect(screen.getByText(/42 seconds/)).toBeInTheDocument()
  })

  it('handles cold starts and network connectivity errors with clear guidance', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)

    fireEvent.click(screen.getByRole('button', { name: /Financial Foundations/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Run calculation' }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/Cannot connect to the AMQUANT API/)).toBeInTheDocument()
    expect(screen.getByText(/Render/)).toBeInTheDocument()
  })

  it('handles backend validation errors (422) without crashing', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers(),
      json: async () => ({
        detail: 'Request validation failed. Please check your parameter values.',
        errors: [{ field: 'volatility', message: 'Input should be greater than 0' }],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    fireEvent.click(screen.getByRole('button', { name: /Financial Foundations/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Run calculation' }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/Validation error: volatility: Input should be greater than 0/)).toBeInTheDocument()
  })
})
