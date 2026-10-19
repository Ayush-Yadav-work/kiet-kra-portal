import { useEffect, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import type { DisplayStatus, Role } from '../api/types'
import { api } from '../api/client'
import { homeFor, useAuth } from '../auth/AuthContext'
import logo from '../assets/kiet-logo.png'
import { Icon, type IconName } from './icons'

const STATUS: Record<DisplayStatus, [string, string]> = {
  NOT_SUBMITTED: ['Not submitted', 'bg-neutral-bg text-neutral'],
  DRAFT: ['Draft', 'bg-warn-bg text-warn'],
  SUBMITTED: ['Submitted', 'bg-info-bg text-info'],
  REJECTED: ['Rejected', 'bg-err-bg text-err'],
  APPROVED: ['Approved', 'bg-ok-bg text-ok'],
}
export const statusLabel = (s: DisplayStatus) => STATUS[s][0]

const TONE: Record<DisplayStatus | 'ASSIGNED', [IconName, string]> = {
  ASSIGNED: ['doc', 'bg-info-bg text-info'], NOT_SUBMITTED: ['circle', 'bg-neutral-bg text-neutral'], DRAFT: ['pencil', 'bg-warn-bg text-warn'],
  SUBMITTED: ['send', 'bg-info-bg text-info'], REJECTED: ['undo', 'bg-err-bg text-err'], APPROVED: ['check', 'bg-ok-bg text-ok'],
}
/** Compact summary card (approved UI-0 dashboard). With `onClick` it is a toggle button (`pressed` = selected filter). */
export function StatCard({ kind, value, label, onClick, pressed }: { kind: DisplayStatus | 'ASSIGNED'; value: number; label: string; onClick?: () => void; pressed?: boolean }) {
  const [icon, tone] = TONE[kind]
  const body = <>
    <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-full md:h-11 md:w-11 ${tone}`}><Icon name={icon} /></span>
    <span className="text-left"><span className="block text-2xl font-bold leading-tight text-heading md:text-[28px]">{value}</span><span className="text-sm text-ink md:text-[15px]">{label}</span></span>
  </>
  const cls = `flex items-center gap-3 rounded-[10px] border bg-white px-3 py-3 md:px-4 ${pressed ? 'border-action ring-2 ring-action' : kind === 'ASSIGNED' ? 'border-[#B9CDE0]' : 'border-line'}`
  return onClick ? <button type="button" className={`${cls} hover:border-action`} aria-pressed={pressed} onClick={onClick}>{body}</button> : <div className={cls}>{body}</div>
}

export function StatusBadge({ status }: { status: DisplayStatus }) {
  const [label, cls] = STATUS[status] ?? [status, 'bg-neutral-bg text-neutral']
  return <span className={`inline-block whitespace-nowrap rounded-full px-3 py-0.5 text-[13px] font-semibold ${cls}`}>{label}</span>
}

export function ErrorBox({ error }: { error?: string | null }) {
  return error ? <p role="alert" className="rounded-lg border-l-4 border-err bg-err-bg px-3 py-2 text-sm text-[#7F1D1D]">{error}</p> : null
}

export function Loading() {
  return <p className="p-4 text-sm text-muted" aria-live="polite">Loading…</p>
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

/** WAI-ARIA tabs keyboard pattern for a role="tablist": arrows/Home/End move to and select a tab (roving tabindex). */
export function tabKeys(e: KeyboardEvent<HTMLElement>) {
  const tabs = [...e.currentTarget.querySelectorAll<HTMLElement>('[role=tab]')]
  const i = tabs.indexOf(document.activeElement as HTMLElement)
  const next = i < 0 ? undefined : ({ ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 } as Record<string, number>)[e.key]
  if (next === undefined) return
  e.preventDefault()
  const t = tabs[(next + tabs.length) % tabs.length]
  t.focus(); t.click()
}

const NAV: Record<Role, { to: string; label: string; icon: IconName }[]> = {
  DEAN: [{ to: '/dean/dashboard', label: 'Dashboard', icon: 'home' }, { to: '/dean/announcements', label: 'Announcements', icon: 'bell' }],
  VC: [{ to: '/vc/dashboard', label: 'Dashboard', icon: 'home' }, { to: '/vc/analytics', label: 'Analytics', icon: 'doc' },
       { to: '/vc/reopen-requests', label: 'Reopening requests', icon: 'list' }, { to: '/vc/assignments', label: 'Annual assignments', icon: 'list' },
       { to: '/vc/kras', label: 'KRAs', icon: 'list' }, { to: '/vc/announcements', label: 'Announcements', icon: 'bell' }],
}
const initials = (name: string) => name.replace(/^(Dr|Prof|Mr|Ms|Mrs)\.?\s+/i, '').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase()

/** Approved UI-0 header: logo, product name, existing destinations only, user and Sign out; on phones the links wrap below. */
function useUnread(enabled: boolean) {
  const { pathname } = useLocation()
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let live = true
    const load = () => api<{ unread_count: number }>('/announcements/unread-count/').then((r) => live && setN(r.unread_count)).catch(() => {})
    load()
    window.addEventListener('focus', load)
    window.addEventListener('kra:announcements-read', load)
    return () => { live = false; window.removeEventListener('focus', load); window.removeEventListener('kra:announcements-read', load) }
  }, [enabled, pathname])
  return n
}

function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const unread = useUnread(user?.role === 'DEAN')
  if (!user) return null
  const links = [...NAV[user.role], { to: '/change-password', label: 'Change password', icon: 'lock' as IconName }]
  const roleLine = user.role === 'VC' ? 'Vice Chancellor' : `Dean, ${user.department?.code ?? ''}`
  const vc = user.role === 'VC'  // the VC's seven links always get their own row (one row overflowed at 1536 px)
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className={`mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-7 gap-y-2 px-4 py-2 md:px-7 ${vc ? '' : 'xl:min-h-[72px] xl:flex-nowrap xl:py-0'}`}>
          <Link to={homeFor(user)} aria-label="KIET KRA Reporting Portal — home" className="shrink-0"><img src={logo} width={974} height={360} alt="" className="h-auto w-28 md:w-[150px]" /></Link>
          <span className={`hidden whitespace-nowrap border-l border-line pl-6 text-xl font-bold text-heading ${vc ? '2xl:inline' : 'lg:inline'}`}>KRA Reporting Portal</span>
          <nav aria-label="Main" className={`order-3 flex w-full flex-wrap gap-x-1 self-stretch ${vc ? '' : 'xl:order-none xl:ml-2 xl:w-auto xl:flex-nowrap'}`}>
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end
                className={({ isActive }) => `flex min-h-11 items-center gap-2 whitespace-nowrap border-b-[3px] px-3 text-[15px] ${isActive ? 'border-accent font-semibold text-action' : 'border-transparent font-medium text-heading hover:text-action'}`}>
                <Icon name={l.icon} />{l.label}
                {l.to === '/dean/announcements' && unread > 0 && <span className="sr-only"> </span>}
                {l.to === '/dean/announcements' && unread > 0 && <span className="rounded-full bg-accent-btn px-1.5 text-xs font-bold text-white">{unread}<span className="sr-only"> unread</span></span>}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3.5">
            <span aria-hidden="true" className="grid h-9 w-9 place-items-center rounded-full bg-brand text-sm font-bold text-white md:h-10 md:w-10">{initials(user.name)}</span>
            <span className="hidden leading-tight sm:block"><b className="block text-heading">{user.name}</b><span className="text-sm text-muted">{roleLine}</span></span>
            <span aria-hidden="true" className="hidden h-8 w-px bg-line sm:block" />
            <button className="btn-secondary min-h-9 px-3.5 text-sm" onClick={() => logout()}>Sign out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] p-4 md:px-7 md:py-6">{children}</main>
    </div>
  )
}
