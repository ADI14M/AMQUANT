import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Atom,
  BarChart3,
  Bookmark,
  ChevronDown,
  Clock,
  Compass,
  Database,
  Globe2,
  HardDrive,
  Layers3,
  Lock,
  Percent,
  Search,
  Shield,
  ShieldCheck,
  Sliders,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useAccess } from '../context/AccessContext'
import AdminModal from './AdminModal'

export type IndiaSectionId =
  | 'overview'
  | 'instruments'
  | 'data'
  | 'backtest-daily'
  | 'backtest-intraday'
  | 'futures'
  | 'options'
  | 'regimes'
  | 'risk'
  | 'storage'
  | 'workspace'
  | 'settings'

interface NavGroup {
  groupLabel: string
  items: {
    id: IndiaSectionId
    label: string
    icon: any
    tag?: string
    tagTone?: 'orange' | 'emerald' | 'sky' | 'purple' | 'amber'
  }[]
}

const navGroups: NavGroup[] = [
  {
    groupLabel: 'MARKET FOUNDATION',
    items: [
      { id: 'overview', label: 'Market Overview', icon: Compass, tag: 'LIVE', tagTone: 'emerald' },
      { id: 'instruments', label: 'Instruments', icon: Search },
      { id: 'data', label: 'Market Data Manager', icon: Database, tag: 'PARQUET', tagTone: 'sky' },
    ],
  },
  {
    groupLabel: 'BACKTESTING ENGINES',
    items: [
      { id: 'backtest-daily', label: 'Daily Equity Backtest', icon: BarChart3, tag: 'PHASE 3', tagTone: 'orange' },
      { id: 'backtest-intraday', label: 'Intraday Backtesting', icon: Clock, tag: '1m-60m', tagTone: 'orange' },
      { id: 'futures', label: 'Futures Lab', icon: Layers3, tag: 'MTM', tagTone: 'amber' },
      { id: 'options', label: 'Options Lab & Payoff', icon: Percent, tag: '11 STRATS', tagTone: 'purple' },
    ],
  },
  {
    groupLabel: 'QUANTITATIVE ANALYTICS',
    items: [
      { id: 'regimes', label: 'Bayesian Regimes', icon: Atom, tag: '3-STATE', tagTone: 'sky' },
      { id: 'risk', label: 'Risk Management', icon: ShieldCheck, tag: 'LIMITS', tagTone: 'emerald' },
      { id: 'storage', label: 'Storage & Coverage', icon: HardDrive, tag: 'DUCKDB', tagTone: 'purple' },
    ],
  },
  {
    groupLabel: 'USER DESK',
    items: [
      { id: 'workspace', label: 'Personal Workspace', icon: Bookmark, tag: 'SAVED', tagTone: 'amber' },
      { id: 'settings', label: 'Platform Settings', icon: Sliders },
    ],
  },
]

