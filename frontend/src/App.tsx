import { useEffect, useState } from 'react'
import { Bell, ChevronDown, CircleHelp, LogIn, LogOut, Search, User } from 'lucide-react'
import Dashboard from './components/Dashboard'
import Sidebar, { type ModuleId } from './components/Sidebar'
import AuthModal from './components/AuthModal'
import { AuthProvider, useAuth } from './context/AuthContext'
import { checkApiHealth } from './lib/api'
import FinancialFoundations from './modules/FinancialFoundations'
import BayesianEngine from './modules/BayesianEngine'
import StochasticSimulator from './modules/StochasticSimulator'
import OptionsLab from './modules/OptionsLab'
import ResearchIntelligence from './modules/ResearchIntelligence'
import PersonalWorkspace from './modules/PersonalWorkspace'

const moduleInfo: Record<Exclude<ModuleId, 'overview'>, { eyebrow: string; title: string; description: string }> = {
  intelligence: { eyebrow: 'CORE · WORKFLOW SYNTHESIS', title: 'Research Intelligence', description: 'Unified workflow connecting Bayesian inference, simulations, and valuation.' },
  foundations: { eyebrow: 'MODULE 01 · LEARNING PATH', title: 'Financial Foundations', description: 'Explore option payoffs, binomial pricing, and hedging.' },
  bayesian: { eyebrow: 'MODULE 02 · INFERENCE', title: 'Bayesian Engine', description: 'Update probability distributions as new evidence arrives.' },
  stochastic: { eyebrow: 'MODULE 03 · SIMULATION', title: 'Stochastic Simulator', description: 'Explore random processes and uncertainty over time.' },
  options: { eyebrow: 'MODULE 04 · DERIVATIVES', title: 'Options Lab', description: 'Study model prices, sensitivities, and risk measures.' },
  workspace: { eyebrow: 'WORKSPACE · PERSONAL DESK', title: 'Personal Workspace', description: 'Saved scenarios and research calculation history.' },
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
      <AuthModal />
    </AuthProvider>
  )
}

