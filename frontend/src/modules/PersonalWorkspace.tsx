import { useEffect, useState, type FormEvent } from 'react'
import {
  Activity,
  Atom,
  BookOpen,
  Bookmark,
  Brain,
  Calendar,
  Check,
  ChevronRight,
  Edit2,
  ExternalLink,
  FlaskConical,
  History,
  Lock,
  LogOut,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  User as UserIcon,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  clearResearchHistory,
  deleteResearchHistoryEntry,
  deleteSavedScenario,
  listResearchHistory,
  listSavedScenarios,
  updateSavedScenario,
  type ResearchHistoryEntry,
  type SavedScenario,
} from '../lib/api'
import type { ModuleId } from '../components/Sidebar'

const moduleMeta: Record<
  string,
  { label: string; icon: typeof Brain; color: string; bg: string; border: string; id: ModuleId }
> = {
  intelligence: {
    label: 'Research Intelligence',
    icon: Brain,
    color: '#3ed7a8',
    bg: '#102a27',
    border: '#1d574b',
    id: 'intelligence',
  },
  foundations: {
    label: 'Financial Foundations',
    icon: BookOpen,
    color: '#38bdf8',
    bg: '#0c2838',
    border: '#1e4963',
    id: 'foundations',
  },
  bayesian: {
    label: 'Bayesian Engine',
    icon: Atom,
    color: '#a78bfa',
    bg: '#231c38',
    border: '#3b2f5c',
    id: 'bayesian',
  },
  stochastic: {
    label: 'Stochastic Simulator',
    icon: Activity,
    color: '#fbbf24',
    bg: '#2d2208',
    border: '#544010',
    id: 'stochastic',
  },
  options: {
    label: 'Options Lab',
    icon: FlaskConical,
    color: '#f43f5e',
    bg: '#2e0f19',
    border: '#571c2f',
    id: 'options',
  },
}

interface PersonalWorkspaceProps {
  onOpenScenario: (moduleId: ModuleId, scenarioData: Record<string, any>) => void
  onNavigate: (moduleId: ModuleId) => void
}

