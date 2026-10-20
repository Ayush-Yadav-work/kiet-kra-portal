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

/** Redesign v2 sign-in layout (reference "KIET KRA Tracker Login Portal"): campus photograph, portal title on the left, sign-in
 *  card on the right; stacked on phones. Used by "/", /dean/login, /vc/login and /change-password. */
export function LoginLayout({ title = 'Welcome back', subtitle, children }: { title?: string; subtitle: string; children: ReactNode }) {
  return (
    <main className="relative isolate min-h-screen overflow-hidden">
      <div aria-hidden="true" className="absolute inset-0 -z-20 bg-cover bg-[position:62%_100%] bg-no-repeat md:bg-[position:left_top]"
        style={{ backgroundImage: `url(${background})` }} />
      {/* the photograph carries a small printed logo in its corner: soften it so only the official logo below reads */}
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top_left,rgba(255,255,255,.97)_0,rgba(255,255,255,.9)_14%,transparent_30%),linear-gradient(100deg,rgba(255,255,255,.88)_0%,rgba(255,255,255,.55)_38%,rgba(255,255,255,.08)_62%,rgba(234,242,250,.55)_100%)]" />
      <div className="mx-auto grid min-h-screen max-w-[1440px] items-center gap-6 px-4 py-6 md:px-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,500px)] lg:gap-12 lg:py-10">
        <div className="self-start lg:self-stretch lg:py-2">
          <span className="inline-block rounded-xl bg-white/95 px-3 py-2 shadow-sm">
            <img src={logo} width={974} height={360} alt="KIET Deemed to be University" className="h-auto w-[190px] md:w-[260px]" /></span>
          <div className="mt-6 md:mt-12">
            <p className="text-[44px] font-extrabold leading-none tracking-tight text-heading md:text-[84px]">KRA <span className="text-accent-btn">Tracker</span></p>
            <span aria-hidden="true" className="mt-3 block h-1 w-20 rounded bg-accent md:mt-5 md:w-24" />
            <p className="mt-3 text-lg font-medium tracking-[.25em] text-heading md:mt-5 md:text-[26px]">Key Result Area Portal</p>
            <p className="mt-1 text-sm tracking-[.3em] text-ink md:mt-3 md:text-lg">Track. Review. Lead.</p>
          </div>
        </div>
        <section className="grid w-full gap-4 rounded-2xl bg-white px-5 pb-5 pt-6 shadow-[0_18px_50px_rgba(12,45,71,.22)] md:gap-5 md:px-10 md:pb-7 md:pt-10">
          <div>
            <h1 className="text-[30px] font-extrabold leading-tight md:text-[42px]">{title}</h1>
            <p className="mt-1 text-lg text-muted md:text-xl">{subtitle}</p>
          </div>
          {children}
          <p className="w-full border-t border-line pt-3.5 text-center text-sm text-muted">
            <span className="mr-1.5 inline-block align-[-3px]"><Icon name="lock" size={16} /></span>For KIET Deans and the Vice Chancellor only.</p>
        </section>
      </div>
    </main>
  )
}

/** Two links to the existing, separate role routes; the current route is marked. Each form only accepts its own role. */
export function RoleSelector({ current }: { current?: Role }) {
  return (
    <nav aria-label="Sign in as" className="grid w-full grid-cols-2 gap-1 rounded-xl bg-[#EEF2F6] p-1">
      {ROLES.map((r) => (
        <Link key={r.role} to={r.to} aria-current={current === r.role ? 'page' : undefined}
          className={`flex min-h-12 items-center justify-center gap-2.5 rounded-lg font-semibold ${current === r.role ? 'bg-accent-btn text-white shadow-sm' : 'text-heading hover:bg-[#E1E8EF]'}`}>
          <Icon name={r.icon} />{r.label}
        </Link>
      ))}
    </nav>
  )
}

export function Landing() {
  return <LoginLayout subtitle="Sign in to the KRA Reporting Portal. Choose your role."><RoleSelector /></LoginLayout>
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

  const field = 'input min-h-[52px] pl-12'
  return (
    <LoginLayout subtitle={`Sign in to the KRA Reporting Portal as ${role === 'VC' ? 'Vice Chancellor' : 'Dean'}.`}>
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
          <label className="label mb-0" htmlFor="username">Username</label>
          <div className="relative -mt-2">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"><Icon name="person" /></span>
            <input id="username" className={field} autoComplete="username" placeholder="Your portal username" value={username} required
              aria-invalid={!!error} aria-describedby={error ? 'login-error' : undefined} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <label className="label mb-0" htmlFor="password">Password</label>
          <div className="relative -mt-2">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"><Icon name="lock" /></span>
            <input id="password" className={`${field} pr-12`} type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password"
              value={password} required aria-invalid={!!error} aria-describedby={error ? 'login-error' : undefined} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(!show)}
              className="absolute right-1.5 top-1/2 grid -translate-y-1/2 place-items-center rounded-md p-2 text-muted hover:text-heading">
              <Icon name={show ? 'eyeOff' : 'eye'} /></button>
          </div>
          {error && <p id="login-error" role="alert" className="text-sm text-err"><b>Error:</b> {error}</p>}
          <button className="btn-signin btn mt-1 min-h-[56px] w-full rounded-xl bg-accent-btn text-lg font-bold shadow-[0_8px_20px_rgba(200,70,26,.28)] text-white hover:bg-accent-btn-hover disabled:border-transparent disabled:bg-accent-btn disabled:text-white disabled:opacity-60"
            disabled={busy || !username || !password}>
            {busy ? 'Signing in…' : <>Sign in <Icon name="arrow" /></>}
          </button>
        </form>
      )}
    </LoginLayout>
  )
}
