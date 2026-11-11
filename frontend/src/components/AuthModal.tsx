import { useState, type FormEvent } from 'react'
import { AlertCircle, CheckCircle2, Eye, EyeOff, Lock, Mail, User, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function AuthModal() {
  const {
    authModalOpen,
    authModalMode,
    authModalMessage,
    closeAuthModal,
    openAuthModal,
    signIn,
    signUp,
    resetPassword,
    updatePassword,
    isConfigured,
  } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)

  if (!authModalOpen) return null

  const resetForm = () => {
    setEmail('')
    setPassword('')
    setConfirmPassword('')
    setDisplayName('')
    setError(null)
    setSuccessNotice(null)
    setShowPassword(false)
  }

  const handleModeChange = (mode: 'login' | 'register' | 'forgot') => {
    resetForm()
    openAuthModal(mode)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessNotice(null)

    if (!isConfigured) {
      setError('Supabase authentication is not configured in this environment.')
      return
    }

    if (authModalMode === 'login') {
      if (!email || !password) {
        setError('Please enter both email and password.')
        return
      }
      setLoading(true)
      const { error: signErr } = await signIn(email, password)
      setLoading(false)
      if (signErr) {
        if (signErr.message.toLowerCase().includes('invalid login credentials')) {
          setError('Invalid email or password. Please verify and try again.')
        } else if (signErr.message.toLowerCase().includes('email not confirmed')) {
          setError('Please check your email and click the confirmation link to verify your account.')
        } else {
          setError(signErr.message)
        }
      } else {
        resetForm()
      }
    } else if (authModalMode === 'register') {
      if (!email || !password) {
        setError('Please enter email and password.')
        return
      }
      if (password.length < 6) {
        setError('Password must be at least 6 characters.')
        return
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match.')
        return
      }
      setLoading(true)
      const { error: regErr, needsEmailVerification } = await signUp(email, password, displayName)
      setLoading(false)
      if (regErr) {
        if (regErr.message.toLowerCase().includes('already registered')) {
          setError('An account with this email already exists. Try signing in.')
        } else {
          setError(regErr.message)
        }
      } else if (needsEmailVerification) {
        setSuccessNotice(`Account registered! We've sent a verification email to ${email}. Please confirm your email to log in.`)
      } else {
        resetForm()
      }
    } else if (authModalMode === 'forgot') {
      if (!email) {
        setError('Please enter your account email.')
        return
      }
      setLoading(true)
      const { error: resetErr } = await resetPassword(email)
      setLoading(false)
      if (resetErr) {
        setError(resetErr.message)
      } else {
        setSuccessNotice(`Password recovery link sent to ${email}. Please check your inbox.`)
      }
    } else if (authModalMode === 'update_password') {
      if (!password || password.length < 6) {
        setError('New password must be at least 6 characters.')
        return
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match.')
        return
      }
      setLoading(true)
      const { error: updateErr } = await updatePassword(password)
      setLoading(false)
      if (updateErr) {
        setError(updateErr.message)
      } else {
        resetForm()
      }
    }
  }

  return (
    <div className="auth-modal-backdrop" onClick={closeAuthModal} role="dialog" aria-modal="true">
      <div className="auth-modal-card" onClick={e => e.stopPropagation()}>
        <header className="auth-modal-header">
          <div className="auth-brand">
            <span className="auth-brand-badge">AMQUANT AUTH</span>
            <h2>
              {authModalMode === 'login' && 'Sign in to Terminal'}
              {authModalMode === 'register' && 'Create Research Account'}
              {authModalMode === 'forgot' && 'Reset Terminal Access'}
              {authModalMode === 'update_password' && 'Set New Password'}
            </h2>
          </div>
          <button className="auth-close-btn" onClick={closeAuthModal} aria-label="Close authentication modal">
            <X size={16} />
          </button>
        </header>

        {authModalMessage && (
          <div className="auth-notice-box">
            <span>ℹ️</span>
            <p>{authModalMessage}</p>
          </div>
        )}

        {(authModalMode === 'login' || authModalMode === 'register') && (
          <div className="auth-tab-switch">
            <button
              type="button"
              className={authModalMode === 'login' ? 'active' : ''}
              onClick={() => handleModeChange('login')}
            >
              Sign In
            </button>
            <button
              type="button"
              className={authModalMode === 'register' ? 'active' : ''}
              onClick={() => handleModeChange('register')}
            >
              Register
            </button>
          </div>
        )}

        {error && (
          <div className="auth-alert-error" role="alert">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {successNotice && (
          <div className="auth-alert-success" role="status">
            <CheckCircle2 size={16} />
            <span>{successNotice}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {authModalMode === 'register' && (
            <label className="auth-field">
              <span>Display name</span>
              <div className="auth-input-wrap">
                <User size={15} />
                <input
                  type="text"
                  placeholder="e.g. QuantResearcher"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  maxLength={100}
                />
              </div>
            </label>
          )}

          {authModalMode !== 'update_password' && (
            <label className="auth-field">
              <span>Email address</span>
              <div className="auth-input-wrap">
                <Mail size={15} />
                <input
                  type="email"
                  placeholder="analyst@firm.com"
                  required
                  autoFocus
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                />
              </div>
            </label>
          )}

          {authModalMode !== 'forgot' && (
            <label className="auth-field">
              <div className="auth-field-header">
                <span>{authModalMode === 'update_password' ? 'New password' : 'Password'}</span>
                {authModalMode === 'login' && (
                  <button
                    type="button"
                    className="auth-link-subtle"
                    onClick={() => handleModeChange('forgot')}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="auth-input-wrap">
                <Lock size={15} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="auth-show-pw"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </label>
          )}

          {(authModalMode === 'register' || authModalMode === 'update_password') && (
            <label className="auth-field">
              <span>Confirm password</span>
              <div className="auth-input-wrap">
                <Lock size={15} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                />
              </div>
            </label>
          )}

          <button className="auth-submit-btn primary-button" type="submit" disabled={loading}>
            {loading ? (
              'Authenticating…'
            ) : authModalMode === 'login' ? (
              'Sign In to Workspace'
            ) : authModalMode === 'register' ? (
              'Create Research Account'
            ) : authModalMode === 'forgot' ? (
              'Send Recovery Link'
            ) : (
              'Save New Password'
            )}
          </button>
        </form>

        <footer className="auth-modal-footer">
          {authModalMode === 'login' && (
            <p>
              New to AMQUANT?{' '}
              <button type="button" onClick={() => handleModeChange('register')}>
                Register account
              </button>
            </p>
          )}
          {authModalMode === 'register' && (
            <p>
              Already have an account?{' '}
              <button type="button" onClick={() => handleModeChange('login')}>
                Sign in
              </button>
            </p>
          )}
          {authModalMode === 'forgot' && (
            <p>
              Remembered your credentials?{' '}
              <button type="button" onClick={() => handleModeChange('login')}>
                Back to Sign in
              </button>
            </p>
          )}
          <small className="auth-disclaimer">
            Guest access remains unrestricted across all 5 calculation engines.
          </small>
        </footer>
      </div>
    </div>
  )
}

