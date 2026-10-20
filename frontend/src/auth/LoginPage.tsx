import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Role, User } from '../api/types'
import background from '../assets/login-background.png'
import logo from '../assets/kiet-logo.png'
import { Icon } from '../components/icons'
import { homeFor, useAuth } from './AuthContext'

const PATH: Record<Role, string> = { DEAN: '/auth/dean/login/', VC: '/auth/vc/login/' }
const ROLES: { role: Role; to: string; label: string; sr?: string; icon: 'person' | 'people' }[] = [
  { role: 'DEAN', to: '/dean/login', label: 'Dean', icon: 'person' },
  { role: 'VC', to: '/vc/login', label: 'VC', sr: 'Vice Chancellor', icon: 'people' },
]

/** Sign-in layout matching reference/ui/redesign-v2/login-reference.png. The campus photograph is always shown complete:
 *  an <img> in a box with the photo's own aspect ratio, never larger than its native 1672 px (no cropping, stretching or
 *  upscaling), on a solid sky colour. From 1280 px the title and the card sit over the photo as in the reference; below that
 *  title, photo and card stack. Used by "/", /dean/login, /vc/login and /change-password; styles are local to this file. */
export function LoginLayout({ title = 'Welcome Back', subtitle, children }: { title?: string; subtitle: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#E3EEF9] px-4 py-6 sm:px-8 xl:p-0">
      <div className="@container relative flex w-full max-w-[1672px] flex-col gap-5 xl:block xl:aspect-[1672/941] xl:w-[min(100vw,1672px,calc(100vh*1672/941))]">
        <div className="relative xl:absolute xl:inset-0">
          <img src={background} width={1672} height={941} alt="" className="mx-auto block h-auto w-full rounded-2xl shadow-[0_8px_24px_rgba(12,45,71,.12)] xl:h-full xl:rounded-none xl:shadow-none" />
          {/* local, not full-photo: hides the small logo printed in the photo's corner, and lifts the sky behind the title */}
          <div aria-hidden="true" className="absolute inset-0 rounded-2xl bg-[radial-gradient(ellipse_18%_19%_at_5%_7%,rgba(227,238,249,1)_0,rgba(227,238,249,.98)_68%,transparent_100%)] xl:rounded-none xl:bg-[radial-gradient(ellipse_18%_19%_at_5%_7%,rgba(255,255,255,1)_0,rgba(255,255,255,.98)_68%,transparent_100%),radial-gradient(ellipse_40%_36%_at_19%_30%,rgba(255,255,255,.84)_0,rgba(255,255,255,.66)_55%,transparent_100%)]" />
        </div>
        <div className="relative -order-1 xl:absolute xl:left-[5.7%] xl:top-[4.3%] xl:order-none">
          <img src={logo} width={974} height={360} alt="KIET Deemed to be University" className="h-auto w-[170px] mix-blend-multiply md:w-[220px] xl:w-[15.7cqw]" />
          <div className="mt-4 xl:mt-[4.6cqw] xl:[text-shadow:0_0_10px_rgba(255,255,255,.95),0_0_2px_rgba(255,255,255,.9)]">
            <p className="text-[42px] font-extrabold leading-[.95] tracking-[-.02em] text-heading sm:text-[56px] xl:text-[6.2cqw]">KRA <span className="text-accent">Tracker</span></p>
            <span aria-hidden="true" className="mt-2.5 block h-[5px] w-16 rounded-full bg-accent xl:mt-[1.1cqw] xl:w-[4.9cqw]" />
            <p className="mt-2.5 text-base font-medium tracking-[.3em] text-heading sm:text-xl xl:mt-[1.2cqw] xl:text-[1.8cqw]">Key Result Area Portal</p>
            <p className="mt-1.5 text-sm font-medium tracking-[.36em] text-heading xl:mt-[1.4cqw] xl:text-[1.2cqw]">Track. Review. Lead.</p>
          </div>
        </div>
        <section className="relative mx-auto grid w-full max-w-[440px] gap-[18px] rounded-3xl bg-white px-5 pb-6 pt-7 shadow-[0_20px_50px_rgba(12,45,71,.2)] sm:px-9 sm:pb-7 sm:pt-10 xl:absolute xl:right-[4.3%] xl:top-1/2 xl:mx-0 xl:-translate-y-1/2">
          <div>
            <h1 className="text-[30px] font-extrabold leading-tight tracking-[-.01em] text-[#0A1A3A] sm:text-[38px]">{title}</h1>
            <p className="mt-0.5 text-lg text-muted sm:text-xl">{subtitle}</p>
          </div>
          {children}
          <p className="w-full border-t border-[#E3E9EF] pt-4 text-center text-sm text-muted">For KIET leadership access.</p>
        </section>
      </div>
    </main>
  )
}

