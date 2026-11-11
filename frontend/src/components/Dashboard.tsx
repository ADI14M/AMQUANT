import { useMemo } from 'react'
import { ArrowDownRight, ArrowUpRight, BookOpen, Brain, ChevronRight, CircleHelp, Clock3, Sparkles, TrendingUp } from 'lucide-react'
import PerformanceChart from './PerformanceChart'

const metrics = [
  { label: 'SIMULATED PORTFOLIO', value: '$124,832', change: '+8.42%', positive: true, detail: 'vs. initial $115,142', icon: TrendingUp },
  { label: 'SHARPE RATIO', value: '1.84', change: '+0.12', positive: true, detail: 'vs. previous period', icon: Sparkles },
  { label: 'MAX DRAWDOWN', value: '−6.28%', change: '−1.24%', positive: true, detail: 'risk improved', icon: ArrowDownRight },
  { label: 'ACTIVE STRATEGIES', value: '04', change: '2 running', positive: false, detail: 'across 3 asset classes', icon: Clock3 },
]
const modules = [
  { id: 'foundations', num: '01', title: 'Financial Foundations', body: 'Build intuition for options, payoffs and hedging.', progress: 68, tone: 'mint', action: 'Continue lesson' },
  { id: 'bayesian', num: '02', title: 'Bayesian Engine', body: 'Update beliefs as evidence arrives over time.', progress: 24, tone: 'violet', action: 'Explore module' },
  { id: 'stochastic', num: '03', title: 'Stochastic Simulator', body: 'Model uncertainty with paths and Monte Carlo.', progress: 0, tone: 'blue', action: 'Explore module' },
  { id: 'options', num: '04', title: 'Options Lab', body: 'Price contracts and study risk sensitivities.', progress: 0, tone: 'amber', action: 'Explore module' },
]

export default function Dashboard({ onNavigate }: { onNavigate: (id: 'intelligence' | 'foundations' | 'bayesian' | 'stochastic' | 'options') => void }) {
  const today = useMemo(() => new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).format(new Date()).toUpperCase(), [])
  return <>
    <div className="greeting-row"><div><div className="eyebrow">{today} <span className="live-mark"><i/> WORKSPACE READY</span></div><h1>Good morning, Researcher <span>✳</span></h1><p>Your research desk is ready. Synthesize your analysis with Research Intelligence.</p></div><button className="primary-button" onClick={() => onNavigate('intelligence')}><Brain size={16}/> Launch Intelligence</button></div>
    <div className="metric-grid">{metrics.map(({ label, value, change, positive, detail, icon: Icon }) => <article key={label} className="metric-card"><div className="metric-top"><span>{label}</span><Icon size={16}/></div><div className="metric-value">{value}</div><div className="metric-detail"><b className={positive ? 'up' : 'neutral'}>{positive && <ArrowUpRight size={13}/>} {change}</b><span>{detail}</span></div></article>)}</div>
    <div className="content-grid"><PerformanceChart/><aside className="panel insight-panel"><div className="panel-heading compact"><div><div className="eyebrow">RESEARCH NOTE</div><h2>Today's insight</h2></div><span className="icon-button" aria-hidden="true"><CircleHelp size={17}/></span></div><div className="insight-icon"><Sparkles size={17}/></div><div className="insight-title">Volatility is clustering</div><p>In your synthetic sample, high-volatility periods tend to follow one another. Explore how this changes option values.</p><div className="insight-callout"><span>CONCEPT TO EXPLORE</span><b>Volatility clustering</b><small>Stochastic Simulator · 6 min read</small></div><button className="text-button" onClick={() => onNavigate('stochastic')}>Explore the concept <ChevronRight size={14}/></button><div className="insight-foot"><CircleHelp size={13}/> Educational prompt · no live data</div></aside></div>
    <div className="section-heading"><div><div className="eyebrow">YOUR LEARNING PATH</div><h2>Research modules</h2></div><button className="text-button" onClick={() => onNavigate('foundations')}>View learning path <ChevronRight size={14}/></button></div>
    <div className="module-grid">{modules.map(module => <div className="module-card" key={module.id} tabIndex={0} onClick={() => onNavigate(module.id as 'foundations'|'bayesian'|'stochastic'|'options')} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigate(module.id as 'foundations'|'bayesian'|'stochastic'|'options') } }}><div className={`module-art ${module.tone}`}><span>{module.num}</span><BookOpen size={20}/></div><div className="module-copy"><div className="module-progress-label"><span>{module.progress ? `${module.progress}% COMPLETE` : 'READY TO EXPLORE'}</span>{module.progress > 0 && <span>{module.progress}%</span>}</div><div className="mini-progress"><i style={{ width: `${module.progress}%` }}/></div><h3>{module.title}</h3><p>{module.body}</p><span className="module-action">{module.action} <ChevronRight size={14}/></span></div></div>)}</div>
    <footer className="page-foot"><span>AMQUANT RESEARCH ENVIRONMENT <i/> Educational use only</span><span>All portfolio figures are synthetic examples.</span></footer>
  </>
}
