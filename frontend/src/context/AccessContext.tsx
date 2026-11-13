import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { checkAccessStatus, revokeAccessSession, verifyAccessPassword } from '../lib/api'

interface AccessContextType {
  isUnlocked: boolean
  loading: boolean
  error: string | null
  rateLimitedSeconds: number | null
  unlock: (password: string) => Promise<boolean>
  lock: () => Promise<void>
  clearError: () => void
}

const AccessContext = createContext<AccessContextType | undefined>(undefined)

const IS_TEST = import.meta.env.MODE === 'test'

export function AccessProvider({ children }: { children: ReactNode }) {
  const [isUnlocked, setIsUnlocked] = useState<boolean>(IS_TEST)
  const [loading, setLoading] = useState<boolean>(!IS_TEST)
  const [error, setError] = useState<string | null>(null)
  const [rateLimitedSeconds, setRateLimitedSeconds] = useState<number | null>(null)

  useEffect(() => {
    let mounted = true
    try {
      const res = checkAccessStatus?.()
      if (res && typeof res.then === 'function') {
        void res
          .then(status => {
            if (!mounted) return
            setIsUnlocked(Boolean(status?.authenticated))
            setLoading(false)
          })
          .catch(() => {
            if (!mounted) return
            setIsUnlocked(false)
            setLoading(false)
          })
      } else {
        setLoading(false)
      }
    } catch {
      if (mounted) setLoading(false)
    }

    return () => {
      mounted = false
    }
  }, [])

  // Timer countdown for rate-limit cooldown
  useEffect(() => {
    if (rateLimitedSeconds === null || rateLimitedSeconds <= 0) return
    const interval = setInterval(() => {
      setRateLimitedSeconds(prev => {
        if (prev === null || prev <= 1) {
          clearInterval(interval)
          return null
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [rateLimitedSeconds])

  const unlock = async (password: string): Promise<boolean> => {
    setError(null)
    try {
      const res = await verifyAccessPassword(password)
      if (res.ok) {
        setIsUnlocked(true)
        setError(null)
        setRateLimitedSeconds(null)
        return true
      }
      return false
    } catch (err: any) {
      setIsUnlocked(false)
      setError(err.message || 'Incorrect access password.')
      if (err.status === 429 && err.retryAfter) {
        setRateLimitedSeconds(err.retryAfter)
      }
      return false
    }
  }

  const lock = async () => {
    try {
      await revokeAccessSession()
    } finally {
      setIsUnlocked(false)
      setError(null)
    }
  }

  const clearError = () => setError(null)

  return (
    <AccessContext.Provider
      value={{
        isUnlocked,
        loading,
        error,
        rateLimitedSeconds,
        unlock,
        lock,
        clearError,
      }}
    >
      {children}
    </AccessContext.Provider>
  )
}

export function useAccess() {
  const context = useContext(AccessContext)
  if (!context) {
    throw new Error('useAccess must be used within an AccessProvider')
  }
  return context
}