export default function IndiaSidebar({
  active,
  onSelect,
}: {
  active: IndiaSectionId
  onSelect: (id: IndiaSectionId) => void
}) {
  const navigate = useNavigate()
  const { user, profile, openAuthModal } = useAuth()
  const { lock } = useAccess()
  const [adminOpen, setAdminOpen] = useState(false)
  const isOwner = user?.email?.toLowerCase() === 'adi@amquant.in'

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : 'IN'
  const displayName = profile?.display_name || user?.email?.split('@')[0] || 'Indian Markets Desk'

  return (
    <aside className="sidebar" style={{ background: '#0b1016', borderRight: '1px solid #1c2734' }}>
      {/* Brand & Home Navigation */}
      <div className="brand" style={{ cursor: 'pointer' }} onClick={() => navigate('/')}>
        <div
          className="brand-mark"
          style={{ background: '#2a1708', borderColor: '#59300e', color: '#f97316' }}
        >
          <Compass size={18} strokeWidth={2.4} />
        </div>
        <div>
          <b style={{ color: '#f8fafc' }}>
            AM<span style={{ color: '#f97316' }}>QUANT</span> <span style={{ color: '#fb923c', fontSize: '11px', letterSpacing: '1px' }}>INDIA</span>
          </b>
          <small style={{ color: '#8d9aa8' }}>NSE · BSE · DERIVATIVES</small>
        </div>
      </div>

      {/* Switch to Global Platform Pill */}
      <div style={{ padding: '0 8px 14px' }}>
        <button
          onClick={() => navigate('/global')}
          className="w-full py-1.5 px-2.5 rounded-lg bg-[#0e1724] hover:bg-[#132032] border border-[#1d314a] text-[#38bdf8] text-[11px] font-semibold flex items-center justify-between transition-colors shadow-sm cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Globe2 size={13} className="text-[#38bdf8]" />
            <span>Global Markets</span>
          </span>
          <span className="text-[10px] text-[#7dd3fc] font-mono">Switch ↗</span>
        </button>
      </div>

      {/* User Workspace Pill */}
      <div
        className="workspace"
        onClick={() => onSelect('workspace')}
        role="button"
        tabIndex={0}
        style={{ cursor: 'pointer', background: '#0e1520', borderColor: '#1f2c3d', marginBottom: '16px' }}
      >
        <div className="workspace-icon" style={{ background: '#352110', color: '#fb923c' }}>
          {initials}
        </div>
        <div className="workspace-copy">
          <span style={{ color: '#e2e8f0' }}>{displayName}</span>
          <small style={{ color: '#8d9aa8' }}>{user ? 'Verified Account' : 'Guest Trading Mode'}</small>
        </div>
        <ChevronDown size={14} />
      </div>

      {/* Grouped 12 Section Navigation */}
      <div style={{ flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
        {navGroups.map(group => (
          <div key={group.groupLabel} style={{ marginBottom: '14px' }}>
            <div
              className="side-label"
              style={{ fontSize: '9px', letterSpacing: '1.2px', color: '#64748b', marginBottom: '4px', paddingLeft: '8px' }}
            >
              {group.groupLabel}
            </div>
            <nav aria-label={group.groupLabel}>
              {group.items.map(({ id, label, icon: Icon, tag, tagTone }) => {
                const isActive = active === id
                const badgeColor =
                  tagTone === 'orange'
                    ? '#f97316'
                    : tagTone === 'emerald'
                    ? '#10b981'
                    : tagTone === 'sky'
                    ? '#38bdf8'
                    : tagTone === 'purple'
                    ? '#a855f7'
                    : '#eab308'

                return (
                  <button
                    key={id}
                    className={`nav-item ${isActive ? 'active' : ''}`}
                    onClick={() => onSelect(id)}
                    style={{
                      height: '32px',
                      padding: '0 8px',
                      marginBottom: '2px',
                      fontSize: '11px',
                    }}
                  >
                    <Icon size={14} />
                    <span style={{ fontSize: '11.5px' }}>{label}</span>
                    {tag && (
                      <i
                        style={{
                          fontSize: '8px',
                          color: badgeColor,
                          background: `${badgeColor}15`,
                          borderColor: `${badgeColor}35`,
                        }}
                      >
                        {tag}
                      </i>
                    )}
                  </button>
                )
              })}
            </nav>
          </div>
        ))}
      </div>

      {/* Bottom Status / Mode Pill */}
      <div className="sidebar-bottom" style={{ paddingTop: '8px' }}>
        <div
          className="plan-card"
          style={{
            background: 'linear-gradient(135deg, #18120c 0%, #0d1218 100%)',
            border: '1px solid #332012',
            padding: '10px 12px',
            marginBottom: '8px',
          }}
        >
          <div className="plan-top" style={{ marginBottom: '4px' }}>
            <span style={{ color: '#fb923c', fontSize: '9px', fontWeight: 700 }}>INDIA 5.0 DEPLOYED</span>
            <span style={{ color: '#10b981', fontSize: '9px' }}>£0/MO VERIFIED</span>
          </div>
          <div className="progress" style={{ height: '3px', background: '#251b14', marginBottom: '6px' }}>
            <i style={{ width: '100%', background: '#f97316' }} />
          </div>
          <p style={{ fontSize: '10px', color: '#94a3b8', margin: 0 }}>
            Strict Zero Lookahead · Real Contracts · MIS Square-off
          </p>
        </div>

        <div
          className="profile"
          onClick={() => (user ? onSelect('workspace') : openAuthModal('login'))}
          role="button"
          tabIndex={0}
          style={{ cursor: 'pointer', height: '40px' }}
        >
          <div className="profile-badge" style={{ background: '#2a1708', color: '#f97316' }}>
            <Compass size={13} />
          </div>
          <div className="profile-meta">
            <b style={{ color: '#f1f5f9' }}>AMQUANT INDIA</b>
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
