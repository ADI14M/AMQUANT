import { useState, type FormEvent, type ReactNode } from 'react'
import { AlertCircle, Clock, Eye, EyeOff, KeyRound, Lock } from 'lucide-react'
import { useAccess } from '../context/AccessContext'

export default function PasswordGate({ children }: { children: ReactNode }) {
  const { isUnlocked, loading, error, rateLimitedSeconds, unlock, clearError } = useAccess()
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Initial loading state while verifying existing session
  if (loading) {
    return (
      <div className="min-h-screen bg-[#080b11] text-[#94a3b8] flex flex-col items-center justify-center p-4">
        <div className="w-10 h-10 border-2 border-[#1e293b] border-t-[#38bdf8] rounded-full animate-spin mb-4" />
        <span className="text-xs font-mono tracking-widest uppercase">Verifying Authorization…</span>
      </div>
    )
  }

  // If already unlocked, render the protected application children
  if (isUnlocked) {
    return <>{children}</>
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!password.trim() || submitting || rateLimitedSeconds !== null) return

    setSubmitting(true)
    clearError()
    await unlock(password.trim())
    setSubmitting(false)
  }

  const isLockedOut = rateLimitedSeconds !== null && rateLimitedSeconds > 0

  return (
    <div className="min-h-screen bg-[#080b11] text-[#f8fafc] flex flex-col justify-between p-4 sm:p-6 lg:p-8 font-sans selection:bg-[#38bdf8]/30">
      {/* Top minimal header */}
      <header className="max-w-6xl w-full mx-auto flex items-center justify-between py-2">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#0e1724] border border-[#1d314a] flex items-center justify-center text-[#38bdf8] shadow-inner">
            <Lock size={14} strokeWidth={2.4} />
          </div>
          <span className="font-extrabold tracking-tight text-sm text-[#f8fafc]">
            AM<span className="text-[#38bdf8]">QUANT</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold tracking-wider uppercase bg-[#111a26] text-[#94a3b8] border border-[#1e2d40]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] animate-pulse" />
            PRIVATE BETA
          </span>
        </div>
      </header>

      {/* Main Center Card */}
      <main className="max-w-md w-full mx-auto my-auto py-10">
        <div className="relative rounded-2xl bg-gradient-to-b from-[#0e1622] to-[#0a0f16] border border-[#1c293a] p-8 sm:p-10 shadow-2xl shadow-black/60">
          {/* Subtle top glow bar */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-[2px] bg-gradient-to-r from-transparent via-[#38bdf8] to-transparent" />

          {/* Icon Badge */}
          <div className="mx-auto w-14 h-14 rounded-2xl bg-[#111e2e] border border-[#1f3854] flex items-center justify-center text-[#38bdf8] mb-6 shadow-inner">
            <KeyRound size={26} strokeWidth={2.2} />
          </div>

          {/* Heading and Subtitle */}
          <div className="text-center space-y-2 mb-8">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#f8fafc]">
              Private Access
            </h1>
            <p className="text-xs sm:text-sm text-[#94a3b8] leading-relaxed max-w-sm mx-auto">
              This platform is privately accessible to authorised users only.
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div
              className={`mb-6 p-3.5 rounded-xl border text-xs flex items-start gap-3 animate-in fade-in ${
                isLockedOut
                  ? 'bg-[#2a1215] border-[#dc2626]/50 text-[#fca5a5]'
                  : 'bg-[#221316] border-[#e11d48]/40 text-[#fecdd3]'
              }`}
              role="alert"
            >
              {isLockedOut ? (
                <Clock size={16} className="text-[#ef4444] shrink-0 mt-0.5" />
              ) : (
                <AlertCircle size={16} className="text-[#f43f5e] shrink-0 mt-0.5" />
              )}
              <div className="space-y-1">
                <p className="font-semibold">{error}</p>
                {isLockedOut && (
                  <p className="text-[11px] text-[#fca5a5]/80 font-mono">
                    Cooldown active: {rateLimitedSeconds}s remaining before re-attempting.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="access-password"
                className="block text-xs font-semibold text-[#cbd5e1] mb-2 tracking-wide"
              >
                Enter access password.
              </label>
              <div className="relative">
                <input
                  id="access-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => {
                    setPassword(e.target.value)
                    if (error) clearError()
                  }}
                  disabled={submitting || isLockedOut}
                  placeholder="••••••••••••"
                  autoFocus
                  required
                  autoComplete="current-password"
                  className="w-full px-4 py-3 pr-11 rounded-xl bg-[#070b10] border border-[#233549] text-[#f8fafc] placeholder-[#475569] text-sm font-mono focus:outline-none focus:border-[#38bdf8] focus:ring-1 focus:ring-[#38bdf8] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-inner"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={submitting || isLockedOut}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#64748b] hover:text-[#94a3b8] transition-colors p-1"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting || !password.trim() || isLockedOut}
              className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-[#0284c7] to-[#0369a1] hover:from-[#0ea5e9] hover:to-[#0284c7] text-white text-sm font-semibold tracking-wide shadow-lg shadow-[#0284c7]/20 flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
            >
              {submitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Verifying…</span>
                </>
              ) : isLockedOut ? (
                <>
                  <Clock size={16} />
                  <span>Locked ({rateLimitedSeconds}s)</span>
                </>
              ) : (
                <>
                  <Lock size={15} />
                  <span>Unlock AMQUANT</span>
                </>
              )}
            </button>
          </form>

          {/* Notice info */}
          <div className="mt-8 pt-6 border-t border-[#182332] text-center">
            <p className="text-[11px] text-[#64748b] leading-relaxed">
              Proprietary quantitative models, derivatives analytics, and backtesting engines are restricted to approved testers.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="max-w-6xl w-full mx-auto text-center py-4">
        <p className="text-[11px] font-mono text-[#475569]">
          AMQUANT · INSTITUTIONAL PRIVATE BETA · STRICT CONFIDENTIALITY
        </p>
      </footer>
    </div>
  )
}
