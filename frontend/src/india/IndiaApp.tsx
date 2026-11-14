import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  ChevronDown,
  Globe2,
  Home,
  LogIn,
  LogOut,
} from 'lucide-react'
import IndiaSidebar, { type IndiaSectionId } from '../components/IndiaSidebar'
import { useAuth } from '../context/AuthContext'
import { checkApiHealth, getIndiaMarketOverview, type IndiaMarketOverview } from '../lib/api'
import AmquantIndia from '../modules/AmquantIndia'
import Footer from '../components/Footer'

const sectionTitles: Record<IndiaSectionId, { title: string; subtitle: string }> = {
  overview: { title: 'Market Overview & Macro', subtitle: 'NSE & BSE benchmark performance, macro indicators and market breadth.' },
  instruments: { title: 'Instrument Universe', subtitle: 'Search and filter active equities, sectoral indices and F&O instruments.' },
  data: { title: 'Market Data Manager', subtitle: 'Historical Parquet & DuckDB datasets, corporate actions and provenance.' },
  'backtest-daily': { title: 'Daily Equity Backtesting', subtitle: 'Professional chronological multi-strategy backtesting with statutory Indian costs.' },
  'backtest-intraday': { title: 'Intraday Backtesting', subtitle: '1m to 60m candle strategies with strict zero lookahead and 15:15 IST square-off.' },
  futures: { title: 'Futures Lab & Rollover', subtitle: 'Real monthly contract cycles, SEBI point-in-time lots, daily MTM and spread accounting.' },
  options: { title: 'Options Lab & Payoff', subtitle: '11 multi-leg option strategies, 121-pt payoff diagrams, net Greeks and margin relief.' },
  regimes: { title: 'Bayesian Regimes', subtitle: '3-state regime classification, probability transitions and persistence metrics.' },
  risk: { title: 'Risk Management', subtitle: 'Pre-trade risk limits, margin caps, position sizing rules and circuit breakers.' },
  storage: { title: 'Storage & Coverage', subtitle: 'Audited Parquet storage breakdown, DuckDB analytical engine and provenance.' },
  workspace: { title: 'Indian Trading Workspace', subtitle: 'Saved backtest scenarios, custom parameter sets and exportable trade logs.' },
  settings: { title: 'Platform Settings', subtitle: 'Execution parameters, statutory tax schedules and broker safety controls.' },
}

