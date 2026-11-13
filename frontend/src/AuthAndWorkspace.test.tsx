import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./lib/api', async () => {
  const actual = await vi.importActual<typeof import('./lib/api')>('./lib/api')
  return {
    ...actual,
    checkAccessStatus: vi.fn().mockResolvedValue({ authenticated: true }),
    checkApiHealth: vi.fn().mockResolvedValue(true),
    listSavedScenarios: vi.fn().mockResolvedValue([
      {
        id: 'scenario-uuid-1',
        user_id: 'user-uuid-1',
        title: 'Calibrated Options Smile',
        module_name: 'options',
        scenario_data: { spot: '150', strike: '160', maturity: '0.75', volatility: '0.28', rate: '0.05', kind: 'call', steps: '100' },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]),
    listResearchHistory: vi.fn().mockResolvedValue([
      {
        id: 'hist-uuid-1',
        user_id: 'user-uuid-1',
        module_name: 'options',
        scenario_id: 'scenario-uuid-1',
        summary: { bsm_price: 12.34, delta: 0.58 },
        created_at: new Date().toISOString(),
      },
    ]),
  }
})

describe('AMQUANT Auth & Personal Workspace Frontend', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  beforeEach(() => {
    window.history.pushState({}, '', '/global')
    render(<App />)
  })

  it('renders guest mode with clear option to sign in or register', () => {
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument()
  })

  it('opens the authentication modal when Sign In is clicked', () => {
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    const modal = screen.getByRole('dialog')
    expect(modal).toBeInTheDocument()
    expect(within(modal).getByRole('heading', { name: 'Sign in to Terminal' })).toBeInTheDocument()
    expect(within(modal).getByPlaceholderText('analyst@firm.com')).toBeInTheDocument()
    expect(within(modal).getByPlaceholderText('••••••••')).toBeInTheDocument()
  })

  it('switches between Sign In, Register, and Forgot Password in modal', () => {
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    const modal = screen.getByRole('dialog')
    
    // Switch to Register tab
    const registerTab = within(modal).getAllByRole('button', { name: /register/i })[0]
    fireEvent.click(registerTab)
    expect(within(modal).getByText(/Tester accounts are by invitation only/i)).toBeInTheDocument()
    expect(within(modal).getByRole('button', { name: 'Back to Sign In' })).toBeInTheDocument()

    // Switch back to Sign In tab using footer button
    const backToSignIn = within(modal).getByRole('button', { name: 'Back to Sign In' })
    fireEvent.click(backToSignIn)
    expect(within(modal).getByRole('heading', { name: 'Sign in to Terminal' })).toBeInTheDocument()

    // Click Forgot password link
    fireEvent.click(within(modal).getByText('Forgot password?'))
    expect(within(modal).getByRole('heading', { name: 'Reset Terminal Access' })).toBeInTheDocument()
    expect(within(modal).getByRole('button', { name: 'Send Recovery Link' })).toBeInTheDocument()

    // Close modal
    fireEvent.click(within(modal).getByLabelText('Close authentication modal'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders guest workspace screen when navigating to Personal Workspace without logging in', () => {
    fireEvent.click(screen.getByRole('button', { name: /Personal Workspace/i }))
    expect(screen.getByRole('heading', { name: 'Personal Research Workspace' })).toBeInTheDocument()
    expect(screen.getByText('Authentication Optional · Workspace Powered by Supabase')).toBeInTheDocument()
    expect(screen.getByText(/Guest access remains unrestricted across all five quantitative engines/i)).toBeInTheDocument()
  })

  it('allows guests to open any calculation module and see Save Scenario button', () => {
    fireEvent.click(screen.getByRole('button', { name: /Options Lab/i }))
    expect(screen.getByRole('heading', { name: 'Options Lab' })).toBeInTheDocument()
    
    // Save scenario button is present
    const saveBtn = screen.getByRole('button', { name: 'Save Scenario' })
    expect(saveBtn).toBeInTheDocument()

    // Clicking it as guest invites user to sign in
    fireEvent.click(saveBtn)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Sign in to save this option scenario to your personal workspace.')).toBeInTheDocument()
  })
})
