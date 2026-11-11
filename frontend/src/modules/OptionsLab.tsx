import { useState, type FormEvent } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ErrorMessage, NumberField, ResultMetric, RunButton, SaveScenarioButton, SelectField } from '../components/ModuleControls'
import SaveScenarioModal from '../components/SaveScenarioModal'
import { useAuth } from '../context/AuthContext'
import { recordResearchHistory } from '../lib/api'
import { ChartFrame, EmptyResult } from './FinancialFoundations'
import { postResearch } from './api'

type GreekSet = { price: number; delta: number; gamma: number; vega: number; theta: number; rho: number }
type Result = { kind: string; black_scholes: GreekSet; binomial_european: { price: number }; binomial_american: { price: number }; model_difference: number; sensitivities: { spot: { input: number; price: number }[]; volatility: { input: number; price: number }[] }; assumptions: Record<string, string | number> }
const defaultInitial = { spot: '100', strike: '100', maturity: '1', rate: '0.05', volatility: '0.2', dividend_yield: '0', kind: 'call', steps: '100' }

export default function OptionsLab({ initialData }: { initialData?: Record<string, any> }) {
  const { user, session, openAuthModal } = useAuth()
  const [values, setValues] = useState(() => ({
    ...defaultInitial,
    ...(initialData ? Object.fromEntries(Object.entries(initialData).map(([k, v]) => [k, String(v)])) : {}),
  }))
  const [axis, setAxis] = useState<'spot' | 'volatility'>('spot')
  const [result, setResult] = useState<Result | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveModalOpen, setSaveModalOpen] = useState(false)

  const update = (key: keyof typeof defaultInitial, value: string) => setValues(current => ({ ...current, [key]: value }))

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(null)
    try {
      const res = await postResearch<Result>('/api/options/analyze', { ...values, spot: +values.spot, strike: +values.strike, maturity: +values.maturity, rate: +values.rate, volatility: +values.volatility, dividend_yield: +values.dividend_yield, steps: +values.steps })
      setResult(res)

      // If user is authenticated, record calculation summary to research history
      if (session?.access_token) {
        void recordResearchHistory(session.access_token, 'options', {
          bsm_price: res.black_scholes.price,
          delta: res.black_scholes.delta,
          spot: +values.spot,
          strike: +values.strike,
          kind: values.kind,
        }).catch(() => {})
      }
    }
    catch (issue) { setError(issue instanceof Error ? issue.message : 'Analysis failed.') }
    finally { setLoading(false) }
  }

  const handleSaveClick = () => {
    if (!user) {
      openAuthModal('login', 'Sign in to save this option scenario to your personal workspace.')
    } else {
      setSaveModalOpen(true)
    }
  }

  const currentSweep = result?.sensitivities[axis].map(item => ({ ...item, label: axis === 'spot' ? `$${item.input.toFixed(0)}` : `${(item.input * 100).toFixed(0)}%` }))
  return <div className="research-workspace"><div className="module-hero"><div className="eyebrow">MODULE 04 · DERIVATIVES</div><h1>Options Lab</h1><p>Price European options, inspect analytical Greeks, compare binomial models, and sweep market assumptions.</p></div>
    <div className="workspace-layout"><form className="panel input-panel" onSubmit={submit}><div className="panel-heading"><div><div className="eyebrow">CONTRACT ASSUMPTIONS</div><h2>Pricing inputs</h2><p>Black–Scholes–Merton · continuous compounding</p></div></div><div className="controls-grid two-controls"><NumberField label="Spot price S" unit="$" min="0.01" step="any" value={values.spot} onChange={e => update('spot', e.target.value)} required/><NumberField label="Strike K" unit="$" min="0.01" step="any" value={values.strike} onChange={e => update('strike', e.target.value)} required/><NumberField label="Time to expiry T" unit="years" min="0" max="20" step="any" value={values.maturity} onChange={e => update('maturity', e.target.value)} required/><NumberField label="Risk-free rate r" unit="decimal" min="-1" max="1" step="any" value={values.rate} onChange={e => update('rate', e.target.value)} required/><NumberField label="Volatility σ" unit="decimal" min="0.0001" max="5" step="any" value={values.volatility} onChange={e => update('volatility', e.target.value)} required/><NumberField label="Dividend yield q" unit="decimal" min="-1" max="1" step="any" value={values.dividend_yield} onChange={e => update('dividend_yield', e.target.value)} required/><SelectField label="Option type" value={values.kind} onChange={e => update('kind', e.target.value)}><option value="call">Call</option><option value="put">Put</option></SelectField><NumberField label="Binomial steps" min="1" max="500" step="1" value={values.steps} onChange={e => update('steps', e.target.value)} required/></div><div className="form-action-row"><RunButton loading={loading} children="Price and analyze"/><SaveScenarioButton onClick={handleSaveClick}/></div><ErrorMessage message={error}/></form>
      <section className="panel result-panel"><div className="panel-heading"><div><div className="eyebrow">PRICING & RISK</div><h2>{values.kind === 'call' ? 'Call' : 'Put'} analysis</h2><p>Analytical BSM Greeks and CRR model comparison</p></div><span className="synthetic-pill"><i/> MODEL OUTPUT</span></div>{result ? <><div className="result-grid four-results"><ResultMetric label="BSM PRICE" value={`$${result.black_scholes.price.toFixed(4)}`} note="European closed-form"/><ResultMetric label="DELTA" value={result.black_scholes.delta.toFixed(4)} note="per $1 spot move"/><ResultMetric label="GAMMA" value={result.black_scholes.gamma.toFixed(5)} note="delta change per $1"/><ResultMetric label="VEGA" value={result.black_scholes.vega.toFixed(4)} note="per 1.00 vol change"/></div><div className="result-grid four-results greek-row"><ResultMetric label="THETA" value={result.black_scholes.theta.toFixed(4)} note="per year"/><ResultMetric label="RHO" value={result.black_scholes.rho.toFixed(4)} note="per 1.00 rate change"/><ResultMetric label="EUROPEAN TREE" value={`$${result.binomial_european.price.toFixed(4)}`} note={`difference vs BSM ${result.model_difference >= 0 ? '+' : ''}${result.model_difference.toFixed(4)}`}/><ResultMetric label="AMERICAN TREE" value={`$${result.binomial_american.price.toFixed(4)}`} note="early exercise allowed"/></div><div className="sensitivity-header"><div><h3>Sensitivity analysis</h3><p>Other model inputs held fixed</p></div><div className="range-switch"><button type="button" className={axis === 'spot' ? 'selected' : ''} aria-pressed={axis === 'spot'} onClick={() => setAxis('spot')}>SPOT</button><button type="button" className={axis === 'volatility' ? 'selected' : ''} aria-pressed={axis === 'volatility'} onClick={() => setAxis('volatility')}>VOLATILITY</button></div></div><ChartFrame title={axis === 'spot' ? 'Option value across spot price' : 'Option value across volatility'}><ResponsiveContainer width="100%" height="100%"><LineChart data={currentSweep}><CartesianGrid stroke="#202b34" strokeDasharray="3 3"/><XAxis dataKey="label" tick={{ fill: '#7d8996', fontSize: 10 }} tickLine={false}/><YAxis tick={{ fill: '#7d8996', fontSize: 10 }} tickFormatter={v => `$${Number(v).toFixed(0)}`} tickLine={false}/><Tooltip contentStyle={{ background: '#101721', border: '1px solid #263342', borderRadius: 8, fontSize: 11 }} formatter={v => [`$${Number(v).toFixed(4)}`, 'Option value']}/><Line dataKey="price" stroke="#37d0a0" strokeWidth={2} dot={false} activeDot={{ r: 4 }}/></LineChart></ResponsiveContainer></ChartFrame><p className="result-explanation">{result.assumptions.greek_units} Sensitivity curves use 21 points; spot sweeps from 70% to 130% of spot and {Number(values.volatility) > 0 ? 'volatility from 40% to 160% of the input volatility.' : 'volatility from 0.08 to 0.32 when the base volatility is zero.'}</p></> : <EmptyResult text="Enter contract assumptions to calculate price and Greeks, compare tree values, and explore sensitivities."/>}</section></div>
    <div className="model-note"><b>Model note</b> Black–Scholes–Merton values a European option with constant volatility, continuous rates and continuous dividend yield. The American CRR tree permits early exercise; for a non-dividend-paying call, early exercise should not increase value.</div>

    <SaveScenarioModal
      isOpen={saveModalOpen}
      onClose={() => setSaveModalOpen(false)}
      moduleName="options"
      moduleTitle="Options Lab"
      scenarioData={values}
      defaultTitle={`Options Lab ${values.kind.toUpperCase()} $${values.strike} (T=${values.maturity}y)`}
    />
  </div>
}
