import { Activity, Atom, Bookmark, BookOpen, Brain, ChevronDown, FlaskConical, Layers3, LineChart, LogIn } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export type ModuleId = 'overview' | 'intelligence' | 'foundations' | 'bayesian' | 'stochastic' | 'options' | 'workspace'

const modules: { id: ModuleId; label: string; icon: typeof LineChart; tag?: string }[] = [
  { id: 'overview', label: 'Overview', icon: Layers3 },
  { id: 'intelligence', label: 'Research Intelligence', icon: Brain, tag: 'CORE' },
  { id: 'foundations', label: 'Financial Foundations', icon: BookOpen },
  { id: 'bayesian', label: 'Bayesian Engine', icon: Atom, tag: '01' },
  { id: 'stochastic', label: 'Stochastic Simulator', icon: Activity, tag: '02' },
  { id: 'options', label: 'Options Lab', icon: FlaskConical, tag: '03' },
  { id: 'workspace', label: 'Personal Workspace', icon: Bookmark, tag: 'SAVED' },
]

export default function Sidebar({ active, onSelect }: { active: ModuleId; onSelect: (id: ModuleId) => void }) {
  const { user, profile, openAuthModal } = useAuth()

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : 'AQ'
  const displayName = profile?.display_name || user?.email?.split('@')[0] || 'Guest Researcher'

  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark"><LineChart size={18} strokeWidth={2.4}/></div><div><b>AM<span>QUANT</span></b><small>RESEARCH TERMINAL</small></div></div>
    <div className="workspace" onClick={() => onSelect('workspace')} role="button" tabIndex={0} style={{ cursor: 'pointer' }}>
      <div className="workspace-icon">{initials}</div>
      <div className="workspace-copy">
        <span>{displayName}</span>
        <small>{user ? 'Personal Desk' : 'Guest Desk (Click to sign in)'}</small>
      </div>
      <ChevronDown size={14}/>
    </div>
    <div className="side-label">WORKSPACE</div>
    <nav aria-label="Research modules">
      {modules.map(({ id, label, icon: Icon, tag }) => (
        <button
          key={id}
          className={`nav-item ${active === id ? 'active' : ''}`}
          onClick={() => onSelect(id)}
        >
          <Icon size={16}/>
          <span>{label}</span>
          {tag && <i>{tag}</i>}
        </button>
      ))}
    </nav>
    <div className="sidebar-bottom">
      <div className="plan-card">
        <div className="plan-top">
          <span>TOOLKIT STATUS</span>
          <span>5 / 5 READY</span>
        </div>
        <div className="progress"><i style={{ width: '100%' }}/></div>
        <p>Professional Quantitative Research Platform.</p>
        <button onClick={() => onSelect('intelligence')}>Launch Intelligence <span>↗</span></button>
      </div>

      <div className="profile" onClick={() => (user ? onSelect('workspace') : openAuthModal('login'))} role="button" tabIndex={0} style={{ cursor: 'pointer' }}>
        <div className="avatar">{initials}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <b style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>{displayName}</b>
          <small>{user ? 'Authenticated · Supabase' : 'Sign in or register'}</small>
        </div>
        {!user && <LogIn size={13} style={{ color: '#8d9aa8' }} />}
      </div>
    </div>
  </aside>
}