/** Two links to the existing, separate role routes; the current route is marked. Each form only accepts its own role. */
export function RoleSelector({ current }: { current?: Role }) {
  return (
    <nav aria-label="Sign in as" className="grid w-full grid-cols-2 gap-1 rounded-xl bg-[#EFF2F6] p-1">
      {ROLES.map((r) => (
        <Link key={r.role} to={r.to} aria-current={current === r.role ? 'page' : undefined}
          className={`flex min-h-[50px] items-center justify-center gap-2.5 rounded-[10px] text-[19px] font-bold ${current === r.role ? 'bg-accent text-white shadow-[0_6px_14px_rgba(241,91,32,.32)]' : 'text-[#3A4A5E] hover:bg-[#E3E9F0]'}`}>
          <Icon name={r.icon} size={20} />{r.label}{r.sr && <span className="sr-only"> ({r.sr})</span>}
        </Link>
      ))}
    </nav>
  )
}

export function Landing() {
  return <LoginLayout subtitle="Sign in to KRA Tracker. Choose your role."><RoleSelector /></LoginLayout>
}

export default function LoginPage({ role }: { role: Role }) {
  const { user, loading, setUser, logout } = useAuth()
  const nav = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [missing, setMissing] = useState<{ username?: boolean; password?: boolean }>({})

  if (loading) return null
  if (user && user.role === role) return <Navigate to={homeFor(user)} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    const m = { username: !username.trim(), password: !password }
    setMissing(m)
    if (m.username || m.password) {  // say what is missing instead of silently refusing (button stays enabled)
      document.getElementById(m.username ? 'username' : 'password')?.focus()
      return
    }
    setBusy(true); setError('')
    try {
      const u = await api<User>(PATH[role], { method: 'POST', body: { username, password } })
      setUser(u)
      nav(u.must_change_password ? '/change-password' : homeFor(u), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.')
    } finally { setBusy(false) }
  }

  const field = 'input min-h-[50px] rounded-xl border-[#CBD5E1] pl-12 text-base placeholder:text-[#7A8797] aria-[invalid=true]:border-err'
  return (
    <LoginLayout subtitle="Sign in to KRA Tracker">
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
        <form onSubmit={submit} className="grid w-full gap-4" noValidate>
          <div className="grid gap-2">
            <label className="text-base font-medium text-[#0A1A3A]" htmlFor="username">Username</label>
            <div className="relative">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#5B6B7F]"><Icon name="person" /></span>
              <input id="username" className={field} autoComplete="username" autoCapitalize="none" spellCheck={false} placeholder="your.username" value={username} required
                aria-invalid={!!error || !!missing.username} aria-describedby={missing.username ? 'username-missing' : error ? 'login-error' : undefined}
                onChange={(e) => { setUsername(e.target.value); setMissing((m) => ({ ...m, username: false })) }} />
            </div>
            {missing.username && <p id="username-missing" className="text-sm font-medium text-err">Enter your username.</p>}
          </div>
          <div className="grid gap-2">
            <label className="text-base font-medium text-[#0A1A3A]" htmlFor="password">Password</label>
            <div className="relative">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#5B6B7F]"><Icon name="lock" /></span>
              <input id="password" className={`${field} pr-12`} type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password"
                value={password} required aria-invalid={!!error || !!missing.password} aria-describedby={missing.password ? 'password-missing' : error ? 'login-error' : undefined}
                onChange={(e) => { setPassword(e.target.value); setMissing((m) => ({ ...m, password: false })) }} />
              <button type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(!show)}
                className="absolute right-2 top-1/2 grid -translate-y-1/2 place-items-center rounded-lg p-2.5 text-[#5B6B7F] hover:text-heading">
                <Icon name={show ? 'eyeOff' : 'eye'} /></button>
            </div>
            {missing.password && <p id="password-missing" className="text-sm font-medium text-err">Enter your password.</p>}
          </div>
          {error && <p id="login-error" role="alert" className="rounded-lg border-l-4 border-err bg-err-bg px-3 py-2 text-sm text-[#7F1D1D]"><b>Error:</b> {error}</p>}
          <button className="btn-signin btn mt-1 min-h-[54px] w-full rounded-xl bg-accent text-xl font-bold text-white shadow-[0_10px_24px_rgba(241,91,32,.3)] hover:bg-[#E04E15] disabled:cursor-wait disabled:border-transparent disabled:bg-accent disabled:text-white disabled:opacity-70"
            disabled={busy}>
            {busy ? 'Signing in…' : <>Sign In <Icon name="arrow" /></>}
          </button>
        </form>
      )}
    </LoginLayout>
  )
}
