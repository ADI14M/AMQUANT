import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Bell, ChevronDown, CircleHelp, Compass, Home, LogIn, LogOut, Search } from 'lucide-react'
import Dashboard from '../components/Dashboard'
import Sidebar, { type ModuleId } from '../components/Sidebar'
import { useAuth } from '../context/AuthContext'
import { checkApiHealth } from '../lib/api'
import FinancialFoundations from '../modules/FinancialFoundations'
import BayesianEngine from '../modules/BayesianEngine'
import StochasticSimulator from '../modules/StochasticSimulator'
import OptionsLab from '../modules/OptionsLab'
import ResearchIntelligence from '../modules/ResearchIntelligence'
import PersonalWorkspace from '../modules/PersonalWorkspace'
import Footer from '../components/Footer'

const moduleInfo: Record<Exclude<ModuleId, 'overview'>, { eyebrow: string; title: string; description: string }> = {
  intelligence: { eyebrow: 'CORE · WORKFLOW SYNTHESIS', title: 'Research Intelligence', description: 'Unified workflow connecting Bayesian inference, simulations, and valuation.' },
  foundations: { eyebrow: 'MODULE 01 · LEARNING PATH', title: 'Financial Foundations', description: 'Explore option payoffs, binomial pricing, and hedging.' },
  bayesian: { eyebrow: 'MODULE 02 · INFERENCE', title: 'Bayesian Engine', description: 'Update probability distributions as new evidence arrives.' },
  stochastic: { eyebrow: 'MODULE 03 · SIMULATION', title: 'Stochastic Simulator', description: 'Explore random processes and uncertainty over time.' },
  options: { eyebrow: 'MODULE 04 · DERIVATIVES', title: 'Options Lab', description: 'Study model prices, sensitivities, and risk measures.' },
  workspace: { eyebrow: 'WORKSPACE · PERSONAL DESK', title: 'Personal Workspace', description: 'Saved scenarios and research calculation history.' },
}

