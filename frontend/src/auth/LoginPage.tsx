import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Role, User } from '../api/types'
import background from '../assets/login-background.jpg'
import logo from '../assets/kiet-logo.png'
import { Icon } from '../components/icons'
import { homeFor, useAuth } from './AuthContext'

const PATH: Record<Role, string> = { DEAN: '/auth/dean/login/', VC: '/auth/vc/login/' }
const ROLES: { role: Role; to: string; label: string; icon: 'person' | 'people' }[] = [
  { role: 'DEAN', to: '/dean/login', label: 'Dean', icon: 'person' },
  { role: 'VC', to: '/vc/login', label: 'Vice Chancellor', icon: 'people' },
]

/** Approved UI-0 sign-in layout: campus photograph, centred card, logo, portal name. Used by "/", /dean/login and /vc/login. */
export function LoginLayout({ title = 'Sign in', subtitle, children }: { title?: string; subtitle: string; children: ReactNode }) {
  return (
    <main className="relative isolate grid min-h-screen place-items-center px-3 py-5 max-md:place-items-start md:px-4 md:py-10">
      <div aria-hidden="true" className="absolute inset-0 -z-20 bg-cover bg-[position:62%_100%] bg-no-repeat saturate-[.85] md:bg-[position:left_top]"
        style={{ backgroundImage: `url(${background})` }} />
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[rgba(12,45,71,.22)]" />
      <section className="grid w-full max-w-[540px] justify-items-center gap-4 rounded-xl bg-white px-5 pb-4 pt-6 shadow-[0_10px_30px_rgba(12,45,71,.25)] md:gap-[18px] md:px-11 md:pb-5 md:pt-9">
        <img src={logo} width={974} height={360} alt="KIET Deemed to be University" className="h-auto w-[260px] max-w-full md:w-[400px]" />
        <p className="flex w-full items-center gap-4 text-lg font-bold text-brand before:h-0.5 before:flex-1 before:bg-brand/75 after:h-0.5 after:flex-1 after:bg-brand/75 md:text-[22px]">
          KRA Reporting Portal</p>
        <div className="text-center">
          <h1 className="text-[28px] font-bold leading-tight md:text-[34px]">{title}</h1>
          <p className="mt-1.5 text-muted">{subtitle}</p>
        </div>
        {children}
        <p className="w-full border-t border-line pt-3.5 text-center text-sm text-muted">
          <span className="mr-1.5 inline-block align-[-3px]"><Icon name="lock" size={16} /></span>Authorized KIET Deans and the Vice Chancellor only.</p>
      </section>
    </main>
  )
}

/** Two links to the existing, separate role routes; the current route is marked. Each form only accepts its own role. */
export function RoleSelector({ current }: { current?: Role }) {
  return (
    <nav aria-label="Sign in as" className="grid w-full max-w-96 grid-cols-2 rounded-full bg-[#EBEFF3] p-1">
      {ROLES.map((r) => (
        <Link key={r.role} to={r.to} aria-current={current === r.role ? 'page' : undefined}
          className={`flex min-h-11 items-center justify-center gap-2.5 rounded-full font-semibold ${current === r.role ? 'bg-action text-white' : 'text-heading hover:bg-[#DCE3EA]'}`}>
          <span className="max-md:hidden"><Icon name={r.icon} /></span>{r.label}
        </Link>
      ))}
    </nav>
  )
}

export function Landing() {
  return <LoginLayout subtitle="Choose your role to sign in."><RoleSelector /></LoginLayout>
}

export default function LoginPage({ role }: { role: Role }) {
  const { user, loading, setUser, logout } = useAuth()
  const nav = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (loading) return null
  if (user && user.role === role) return <Navigate to={homeFor(user)} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const u = await api<User>(PATH[role], { method: 'POST', body: { username, password } })
      setUser(u)
      nav(u.must_change_password ? '/change-password' : homeFor(u), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.')
    } finally { setBusy(false) }
  }

  const field = 'input min-h-[50px] pl-12'
  return (
    <LoginLayout subtitle="Choose your role, then enter your portal account.">
      <RoleSelector current={role} />
      {user && user.role !== role ? (
        <div role="alert" className="w-full space-y-3 rounded-lg bg-subtle p-4 text-sm">
          <p>You are signed in to the {user.role === 'VC' ? 'Vice Chancellor' : 'Dean'} portal as {user.name}.</p>
          <div className="flex flex-wrap gap-2">
            <Link className="btn-primary" to={homeFor(user)}>Return to my portal</Link>
            <button className="btn-secondary" onClick={() => logout()}>Sign out</button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="grid w-full gap-3.5" noValidate>
          <div className="relative">
            <label className="sr-only" htmlFor="username">Username</label>
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"><Icon name="person" /></span>
            <input id="username" className={field} autoComplete="username" placeholder="Username" value={username} required
              aria-invalid={!!error} aria-describedby={error ? 'login-error' : undefined} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="relative">
            <label className="sr-only" htmlFor="password">Password</label>
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"><Icon name="lock" /></span>
            <input id="password" className={`${field} pr-12`} type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Password"
              value={password} required aria-invalid={!!error} aria-describedby={error ? 'login-error' : undefined} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(!show)}
              className="absolute right-1.5 top-1/2 grid -translate-y-1/2 place-items-center rounded-md p-2 text-muted hover:text-heading">
              <Icon name={show ? 'eyeOff' : 'eye'} /></button>
          </div>
          {error && <p id="login-error" role="alert" className="text-sm text-err"><b>Error:</b> {error}</p>}
          <button className="btn-signin btn min-h-[54px] w-full bg-accent-btn text-lg font-bold text-white hover:bg-accent-btn-hover disabled:border-transparent disabled:bg-accent-btn disabled:text-white disabled:opacity-60"
            disabled={busy || !username || !password}>
            {busy ? 'Signing in…' : <>Sign in <Icon name="arrow" /></>}
          </button>
        </form>
      )}
    </LoginLayout>
  )
}
