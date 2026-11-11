const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface ApiValidationError {
  field?: string
  message?: string
}

interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string; loc?: string[] }>
  errors?: ApiValidationError[]
}

export async function postResearch<T>(path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (err) {
    throw new Error(
      'Cannot connect to the AMQUANT API. If the backend is waking up from idle on free-tier hosting (Render), please wait 30–50 seconds and click Run again.'
    )
  }

  if (!response.ok) {
    const status = response.status
    const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null

    if (status === 429) {
      const retryAfter = response.headers.get('Retry-After')
      const waitNotice = retryAfter ? ` Please wait ${retryAfter} seconds before retrying.` : ' Please wait a moment before retrying.'
      const msg = typeof payload?.detail === 'string' ? payload.detail : `Rate limit exceeded (30 requests/minute).${waitNotice}`
      throw new Error(msg)
    }

    if (status === 503) {
      const retryAfter = response.headers.get('Retry-After')
      const waitNotice = retryAfter ? ` Please retry in ${retryAfter} seconds.` : ' Please retry in a few moments.'
      const msg = typeof payload?.detail === 'string' ? payload.detail : `The calculation engine is currently at peak capacity.${waitNotice}`
      throw new Error(msg)
    }

    if (status === 413) {
      const msg = typeof payload?.detail === 'string' ? payload.detail : 'Request payload exceeds the 64 KB limit. Please reduce parameter sizes and retry.'
      throw new Error(msg)
    }

    if (status === 422) {
      if (Array.isArray(payload?.errors) && payload.errors.length > 0) {
        const issues = payload.errors.map(e => e.field && e.message ? `${e.field}: ${e.message}` : e.message || 'Invalid input').join('; ')
        throw new Error(`Validation error: ${issues}`)
      }
      if (typeof payload?.detail === 'string') {
        throw new Error(payload.detail)
      }
      if (Array.isArray(payload?.detail)) {
        const issues = payload.detail.map(d => d.msg).filter(Boolean).join('; ')
        throw new Error(`Validation error: ${issues || 'Invalid input parameters.'}`)
      }
      throw new Error('Validation error: Please verify your input parameters.')
    }

    if (status >= 500) {
      const msg = typeof payload?.detail === 'string' ? payload.detail : 'An internal calculation error occurred. Please verify your inputs and retry.'
      throw new Error(msg)
    }

    const fallbackMsg = typeof payload?.detail === 'string' ? payload.detail : `Request failed with HTTP ${status}. Please try again.`
    throw new Error(fallbackMsg)
  }

  return response.json() as Promise<T>
}
