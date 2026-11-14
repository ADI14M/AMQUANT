import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  Atom,
  BarChart3,
  BookOpen,
  Brain,
  Compass,
  Database,
  Flame,
  FlaskConical,
  Globe2,
  Layers,
  LineChart,
  Lock,
  Percent,
  Shield,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useAccess } from '../context/AccessContext'
import AdminModal from '../components/AdminModal'
import Footer from '../components/Footer'

export default function LandingPage() {
  const navigate = useNavigate()
  const { user, openAuthModal } = useAuth()
  const { lock } = useAccess()
  const [adminOpen, setAdminOpen] = useState(false)
  const isOwner = user?.email?.toLowerCase() === 'adi@amquant.in'

  return (
    <div className="landing-root min-h-screen bg-[#06090e] text-[#e2e8f0] font-sans antialiased selection:bg-[#10b981]/20 selection:text-[#10b981]">
      {/* Top Navigation */}
      <header className="border-b border-[#172230] bg-[#090d14]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#102a27] to-[#0c1824] border border-[#1d574b] flex items-center justify-center text-[#3ed7a8] shadow-sm">
              <LineChart size={18} strokeWidth={2.4} />
            </div>
            <div>
              <span className="font-extrabold text-base tracking-[0.12em] text-[#f8fafc]">
                AM<span className="text-[#94a3b8] font-medium">QUANT</span>
              </span>
              <span className="hidden sm:inline-block ml-2 px-1.5 py-0.5 text-[9px] font-mono font-semibold tracking-wider uppercase rounded bg-[#132230] text-[#7dd3fc] border border-[#1e3a5f]">
                QUANTITATIVE RESEARCH TERMINAL
              </span>
            </div>
          </div>

          <nav className="flex items-center gap-3 sm:gap-4">
            <Link
              to="/global"
              className="text-xs font-semibold text-[#94a3b8] hover:text-[#f8fafc] px-3 py-1.5 rounded-md hover:bg-[#111822] transition-colors flex items-center gap-1.5"
            >
              <Globe2 size={13} className="text-[#38bdf8]" />
              <span className="hidden md:inline">Global Platform</span>
            </Link>
            <Link
              to="/india"
              className="text-xs font-semibold text-[#94a3b8] hover:text-[#f8fafc] px-3 py-1.5 rounded-md hover:bg-[#111822] transition-colors flex items-center gap-1.5"
            >
              <Compass size={13} className="text-[#f97316]" />
              <span className="hidden md:inline">Indian Platform</span>
            </Link>

            <div className="h-4 w-[1px] bg-[#1e293b]" />

            {user ? (
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-[#94a3b8] hidden sm:inline">
                  {user.email?.split('@')[0]}
                </span>
                <Link
                  to="/india/workspace"
                  className="px-3 py-1.5 rounded-md bg-[#131d2a] hover:bg-[#1e2c3e] border border-[#233549] text-xs font-semibold text-[#f1f5f9] transition-all"
                >
                  Workspace
                </Link>
              </div>
            ) : (
              <button
                onClick={() => openAuthModal('login')}
                className="px-3.5 py-1.5 rounded-md bg-[#111a26] hover:bg-[#182535] border border-[#233549] text-xs font-semibold text-[#e2e8f0] transition-all flex items-center gap-1.5 shadow-sm"
              >
                <span>Sign In</span>
              </button>
            )}

            {isOwner && (
              <button
                onClick={() => setAdminOpen(true)}
                className="px-2.5 py-1.5 rounded-md bg-[#0f233a] hover:bg-[#16375c] border border-[#1d446e] text-xs font-semibold text-[#38bdf8] transition-all flex items-center gap-1.5 shadow-sm"
                title="Admin Desk (Owner Only)"
              >
                <Shield size={13} />
                <span className="hidden sm:inline">Admin Desk</span>
              </button>
            )}

            <button
              onClick={() => void lock()}
              className="p-1.5 sm:px-2.5 sm:py-1.5 rounded-md bg-[#131d2a] hover:bg-[#1c2a3d] border border-[#233549] text-xs font-semibold text-[#94a3b8] hover:text-[#f8fafc] transition-all flex items-center gap-1.5"
              title="Lock Platform"
            >
              <Lock size={13} />
              <span className="hidden sm:inline">Lock</span>
            </button>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-20">
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0e1724] border border-[#1e2d42] text-[11px] font-mono text-[#94a3b8] shadow-inner">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
            <span>INSTITUTIONAL QUANTITATIVE TERMINAL · 2 SEPARATE MARKET EXPERIENCES</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-[#f8fafc] leading-tight">
            AM<span className="text-[#94a3b8] font-normal">QUANT</span>
          </h1>

          <p className="text-lg sm:text-xl font-medium text-[#38bdf8] tracking-wide">
            Quantitative Intelligence. Data-Driven Decisions.
          </p>

          <p className="text-sm sm:text-base text-[#94a3b8] leading-relaxed max-w-2xl mx-auto">
            Choose your trading universe below. Model complex derivatives and stochastic processes across global asset classes, or execute rigorous zero look-ahead backtests across Indian equities, index futures, and multi-leg options.
          </p>
        </div>

        {/* Two Primary Market Selection Cards */}
        <div className="mt-12 sm:mt-16 grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-10">
          {/* Card 1: Global Markets */}
          <div className="group relative rounded-2xl bg-gradient-to-b from-[#0c131d] to-[#070b10] border border-[#1b2738] hover:border-[#38bdf8]/60 p-8 sm:p-10 transition-all duration-300 hover:shadow-2xl hover:shadow-[#38bdf8]/10 flex flex-col justify-between">
            <div className="absolute top-0 right-0 transform translate-x-2 -translate-y-2">
              <span className="px-3 py-1 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase bg-[#0d2238] text-[#38bdf8] border border-[#1d4263]">
                GLOBAL ASSET CLASSES
              </span>
            </div>

            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-[#0e2238] border border-[#1a3d61] flex items-center justify-center text-[#38bdf8] shadow-inner group-hover:scale-105 transition-transform">
                  <Globe2 size={24} strokeWidth={2} />
                </div>
                <div>
                  <h2 className="text-2xl font-bold tracking-tight text-[#f8fafc]">
                    GLOBAL MARKETS
                  </h2>
                  <span className="text-xs font-mono text-[#64748b]">AMQUANT GLOBAL PLATFORM</span>
                </div>
              </div>

              <p className="text-sm text-[#94a3b8] leading-relaxed mb-6">
                Quantitative finance, stochastic modelling, Bayesian inference and derivatives analytics across global asset classes.
              </p>

              <div className="space-y-3 mb-8">
                <div className="text-[11px] font-mono font-semibold uppercase text-[#64748b] tracking-wider">
                  Core Research Capabilities
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0a0f16] border border-[#16202c]">
                    <BookOpen size={14} className="text-[#38bdf8] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Financial Foundations</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0a0f16] border border-[#16202c]">
                    <Atom size={14} className="text-[#a78bfa] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Bayesian Engine</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0a0f16] border border-[#16202c]">
                    <Activity size={14} className="text-[#34d399] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Stochastic Simulator</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0a0f16] border border-[#16202c]">
                    <FlaskConical size={14} className="text-[#fbbf24] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Options Lab & Greeks</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0a0f16] border border-[#16202c] sm:col-span-2">
                    <Brain size={14} className="text-[#f472b6] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Research Intelligence (Synthesis)</span>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <button
                onClick={() => navigate('/global')}
                className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-[#1d4ed8] to-[#0284c7] hover:from-[#2563eb] hover:to-[#0ea5e9] text-white text-sm font-semibold tracking-wide shadow-lg shadow-[#0284c7]/20 flex items-center justify-center gap-2 group-hover:gap-3 transition-all cursor-pointer"
              >
                <span>Explore Global Markets</span>
                <ArrowRight size={16} />
              </button>
              <div className="mt-3 flex items-center justify-center gap-4 text-[11px] font-mono text-[#64748b]">
                <span>5 Core Modules</span>
                <span>•</span>
                <span>CRR & Black-Scholes</span>
                <span>•</span>
                <span>SDEs</span>
              </div>
            </div>
          </div>

          {/* Card 2: Indian Markets */}
          <div className="group relative rounded-2xl bg-gradient-to-b from-[#13110d] to-[#07070b] border border-[#33261a] hover:border-[#f97316]/60 p-8 sm:p-10 transition-all duration-300 hover:shadow-2xl hover:shadow-[#f97316]/10 flex flex-col justify-between">
            <div className="absolute top-0 right-0 transform translate-x-2 -translate-y-2">
              <span className="px-3 py-1 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase bg-[#331c0a] text-[#fb923c] border border-[#663814]">
                NSE & BSE PLATFORM
              </span>
            </div>

            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-[#2a1708] border border-[#59300e] flex items-center justify-center text-[#f97316] shadow-inner group-hover:scale-105 transition-transform">
                  <Compass size={24} strokeWidth={2} />
                </div>
                <div>
                  <h2 className="text-2xl font-bold tracking-tight text-[#f8fafc]">
                    INDIAN MARKETS
                  </h2>
                  <span className="text-xs font-mono text-[#9a6438]">AMQUANT INDIA PLATFORM</span>
                </div>
              </div>

              <p className="text-sm text-[#94a3b8] leading-relaxed mb-6">
                Indian equity markets, quantitative strategies, historical backtesting and derivatives analytics.
              </p>

              <div className="space-y-3 mb-8">
                <div className="text-[11px] font-mono font-semibold uppercase text-[#9a6438] tracking-wider">
                  Core Trading & Backtesting Capabilities
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0e0c0a] border border-[#261c14]">
                    <TrendingUp size={14} className="text-[#f97316] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">NSE & BSE Equities</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0e0c0a] border border-[#261c14]">
                    <LineChart size={14} className="text-[#38bdf8] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">NIFTY & BANKNIFTY</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0e0c0a] border border-[#261c14]">
                    <BarChart3 size={14} className="text-[#10b981] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Daily Equity Backtesting</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0e0c0a] border border-[#261c14]">
                    <Flame size={14} className="text-[#fb923c] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Intraday Strategies (1m-60m)</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0e0c0a] border border-[#261c14]">
                    <Layers size={14} className="text-[#eab308] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Futures Lab & Rollover</span>
                  </div>
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#0e0c0a] border border-[#261c14]">
                    <Percent size={14} className="text-[#ec4899] shrink-0" />
                    <span className="text-xs font-medium text-[#e2e8f0]">Options Lab (11 Strategies)</span>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <button
                onClick={() => navigate('/india')}
                className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-[#ea580c] to-[#c2410c] hover:from-[#f97316] hover:to-[#ea580c] text-white text-sm font-semibold tracking-wide shadow-lg shadow-[#ea580c]/20 flex items-center justify-center gap-2 group-hover:gap-3 transition-all cursor-pointer"
              >
                <span>Explore Indian Markets</span>
                <ArrowRight size={16} />
              </button>
              <div className="mt-3 flex items-center justify-center gap-4 text-[11px] font-mono text-[#9a6438]">
                <span>12 Indian Sections</span>
                <span>•</span>
                <span>Zero Lookahead</span>
                <span>•</span>
                <span>Statutory Taxes</span>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Highlights Grid */}
        <div className="mt-20 pt-12 border-t border-[#172230] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="p-5 rounded-xl bg-[#090d14] border border-[#16212e]">
            <div className="w-8 h-8 rounded-lg bg-[#111f2e] text-[#38bdf8] flex items-center justify-center mb-3">
              <ShieldCheck size={18} />
            </div>
            <h3 className="text-sm font-bold text-[#f1f5f9] mb-1">Zero Look-Ahead Bias</h3>
            <p className="text-xs text-[#94a3b8] leading-relaxed">
              Signals generated at candle Close are strictly executed at next candle Open with realistic slippage and conservative conflict handling.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-[#090d14] border border-[#16212e]">
            <div className="w-8 h-8 rounded-lg bg-[#1f1b13] text-[#fb923c] flex items-center justify-center mb-3">
              <Percent size={18} />
            </div>
            <h3 className="text-sm font-bold text-[#f1f5f9] mb-1">Indian Statutory Costs</h3>
            <p className="text-xs text-[#94a3b8] leading-relaxed">
              Full schedule breakdown: STT, GST, Exchange turnover charges, SEBI fees, Stamp duty, and flat ₹20 capped brokerage.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-[#090d14] border border-[#16212e]">
            <div className="w-8 h-8 rounded-lg bg-[#11241f] text-[#34d399] flex items-center justify-center mb-3">
              <Database size={18} />
            </div>
            <h3 className="text-sm font-bold text-[#f1f5f9] mb-1">Parquet & DuckDB Storage</h3>
            <p className="text-xs text-[#94a3b8] leading-relaxed">
              Audited historical Parquet partitioning with zero-copy DuckDB SQL queries. Fast analytical execution with £0 operating cost.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-[#090d14] border border-[#16212e]">
            <div className="w-8 h-8 rounded-lg bg-[#1c1429] text-[#c084fc] flex items-center justify-center mb-3">
              <Lock size={18} />
            </div>
            <h3 className="text-sm font-bold text-[#f1f5f9] mb-1">Personal Workspace</h3>
            <p className="text-xs text-[#94a3b8] leading-relaxed">
              Supabase cloud authentication with Row-Level Security (RLS). Save and resume backtests across devices with user isolation.
            </p>
          </div>
        </div>

        {/* Footer Disclaimer */}
        <div className="mt-16 text-center text-xs text-[#64748b] pt-8 space-y-2 mb-6">
          <p className="font-mono text-[11px] text-[#475569]">
            AMQUANT RESEARCH ENVIRONMENT · SIMULATION & QUANTITATIVE RESEARCH ONLY · REAL-MONEY TRADING DISABLED
          </p>
        </div>

        <Footer variant="landing" className="rounded-xl border border-[#16212e]" />
      </main>

      <AdminModal isOpen={adminOpen} onClose={() => setAdminOpen(false)} />
    </div>
  )
}
