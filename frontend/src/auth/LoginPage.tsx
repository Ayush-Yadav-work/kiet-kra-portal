import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Role, User } from '../api/types'
import background from '../assets/login-background.jpg'
import logo from '../assets/kiet-logo.png'
import { Icon } from '../components/icons'
import { homeFor, useAuth } from './AuthContext'

const PATH: Record<Role, string> = { DEAN: '/auth/dean/login/', VC: '/auth/vc/login/' }
const ROLES: { role: Role; to: string; label: string; sr?: string; icon: 'person' | 'people' }[] = [
  { role: 'DEAN', to: '/dean/login', label: 'Dean', icon: 'person' },
  { role: 'VC', to: '/vc/login', label: 'VC', sr: 'Vice Chancellor', icon: 'people' },
]

/** Sign-in layout matching reference/ui/redesign-v2/login-reference.png: campus photograph with a light wash, official logo and
 *  "KRA Tracker" title on the left, sign-in card on the right; stacked on phones and tablets. Used by "/", /dean/login,
 *  /vc/login and /change-password. Styling is local to this page (no global rules), so dashboards and reports are unaffected. */
export function LoginLayout({ title = 'Welcome Back', subtitle, children }: { title?: string; subtitle: string; children: ReactNode }) {
  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-[#EAF2FA]">
      <div aria-hidden="true" className="absolute inset-0 -z-20 bg-cover bg-[position:58%_100%] bg-no-repeat lg:bg-[position:left_top]"
        style={{ backgroundImage: `url(${background})` }} />
      {/* light wash as in the reference: hazy top-left behind the title (it also hides the small logo printed in the
          photograph's corner), clear centre, soft blue-white on the right behind the card, faint orange/blue corner tints */}
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_20%_17%_at_5%_6%,rgba(255,255,255,.99)_0,rgba(255,255,255,.97)_62%,transparent_100%),radial-gradient(ellipse_46%_40%_at_10%_8%,rgba(255,255,255,.94)_0,rgba(255,255,255,.8)_45%,transparent_100%),radial-gradient(ellipse_30%_26%_at_100%_0%,rgba(241,91,32,.18),transparent_70%),radial-gradient(ellipse_22%_30%_at_0%_45%,rgba(241,91,32,.12),transparent_70%),linear-gradient(95deg,rgba(255,255,255,.74)_0%,rgba(255,255,255,.5)_30%,rgba(255,255,255,.1)_50%,rgba(255,255,255,0)_56%,rgba(232,241,251,.35)_72%,rgba(232,241,251,.6)_100%)]" />
      <div className="grid min-h-screen w-full items-center gap-6 px-4 py-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,548px)] lg:gap-10 lg:px-[5.7%] lg:py-[6vh]">
        <div className="self-start lg:self-stretch">
          <img src={logo} width={974} height={360} alt="KIET Deemed to be University" className="h-auto w-[180px] mix-blend-multiply md:w-[262px] lg:mt-[-1vh]" />
          <div className="mt-6 md:mt-10 lg:mt-[6vh]">
            <p className="text-[46px] font-extrabold leading-[.95] tracking-[-.02em] text-heading sm:text-[64px] xl:text-[104px]">KRA <span className="text-accent">Tracker</span></p>
            <span aria-hidden="true" className="mt-3 block h-[5px] w-20 rounded-full bg-accent md:mt-4 md:w-[82px]" />
            <p className="mt-3 text-lg font-medium tracking-[.32em] text-heading md:mt-4 md:text-[30px]">Key Result Area Portal</p>
            <p className="mt-2 text-sm font-medium tracking-[.38em] text-heading md:mt-5 md:text-xl">Track. Review. Lead.</p>
          </div>
        </div>
        <section className="grid w-full gap-5 rounded-[28px] bg-white px-5 pb-6 pt-7 shadow-[0_24px_60px_rgba(12,45,71,.18)] sm:px-10 md:gap-6 lg:px-[58px] lg:pb-10 lg:pt-[72px]">
          <div>
            <h1 className="text-[34px] font-extrabold leading-tight tracking-[-.01em] text-[#0A1A3A] md:text-[48px]">{title}</h1>
            <p className="mt-1 text-lg text-muted md:text-[26px] md:leading-tight">{subtitle}</p>
          </div>
          {children}
          <p className="w-full border-t border-[#E3E9EF] pt-6 text-center text-[15px] text-muted md:text-base">For KIET leadership access.</p>
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
          className={`flex min-h-[58px] items-center justify-center gap-3 rounded-[10px] text-[19px] font-bold ${current === r.role ? 'bg-accent text-white shadow-[0_6px_14px_rgba(241,91,32,.32)]' : 'text-[#3A4A5E] hover:bg-[#E3E9F0]'}`}>
          <Icon name={r.icon} size={22} />{r.label}{r.sr && <span className="sr-only"> ({r.sr})</span>}
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

  const field = 'input min-h-[58px] rounded-xl border-[#CBD5E1] pl-14 text-[17px] placeholder:text-[#7A8797] aria-[invalid=true]:border-err'
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
        <form onSubmit={submit} className="grid w-full gap-5" noValidate>
          <div className="grid gap-2.5">
            <label className="text-[17px] font-medium text-[#0A1A3A]" htmlFor="username">Username</label>
            <div className="relative">
              <span className="pointer-events-none absolute left-[18px] top-1/2 -translate-y-1/2 text-[#5B6B7F]"><Icon name="person" size={22} /></span>
              <input id="username" className={field} autoComplete="username" autoCapitalize="none" spellCheck={false} placeholder="your.username" value={username} required
                aria-invalid={!!error || !!missing.username} aria-describedby={missing.username ? 'username-missing' : error ? 'login-error' : undefined}
                onChange={(e) => { setUsername(e.target.value); setMissing((m) => ({ ...m, username: false })) }} />
            </div>
            {missing.username && <p id="username-missing" className="text-sm font-medium text-err">Enter your username.</p>}
          </div>
          <div className="grid gap-2.5">
            <label className="text-[17px] font-medium text-[#0A1A3A]" htmlFor="password">Password</label>
            <div className="relative">
              <span className="pointer-events-none absolute left-[18px] top-1/2 -translate-y-1/2 text-[#5B6B7F]"><Icon name="lock" size={22} /></span>
              <input id="password" className={`${field} pr-14`} type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password"
                value={password} required aria-invalid={!!error || !!missing.password} aria-describedby={missing.password ? 'password-missing' : error ? 'login-error' : undefined}
                onChange={(e) => { setPassword(e.target.value); setMissing((m) => ({ ...m, password: false })) }} />
              <button type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(!show)}
                className="absolute right-2 top-1/2 grid -translate-y-1/2 place-items-center rounded-lg p-2.5 text-[#5B6B7F] hover:text-heading">
                <Icon name={show ? 'eyeOff' : 'eye'} size={22} /></button>
            </div>
            {missing.password && <p id="password-missing" className="text-sm font-medium text-err">Enter your password.</p>}
          </div>
          {error && <p id="login-error" role="alert" className="rounded-lg border-l-4 border-err bg-err-bg px-3 py-2 text-sm text-[#7F1D1D]"><b>Error:</b> {error}</p>}
          <button className="btn-signin btn mt-2 min-h-[62px] w-full rounded-xl bg-accent text-[22px] font-bold text-white shadow-[0_10px_24px_rgba(241,91,32,.3)] hover:bg-[#E04E15] disabled:cursor-wait disabled:border-transparent disabled:bg-accent disabled:text-white disabled:opacity-70"
            disabled={busy}>
            {busy ? 'Signing in…' : <>Sign In <Icon name="arrow" size={22} /></>}
          </button>
        </form>
      )}
    </LoginLayout>
  )
}