function AppContent() {
  const { user, profile, openAuthModal, signOut } = useAuth()
  const [active, setActive] = useState<ModuleId>('overview')
  const [apiOnline, setApiOnline] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showNotifications, setShowNotifications] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [preloadedScenario, setPreloadedScenario] = useState<{ moduleId: ModuleId; data: Record<string, any> } | null>(null)

  useEffect(() => {
    let mounted = true
    const ping = () => {
      void checkApiHealth().then(status => {
        if (mounted) setApiOnline(status)
      })
    }
    ping()
    const interval = setInterval(ping, 5000)
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setShowSearch(prev => !prev)
        setSearchQuery('')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      mounted = false
      clearInterval(interval)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  const handleOpenScenario = (moduleId: ModuleId, scenarioData: Record<string, any>) => {
    setPreloadedScenario({ moduleId, data: scenarioData })
    setActive(moduleId)
  }

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'AQ'
  const displayName = profile?.display_name || user?.email?.split('@')[0] || 'Guest'

  return <div className="app-shell">
    <Sidebar active={active} onSelect={setActive}/>
    <main className="main-area"><header className="topbar"><div className="breadcrumbs"><span>Research desk</span><span className="slash">/</span><b>{active === 'overview' ? 'Overview' : moduleInfo[active].title}</b></div><div className="top-actions">
      {showSearch && <input className="search-input" autoFocus value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder="Search modules…" aria-label="Search modules"/>}
      <button className="top-action" onClick={() => { setShowSearch(!showSearch); setSearchQuery('') }} aria-label="Search"><Search size={16}/><span>Search</span><kbd>⌘ K</kbd></button>
      <span className="top-divider"/>
      <button className={`top-action icon-top ${showNotifications ? 'chosen' : ''}`} aria-label="Notifications" onClick={() => setShowNotifications(!showNotifications)}><Bell size={17}/><i className="notification-dot"/></button>
      <span className="help-button"><CircleHelp size={16}/><span>Help</span></span>
      <span className="top-divider"/>

      {user ? (
        <div className="user-menu-wrapper" style={{ position: 'relative' }}>
          <button
            className="top-action user-pill-btn"
            onClick={() => setShowUserMenu(!showUserMenu)}
            aria-label="User account menu"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
          >
            <div className="top-avatar" style={{ margin: 0 }}>{initials}</div>
            <span style={{ fontSize: '12px', fontWeight: 600 }}>{displayName}</span>
            <ChevronDown size={13} className="avatar-chevron"/>
          </button>
          {showUserMenu && (
            <div className="user-popover panel" style={{ position: 'absolute', right: 0, top: '100%', marginTop: '6px', width: '220px', padding: '8px', zIndex: 50 }}>
              <div style={{ padding: '6px 8px', borderBottom: '1px solid #1f2937', marginBottom: '6px' }}>
                <b style={{ display: 'block', fontSize: '13px' }}>{displayName}</b>
                <small style={{ color: '#8d9aa8', fontSize: '11px', wordBreak: 'break-all' }}>{user.email}</small>
              </div>
              <button
                className="user-menu-item"
                onClick={() => { setActive('workspace'); setShowUserMenu(false) }}
                style={{ width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 8px', background: 'transparent', border: 'none', color: '#e5eaf0', cursor: 'pointer', borderRadius: '4px', fontSize: '12px' }}
              >
                <User size={14} />
                <span>Personal Workspace</span>
              </button>
              <button
                className="user-menu-item"
                onClick={() => { void signOut(); setShowUserMenu(false) }}
                style={{ width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 8px', background: 'transparent', border: 'none', color: '#f43f5e', cursor: 'pointer', borderRadius: '4px', fontSize: '12px' }}
              >
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button className="top-action signin-btn" onClick={() => openAuthModal('login')} style={{ fontSize: '12px', fontWeight: 600, color: '#3ed7a8' }}>
            <LogIn size={14} />
            <span>Sign In</span>
          </button>
          <button className="primary-button" onClick={() => openAuthModal('register')} style={{ padding: '5px 12px', fontSize: '11px', height: '28px' }}>
            Register
          </button>
        </div>
      )}
    </div>{showSearch && <div className="search-results">{Object.entries(moduleInfo).filter(([, info]) => !searchQuery || info.title.toLowerCase().includes(searchQuery.toLowerCase()) || info.description.toLowerCase().includes(searchQuery.toLowerCase())).map(([id, info]) => <button key={id} onClick={() => { setActive(id as ModuleId); setShowSearch(false); setSearchQuery('') }}><span>{info.title}</span><small>{info.eyebrow}</small></button>)}</div>}{showNotifications && <div className="notification-popover"><b>You're all caught up</b><p>Research notes and module updates will appear here.</p></div>}</header>
      <div className="page-content">{active === 'overview' ? <Dashboard onNavigate={setActive}/> : active === 'workspace' ? <PersonalWorkspace onOpenScenario={handleOpenScenario} onNavigate={setActive} /> : <ModuleWorkspace id={active} preloadedData={preloadedScenario?.moduleId === active ? preloadedScenario.data : undefined}/>}</div>
      <div className={`connection-status ${apiOnline ? 'online' : ''}`}><i/>{apiOnline ? 'API CONNECTED' : 'LOCAL PREVIEW'} <span>·</span> {apiOnline ? 'Research engine ready' : 'Start the API for calculations'}</div>
    </main>
  </div>
}

function ModuleWorkspace({ id, preloadedData }: { id: Exclude<ModuleId, 'overview' | 'workspace'>; preloadedData?: Record<string, any> }) {
  switch (id) {
    case 'intelligence': return <ResearchIntelligence initialData={preloadedData}/>
    case 'foundations': return <FinancialFoundations initialData={preloadedData}/>
    case 'bayesian': return <BayesianEngine initialData={preloadedData}/>
    case 'stochastic': return <StochasticSimulator initialData={preloadedData}/>
    case 'options': return <OptionsLab initialData={preloadedData}/>
  }
}
