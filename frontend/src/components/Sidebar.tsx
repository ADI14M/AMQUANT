import { Activity, Atom, BookOpen, Brain, ChevronDown, FlaskConical, Layers3, LineChart } from 'lucide-react'

export type ModuleId = 'overview' | 'intelligence' | 'foundations' | 'bayesian' | 'stochastic' | 'options'

const modules: { id: ModuleId; label: string; icon: typeof LineChart; tag?: string }[] = [
  { id: 'overview', label: 'Overview', icon: Layers3 },
  { id: 'intelligence', label: 'Research Intelligence', icon: Brain, tag: 'CORE' },
  { id: 'foundations', label: 'Financial Foundations', icon: BookOpen },
  { id: 'bayesian', label: 'Bayesian Engine', icon: Atom, tag: '01' },
  { id: 'stochastic', label: 'Stochastic Simulator', icon: Activity, tag: '02' },
  { id: 'options', label: 'Options Lab', icon: FlaskConical, tag: '03' },
]

export default function Sidebar({ active, onSelect }: { active: ModuleId; onSelect: (id: ModuleId) => void }) {
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark"><LineChart size={18} strokeWidth={2.4}/></div><div><b>AM<span>QUANT</span></b><small>RESEARCH TERMINAL</small></div></div>
    <div className="workspace"><div className="workspace-icon">AQ</div><div className="workspace-copy"><span>Research Desk</span><small>Quantitative Workspace</small></div><ChevronDown size={14}/></div>
    <div className="side-label">WORKSPACE</div>
    <nav aria-label="Research modules">{modules.map(({ id, label, icon: Icon, tag }) => <button key={id} className={`nav-item ${active === id ? 'active' : ''}`} onClick={() => onSelect(id)}><Icon size={16}/><span>{label}</span>{tag && <i>{tag}</i>}</button>)}</nav>
    <div className="sidebar-bottom"><div className="plan-card"><div className="plan-top"><span>TOOLKIT STATUS</span><span>5 / 5 READY</span></div><div className="progress"><i style={{ width: '100%' }}/></div><p>Professional Quantitative Research Platform.</p><button onClick={() => onSelect('intelligence')}>Launch Intelligence <span>↗</span></button></div><div className="profile"><div className="avatar">AQ</div><div><b>AMQUANT Terminal</b><small>Research Edition</small></div></div></div>
  </aside>
}
