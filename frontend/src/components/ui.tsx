import { useEffect, useState, type ReactNode } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import type { DisplayStatus, Role } from '../api/types'
import { homeFor, useAuth } from '../auth/AuthContext'

const STATUS: Record<DisplayStatus, [string, string]> = {
  NOT_SUBMITTED: ['Not submitted', 'bg-slate-100 text-slate-700'],
  DRAFT: ['Draft', 'bg-amber-100 text-amber-900'],
  SUBMITTED: ['Submitted', 'bg-blue-100 text-blue-900'],
  REJECTED: ['Rejected', 'bg-red-100 text-red-900'],
  APPROVED: ['Approved', 'bg-green-100 text-green-900'],
}
export const statusLabel = (s: DisplayStatus) => STATUS[s][0]

export function StatusBadge({ status }: { status: DisplayStatus }) {
  const [label, cls] = STATUS[status] ?? [status, 'bg-slate-100']
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>
}

export function ErrorBox({ error }: { error?: string | null }) {
  return error ? <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-800">{error}</p> : null
}

export function Loading() {
  return <p className="p-4 text-sm text-slate-500" aria-live="polite">Loading…</p>
}

/** Countdown from server-provided expiry and server time; the browser only displays it (C9). */
export function useServerClock(serverTime?: string) {
  const [offset] = useState(() => (serverTime ? new Date(serverTime).getTime() - Date.now() : 0))
  const [now, setNow] = useState(() => Date.now() + offset)
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() + offset), 30_000)
    return () => clearInterval(t)
  }, [offset])
  return now
}

export function timeLeft(expires: string, now: number) {
  const ms = new Date(expires).getTime() - now
  if (ms <= 0) return 'Expired'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  return `Expires in ${h}h ${m}m`
}

export function RequireRole({ role }: { role: Role }) {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return <Loading />
  if (!user) return <Navigate to={role === 'VC' ? '/vc/login' : '/dean/login'} replace state={{ from: loc.pathname }} />
  if (user.must_change_password) return <Navigate to="/change-password" replace />
  if (user.role !== role) return <Navigate to={homeFor(user)} replace />
  return <Shell><Outlet /></Shell>
}

function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  if (!user) return null
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-2">
          <Link to={homeFor(user)} className="font-semibold text-blue-900">KIET KRA Portal</Link>
          <span className="text-sm text-slate-600">{user.role === 'VC' ? 'Vice Chancellor' : `Dean — ${user.department?.name}`}</span>
          <nav className="ml-auto flex items-center gap-3 text-sm">
            {user.role === 'VC' && <Link className="underline" to="/vc/reopen-requests">Reopening requests</Link>}
            <span className="text-slate-600">{user.name}</span>
            <Link className="underline" to="/change-password">Change password</Link>
            <button className="btn-secondary" onClick={() => logout()}>Sign out</button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl p-4">{children}</main>
    </div>
  )
}
