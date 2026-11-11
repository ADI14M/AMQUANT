import { useState, type FormEvent } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Brain,
  CheckCircle2,
  Info,
  Layers,
  Scale,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import { postResearch } from './api'
import { ErrorMessage, NumberField, ResultMetric, RunButton, SelectField } from '../components/ModuleControls'
import { ChartFrame, EmptyResult } from './FinancialFoundations'

export type IntelligenceResult = {
  setup: {
    asset: string
    spot: number
    strike: number
    maturity: number
    rate: number
    volatility: number
    drift: number
    dividend_yield: number
    kind: 'call' | 'put'
  }
  bayesian: {
    prior: { alpha: number; beta: number; mean: number }
    posterior: {
      alpha: number
      beta: number
      mean: number
      variance: number
      predictive_success_probability: number
      credible_interval_95: [number, number]
    }
    successes: number
    failures: number
    log_marginal_likelihood: number
    density: { probability: number; prior_density: number; likelihood_relative: number; posterior_density: number }[]
    sequence: { observation: number | string; successes: number; failures: number; alpha: number; beta: number; mean: number }[]
    shift_summary: string
  }
  stochastic: {
    physical: {
      time: number[]
      paths: Record<string, number>[]
      terminal_mean: number
      terminal_median: number
      terminal_std: number
      theory_mean: number
      theory_std: number
      drift_type: string
      drift_value: number
    }
    risk_neutral: {
      time: number[]
      paths: Record<string, number>[]
      terminal_mean: number
      terminal_median: number
      terminal_std: number
      theory_mean: number
      theory_std: number
      drift_type: string
      drift_value: number
    }
    measure_distinction: string
  }
  valuation: {
    kind: 'call' | 'put'
    black_scholes: { price: number; delta: number; gamma: number; vega: number; theta: number; rho: number }
    binomial_european: {
      price: number
      delta: number
      hedge_shares: number
      hedge_cash: number
      up_factor: number
      down_factor: number
      risk_neutral_probability: number
    }
    binomial_american: { price: number; delta: number }
    early_exercise_premium: number
    monte_carlo: { price: number; standard_error: number; confidence_interval_95: [number, number]; paths: number } | null
    put_call_parity: { call_price: number; put_price: number; parity_difference: number; holds: boolean; formula: string }
    models_comparison: { model: string; price: number; delta: number | null; assumptions: string; divergence: number }[]
    root_hedge: { delta_shares: number; cash_borrowing: number; explanation: string }
  }
  sensitivities: { spot: { input: number; price: number }[]; volatility: { input: number; price: number }[] }
  conclusion: {
    executive_summary: string
    uncertainty_drivers: string[]
    model_limitations: string[]
    disclaimer: string
  }
}

const defaultInputs = {
  asset: 'SYNTH_TECH',
  spot: '100',
  strike: '100',
  maturity: '1',
  rate: '0.05',
  volatility: '0.20',
  drift: '0.08',
  dividend_yield: '0',
  kind: 'call' as 'call' | 'put',
  prior_alpha: '2',
  prior_beta: '2',
  observations: '1, 1, 0, 1, 1, 0, 1',
  sim_steps: '60',
  sim_paths: '12',
  sim_seed: '42',
  mc_paths: '10000',
  tree_steps: '50',
}

const pathColors = [
  '#36d0a0', '#7d8fe5', '#e5ae64', '#53b7d8', '#cf7bc6', '#b1cd68',
  '#ef8079', '#7bc7a9', '#9c87df', '#d7cc75', '#56a3bd', '#ed9d62'
]

