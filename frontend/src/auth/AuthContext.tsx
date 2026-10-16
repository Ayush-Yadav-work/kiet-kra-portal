import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ensureCsrf } from '../api/client'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean
  setUser: (u: User | null) => void
  refresh: () => Promise<void>
  logout: () => Promise<void>
}

const Ctx = createContext<AuthState>(null as unknown as AuthState)
const CHANNEL = 'kiet-kra-auth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      await ensureCsrf()
      setUser(await api<User>('/auth/me/'))
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    try { await api('/auth/logout/', { method: 'POST' }) } finally {
      setUser(null)
      // Logout ends the shared session; tell other tabs (plan 2.1.1).
      try { new BroadcastChannel(CHANNEL).postMessage('logout') } catch { /* unsupported */ }
      await ensureCsrf()
    }
  }, [])

  useEffect(() => {
    refresh()
    let bc: BroadcastChannel | null = null
    try {
      bc = new BroadcastChannel(CHANNEL)
      bc.onmessage = () => setUser(null)
    } catch { /* unsupported */ }
    const onUnauth = () => setUser(null)
    window.addEventListener('kra:unauthenticated', onUnauth)
    return () => { bc?.close(); window.removeEventListener('kra:unauthenticated', onUnauth) }
  }, [refresh])

  return <Ctx.Provider value={{ user, loading, setUser, refresh, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
export const homeFor = (u: User) => (u.role === 'VC' ? '/vc/dashboard' : '/dean/dashboard')
