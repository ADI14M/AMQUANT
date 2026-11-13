import { useEffect, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Database,
  KeyRound,
  Lock,
  RefreshCw,
  Server,
  Shield,
  ShieldAlert,
  Trash2,
  X,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  getAdminSystemStatus,
  getSecurityLogs,
  revokeAllAccessSessions,
  rotateAccessPassword,
  type AdminSystemStatusResponse,
  type SecurityEvent,
} from '../lib/api'

interface AdminModalProps {
  isOpen: boolean
  onClose: () => void
}

type AdminTab = 'logs' | 'rotate' | 'sessions' | 'system'

export default function AdminModal({ isOpen, onClose }: AdminModalProps) {
  const { user, session } = useAuth()
  const [activeTab, setActiveTab] = useState<AdminTab>('logs')
  const [logs, setLogs] = useState<SecurityEvent[]>([])
  const [systemStatus, setSystemStatus] = useState<AdminSystemStatusResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Password rotation state
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const jwt = session?.access_token

  const isOwner = user?.email?.toLowerCase() === 'adi@amquant.in'

  useEffect(() => {
    if (!isOpen || !jwt || !isOwner) return
    void refreshData()
  }, [isOpen, jwt, activeTab])

  const refreshData = async () => {
    if (!jwt) return
    setLoading(true)
    setMessage(null)
    try {
      if (activeTab === 'logs') {
        const res = await getSecurityLogs(jwt, 100)
        setLogs(res.events || [])
      } else if (activeTab === 'system') {
        const res = await getAdminSystemStatus(jwt)
        setSystemStatus(res)
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to fetch admin data' })
    } finally {
      setLoading(false)
    }
  }

  const handleRotatePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!jwt) return
    if (!newPassword || newPassword.length < 8) {
      setMessage({ type: 'error', text: 'Password must be at least 8 characters long.' })
      return
    }
    if (newPassword !== confirmPassword) {
      setMessage({ type: 'error', text: 'Passwords do not match.' })
      return
    }

    setActionLoading(true)
    setMessage(null)
    try {
      const res = await rotateAccessPassword(jwt, newPassword)
      setMessage({
        type: 'success',
        text: `${res.detail} (Hash: ${res.hash_preview}). All existing tester sessions have been invalidated.`,
      })
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to rotate password' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleRevokeAllSessions = async () => {
    if (!jwt) return
    const confirmed = window.confirm(
      'Are you sure you want to revoke ALL active sessions? This will immediately disconnect all users and require them to re-enter the shared access password.',
    )
    if (!confirmed) return

    setActionLoading(true)
    setMessage(null)
    try {
      const res = await revokeAllAccessSessions(jwt)
      setMessage({ type: 'success', text: res.detail })
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to revoke sessions' })
    } finally {
      setActionLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-[#0c121d] border border-[#1e2d42] rounded-2xl shadow-2xl flex flex-col overflow-hidden text-[#e2e8f0]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1b2738] bg-[#090d15]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#0f233a] border border-[#1d446e] flex items-center justify-center text-[#38bdf8]">
              <Shield size={18} strokeWidth={2.4} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-[#f8fafc]">Security & Administration Desk</h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#0369a1]/30 text-[#38bdf8] border border-[#0369a1]/50 uppercase">
                  Owner Only
                </span>
              </div>
              <p className="text-xs text-[#94a3b8]">Operator: {user?.email ?? 'Unknown'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-[#94a3b8] hover:text-[#f8fafc] hover:bg-[#1a2536] transition-colors"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Not Owner Guard */}
        {!isOwner ? (
          <div className="p-8 text-center space-y-4">
            <ShieldAlert size={48} className="mx-auto text-[#ef4444]" />
            <h3 className="text-lg font-bold text-[#f8fafc]">Access Denied</h3>
            <p className="text-sm text-[#94a3b8] max-w-md mx-auto">
              This panel is strictly restricted to the platform owner (<code>adi@amquant.in</code>). Shared access testers do not possess administrative permissions.
            </p>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-[#1e293b] hover:bg-[#334155] text-white rounded-lg text-sm font-medium transition"
            >
              Return to Platform
            </button>
          </div>
        ) : (
          <>
            {/* Nav Tabs */}
            <div className="flex border-b border-[#1b2738] bg-[#0b1018] px-6 gap-2 pt-2">
              <button
                onClick={() => setActiveTab('logs')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                  activeTab === 'logs'
                    ? 'border-[#38bdf8] text-[#38bdf8]'
                    : 'border-transparent text-[#94a3b8] hover:text-white'
                }`}
              >
                <ShieldAlert size={14} />
                Security Audit Logs
              </button>
              <button
                onClick={() => setActiveTab('rotate')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                  activeTab === 'rotate'
                    ? 'border-[#38bdf8] text-[#38bdf8]'
                    : 'border-transparent text-[#94a3b8] hover:text-white'
                }`}
              >
                <KeyRound size={14} />
                Rotate Password
              </button>
              <button
                onClick={() => setActiveTab('sessions')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                  activeTab === 'sessions'
                    ? 'border-[#38bdf8] text-[#38bdf8]'
                    : 'border-transparent text-[#94a3b8] hover:text-white'
                }`}
              >
                <Lock size={14} />
                Session Kill Switch
              </button>
              <button
                onClick={() => setActiveTab('system')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                  activeTab === 'system'
                    ? 'border-[#38bdf8] text-[#38bdf8]'
                    : 'border-transparent text-[#94a3b8] hover:text-white'
                }`}
              >
                <Server size={14} />
                System Status
              </button>
            </div>

            {/* Notification Banner */}
            {message && (
              <div
                className={`mx-6 mt-4 p-3 rounded-lg flex items-center gap-2.5 text-xs ${
                  message.type === 'success'
                    ? 'bg-[#064e3b]/40 border border-[#059669]/60 text-[#a7f3d0]'
                    : 'bg-[#4c0519]/40 border border-[#e11d48]/60 text-[#fecdd3]'
                }`}
              >
                {message.type === 'success' ? (
                  <CheckCircle2 size={16} className="shrink-0 text-[#10b981]" />
                ) : (
                  <AlertCircle size={16} className="shrink-0 text-[#ef4444]" />
                )}
                <span>{message.text}</span>
              </div>
            )}

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* TAB 1: SECURITY LOGS */}
              {activeTab === 'logs' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-[#f8fafc]">Real-Time Security Event Stream</h3>
                      <p className="text-xs text-[#94a3b8]">
                        Tracks password verifications, failed attempts, IP lockouts, and administrative actions.
                      </p>
                    </div>
                    <button
                      onClick={refreshData}
                      disabled={loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#162232] hover:bg-[#1f3148] text-xs font-medium rounded-lg text-[#94a3b8] hover:text-white transition disabled:opacity-50"
                    >
                      <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                      Refresh
                    </button>
                  </div>

                  <div className="border border-[#1e2d42] rounded-xl overflow-hidden bg-[#0a0e16]">
                    <div className="overflow-x-auto max-h-[420px]">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-[#0f1724] text-[#94a3b8] border-b border-[#1e2d42] sticky top-0">
                          <tr>
                            <th className="py-2.5 px-3">Timestamp (UTC)</th>
                            <th className="py-2.5 px-3">Event</th>
                            <th className="py-2.5 px-3">Client IP</th>
                            <th className="py-2.5 px-3">Detail</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#172233]">
                          {logs.length === 0 ? (
                            <tr>
                              <td colSpan={4} className="py-8 text-center text-[#64748b] font-sans">
                                {loading ? 'Loading events…' : 'No security events recorded in buffer.'}
                              </td>
                            </tr>
                          ) : (
                            logs.map((evt, idx) => {
                              const isFailure =
                                evt.event_type.includes('FAILURE') ||
                                evt.event_type.includes('LOCKED') ||
                                evt.event_type.includes('UNAUTHORIZED')
                              const isSuccess = evt.event_type.includes('SUCCESS')
                              return (
                                <tr key={idx} className="hover:bg-[#111927]/60 transition-colors">
                                  <td className="py-2 px-3 text-[#94a3b8] whitespace-nowrap">
                                    {evt.timestamp?.replace('T', ' ').slice(0, 19)}
                                  </td>
                                  <td className="py-2 px-3 whitespace-nowrap">
                                    <span
                                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                                        isFailure
                                          ? 'bg-[#dc2626]/20 text-[#fca5a5] border border-[#dc2626]/40'
                                          : isSuccess
                                          ? 'bg-[#10b981]/20 text-[#6ee7b7] border border-[#10b981]/40'
                                          : 'bg-[#0284c7]/20 text-[#7dd3fc] border border-[#0284c7]/40'
                                      }`}
                                    >
                                      {evt.event_type}
                                    </span>
                                  </td>
                                  <td className="py-2 px-3 text-[#cbd5e1] whitespace-nowrap">{evt.client_ip}</td>
                                  <td className="py-2 px-3 text-[#94a3b8] truncate max-w-xs">{evt.detail}</td>
                                </tr>
                              )
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: ROTATE PASSWORD */}
              {activeTab === 'rotate' && (
                <div className="max-w-lg mx-auto space-y-6">
                  <div className="bg-[#101725] border border-[#1d2d42] p-4 rounded-xl space-y-2">
                    <div className="flex items-center gap-2 text-xs font-semibold text-[#38bdf8]">
                      <KeyRound size={15} />
                      <span>Argon2id Hash Protection</span>
                    </div>
                    <p className="text-xs text-[#94a3b8] leading-relaxed">
                      Rotating the shared platform access password immediately updates the active in-memory hash and
                      invalidates all issued tester session tokens. Every user must authenticate with the new password.
                    </p>
                  </div>

                  <form onSubmit={handleRotatePassword} className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-[#cbd5e1]">New Shared Access Password</label>
                      <input
                        type="password"
                        value={newPassword}
                        onChange={e => setNewPassword(e.target.value)}
                        placeholder="Minimum 8 characters"
                        required
                        minLength={8}
                        className="w-full px-3.5 py-2.5 rounded-lg bg-[#0a0f16] border border-[#1e2d42] text-sm text-white placeholder-[#475569] focus:outline-none focus:border-[#38bdf8]"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-[#cbd5e1]">Confirm New Password</label>
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={e => setConfirmPassword(e.target.value)}
                        placeholder="Re-enter password"
                        required
                        minLength={8}
                        className="w-full px-3.5 py-2.5 rounded-lg bg-[#0a0f16] border border-[#1e2d42] text-sm text-white placeholder-[#475569] focus:outline-none focus:border-[#38bdf8]"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={actionLoading}
                      className="w-full py-2.5 bg-[#0284c7] hover:bg-[#0369a1] text-white rounded-lg text-sm font-semibold transition disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {actionLoading ? (
                        <>
                          <RefreshCw size={15} className="animate-spin" />
                          <span>Hashing with Argon2id…</span>
                        </>
                      ) : (
                        <>
                          <KeyRound size={15} />
                          <span>Rotate Access Password Now</span>
                        </>
                      )}
                    </button>
                  </form>
                </div>
              )}

              {/* TAB 3: SESSION MANAGEMENT & KILL SWITCH */}
              {activeTab === 'sessions' && (
                <div className="max-w-lg mx-auto space-y-6 text-center">
                  <div className="p-4 rounded-xl bg-[#2a0e14] border border-[#7f1d1d] text-left space-y-3">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#fca5a5]">
                      <AlertTriangle size={16} />
                      <span>Emergency Session Revocation</span>
                    </div>
                    <p className="text-xs text-[#fecdd3]/90 leading-relaxed">
                      Triggering the kill switch increments the server revocation epoch. Any tester access token issued
                      prior to this moment will be instantly rejected on all subsequent requests with a{' '}
                      <code>401 Unauthorized</code> error.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-[#0b1018] border border-[#1e2d42] space-y-4">
                    <p className="text-xs text-[#94a3b8]">
                      Use this in case of unauthorized link distribution, compromised credentials, or when completing a
                      private test phase.
                    </p>
                    <button
                      type="button"
                      onClick={handleRevokeAllSessions}
                      disabled={actionLoading}
                      className="px-5 py-2.5 bg-[#dc2626] hover:bg-[#b91c1c] text-white rounded-lg text-xs font-bold tracking-wider uppercase transition shadow-lg shadow-red-900/40 disabled:opacity-50 flex items-center justify-center gap-2 mx-auto"
                    >
                      <Trash2 size={15} />
                      <span>Revoke All Active Sessions</span>
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 4: SYSTEM STATUS */}
              {activeTab === 'system' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-[#0b1018] border border-[#1e2d42] space-y-2">
                      <div className="flex items-center gap-2 text-xs font-semibold text-[#38bdf8]">
                        <Shield size={14} />
                        <span>Security Configuration</span>
                      </div>
                      <div className="text-xs font-mono space-y-1 text-[#94a3b8]">
                        <div>
                          Owner:{' '}
                          <span className="text-[#f8fafc] font-semibold">{systemStatus?.owner_email || 'adi@amquant.in'}</span>
                        </div>
                        <div>
                          Password Configured:{' '}
                          <span className="text-[#10b981]">
                            {systemStatus?.active_password_configured ? 'YES (Active)' : 'NO'}
                          </span>
                        </div>
                        <div>
                          Hash Algorithm: <span className="text-[#f8fafc]">Argon2id (RFC 9106)</span>
                        </div>
                        <div className="truncate">
                          Hash Preview: <span className="text-[#94a3b8]">{systemStatus?.password_hash_preview || '—'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="p-4 rounded-xl bg-[#0b1018] border border-[#1e2d42] space-y-2">
                      <div className="flex items-center gap-2 text-xs font-semibold text-[#38bdf8]">
                        <Database size={14} />
                        <span>Storage & Retention</span>
                      </div>
                      <div className="text-xs font-mono space-y-1 text-[#94a3b8]">
                        <div className="truncate">
                          Path: <span className="text-[#f8fafc]">{systemStatus?.storage_directory || 'data'}</span>
                        </div>
                        <div>
                          Parquet Files:{' '}
                          <span className="text-[#f8fafc]">{systemStatus?.disk_usage?.parquet_files_count ?? '—'}</span>
                        </div>
                        <div>
                          Storage Size:{' '}
                          <span className="text-[#f8fafc]">
                            {systemStatus?.disk_usage?.parquet_total_mb != null
                              ? `${systemStatus.disk_usage.parquet_total_mb} MB`
                              : '—'}
                          </span>
                        </div>
                        <div>
                          DuckDB Size:{' '}
                          <span className="text-[#f8fafc]">
                            {systemStatus?.disk_usage?.duckdb_size_mb != null
                              ? `${systemStatus.disk_usage.duckdb_size_mb} MB`
                              : '—'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-[#0b1018] border border-[#1e2d42] space-y-2">
                    <div className="flex items-center gap-2 text-xs font-semibold text-[#38bdf8]">
                      <Server size={14} />
                      <span>Rate Limiter Diagnostics</span>
                    </div>
                    <div className="text-xs font-mono text-[#94a3b8] space-y-1">
                      <div>
                        Max Attempts: <span className="text-[#f8fafc]">5 failed attempts per 5 minutes</span>
                      </div>
                      <div>
                        Lockout Period: <span className="text-[#f8fafc]">15 minutes</span>
                      </div>
                      <div>
                        Currently Locked IPs:{' '}
                        <span className="text-[#ef4444] font-bold">
                          {systemStatus?.rate_limiter_status?.locked_ips_count ?? 0}
                        </span>
                      </div>
                      <div>
                        IPs in Failure Window:{' '}
                        <span className="text-[#f8fafc]">
                          {systemStatus?.rate_limiter_status?.tracked_ips_count ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-[#1b2738] bg-[#090d15] flex items-center justify-between text-xs text-[#64748b]">
              <span>AMQUANT Security Layer • Zero-Cost Production Model</span>
              <button
                onClick={onClose}
                className="px-4 py-1.5 rounded-lg bg-[#162232] hover:bg-[#1e2d42] text-[#cbd5e1] font-medium transition"
              >
                Close Desk
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