export default function PersonalWorkspace({ onOpenScenario, onNavigate }: PersonalWorkspaceProps) {
  const { user, profile, session, signOut, openAuthModal, updateDisplayName } = useAuth()

  const [activeTab, setActiveTab] = useState<'scenarios' | 'history'>('scenarios')
  const [scenarios, setScenarios] = useState<SavedScenario[]>([])
  const [history, setHistory] = useState<ResearchHistoryEntry[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [filterModule, setFilterModule] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')

  // Editing profile name
  const [editingName, setEditingName] = useState(false)
  const [displayNameInput, setDisplayNameInput] = useState('')
  const [nameSaving, setNameSaving] = useState(false)

  // Editing scenario title
  const [editingScenarioId, setEditingScenarioId] = useState<string | null>(null)
  const [editingTitleInput, setEditingTitleInput] = useState('')

  const token = session?.access_token

  const loadData = async () => {
    if (!token) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [scenariosRes, historyRes] = await Promise.all([
        listSavedScenarios(token),
        listResearchHistory(token, 50, 0),
      ])
      setScenarios(scenariosRes)
      setHistory(historyRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspace data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) {
      void loadData()
    } else {
      setScenarios([])
      setHistory([])
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (profile?.display_name) {
      setDisplayNameInput(profile.display_name)
    }
  }, [profile?.display_name])

  // Profile update handler
  const handleSaveProfile = async (e: FormEvent) => {
    e.preventDefault()
    if (!displayNameInput.trim()) return
    setNameSaving(true)
    const { error: err } = await updateDisplayName(displayNameInput.trim())
    setNameSaving(false)
    if (!err) {
      setEditingName(false)
    }
  }

  // Scenario deletion
  const handleDeleteScenario = async (id: string, title: string) => {
    if (!token) return
    if (!window.confirm(`Delete scenario "${title}"? This cannot be undone.`)) return
    try {
      await deleteSavedScenario(token, id)
      setScenarios(prev => prev.filter(s => s.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete scenario')
    }
  }

  // Scenario rename
  const handleStartRename = (scenario: SavedScenario) => {
    setEditingScenarioId(scenario.id)
    setEditingTitleInput(scenario.title)
  }

  const handleSaveRename = async (id: string) => {
    if (!token || !editingTitleInput.trim()) return
    try {
      const updated = await updateSavedScenario(token, id, editingTitleInput.trim())
      setScenarios(prev => prev.map(s => (s.id === id ? { ...s, title: updated.title } : s)))
      setEditingScenarioId(null)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to rename scenario')
    }
  }

  // History entry deletion
  const handleDeleteHistoryEntry = async (id: string) => {
    if (!token) return
    try {
      await deleteResearchHistoryEntry(token, id)
      setHistory(prev => prev.filter(h => h.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete history entry')
    }
  }

  // Clear all history
  const handleClearHistory = async () => {
    if (!token) return
    if (!window.confirm('Clear your entire calculation audit history?')) return
    try {
      await clearResearchHistory(token)
      setHistory([])
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to clear history')
    }
  }

  // Filtered scenarios
  const filteredScenarios = scenarios.filter(s => {
    const matchesModule = filterModule === 'all' || s.module_name === filterModule
    const matchesSearch =
      !searchQuery ||
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.module_name.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesModule && matchesSearch
  })

  // If user is guest
  if (!user) {
    return (
      <div className="research-workspace">
        <div className="module-hero">
          <div className="eyebrow">WORKSPACE · USER REPOSITORY</div>
          <h1>Personal Research Workspace</h1>
          <p>Securely save model configurations, inspect historical research runs, and restore scenario parameters.</p>
        </div>

        <div className="guest-workspace-card panel">
          <div className="guest-lock-icon">
            <Lock size={32} />
          </div>
          <h2>Authentication Optional · Workspace Powered by Supabase</h2>
          <p>
            Guest access remains unrestricted across all five quantitative engines. Sign in or register to
            create your encrypted scenario library, track calculations, and restore saved parameter surfaces.
          </p>
          <div className="guest-actions">
            <button className="primary-button" onClick={() => openAuthModal('login')}>
              Sign In to Workspace
            </button>
            <button className="secondary-button" onClick={() => openAuthModal('register')}>
              Create Free Account
            </button>
          </div>
          <div className="guest-perks">
            <div className="perk-item">
              <Bookmark size={16} />
              <span>Save & reload custom scenarios in any module</span>
            </div>
            <div className="perk-item">
              <History size={16} />
              <span>Full audit history of mathematical calculation runs</span>
            </div>
            <div className="perk-item">
              <ShieldCheck size={16} />
              <span>PostgreSQL Row Level Security (RLS) encrypted isolation</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="research-workspace">
      <div className="module-hero">
        <div className="eyebrow">WORKSPACE · PERSONAL DESK</div>
        <h1>Personal Research Workspace</h1>
        <p>Manage your saved quantitative scenarios, parameter setups, and calculation history.</p>
      </div>

      {/* Profile & Security Header Card */}
      <div className="panel profile-desk-card">
        <div className="profile-desk-info">
          <div className="profile-desk-avatar">
            <UserIcon size={22} />
          </div>
          <div className="profile-desk-details">
            <div className="profile-name-row">
              {editingName ? (
                <form onSubmit={handleSaveProfile} className="profile-rename-form">
                  <input
                    type="text"
                    value={displayNameInput}
                    onChange={e => setDisplayNameInput(e.target.value)}
                    maxLength={100}
                    autoFocus
                  />
                  <button type="submit" className="rename-save-btn" disabled={nameSaving}>
                    <Check size={14} />
                  </button>
                  <button type="button" className="rename-cancel-btn" onClick={() => setEditingName(false)}>
                    ✕
                  </button>
                </form>
              ) : (
                <>
                  <h2>{profile?.display_name || user.email?.split('@')[0] || 'Quant Researcher'}</h2>
                  <button
                    className="edit-icon-btn"
                    onClick={() => {
                      setDisplayNameInput(profile?.display_name || user.email?.split('@')[0] || '')
                      setEditingName(true)
                    }}
                    title="Edit display name"
                  >
                    <Edit2 size={13} />
                  </button>
                </>
              )}
            </div>
            <div className="profile-sub-row">
              <span className="profile-email">{user.email}</span>
              <span className="profile-dot">·</span>
              <span className="profile-rls-pill">
                <ShieldCheck size={12} /> SUPABASE RLS ACTIVE
              </span>
            </div>
          </div>
        </div>

        <div className="profile-desk-actions">
          <button className="refresh-data-btn" onClick={loadData} disabled={loading} title="Refresh workspace data">
            <RefreshCw size={14} className={loading ? 'spin-icon' : ''} />
            <span>Sync</span>
          </button>
          <button className="signout-desk-btn" onClick={signOut} title="Sign out securely">
            <LogOut size={14} />
            <span>Sign Out</span>
          </button>
        </div>
      </div>

      {/* Main Workspace Tabs */}
      <div className="workspace-tabs-bar">
        <button
          className={`workspace-tab ${activeTab === 'scenarios' ? 'active' : ''}`}
          onClick={() => setActiveTab('scenarios')}
        >
          <Bookmark size={15} />
          <span>Saved Scenarios</span>
          <span className="tab-badge">{scenarios.length}</span>
        </button>
        <button
          className={`workspace-tab ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          <History size={15} />
          <span>Research Run History</span>
          <span className="tab-badge">{history.length}</span>
        </button>
      </div>

      {error && (
        <div className="calc-error" role="alert">
          {error}
        </div>
      )}

      {/* SCENARIOS TAB CONTENT */}
      {activeTab === 'scenarios' && (
        <div className="workspace-tab-content">
          <div className="workspace-filter-toolbar">
            <div className="module-filter-pills">
              <button
                className={`filter-pill ${filterModule === 'all' ? 'active' : ''}`}
                onClick={() => setFilterModule('all')}
              >
                All Modules ({scenarios.length})
              </button>
              {Object.entries(moduleMeta).map(([modKey, meta]) => {
                const count = scenarios.filter(s => s.module_name === modKey).length
                return (
                  <button
                    key={modKey}
                    className={`filter-pill ${filterModule === modKey ? 'active' : ''}`}
                    onClick={() => setFilterModule(modKey)}
                  >
                    {meta.label} ({count})
                  </button>
                )
              })}
            </div>

            <div className="workspace-search-box">
              <Search size={14} />
              <input
                type="text"
                placeholder="Search scenarios by title…"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <div className="empty-result">
              <span>∑</span>
              <p>Loading your saved research scenarios from Supabase…</p>
            </div>
          ) : filteredScenarios.length === 0 ? (
            <div className="empty-result workspace-empty">
              <Bookmark size={32} />
              <h3>{searchQuery || filterModule !== 'all' ? 'No matching scenarios found' : 'No scenarios saved yet'}</h3>
              <p>
                Configure inputs in any of the five quantitative modules and click <b>Save Scenario</b> to build your
                personal research library.
              </p>
              <div className="empty-quick-links">
                {Object.entries(moduleMeta).map(([modKey, meta]) => {
                  const Icon = meta.icon
                  return (
                    <button key={modKey} onClick={() => onNavigate(meta.id)}>
                      <Icon size={14} />
                      <span>{meta.label}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="scenarios-grid">
              {filteredScenarios.map(scenario => {
                const meta = moduleMeta[scenario.module_name] || moduleMeta.options
                const Icon = meta.icon
                const isEditing = editingScenarioId === scenario.id

                return (
                  <div key={scenario.id} className="scenario-card panel">
                    <div className="scenario-card-header">
                      <div
                        className="scenario-badge"
                        style={{ color: meta.color, background: meta.bg, borderColor: meta.border }}
                      >
                        <Icon size={13} />
                        <span>{meta.label}</span>
                      </div>
                      <span className="scenario-date">
                        <Calendar size={11} />
                        {new Date(scenario.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </span>
                    </div>

                    <div className="scenario-card-body">
                      {isEditing ? (
                        <div className="scenario-rename-row">
                          <input
                            type="text"
                            value={editingTitleInput}
                            onChange={e => setEditingTitleInput(e.target.value)}
                            maxLength={120}
                            autoFocus
                          />
                          <button
                            className="rename-save-btn"
                            onClick={() => handleSaveRename(scenario.id)}
                            title="Save title"
                          >
                            <Check size={13} />
                          </button>
                          <button
                            className="rename-cancel-btn"
                            onClick={() => setEditingScenarioId(null)}
                            title="Cancel"
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <div className="scenario-title-row">
                          <h3 title={scenario.title}>{scenario.title}</h3>
                          <button
                            className="title-edit-btn"
                            onClick={() => handleStartRename(scenario)}
                            title="Rename scenario"
                          >
                            <Edit2 size={12} />
                          </button>
                        </div>
                      )}

                      <div className="scenario-params-chips">
                        {Object.entries(scenario.scenario_data)
                          .filter(([k]) => !['observations', 'steps'].includes(k))
                          .slice(0, 5)
                          .map(([key, val]) => (
                            <span key={key} className="param-chip">
                              <small>{key}:</small> <b>{String(val)}</b>
                            </span>
                          ))}
                      </div>
                    </div>

                    <div className="scenario-card-footer">
                      <button
                        className="open-scenario-btn"
                        onClick={() => onOpenScenario(meta.id, scenario.scenario_data)}
                      >
                        <span>Open in {meta.label}</span>
                        <ChevronRight size={14} />
                      </button>
                      <button
                        className="delete-scenario-btn"
                        onClick={() => handleDeleteScenario(scenario.id, scenario.title)}
                        title="Delete scenario"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* RESEARCH HISTORY TAB CONTENT */}
      {activeTab === 'history' && (
        <div className="workspace-tab-content">
          <div className="history-toolbar">
            <p className="history-subtitle">
              Audit log of calculations executed under your account. Stored with PostgreSQL RLS.
            </p>
            {history.length > 0 && (
              <button className="clear-history-btn" onClick={handleClearHistory}>
                <Trash2 size={13} />
                <span>Clear History</span>
              </button>
            )}
          </div>

          {loading ? (
            <div className="empty-result">
              <span>∑</span>
              <p>Loading calculation history…</p>
            </div>
          ) : history.length === 0 ? (
            <div className="empty-result workspace-empty">
              <History size={32} />
              <h3>No research history recorded yet</h3>
              <p>When you run calculations in any module while signed in, a concise execution summary is logged here.</p>
            </div>
          ) : (
            <div className="history-table-wrap panel">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>TIMESTAMP</th>
                    <th>MODULE</th>
                    <th>RESEARCH SUMMARY</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(item => {
                    const meta = moduleMeta[item.module_name] || moduleMeta.options
                    const Icon = meta.icon
                    const formattedDate = new Date(item.created_at).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })

                    return (
                      <tr key={item.id}>
                        <td className="history-cell-date">{formattedDate}</td>
                        <td>
                          <span
                            className="scenario-badge"
                            style={{ color: meta.color, background: meta.bg, borderColor: meta.border }}
                          >
                            <Icon size={12} />
                            <span>{meta.label}</span>
                          </span>
                        </td>
                        <td className="history-cell-summary">
                          <div className="history-summary-chips">
                            {Object.entries(item.summary).map(([k, v]) => (
                              <span key={k} className="param-chip">
                                <small>{k}:</small>{' '}
                                <b>{typeof v === 'number' ? Number(v).toFixed(4) : String(v)}</b>
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="history-cell-actions">
                          <button
                            className="history-action-btn"
                            onClick={() => onNavigate(meta.id)}
                            title={`Navigate to ${meta.label}`}
                          >
                            <ExternalLink size={13} />
                          </button>
                          <button
                            className="history-delete-btn"
                            onClick={() => handleDeleteHistoryEntry(item.id)}
                            title="Delete entry"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
