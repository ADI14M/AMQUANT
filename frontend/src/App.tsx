import { useEffect, useState } from 'react'
import { Bell, ChevronDown, CircleHelp, Search } from 'lucide-react'
import Dashboard from './components/Dashboard'
import Sidebar, { type ModuleId } from './components/Sidebar'
import { checkApiHealth } from './lib/api'
import FinancialFoundations from './modules/FinancialFoundations'
import BayesianEngine from './modules/BayesianEngine'
import StochasticSimulator from './modules/StochasticSimulator'
import OptionsLab from './modules/OptionsLab'
import ResearchIntelligence from './modules/ResearchIntelligence'

const moduleInfo: Record<Exclude<ModuleId, 'overview'>, { eyebrow: string; title: string; description: string }> = {
  intelligence: { eyebrow: 'CORE · WORKFLOW SYNTHESIS', title: 'Research Intelligence', description: 'Unified workflow connecting Bayesian inference, simulations, and valuation.' },
  foundations: { eyebrow: 'MODULE 01 · LEARNING PATH', title: 'Financial Foundations', description: 'Explore option payoffs, binomial pricing, and hedging.' },
  bayesian: { eyebrow: 'MODULE 02 · INFERENCE', title: 'Bayesian Engine', description: 'Update probability distributions as new evidence arrives.' },
  stochastic: { eyebrow: 'MODULE 03 · SIMULATION', title: 'Stochastic Simulator', description: 'Explore random processes and uncertainty over time.' },
  options: { eyebrow: 'MODULE 04 · DERIVATIVES', title: 'Options Lab', description: 'Study model prices, sensitivities, and risk measures.' },
}

export default function App() {
  const [active, setActive] = useState<ModuleId>('overview')
  const [apiOnline, setApiOnline] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showNotifications, setShowNotifications] = useState(false)
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
  return <div className="app-shell">
    <Sidebar active={active} onSelect={setActive}/>
    <main className="main-area"><header className="topbar"><div className="breadcrumbs"><span>Research desk</span><span className="slash">/</span><b>{active === 'overview' ? 'Overview' : moduleInfo[active].title}</b></div><div className="top-actions">{showSearch && <input className="search-input" autoFocus value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder="Search modules…" aria-label="Search modules"/>}<button className="top-action" onClick={() => { setShowSearch(!showSearch); setSearchQuery('') }} aria-label="Search"><Search size={16}/><span>Search</span><kbd>⌘ K</kbd></button><span className="top-divider"/><button className={`top-action icon-top ${showNotifications ? 'chosen' : ''}`} aria-label="Notifications" onClick={() => setShowNotifications(!showNotifications)}><Bell size={17}/><i className="notification-dot"/></button><span className="help-button"><CircleHelp size={16}/><span>Help</span></span><div className="top-avatar">AQ</div><ChevronDown size={13} className="avatar-chevron"/></div>{showSearch && <div className="search-results">{Object.entries(moduleInfo).filter(([, info]) => !searchQuery || info.title.toLowerCase().includes(searchQuery.toLowerCase()) || info.description.toLowerCase().includes(searchQuery.toLowerCase())).map(([id, info]) => <button key={id} onClick={() => { setActive(id as ModuleId); setShowSearch(false); setSearchQuery('') }}><span>{info.title}</span><small>{info.eyebrow}</small></button>)}</div>}{showNotifications && <div className="notification-popover"><b>You're all caught up</b><p>Research notes and module updates will appear here.</p></div>}</header>
      <div className="page-content">{active === 'overview' ? <Dashboard onNavigate={setActive}/> : <ModuleWorkspace id={active}/>}</div>
      <div className={`connection-status ${apiOnline ? 'online' : ''}`}><i/>{apiOnline ? 'API CONNECTED' : 'LOCAL PREVIEW'} <span>·</span> {apiOnline ? 'Research engine ready' : 'Start the API for calculations'}</div>
    </main>
  </div>
}

function ModuleWorkspace({ id }: { id: Exclude<ModuleId, 'overview'> }) {
  switch (id) {
    case 'intelligence': return <ResearchIntelligence/>
    case 'foundations': return <FinancialFoundations/>
    case 'bayesian': return <BayesianEngine/>
    case 'stochastic': return <StochasticSimulator/>
    case 'options': return <OptionsLab/>
  }
}
