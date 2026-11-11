const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.PROD ? 'https://amquant-api.onrender.com' : 'http://localhost:8000')

export interface SavedScenario {
  id: string
  user_id: string
  title: string
  module_name: 'foundations' | 'bayesian' | 'stochastic' | 'options' | 'intelligence'
  scenario_data: Record<string, any>
  created_at: string
  updated_at: string
}

export interface ResearchHistoryEntry {
  id: string
  user_id: string
  module_name: 'foundations' | 'bayesian' | 'stochastic' | 'options' | 'intelligence'
  scenario_id: string | null
  summary: Record<string, any>
  created_at: string
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/health`)
    return response.ok
  } catch {
    return false
  }
}

function authHeaders(token: string | null | undefined, extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

// ============================================================================
// SCENARIOS API
// ============================================================================

export async function listSavedScenarios(token: string, moduleName?: string): Promise<SavedScenario[]> {
  const query = moduleName ? `?module_name=${encodeURIComponent(moduleName)}` : ''
  const res = await fetch(`${API_BASE}/api/scenarios${query}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to list scenarios')
  }
  return res.json() as Promise<SavedScenario[]>
}

export async function getSavedScenario(token: string, scenarioId: string): Promise<SavedScenario> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Scenario not found')
  }
  return res.json() as Promise<SavedScenario>
}

export async function createSavedScenario(
  token: string,
  title: string,
  moduleName: string,
  scenarioData: Record<string, any>
): Promise<SavedScenario> {
  const res = await fetch(`${API_BASE}/api/scenarios`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      title: title.trim(),
      module_name: moduleName,
      scenario_data: scenarioData,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to save scenario')
  }
  return res.json() as Promise<SavedScenario>
}

export async function updateSavedScenario(
  token: string,
  scenarioId: string,
  title?: string,
  scenarioData?: Record<string, any>
): Promise<SavedScenario> {
  const body: Record<string, any> = {}
  if (title !== undefined) body.title = title.trim()
  if (scenarioData !== undefined) body.scenario_data = scenarioData

  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to update scenario')
  }
  return res.json() as Promise<SavedScenario>
}

export async function deleteSavedScenario(token: string, scenarioId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to delete scenario')
  }
}

// ============================================================================
// RESEARCH HISTORY API
// ============================================================================

export async function listResearchHistory(token: string, limit = 50, offset = 0): Promise<ResearchHistoryEntry[]> {
  const res = await fetch(`${API_BASE}/api/research-history?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to list research history')
  }
  return res.json() as Promise<ResearchHistoryEntry[]>
}

export async function recordResearchHistory(
  token: string,
  moduleName: string,
  summary: Record<string, any>,
  scenarioId?: string | null
): Promise<ResearchHistoryEntry> {
  const res = await fetch(`${API_BASE}/api/research-history`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      module_name: moduleName,
      summary,
      scenario_id: scenarioId ?? null,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to record research history')
  }
  return res.json() as Promise<ResearchHistoryEntry>
}

export async function deleteResearchHistoryEntry(token: string, historyId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/research-history/${historyId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to delete history entry')
  }
}

export async function clearResearchHistory(token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/research-history`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to clear research history')
  }
}
