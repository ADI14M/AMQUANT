import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AccessProvider, useAccess } from './context/AccessContext'
import PasswordGate from './components/PasswordGate'
import * as api from './lib/api'

// Helper component that allows manually calling lock() or viewing unlocked content
function ProtectedApp() {
  const { lock } = useAccess()
  return (
    <div>
      <h1>Protected Financial Platform</h1>
      <button onClick={() => void lock()}>Lock Platform</button>
    </div>
  )
}

describe('PasswordGate Security Component', () => {
  beforeEach(() => {
    vi.spyOn(api, 'checkAccessStatus').mockResolvedValue({ authenticated: true })
    vi.spyOn(api, 'revokeAccessSession').mockResolvedValue(undefined)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders the Private Access gate when platform is locked', async () => {
    render(
      <AccessProvider>
        <PasswordGate>
          <ProtectedApp />
        </PasswordGate>
      </AccessProvider>
    )

    // Lock platform
    fireEvent.click(screen.getByRole('button', { name: 'Lock Platform' }))

    expect(await screen.findByRole('heading', { name: 'Private Access' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Enter access password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Unlock AMQUANT/i })).toBeInTheDocument()
  })

  it('unlocks the platform when valid password is provided', async () => {
    const verifySpy = vi.spyOn(api, 'verifyAccessPassword').mockResolvedValue({
      ok: true,
      session_token: 'valid-jwt-token',
      expires_at: '2026-11-20T00:00:00Z',
    })

    render(
      <AccessProvider>
        <PasswordGate>
          <ProtectedApp />
        </PasswordGate>
      </AccessProvider>
    )

    // Lock first
    fireEvent.click(screen.getByRole('button', { name: 'Lock Platform' }))

    // Now gate is visible
    expect(await screen.findByRole('heading', { name: 'Private Access' })).toBeInTheDocument()

    const input = screen.getByLabelText(/Enter access password/i)
    fireEvent.change(input, { target: { value: 'amquant2026' } })
    fireEvent.click(screen.getByRole('button', { name: /Unlock AMQUANT/i }))

    await waitFor(() => expect(verifySpy).toHaveBeenCalledWith('amquant2026'))
    expect(await screen.findByRole('heading', { name: 'Protected Financial Platform' })).toBeInTheDocument()
  })

  it('displays error message when invalid password is entered', async () => {
    vi.spyOn(api, 'verifyAccessPassword').mockRejectedValue(new Error('Incorrect access password. 4 attempts remaining.'))

    render(
      <AccessProvider>
        <PasswordGate>
          <ProtectedApp />
        </PasswordGate>
      </AccessProvider>
    )

    // Lock first
    fireEvent.click(screen.getByRole('button', { name: 'Lock Platform' }))

    // Now gate is visible
    expect(await screen.findByRole('heading', { name: 'Private Access' })).toBeInTheDocument()

    const input = screen.getByLabelText(/Enter access password/i)
    fireEvent.change(input, { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: /Unlock AMQUANT/i }))

    expect(await screen.findByText(/Incorrect access password. 4 attempts remaining./i)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Protected Financial Platform' })).not.toBeInTheDocument()
  })

  it('displays rate-limit lockout cooldown on 429 status', async () => {
    const rateLimitError: any = new Error('Too many failed attempts. Access locked for 15 minutes.')
    rateLimitError.status = 429
    rateLimitError.retryAfter = 900
    vi.spyOn(api, 'verifyAccessPassword').mockRejectedValue(rateLimitError)

    render(
      <AccessProvider>
        <PasswordGate>
          <ProtectedApp />
        </PasswordGate>
      </AccessProvider>
    )

    // Lock first
    fireEvent.click(screen.getByRole('button', { name: 'Lock Platform' }))

    expect(await screen.findByRole('heading', { name: 'Private Access' })).toBeInTheDocument()

    const input = screen.getByLabelText(/Enter access password/i)
    fireEvent.change(input, { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: /Unlock AMQUANT/i }))

    expect(await screen.findByText(/Too many failed attempts/i)).toBeInTheDocument()
    expect(screen.getByText(/Cooldown active:/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Locked/i })).toBeDisabled()
  })
})