export default function IndiaApp() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, profile, openAuthModal, signOut } = useAuth()

  // Derive active section from URL (e.g., /india/backtest-intraday -> backtest-intraday)
  const pathParts = location.pathname.replace(/^\/india\/?/, '').split('/')
  const rawSection = pathParts[0] as IndiaSectionId

  const validSections: IndiaSectionId[] = [
    'overview',
    'instruments',
    'data',
    'backtest-daily',
    'backtest-intraday',
    'futures',
    'options',
    'regimes',
    'risk',
    'storage',
    'workspace',
    'settings',
  ]

  const [activeSection, setActiveSection] = useState<IndiaSectionId>(
    validSections.includes(rawSection) ? rawSection : 'overview'
  )
  const [apiOnline, setApiOnline] = useState<boolean>(false)
  const [overviewData, setOverviewData] = useState<IndiaMarketOverview | null>(null)
  const [showUserMenu, setShowUserMenu] = useState<boolean>(false)

  // Sync state with URL path
  useEffect(() => {
    const raw = location.pathname.replace(/^\/india\/?/, '').split('/')[0] as IndiaSectionId
    if (raw && validSections.includes(raw)) {
      setActiveSection(raw)
    } else if (!raw || (raw as string) === '') {
      setActiveSection('overview')
    }
  }, [location.pathname])

  const handleSelectSection = (sec: IndiaSectionId) => {
    setActiveSection(sec)
    if (sec === 'overview') {
      navigate('/india')
    } else {
      navigate(`/india/${sec}`)
    }
  }

  // Initial checks and live market data
  useEffect(() => {
    let mounted = true
    const ping = () => {
      void checkApiHealth().then(s => {
        if (mounted) setApiOnline(s)
      })
    }
    ping()
    const intv = setInterval(ping, 5000)

    void getIndiaMarketOverview()
      .then(d => {
        if (mounted) setOverviewData(d)
      })
      .catch(e => console.error('Could not fetch India overview:', e))

    return () => {
      mounted = false
      clearInterval(intv)
    }
  }, [])

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'IN'
  const displayName = profile?.display_name || user?.email?.split('@')[0] || 'Trader'

  // Headline tickers
  const niftyQuote = overviewData?.headline_quotes?.find(q => q.symbol === 'NIFTY 50')
  const sensexQuote = overviewData?.headline_quotes?.find(q => q.symbol === 'SENSEX')
  const repoRate = overviewData?.macro_snapshot?.rbi_repo_rate ?? 6.5

  return (
    <div className="app-shell" style={{ background: '#070b10' }}>
      <IndiaSidebar active={activeSection} onSelect={handleSelectSection} />
      <main className="main-area" style={{ background: '#070b10' }}>
        {/* Dedicated India Topbar */}
        <header className="topbar" style={{ background: '#0b1016', borderBottom: '1px solid #1c2734' }}>
          <div className="breadcrumbs">
            <span
              onClick={() => navigate('/')}
              style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
            >
              <Home size={12} /> AMQUANT
            </span>
            <span className="slash">/</span>
            <span
              onClick={() => handleSelectSection('overview')}
              style={{ cursor: 'pointer', color: '#f97316', fontWeight: 600 }}
            >
              AMQUANT INDIA
            </span>
            <span className="slash">/</span>
            <b style={{ color: '#f8fafc' }}>{sectionTitles[activeSection]?.title || 'Overview'}</b>
          </div>

          <div className="top-actions">
            {/* Live Ticker Chips */}
            {niftyQuote && (
              <div
                className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded bg-[#0e1622] border border-[#1d2a3a] text-[11px] font-mono"
              >
                <span className="text-[#94a3b8] font-bold">NIFTY 50:</span>
                <span className="text-[#f8fafc] font-semibold">₹{niftyQuote.price.toLocaleString('en-IN')}</span>
                <span className={niftyQuote.change >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}>
                  {niftyQuote.change >= 0 ? '+' : ''}{niftyQuote.change_pct.toFixed(2)}%
                </span>
              </div>
            )}

            {sensexQuote && (
              <div
                className="hidden xl:flex items-center gap-2 px-2.5 py-1 rounded bg-[#0e1622] border border-[#1d2a3a] text-[11px] font-mono"
              >
                <span className="text-[#94a3b8] font-bold">SENSEX:</span>
                <span className="text-[#f8fafc] font-semibold">₹{sensexQuote.price.toLocaleString('en-IN')}</span>
                <span className={sensexQuote.change >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}>
                  {sensexQuote.change >= 0 ? '+' : ''}{sensexQuote.change_pct.toFixed(2)}%
                </span>
              </div>
            )}

            <div
              className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded bg-[#0e1622] border border-[#1d2a3a] text-[11px] font-mono text-[#fb923c]"
            >
              <span>RBI REPO:</span>
              <span className="font-bold">{repoRate.toFixed(2)}%</span>
            </div>

            <span className="top-divider" />

            {/* Quick Switch to Global */}
            <button
              onClick={() => navigate('/global')}
              className="top-action"
              style={{ borderColor: '#16314d', background: '#0b1928', color: '#38bdf8' }}
              title="Switch to Global Markets Platform"
            >
              <Globe2 size={14} className="text-[#38bdf8]" />
              <span className="hidden sm:inline">Global Markets</span>
            </button>

            <span className="top-divider" />

            {/* User Desk / Sign In */}
            {user ? (
              <div className="user-menu-wrapper" style={{ position: 'relative' }}>
                <button
                  className="top-action user-pill-btn"
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  aria-label="User account menu"
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', background: '#131b26' }}
                >
                  <div className="top-avatar" style={{ margin: 0, background: '#2a1a0c', color: '#f97316' }}>
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
                      background: '#0d131c',
                      borderColor: '#1d2a3a',
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
                        handleSelectSection('workspace')
                      }}
                      className="text-button"
                      style={{ width: '100%', textAlign: 'left', padding: '6px 8px' }}
                    >
                      Indian Workspace
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
                  style={{ background: '#251508', borderColor: '#4d2a10', color: '#fb923c', fontWeight: 600 }}
                >
                  <LogIn size={15} />
                  <span>Sign In</span>
                </button>
                <button
                  className="primary-button"
                  onClick={() => openAuthModal('register')}
                  style={{ padding: '5px 12px', fontSize: '11px', height: '28px', background: '#ea580c', borderColor: '#c2410c' }}
                >
                  Register
                </button>
              </div>
            )}

            <span className={`status-pill ${apiOnline ? 'online' : 'offline'}`}>
              <i />
              {apiOnline ? 'NSE Online' : 'Connecting'}
            </span>
          </div>
        </header>

        {/* Content Area rendering AmquantIndia */}
        <div className="content-scroll" style={{ background: '#070b10' }}>
          <AmquantIndia
            activeSection={activeSection}
            onSelectSection={handleSelectSection}
            hideSubtabBar={true}
          />
          <Footer variant="india" className="mt-8" />
        </div>
      </main>
    </div>
  )
}