export default function GlobalApp() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, profile, openAuthModal, signOut } = useAuth()

  // Derive active module from URL path (e.g., /global/bayesian -> bayesian)
  const pathParts = location.pathname.replace(/^\/global\/?/, '').split('/')
  const initialModule = (pathParts[0] as ModuleId) || 'overview'

  const [active, setActive] = useState<ModuleId>(
    ['overview', 'intelligence', 'foundations', 'bayesian', 'stochastic', 'options', 'workspace'].includes(initialModule)
      ? initialModule
      : 'overview'
  )
  const [apiOnline, setApiOnline] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showNotifications, setShowNotifications] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [preloadedScenario, setPreloadedScenario] = useState<{ moduleId: ModuleId; data: Record<string, any> } | null>(null)

  // Sync state when URL changes
  useEffect(() => {
    const raw = location.pathname.replace(/^\/global\/?/, '').split('/')[0] as ModuleId
    if (raw && ['overview', 'intelligence', 'foundations', 'bayesian', 'stochastic', 'options', 'workspace'].includes(raw)) {
      setActive(raw)
    } else if (!raw || (raw as string) === '') {
      setActive('overview')
    }
  }, [location.pathname])

  const handleSelectModule = (id: ModuleId) => {
    setActive(id)
    if (id === 'overview') {
      navigate('/global')
    } else {
      navigate(`/global/${id}`)
    }
  }

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
    handleSelectModule(moduleId)
  }

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'AQ'
  const displayName = profile?.display_name || user?.email?.split('@')[0] || 'Guest Researcher'

  return (
    <div className="app-shell">
      <Sidebar active={active} onSelect={handleSelectModule} />
      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span
              onClick={() => navigate('/')}
              style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
            >
              <Home size={12} /> AMQUANT
            </span>
            <span className="slash">/</span>
            <span
              onClick={() => handleSelectModule('overview')}
              style={{ cursor: 'pointer', color: '#94a3b8' }}
            >
              Global Markets
            </span>
            <span className="slash">/</span>
            <b>{active === 'overview' ? 'Overview' : moduleInfo[active].title}</b>
          </div>

          <div className="top-actions">
            {/* Quick Switch to India */}
            <button
              onClick={() => navigate('/india')}
              className="top-action"
              style={{ borderColor: '#1d4838', background: '#0e1d17', color: '#34d399' }}
              title="Open AMQUANT INDIA"
            >
              <Compass size={14} className="text-[#f97316]" />
              <span className="hidden sm:inline">AMQUANT INDIA</span>
            </button>

            <span className="top-divider" />

            {showSearch && (
              <input
                className="search-input"
                autoFocus
                value={searchQuery}
                onChange={event => setSearchQuery(event.target.value)}
                placeholder="Search modules…"
                aria-label="Search modules"
              />
            )}
            <button
              className="top-action"
              onClick={() => {
                setShowSearch(!showSearch)
                setSearchQuery('')
              }}
              aria-label="Search"
            >
              <Search size={16} />
              <span>Search</span>
              <kbd>⌘ K</kbd>
            </button>
            <span className="top-divider" />
            <button
              className={`top-action icon-top ${showNotifications ? 'chosen' : ''}`}
              aria-label="Notifications"
              onClick={() => setShowNotifications(!showNotifications)}
            >
              <Bell size={17} />
              <i className="notification-dot" />
            </button>
            <span className="help-button">
              <CircleHelp size={16} />
              <span>Help</span>
            </span>
            <span className="top-divider" />

            {user ? (
              <div className="user-menu-wrapper" style={{ position: 'relative' }}>
                <button
                  className="top-action user-pill-btn"
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  aria-label="User account menu"
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
                >
                  <div className="top-avatar" style={{ margin: 0 }}>
                    {initials}
                  </div>
                  <span style={{ fontSize: '12px', fontWeight: 600 }}>{displayName}</span>
                  <ChevronDown size={13} className="avatar-chevron" />
                </button>
                {showUserMenu && (
                  <div
                    className="user-popover panel"
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: '100%',
                      marginTop: '6px',
                      width: '220px',
                      padding: '8px',
                      zIndex: 50,
                    }}
                  >
                    <div style={{ padding: '8px', borderBottom: '1px solid #1b242e', marginBottom: '6px' }}>
                      <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#f8fafc' }}>
                        {displayName}
                      </p>
                      <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8' }}>{user.email}</p>
                    </div>
                    <button
                      onClick={() => {
                        setShowUserMenu(false)
                        handleSelectModule('workspace')
                      }}
                      className="text-button"
                      style={{ width: '100%', textAlign: 'left', padding: '6px 8px' }}
                    >
                      Personal Workspace
                    </button>
                    <button
                      onClick={() => {
                        setShowUserMenu(false)
                        signOut()
                      }}
                      className="text-button"
                      style={{ width: '100%', textAlign: 'left', padding: '6px 8px', color: '#ef4444' }}
                    >
                      <LogOut size={13} style={{ marginRight: '6px', display: 'inline' }} /> Sign Out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  className="top-action"
                  onClick={() => openAuthModal('login')}
                  style={{ background: '#102a27', borderColor: '#1d574b', color: '#3ed7a8', fontWeight: 600 }}
                >
                  <LogIn size={15} />
                  <span>Sign In</span>
                </button>
                <button
                  className="primary-button"
                  onClick={() => openAuthModal('register')}
                  style={{ padding: '5px 12px', fontSize: '11px', height: '28px' }}
                >
                  Register
                </button>
              </div>
            )}

            <span className={`status-pill ${apiOnline ? 'online' : 'offline'}`}>
              <i />
              {apiOnline ? 'Engine Online' : 'Connecting'}
            </span>
          </div>
        </header>

        {showSearch && (
          <div className="search-backdrop" onClick={() => setShowSearch(false)}>
            <div className="search-palette" onClick={e => e.stopPropagation()}>
              <div className="palette-input-row">
                <Search size={18} />
                <input
                  autoFocus
                  placeholder="Type to search research modules…"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </div>
              <div className="palette-results">
                {(['foundations', 'bayesian', 'stochastic', 'options', 'intelligence', 'workspace'] as ModuleId[])
                  .filter(m => moduleInfo[m as Exclude<ModuleId, 'overview'>]?.title.toLowerCase().includes(searchQuery.toLowerCase()))
                  .map(m => (
                    <button
                      key={m}
                      className="palette-item"
                      onClick={() => {
                        handleSelectModule(m)
                        setShowSearch(false)
                      }}
                    >
                      <span>{moduleInfo[m as Exclude<ModuleId, 'overview'>]?.title}</span>
                      <small>{moduleInfo[m as Exclude<ModuleId, 'overview'>]?.eyebrow}</small>
                    </button>
                  ))}
              </div>
            </div>
          </div>
        )}

        <div className="content-scroll">
          {active === 'overview' && (
            <Dashboard
              onNavigate={id => {
                handleSelectModule(id as ModuleId)
              }}
            />
          )}
          {active === 'foundations' && (
            <FinancialFoundations initialData={preloadedScenario?.moduleId === 'foundations' ? preloadedScenario.data : undefined} />
          )}
          {active === 'bayesian' && (
            <BayesianEngine initialData={preloadedScenario?.moduleId === 'bayesian' ? preloadedScenario.data : undefined} />
          )}
          {active === 'stochastic' && (
            <StochasticSimulator initialData={preloadedScenario?.moduleId === 'stochastic' ? preloadedScenario.data : undefined} />
          )}
          {active === 'options' && (
            <OptionsLab initialData={preloadedScenario?.moduleId === 'options' ? preloadedScenario.data : undefined} />
          )}
          {active === 'intelligence' && (
            <ResearchIntelligence initialData={preloadedScenario?.moduleId === 'intelligence' ? preloadedScenario.data : undefined} />
          )}
          {active === 'workspace' && (
            <PersonalWorkspace
              onOpenScenario={(mod, data) => handleOpenScenario(mod as ModuleId, data)}
              onNavigate={handleSelectModule}
            />
          )}
          <Footer variant="global" className="mt-8" />
        </div>
      </main>
    </div>
  )
}
