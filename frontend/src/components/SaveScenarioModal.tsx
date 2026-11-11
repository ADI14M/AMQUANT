import { useState, type FormEvent } from 'react'
import { Bookmark, Check, X } from 'lucide-react'
import { createSavedScenario, type SavedScenario } from '../lib/api'
import { useAuth } from '../context/AuthContext'

interface SaveScenarioModalProps {
  isOpen: boolean
  onClose: () => void
  moduleName: 'foundations' | 'bayesian' | 'stochastic' | 'options' | 'intelligence'
  moduleTitle: string
  scenarioData: Record<string, any>
  defaultTitle?: string
  onSaved?: (scenario: SavedScenario) => void
}

export default function SaveScenarioModal({
  isOpen,
  onClose,
  moduleName,
  moduleTitle,
  scenarioData,
  defaultTitle = '',
  onSaved,
}: SaveScenarioModalProps) {
  const { session } = useAuth()
  const [title, setTitle] = useState(defaultTitle || `${moduleTitle} Scenario`)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedSuccess, setSavedSuccess] = useState(false)

  if (!isOpen) return null

  const handleSave = async (e: FormEvent) => {
    e.preventDefault()
    if (!title.trim()) {
      setError('Please provide a title for this scenario.')
      return
    }
    if (!session?.access_token) {
      setError('Authentication session missing. Please sign in again.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const created = await createSavedScenario(session.access_token, title.trim(), moduleName, scenarioData)
      setSavedSuccess(true)
      setTimeout(() => {
        setSavedSuccess(false)
        onSaved?.(created)
        onClose()
      }, 700)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save scenario')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="auth-modal-card save-scenario-card" onClick={e => e.stopPropagation()}>
        <header className="auth-modal-header">
          <div className="auth-brand">
            <span className="auth-brand-badge">PERSONAL WORKSPACE</span>
            <h2>Save Scenario Configuration</h2>
          </div>
          <button className="auth-close-btn" onClick={onClose} aria-label="Close save scenario modal">
            <X size={16} />
          </button>
        </header>

        {error && (
          <div className="auth-alert-error" role="alert">
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSave} className="auth-form">
          <div className="scenario-meta-row">
            <span className="scenario-module-tag">{moduleTitle}</span>
            <small className="scenario-keys-count">
              {Object.keys(scenarioData).length} parameters captured
            </small>
          </div>

          <label className="auth-field">
            <span>Scenario title</span>
            <div className="auth-input-wrap">
              <Bookmark size={15} />
              <input
                type="text"
                required
                autoFocus
                maxLength={120}
                placeholder="e.g. S&P 500 Out-of-the-Money Call Volatility"
                value={title}
                onChange={e => setTitle(e.target.value)}
              />
            </div>
          </label>

          <div className="scenario-preview-box">
            <span className="scenario-preview-label">CAPTURED PARAMETERS</span>
            <pre className="scenario-preview-json">
              {JSON.stringify(scenarioData, null, 2)}
            </pre>
          </div>

          <button
            className={`auth-submit-btn primary-button ${savedSuccess ? 'saved-success-btn' : ''}`}
            type="submit"
            disabled={loading || savedSuccess}
          >
            {savedSuccess ? (
              <>
                <Check size={16} /> Saved to Workspace!
              </>
            ) : loading ? (
              'Saving Scenario…'
            ) : (
              'Save to Personal Workspace'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

