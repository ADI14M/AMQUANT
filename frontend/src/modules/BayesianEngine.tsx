import { useState, type FormEvent } from 'react'
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ErrorMessage, NumberField, ResultMetric, RunButton, SaveScenarioButton } from '../components/ModuleControls'
import SaveScenarioModal from '../components/SaveScenarioModal'
import { useAuth } from '../context/AuthContext'
import { recordResearchHistory } from '../lib/api'
import { ChartFrame, EmptyResult } from './FinancialFoundations'
import { postResearch } from './api'

type Result = {
  prior: { alpha: number; beta: number; mean: number }
  posterior: { alpha: number; beta: number; mean: number; variance: number; predictive_success_probability: number; credible_interval_95: number[] }
  successes: number; failures: number; log_marginal_likelihood: number
  density: { probability: number; prior_density: number; likelihood_relative: number; posterior_density: number }[]
  sequence: { observation: number | string; successes: number; failures: number; alpha: number; beta: number; mean: number }[]
}

export default function BayesianEngine({ initialData }: { initialData?: Record<string, any> }) {
  const { user, session, openAuthModal } = useAuth()
  const [alpha, setAlpha] = useState(() => (initialData?.alpha ? String(initialData.alpha) : '2'))
  const [beta, setBeta] = useState(() => (initialData?.beta ? String(initialData.beta) : '2'))
  const [observations, setObservations] = useState(() =>
    initialData?.observations
      ? Array.isArray(initialData.observations)
        ? initialData.observations.join(', ')
        : String(initialData.observations)
      : '1, 0, 1, 1, 0, 1'
  )
  const [result, setResult] = useState<Result | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveModalOpen, setSaveModalOpen] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(null)
    try {
      const parsed = observations.trim() ? observations.split(/[\s,;]+/).map(Number) : []
      if (parsed.some(value => value !== 0 && value !== 1)) throw new Error('Enter only binary observations: 1 for success and 0 for failure.')
      const res = await postResearch<Result>('/api/bayesian/update', { alpha: +alpha, beta: +beta, observations: parsed })
      setResult(res)

      if (session?.access_token) {
        void recordResearchHistory(session.access_token, 'bayesian', {
          prior_mean: res.prior.mean,
          posterior_mean: res.posterior.mean,
          successes: res.successes,
          failures: res.failures,
        }).catch(() => {})
      }
    } catch (issue) { setError(issue instanceof Error ? issue.message : 'Update failed.') }
    finally { setLoading(false) }
  }

  const handleSaveClick = () => {
    if (!user) {
      openAuthModal('login', 'Sign in to save this Bayesian prior & evidence scenario.')
    } else {
      setSaveModalOpen(true)
    }
  }

  return <div className="research-workspace"><div className="module-hero"><div className="eyebrow">MODULE 02 · SEQUENTIAL INFERENCE</div><h1>Bayesian Engine</h1><p>Begin with a Beta prior, evaluate binary evidence, and update your belief one observation at a time.</p></div>
    <div className="workspace-layout"><form className="panel input-panel" onSubmit={submit}><div className="panel-heading"><div><div className="eyebrow">MODEL INPUTS</div><h2>Prior and evidence</h2><p>Beta–Bernoulli conjugate model</p></div></div><div className="controls-grid two-controls"><NumberField label="Prior α" min="0.001" max="100000" step="any" value={alpha} onChange={e => setAlpha(e.target.value)} required/><NumberField label="Prior β" min="0.001" max="100000" step="any" value={beta} onChange={e => setBeta(e.target.value)} required/><label className="control-field full-control"><span>Observed outcomes</span><textarea rows={4} value={observations} onChange={event => setObservations(event.target.value)} placeholder="1, 0, 1, 1, 0"/><small>Comma or space separated · 1 = success, 0 = failure</small></label></div><div className="form-action-row"><RunButton loading={loading} children="Update posterior"/><SaveScenarioButton onClick={handleSaveClick}/></div><ErrorMessage message={error}/></form>
      <section className="panel result-panel"><div className="panel-heading"><div><div className="eyebrow">POSTERIOR SUMMARY</div><h2>Belief update</h2><p>Posterior predictive distribution for the next trial</p></div><span className="synthetic-pill"><i/> USER-DEFINED EVIDENCE</span></div>{result ? <><div className="result-grid four-results"><ResultMetric label="PRIOR MEAN" value={`${(result.prior.mean * 100).toFixed(1)}%`} note={`Beta(${result.prior.alpha}, ${result.prior.beta})`}/><ResultMetric label="POSTERIOR MEAN" value={`${(result.posterior.mean * 100).toFixed(1)}%`} note={`Beta(${result.posterior.alpha}, ${result.posterior.beta})`}/><ResultMetric label="95% CREDIBLE RANGE" value={`${(result.posterior.credible_interval_95[0] * 100).toFixed(1)}–${(result.posterior.credible_interval_95[1] * 100).toFixed(1)}%`} note="equal-tailed interval"/><ResultMetric label="NEXT SUCCESS P" value={`${(result.posterior.predictive_success_probability * 100).toFixed(1)}%`} note={`${result.successes} success · ${result.failures} failure`}/></div><ChartFrame title="Prior, likelihood, and posterior"><ResponsiveContainer width="100%" height="100%"><AreaChart data={result.density}><CartesianGrid stroke="#202b34" strokeDasharray="3 3"/><XAxis dataKey="probability" tick={{ fill: '#7d8996', fontSize: 10 }} tickFormatter={v => `${Math.round(v * 100)}%`} tickLine={false}/><YAxis tick={{ fill: '#7d8996', fontSize: 10 }} tickLine={false}/><Tooltip contentStyle={{ background: '#101721', border: '1px solid #263342', borderRadius: 8, fontSize: 11 }} labelFormatter={v => `Success probability ${(Number(v)*100).toFixed(1)}%`}/><Area type="monotone" dataKey="prior_density" stroke="#8e7ed1" fill="#8e7ed1" fillOpacity={0.1} strokeWidth={1.5} name="Prior density"/><Line type="monotone" dataKey="likelihood_relative" stroke="#e4b36d" strokeDasharray="4 4" dot={false} name="Relative likelihood"/><Area type="monotone" dataKey="posterior_density" stroke="#39d1a1" fill="#39d1a1" fillOpacity={0.17} strokeWidth={2} name="Posterior density"/></AreaChart></ResponsiveContainer></ChartFrame><ChartFrame title="Sequential posterior mean"><ResponsiveContainer width="100%" height="100%"><LineChart data={result.sequence.map((row, index) => ({ ...row, step: index }))}><CartesianGrid stroke="#202b34" strokeDasharray="3 3"/><XAxis dataKey="step" tick={{ fill: '#7d8996', fontSize: 10 }} label={{ value: 'Observation index', position: 'insideBottom', offset: -2, fill: '#748190', fontSize: 10 }}/><YAxis domain={[0, 1]} tickFormatter={v => `${Math.round(v*100)}%`} tick={{ fill: '#7d8996', fontSize: 10 }}/><Tooltip formatter={v => [`${(Number(v)*100).toFixed(1)}%`, 'Posterior mean']}/><Line dataKey="mean" stroke="#39d1a1" strokeWidth={2} dot={{ r: 2 }}/></LineChart></ResponsiveContainer></ChartFrame><p className="result-explanation">Log marginal likelihood of the observed sequence: {result.log_marginal_likelihood.toFixed(4)}. Observations are treated as conditionally independent Bernoulli trials with a shared success probability.</p></> : <EmptyResult text="Enter positive prior parameters and a sequence of binary observations to calculate the posterior."/>}</section></div>
    <div className="model-note"><b>Model note</b> Beta(α, β) is conjugate to Bernoulli data: after s successes and f failures, the posterior is Beta(α+s, β+f). The evidence order changes the sequential path, but not the final posterior.</div>

    <SaveScenarioModal
      isOpen={saveModalOpen}
      onClose={() => setSaveModalOpen(false)}
      moduleName="bayesian"
      moduleTitle="Bayesian Engine"
      scenarioData={{ alpha: +alpha, beta: +beta, observations: observations.trim() ? observations.split(/[\s,;]+/).map(Number) : [] }}
      defaultTitle={`Bayesian Prior Beta(${alpha}, ${beta}) with Signals`}
    />
  </div>
}
