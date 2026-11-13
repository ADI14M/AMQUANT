import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  Atom,
  Bookmark,
  BookOpen,
  Brain,
  ChevronDown,
  Compass,
  FlaskConical,
  Globe2,
  Layers3,
  LineChart,
  Lock,
  Shield,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useAccess } from '../context/AccessContext'
import AdminModal from './AdminModal'

export type ModuleId =
  | 'overview'
  | 'intelligence'
  | 'foundations'
  | 'bayesian'
  | 'stochastic'
  | 'options'
  | 'workspace'

const modules: { id: ModuleId; label: string; icon: typeof LineChart; tag?: string }[] = [
  { id: 'overview', label: 'Overview', icon: Layers3 },
  { id: 'intelligence', label: 'Research Intelligence', icon: Brain, tag: 'CORE' },
  { id: 'foundations', label: 'Financial Foundations', icon: BookOpen },
  { id: 'bayesian', label: 'Bayesian Engine', icon: Atom, tag: '01' },
  { id: 'stochastic', label: 'Stochastic Simulator', icon: Activity, tag: '02' },
  { id: 'options', label: 'Options Lab', icon: FlaskConical, tag: '03' },
  { id: 'workspace', label: 'Personal Workspace', icon: Bookmark, tag: 'SAVED' },
]

export default function Sidebar({
  active,
  onSelect,
}: {
  active: ModuleId
  onSelect: (id: ModuleId) => void
}) {
  const navigate = useNavigate()
  const { user, profile, openAuthModal } = useAuth()
  const { lock } = useAccess()
  const [adminOpen, setAdminOpen] = useState(false)
  const isOwner = user?.email?.toLowerCase() === 'adi@amquant.in'

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : 'AQ'
  const displayName = profile?.display_name || user?.email?.split('@')[0] || 'Guest Researcher'

  return (
    <aside className="sidebar">
      {/* Brand & Market Switcher */}
      <div className="brand" style={{ cursor: 'pointer' }} onClick={() => navigate('/')}>
        <div className="brand-mark">
          <LineChart size={18} strokeWidth={2.4} />
        </div>
        <div>
          <b>
            AM<span>QUANT</span>
          </b>
          <small>GLOBAL PLATFORM</small>
        </div>
      </div>

      {/* Switch to Indian Platform Pill */}
      <div style={{ padding: '0 8px 16px' }}>
        <button
          onClick={() => navigate('/india')}
          className="w-full py-1.5 px-2.5 rounded-lg bg-[#111c19] hover:bg-[#152622] border border-[#1b3d33] text-[#34d399] text-[11px] font-semibold flex items-center justify-between transition-colors shadow-sm cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Compass size={13} className="text-[#f97316]" />
            <span>AMQUANT INDIA</span>
          </span>
          <span className="text-[10px] text-[#6ee7b7] font-mono">Switch ↗</span>
        </button>
      </div>

      {/* User Desk */}
      <div
        className="workspace"
        onClick={() => onSelect('workspace')}
        role="button"
        tabIndex={0}
        style={{ cursor: 'pointer' }}
      >
        <div className="workspace-icon">{initials}</div>
        <div className="workspace-copy">
          <span>{displayName}</span>
          <small>{user ? 'Personal Desk' : 'Guest Desk (Click to sign in)'}</small>
        </div>
        <ChevronDown size={14} />
      </div>

      <div className="side-label">GLOBAL RESEARCH MODULES</div>
      <nav aria-label="Research modules">
        {modules.map(({ id, label, icon: Icon, tag }) => (
          <button
            key={id}
            className={`nav-item ${active === id ? 'active' : ''}`}
            onClick={() => onSelect(id)}
          >
            <Icon size={16} />
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
          <div className="progress">
            <i style={{ width: '100%' }} />
          </div>
          <p>Global Quantitative Engine & Analytics.</p>
          <button onClick={() => onSelect('intelligence')}>
            Launch Intelligence <span>↗</span>
          </button>
        </div>

        <div
          className="profile"
          onClick={() => (user ? onSelect('workspace') : openAuthModal('login'))}
          role="button"
          tabIndex={0}
          style={{ cursor: 'pointer' }}
        >
          <div className="profile-badge">
            <Globe2 size={13} className="text-[#38bdf8]" />
          </div>
          <div className="profile-meta">
            <b>Global Desk</b>
            <span>{user ? user.email : 'Public Session'}</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
          {isOwner && (
            <button
              onClick={() => setAdminOpen(true)}
              style={{
                flex: 1,
                padding: '6px 8px',
                borderRadius: '6px',
                background: '#0f233a',
                border: '1px solid #1d446e',
                color: '#38bdf8',
                fontSize: '11px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px',
                cursor: 'pointer',
              }}
              title="Admin Desk (Owner Only)"
            >
              <Shield size={12} />
              <span>Admin</span>
            </button>
          )}
          <button
            onClick={() => void lock()}
            style={{
              flex: 1,
              padding: '6px 8px',
              borderRadius: '6px',
              background: '#111822',
              border: '1px solid #1f2c3d',
              color: '#94a3b8',
              fontSize: '11px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              cursor: 'pointer',
            }}
            title="Lock Platform"
          >
            <Lock size={12} />
            <span>Lock</span>
          </button>
        </div>
      </div>

      <AdminModal isOpen={adminOpen} onClose={() => setAdminOpen(false)} />
    </aside>
  )
}
