import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { isSupabaseConfigured, supabase } from '../lib/supabase'

export interface UserProfile {
  id: string
  email: string
  display_name: string | null
  created_at?: string
  updated_at?: string
}

export type AuthModalMode = 'login' | 'register' | 'forgot' | 'update_password'

interface AuthContextType {
  user: User | null
  session: Session | null
  profile: UserProfile | null
  loading: boolean
  isConfigured: boolean
  authModalOpen: boolean
  authModalMode: AuthModalMode
  authModalMessage: string | null
  openAuthModal: (mode?: AuthModalMode, message?: string | null) => void
  closeAuthModal: () => void
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>
  signUp: (email: string, password: string, displayName?: string) => Promise<{ error: Error | null; needsEmailVerification: boolean }>
  signOut: () => Promise<void>
  resetPassword: (email: string) => Promise<{ error: Error | null }>
  updatePassword: (password: string) => Promise<{ error: Error | null }>
  updateDisplayName: (displayName: string) => Promise<{ error: Error | null }>
  refreshProfile: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [authModalOpen, setAuthModalOpen] = useState<boolean>(false)
  const [authModalMode, setAuthModalMode] = useState<AuthModalMode>('login')
  const [authModalMessage, setAuthModalMessage] = useState<string | null>(null)

  const openAuthModal = (mode: AuthModalMode = 'login', message: string | null = null) => {
    setAuthModalMode(mode)
    setAuthModalMessage(message)
    setAuthModalOpen(true)
  }

  const closeAuthModal = () => {
    setAuthModalOpen(false)
    setAuthModalMessage(null)
  }

  const fetchProfile = async (accessToken: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      if (res.ok) {
        const data = (await res.json()) as UserProfile
        setProfile(data)
      } else {
        setProfile(null)
      }
    } catch {
      setProfile(null)
    }
  }

  const refreshProfile = async () => {
    if (session?.access_token) {
      await fetchProfile(session.access_token)
    }
  }

  useEffect(() => {
    if (!isSupabaseConfigured || !supabase) {
      setLoading(false)
      return
    }

    let mounted = true

    // Restore initial session
    void supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      if (!mounted) return
      setSession(initialSession)
      setUser(initialSession?.user ?? null)
      if (initialSession?.access_token) {
        void fetchProfile(initialSession.access_token)
      }
      setLoading(false)
    })

    // Listen for auth state transitions (login, logout, token refresh, password recovery)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, currentSession) => {
      if (!mounted) return
      setSession(currentSession)
      setUser(currentSession?.user ?? null)

      if (event === 'SIGNED_OUT') {
        setProfile(null)
      } else if (currentSession?.access_token) {
        void fetchProfile(currentSession.access_token)
      }

      if (event === 'PASSWORD_RECOVERY') {
        openAuthModal('update_password')
      }
    })

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [])

  const signIn = async (email: string, password: string) => {
    if (!isSupabaseConfigured || !supabase) {
      return { error: new Error('Supabase authentication is not configured in this environment.') }
    }
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim(), password })
      if (error) return { error }
      setUser(data.user)
      setSession(data.session)
      if (data.session?.access_token) {
        await fetchProfile(data.session.access_token)
      }
      closeAuthModal()
      return { error: null }
    } catch (err) {
      return { error: err instanceof Error ? err : new Error('Sign in failed') }
    }
  }

  const signUp = async (email: string, password: string, displayName?: string) => {
    if (!isSupabaseConfigured || !supabase) {
      return { error: new Error('Supabase authentication is not configured in this environment.'), needsEmailVerification: false }
    }
    try {
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: { display_name: displayName?.trim() || email.trim().split('@')[0] },
        },
      })
      if (error) return { error, needsEmailVerification: false }
      const needsEmailVerification = !data.session && Boolean(data.user)
      if (data.session) {
        setUser(data.user)
        setSession(data.session)
        if (data.session.access_token) {
          await fetchProfile(data.session.access_token)
        }
        closeAuthModal()
      }
      return { error: null, needsEmailVerification }
    } catch (err) {
      return { error: err instanceof Error ? err : new Error('Sign up failed'), needsEmailVerification: false }
    }
  }

  const signOut = async () => {
    if (isSupabaseConfigured && supabase) {
      await supabase.auth.signOut()
    }
    setUser(null)
    setSession(null)
    setProfile(null)
  }

  const resetPassword = async (email: string) => {
    if (!isSupabaseConfigured || !supabase) {
      return { error: new Error('Supabase authentication is not configured in this environment.') }
    }
    try {
      const redirectTo = `${window.location.origin}`
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo })
      return { error: error ?? null }
    } catch (err) {
      return { error: err instanceof Error ? err : new Error('Password reset failed') }
    }
  }

  const updatePassword = async (password: string) => {
    if (!isSupabaseConfigured || !supabase) {
      return { error: new Error('Supabase authentication is not configured in this environment.') }
    }
    try {
      const { error } = await supabase.auth.updateUser({ password })
      if (!error) closeAuthModal()
      return { error: error ?? null }
    } catch (err) {
      return { error: err instanceof Error ? err : new Error('Password update failed') }
    }
  }

  const updateDisplayName = async (displayName: string) => {
    if (!session?.access_token) {
      return { error: new Error('Authentication required') }
    }
    try {
      const res = await fetch(`${API_BASE}/api/auth/profile`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ display_name: displayName.trim() }),
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => null)
        return { error: new Error(errJson?.detail || 'Failed to update profile') }
      }
      const updated = (await res.json()) as UserProfile
      setProfile(prev => ({ ...prev, ...updated }))
      return { error: null }
    } catch (err) {
      return { error: err instanceof Error ? err : new Error('Profile update failed') }
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        loading,
        isConfigured: isSupabaseConfigured,
        authModalOpen,
        authModalMode,
        authModalMessage,
        openAuthModal,
        closeAuthModal,
        signIn,
        signUp,
        signOut,
        resetPassword,
        updatePassword,
        updateDisplayName,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

