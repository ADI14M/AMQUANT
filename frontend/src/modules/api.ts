const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function postResearch<T>(path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('Cannot reach the AMQUANT API. Start it with the documented uvicorn command and retry.')
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map(issue => issue?.msg).filter(Boolean).join('; ')
        : ''
    throw new Error(message || `Calculation request failed (${response.status}). Check the inputs and try again.`)
  }
  return response.json() as Promise<T>
}