export default function ResearchIntelligence() {
  const [inputs, setInputs] = useState(defaultInputs)
  const [result, setResult] = useState<IntelligenceResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stochasticMeasure, setStochasticMeasure] = useState<'physical' | 'risk_neutral'>('physical')
  const [sensitivityAxis, setSensitivityAxis] = useState<'spot' | 'volatility'>('spot')
  const [activeStepTab, setActiveStepTab] = useState<'all' | 'bayesian' | 'stochastic' | 'valuation' | 'conclusion'>('all')

  const update = (key: keyof typeof defaultInputs, value: string) => {
    setInputs(prev => ({ ...prev, [key]: value }))
  }

  const applyPreset = (preset: 'tech' | 'highvol' | 'put') => {
    if (preset === 'tech') {
      setInputs({
        ...defaultInputs,
        asset: 'TECH_GROWTH',
        spot: '120',
        strike: '125',
        volatility: '0.24',
        drift: '0.12',
        observations: '1, 1, 1, 0, 1, 1, 1, 0',
      })
    } else if (preset === 'highvol') {
      setInputs({
        ...defaultInputs,
        asset: 'VOL_SPIKE',
        spot: '90',
        strike: '90',
        volatility: '0.45',
        drift: '0.02',
        observations: '0, 1, 0, 0, 1, 0',
      })
    } else {
      setInputs({
        ...defaultInputs,
        asset: 'HEDGE_PUT',
        spot: '105',
        strike: '100',
        volatility: '0.18',
        drift: '0.06',
        kind: 'put',
        observations: '1, 0, 1, 1, 0, 1',
      })
    }
  }

  async function handleRun(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const parsedObs = inputs.observations.trim()
        ? inputs.observations.split(/[\s,;]+/).map(Number)
        : [1, 0]
      if (parsedObs.some(v => v !== 0 && v !== 1)) {
        throw new Error('Observations must contain only binary values: 1 for positive signal, 0 for negative.')
      }

      const payload = {
        asset: inputs.asset.trim() || 'SYNTH',
        spot: +inputs.spot,
        strike: +inputs.strike,
        maturity: +inputs.maturity,
        rate: +inputs.rate,
        volatility: +inputs.volatility,
        drift: +inputs.drift,
        dividend_yield: +inputs.dividend_yield,
        kind: inputs.kind,
        prior_alpha: +inputs.prior_alpha,
        prior_beta: +inputs.prior_beta,
        observations: parsedObs,
        sim_steps: Math.min(Math.max(+inputs.sim_steps || 50, 10), 252),
        sim_paths: Math.min(Math.max(+inputs.sim_paths || 12, 2), 40),
        sim_seed: +inputs.sim_seed || 42,
        mc_paths: Math.min(Math.max(+inputs.mc_paths || 10000, 500), 50000),
        tree_steps: Math.min(Math.max(+inputs.tree_steps || 50, 10), 200),
      }

      const response = await postResearch<IntelligenceResult>('/api/intelligence/analyze', payload)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Research workflow calculation failed.')
    } finally {
      setLoading(false)
    }
  }

  const activePathsData = result
    ? stochasticMeasure === 'physical'
      ? result.stochastic.physical.paths
      : result.stochastic.risk_neutral.paths
    : []

  const activePathKeys = activePathsData[0]
    ? Object.keys(activePathsData[0]).filter(k => k.startsWith('path_'))
    : []

  return (
    <div className="research-workspace intelligence-workspace">
      <div className="module-hero intelligence-hero">
        <div className="hero-top-badge">
          <span className="hero-pill"><Brain size={13}/> UNIFIED RESEARCH ENGINE</span>
          <span className="synthetic-pill"><i/> MATHEMATICAL SYNTHESIS</span>
        </div>
        <h1>AMQUANT Research Intelligence</h1>
        <p>
          End-to-end quantitative workflow connecting prior uncertainty, Bayesian signal updates,
          stochastic price distributions, and multi-framework derivatives valuation.
        </p>

        <div className="preset-bar">
          <span className="preset-label">SCENARIO PRESETS:</span>
          <button type="button" className="preset-btn" onClick={() => applyPreset('tech')}>Tech Momentum Call</button>
          <button type="button" className="preset-btn" onClick={() => applyPreset('highvol')}>High-Vol Regime Shift</button>
          <button type="button" className="preset-btn" onClick={() => applyPreset('put')}>Downside Protective Put</button>
        </div>
      </div>

      <div className="workspace-layout">
        {/* INPUT PANEL */}
        <form className="panel input-panel intelligence-inputs" onSubmit={handleRun}>
          <div className="panel-heading">
            <div>
              <div className="eyebrow">RESEARCH PARAMETERS</div>
              <h2>Integrated assumptions</h2>
              <p>Asset profile, Bayesian prior, and stochastic settings</p>
            </div>
          </div>

          <div className="controls-grid two-controls">
            <label className="control-field full-control">
              <span>Asset Ticker / Label</span>
              <input
                type="text"
                value={inputs.asset}
                onChange={e => update('asset', e.target.value)}
                placeholder="e.g. NVDA, SPY, TECH_INDEX"
                required
              />
            </label>

            <NumberField label="Spot price S" unit="$" min="0.01" step="any" value={inputs.spot} onChange={e => update('spot', e.target.value)} required/>
            <NumberField label="Option strike K" unit="$" min="0.01" step="any" value={inputs.strike} onChange={e => update('strike', e.target.value)} required/>
            <NumberField label="Horizon T" unit="years" min="0.01" max="20" step="any" value={inputs.maturity} onChange={e => update('maturity', e.target.value)} required/>
            <NumberField label="Risk-free rate r" unit="dec" min="-1" max="1" step="any" value={inputs.rate} onChange={e => update('rate', e.target.value)} required/>
            <NumberField label="Volatility σ" unit="dec" min="0.001" max="5" step="any" value={inputs.volatility} onChange={e => update('volatility', e.target.value)} required/>
            <NumberField label="Physical drift μ" unit="dec" min="-5" max="5" step="any" value={inputs.drift} onChange={e => update('drift', e.target.value)} required/>
            <NumberField label="Dividend yield q" unit="dec" min="-1" max="1" step="any" value={inputs.dividend_yield} onChange={e => update('dividend_yield', e.target.value)} required/>
            <SelectField label="Contract type" value={inputs.kind} onChange={e => update('kind', e.target.value as 'call' | 'put')}>
              <option value="call">European Call</option>
              <option value="put">European Put</option>
            </SelectField>

            <div className="section-divider-inline">
              <span>BAYESIAN REGIME PRIOR</span>
            </div>

            <NumberField label="Prior α (Successes)" min="0.01" max="10000" step="any" value={inputs.prior_alpha} onChange={e => update('prior_alpha', e.target.value)} required/>
            <NumberField label="Prior β (Failures)" min="0.01" max="10000" step="any" value={inputs.prior_beta} onChange={e => update('prior_beta', e.target.value)} required/>

            <label className="control-field full-control">
              <span>Regime evidence observations</span>
              <textarea
                rows={2}
                value={inputs.observations}
                onChange={e => update('observations', e.target.value)}
                placeholder="1, 1, 0, 1, 0"
              />
              <small>Binary outcomes (1 = positive signal, 0 = negative signal)</small>
            </label>

            <div className="section-divider-inline">
              <span>SIMULATION & LATTICE SETUP</span>
            </div>

            <NumberField label="Simulation steps" min="10" max="252" step="1" value={inputs.sim_steps} onChange={e => update('sim_steps', e.target.value)} required/>
            <NumberField label="Sample paths" min="2" max="40" step="1" value={inputs.sim_paths} onChange={e => update('sim_paths', e.target.value)} required/>
            <NumberField label="Random seed" min="0" step="1" value={inputs.sim_seed} onChange={e => update('sim_seed', e.target.value)} required/>
            <NumberField label="Monte Carlo paths" min="500" max="50000" step="500" value={inputs.mc_paths} onChange={e => update('mc_paths', e.target.value)} required/>
            <NumberField label="Binomial tree steps" min="10" max="200" step="1" value={inputs.tree_steps} onChange={e => update('tree_steps', e.target.value)} required/>
          </div>

          <RunButton loading={loading}>Execute Research Workflow</RunButton>
          <ErrorMessage message={error}/>
        </form>

        {/* RESULTS AREA */}
        <section className="panel result-panel intelligence-results">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">RESEARCH SYNTHESIS</div>
              <h2>Workflow stages</h2>
              <p>Bayesian inference · Stochastic simulation · Derivatives pricing</p>
            </div>
            {result && (
              <div className="workflow-tab-bar">
                <button type="button" className={activeStepTab === 'all' ? 'active' : ''} onClick={() => setActiveStepTab('all')}>Overview</button>
                <button type="button" className={activeStepTab === 'bayesian' ? 'active' : ''} onClick={() => setActiveStepTab('bayesian')}>Bayesian</button>
                <button type="button" className={activeStepTab === 'stochastic' ? 'active' : ''} onClick={() => setActiveStepTab('stochastic')}>Stochastic</button>
                <button type="button" className={activeStepTab === 'valuation' ? 'active' : ''} onClick={() => setActiveStepTab('valuation')}>Valuation</button>
                <button type="button" className={activeStepTab === 'conclusion' ? 'active' : ''} onClick={() => setActiveStepTab('conclusion')}>Conclusion</button>
              </div>
            )}
          </div>

          {result ? (
            <div className="workflow-stages-container">
              {/* STAGE A & B: BAYESIAN INFERENCE */}
              {(activeStepTab === 'all' || activeStepTab === 'bayesian') && (
                <article className="workflow-card">
                  <div className="card-stage-header">
                    <span className="stage-pill">STAGE 01</span>
                    <h3>Bayesian Parameter Inference</h3>
                    <span className="card-tag">Beta–Bernoulli Conjugacy</span>
                  </div>

                  <div className="result-grid four-results">
                    <ResultMetric label="PRIOR MEAN" value={`${(result.bayesian.prior.mean * 100).toFixed(1)}%`} note={`Beta(${result.bayesian.prior.alpha}, ${result.bayesian.prior.beta})`}/>
                    <ResultMetric label="POSTERIOR MEAN" value={`${(result.bayesian.posterior.mean * 100).toFixed(1)}%`} note={`Beta(${result.bayesian.posterior.alpha}, ${result.bayesian.posterior.beta})`}/>
                    <ResultMetric label="95% CREDIBLE RANGE" value={`${(result.bayesian.posterior.credible_interval_95[0] * 100).toFixed(1)}% – ${(result.bayesian.posterior.credible_interval_95[1] * 100).toFixed(1)}%`} note="Equal-tailed interval"/>
                    <ResultMetric label="LOG MARGINAL LIKELIHOOD" value={result.bayesian.log_marginal_likelihood.toFixed(4)} note={`${result.bayesian.successes} succ · ${result.bayesian.failures} fail`}/>
                  </div>

                  <ChartFrame title="Prior vs. Likelihood vs. Posterior Density">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={result.bayesian.density}>
                        <CartesianGrid stroke="#202b34" strokeDasharray="3 3"/>
                        <XAxis dataKey="probability" tick={{ fill: '#7d8996', fontSize: 10 }} tickFormatter={v => `${Math.round(v * 100)}%`} tickLine={false}/>
                        <YAxis tick={{ fill: '#7d8996', fontSize: 10 }} tickLine={false}/>
                        <Tooltip contentStyle={{ background: '#101721', border: '1px solid #263342', borderRadius: 8, fontSize: 11 }} labelFormatter={v => `Probability: ${(Number(v) * 100).toFixed(1)}%`}/>
                        <Area type="monotone" dataKey="prior_density" stroke="#8e7ed1" fill="#8e7ed1" fillOpacity={0.12} strokeWidth={1.5} name="Prior Density"/>
                        <Line type="monotone" dataKey="likelihood_relative" stroke="#e4b36d" strokeDasharray="4 4" dot={false} name="Relative Likelihood"/>
                        <Area type="monotone" dataKey="posterior_density" stroke="#39d1a1" fill="#39d1a1" fillOpacity={0.2} strokeWidth={2} name="Posterior Density"/>
                      </AreaChart>
                    </ResponsiveContainer>
                  </ChartFrame>

                  <div className="workflow-narrative-box">
                    <Info size={15}/>
                    <p>{result.bayesian.shift_summary}</p>
                  </div>
                </article>
              )}

              {/* STAGE C: STOCHASTIC FORECASTING */}
              {(activeStepTab === 'all' || activeStepTab === 'stochastic') && (
                <article className="workflow-card">
                  <div className="card-stage-header">
                    <span className="stage-pill">STAGE 02</span>
                    <h3>Stochastic Asset Simulation</h3>
                    <div className="measure-toggle" role="group" aria-label="Stochastic measure toggle">
                      <button
                        type="button"
                        className={stochasticMeasure === 'physical' ? 'selected' : ''}
                        onClick={() => setStochasticMeasure('physical')}
                      >
                        Physical Measure $\mathbb&#123;P\&#125;$ ($\mu={result.setup.drift}$)
                      </button>
                      <button
                        type="button"
                        className={stochasticMeasure === 'risk_neutral' ? 'selected' : ''}
                        onClick={() => setStochasticMeasure('risk_neutral')}
                      >
                        Risk-Neutral Measure $\mathbb&#123;Q\&#125;$ ($r={result.setup.rate}$)
                      </button>
                    </div>
                  </div>

                  {stochasticMeasure === 'physical' ? (
                    <div className="result-grid four-results">
                      <ResultMetric label="PHYSICAL DRIFT μ" value={`${(result.stochastic.physical.drift_value * 100).toFixed(1)}%`} note="Annualized expected return"/>
                      <ResultMetric label="TERMINAL MEAN S(T)" value={`$${result.stochastic.physical.terminal_mean.toFixed(2)}`} note={`Theory: $${result.stochastic.physical.theory_mean.toFixed(2)}`}/>
                      <ResultMetric label="TERMINAL MEDIAN" value={`$${result.stochastic.physical.terminal_median.toFixed(2)}`} note="50th percentile"/>
                      <ResultMetric label="TERMINAL STD DEV" value={`$${result.stochastic.physical.terminal_std.toFixed(2)}`} note={`Theory: $${result.stochastic.physical.theory_std.toFixed(2)}`}/>
                    </div>
                  ) : (
                    <div className="result-grid four-results">
                      <ResultMetric label="RISK-NEUTRAL DRIFT" value={`${(result.stochastic.risk_neutral.drift_value * 100).toFixed(1)}%`} note="r - q martingale drift"/>
                      <ResultMetric label="RN TERMINAL MEAN" value={`$${result.stochastic.risk_neutral.terminal_mean.toFixed(2)}`} note={`Forward: $${result.stochastic.risk_neutral.theory_mean.toFixed(2)}`}/>
                      <ResultMetric label="RN TERMINAL MEDIAN" value={`$${result.stochastic.risk_neutral.terminal_median.toFixed(2)}`} note="Discounted expectation"/>
                      <ResultMetric label="RN TERMINAL STD DEV" value={`$${result.stochastic.risk_neutral.terminal_std.toFixed(2)}`} note="Sampling dispersion"/>
                    </div>
                  )}

                  <ChartFrame title={`Geometric Brownian Motion Paths (${stochasticMeasure === 'physical' ? 'Physical Forecast P' : 'Risk-Neutral Pricing Q'})`}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={activePathsData}>
                        <CartesianGrid stroke="#202b34" strokeDasharray="3 3"/>
                        <XAxis dataKey="time" tick={{ fill: '#7d8996', fontSize: 10 }} tickFormatter={v => `${Number(v).toFixed(2)}y`} tickLine={false}/>
                        <YAxis tick={{ fill: '#7d8996', fontSize: 10 }} tickFormatter={v => `$${Number(v).toFixed(0)}`} tickLine={false}/>
                        <Tooltip contentStyle={{ background: '#101721', border: '1px solid #263342', borderRadius: 8, fontSize: 11 }} labelFormatter={v => `Time: ${Number(v).toFixed(3)}y`}/>
                        <ReferenceLine y={result.setup.strike} stroke="#ef8079" strokeDasharray="4 4" label={{ value: `Strike $${result.setup.strike}`, fill: '#ef8079', fontSize: 10 }}/>
                        {activePathKeys.map((key, i) => (
                          <Line
                            key={key}
                            type="monotone"
                            dataKey={key}
                            stroke={pathColors[i % pathColors.length]}
                            strokeOpacity={0.7}
                            strokeWidth={1.3}
                            dot={false}
                            isAnimationActive={false}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </ChartFrame>

                  <div className="workflow-narrative-box">
                    <Scale size={15}/>
                    <p><b>Measure distinction:</b> {result.stochastic.measure_distinction}</p>
                  </div>
                </article>
              )}

              {/* STAGE D: DERIVATIVES VALUATION */}
              {(activeStepTab === 'all' || activeStepTab === 'valuation') && (
                <article className="workflow-card">
                  <div className="card-stage-header">
                    <span className="stage-pill">STAGE 03</span>
                    <h3>Multi-Model Derivatives Valuation</h3>
                    <span className="card-tag">{result.setup.kind.toUpperCase()} ANALYSIS</span>
                  </div>

                  <div className="result-grid four-results">
                    <ResultMetric label="BLACK–SCHOLES PRICE" value={`$${result.valuation.black_scholes.price.toFixed(4)}`} note="Analytical European"/>
                    <ResultMetric label="CRR BINOMIAL EUROPEAN" value={`$${result.valuation.binomial_european.price.toFixed(4)}`} note={`Lattice (${result.valuation.binomial_european.risk_neutral_probability.toFixed(3)} p_rn)`}/>
                    <ResultMetric label="CRR AMERICAN VALUE" value={`$${result.valuation.binomial_american.price.toFixed(4)}`} note={`Early exercise: +$${result.valuation.early_exercise_premium.toFixed(4)}`}/>
                    <ResultMetric
                      label="MONTE CARLO ESTIMATE"
                      value={result.valuation.monte_carlo ? `$${result.valuation.monte_carlo.price.toFixed(4)}` : 'N/A'}
                      note={result.valuation.monte_carlo ? `SE: ±$${result.valuation.monte_carlo.standard_error.toFixed(4)}` : undefined}
                    />
                  </div>

                  <div className="result-grid four-results greek-row">
                    <ResultMetric label="DELTA Δ" value={result.valuation.black_scholes.delta.toFixed(4)} note="Hedge ratio per share"/>
                    <ResultMetric label="GAMMA Γ" value={result.valuation.black_scholes.gamma.toFixed(5)} note="Δ sensitivity per $1"/>
                    <ResultMetric label="VEGA V" value={result.valuation.black_scholes.vega.toFixed(4)} note="Value change per 1.00 σ"/>
                    <ResultMetric label="THETA Θ" value={result.valuation.black_scholes.theta.toFixed(4)} note="Annualized time decay"/>
                  </div>

                  {/* MODEL COMPARISON TABLE */}
                  <div className="model-comparison-wrap">
                    <div className="table-caption">
                      <Layers size={14}/>
                      <b>Valuation Framework Comparison</b>
                    </div>
                    <table className="comparison-table">
                      <thead>
                        <tr>
                          <th>Valuation Framework</th>
                          <th>Price ($)</th>
                          <th>Delta</th>
                          <th>Divergence vs. BSM</th>
                          <th>Key Framework Assumptions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.valuation.models_comparison.map(row => (
                          <tr key={row.model}>
                            <td className="fw-name">{row.model}</td>
                            <td className="fw-price">${row.price.toFixed(4)}</td>
                            <td>{row.delta !== null ? row.delta.toFixed(4) : '—'}</td>
                            <td className={row.divergence === 0 ? 'zero-div' : 'diff-div'}>
                              {row.divergence >= 0 ? `+${row.divergence.toFixed(4)}` : row.divergence.toFixed(4)}
                            </td>
                            <td className="fw-note">{row.assumptions}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* PUT-CALL PARITY & REPLICATING HEDGE CARD */}
                  <div className="parity-container">
                    <div className="parity-card">
                      <div className="parity-header">
                        <CheckCircle2 size={16} className="text-mint"/>
                        <b>Put-Call Parity Verification</b>
                      </div>
                      <div className="parity-body">
                        <code>{result.valuation.put_call_parity.formula}</code>
                        <div className="parity-metric-row">
                          <span>Call: <b>${result.valuation.put_call_parity.call_price.toFixed(4)}</b></span>
                          <span>Put: <b>${result.valuation.put_call_parity.put_price.toFixed(4)}</b></span>
                          <span>Parity Residual: <b>{result.valuation.put_call_parity.parity_difference.toExponential(2)}</b></span>
                        </div>
                        <small className="parity-status">
                          {result.valuation.put_call_parity.holds
                            ? '✓ Parity holds exactly within floating-point tolerance.'
                            : 'Arbitrage opportunity detected.'}
                        </small>
                      </div>
                    </div>

                    <div className="hedge-replicate-card">
                      <div className="parity-header">
                        <Sparkles size={16} className="text-mint"/>
                        <b>Replicating Portfolio at Node 0</b>
                      </div>
                      <p>{result.valuation.root_hedge.explanation}</p>
                    </div>
                  </div>

                  {/* SENSITIVITY SWEEPS */}
                  <div className="sensitivity-section">
                    <div className="sensitivity-header">
                      <div>
                        <h3>Parametric Sensitivity Curves</h3>
                        <p>One-factor sweeps holding other assumptions fixed</p>
                      </div>
                      <div className="range-switch">
                        <button
                          type="button"
                          className={sensitivityAxis === 'spot' ? 'selected' : ''}
                          onClick={() => setSensitivityAxis('spot')}
                        >
                          SPOT SWEEP
                        </button>
                        <button
                          type="button"
                          className={sensitivityAxis === 'volatility' ? 'selected' : ''}
                          onClick={() => setSensitivityAxis('volatility')}
                        >
                          VOLATILITY SWEEP
                        </button>
                      </div>
                    </div>

                    <ChartFrame title={`Option Value Across ${sensitivityAxis === 'spot' ? 'Underlying Spot Price' : 'Implied Volatility'}`}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                          data={result.sensitivities[sensitivityAxis].map(item => ({
                            ...item,
                            label: sensitivityAxis === 'spot' ? `$${item.input.toFixed(0)}` : `${(item.input * 100).toFixed(0)}%`,
                          }))}
                        >
                          <CartesianGrid stroke="#202b34" strokeDasharray="3 3"/>
                          <XAxis dataKey="label" tick={{ fill: '#7d8996', fontSize: 10 }} tickLine={false}/>
                          <YAxis tick={{ fill: '#7d8996', fontSize: 10 }} tickFormatter={v => `$${Number(v).toFixed(0)}`} tickLine={false}/>
                          <Tooltip contentStyle={{ background: '#101721', border: '1px solid #263342', borderRadius: 8, fontSize: 11 }} formatter={v => [`$${Number(v).toFixed(4)}`, 'Option Value']}/>
                          <Line dataKey="price" stroke="#36d0a0" strokeWidth={2} dot={false} activeDot={{ r: 4 }}/>
                        </LineChart>
                      </ResponsiveContainer>
                    </ChartFrame>
                  </div>
                </article>
              )}

              {/* STAGE E: RESEARCH CONCLUSION */}
              {(activeStepTab === 'all' || activeStepTab === 'conclusion') && (
                <article className="workflow-card conclusion-card">
                  <div className="card-stage-header">
                    <span className="stage-pill">STAGE 04</span>
                    <h3>Executive Quantitative Conclusion</h3>
                    <span className="card-tag">RESEARCH MEMO</span>
                  </div>

                  <div className="conclusion-narrative">
                    <p className="lead-summary">{result.conclusion.executive_summary}</p>

                    <div className="conclusion-columns">
                      <div className="conclusion-col">
                        <h4><TrendingUp size={15}/> Primary Uncertainty Drivers</h4>
                        <ul>
                          {result.conclusion.uncertainty_drivers.map((point, idx) => (
                            <li key={idx}>{point}</li>
                          ))}
                        </ul>
                      </div>

                      <div className="conclusion-col">
                        <h4><ShieldAlert size={15}/> Theoretical Model Limitations</h4>
                        <ul>
                          {result.conclusion.model_limitations.map((limit, idx) => (
                            <li key={idx}>{limit}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>

                  <div className="terminal-disclaimer-box">
                    <span className="disclaimer-mark">COMPLIANCE NOTICE</span>
                    <p>{result.conclusion.disclaimer}</p>
                  </div>
                </article>
              )}
            </div>
          ) : (
            <EmptyResult text="Configure parameters or select a scenario preset and run the research workflow to generate unified intelligence."/>
          )}
        </section>
      </div>

      <div className="model-note">
        <b>Framework Architecture:</b> AMQUANT Research Intelligence integrates conjugate Bayesian updating,
        discrete Brownian/GBM paths, numerical CRR binomial lattices, and Black–Scholes–Merton continuous-time partial differential equations.
        All calculations execute natively in the pure Python quantitative engine.
      </div>
    </div>
  )
}
