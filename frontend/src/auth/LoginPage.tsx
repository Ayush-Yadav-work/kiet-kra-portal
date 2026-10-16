import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Role, User } from '../api/types'
import { homeFor, useAuth } from './AuthContext'

const COPY: Record<Role, { title: string; desc: string; path: string }> = {
  DEAN: { title: 'Dean Portal', desc: 'Department Deans: prepare, evidence and submit bimonthly KRA reports.', path: '/auth/dean/login/' },
  VC: { title: 'Vice Chancellor Portal', desc: 'Institution-wide review, approval and reopening of KRA reports.', path: '/auth/vc/login/' },
}

export default function LoginPage({ role }: { role: Role }) {
  const { user, loading, setUser, logout } = useAuth()
  const nav = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const copy = COPY[role]

  if (loading) return null
  if (user && user.role === role) return <Navigate to={homeFor(user)} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const u = await api<User>(copy.path, { method: 'POST', body: { username, password } })
      setUser(u)
      nav(u.must_change_password ? '/change-password' : homeFor(u), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.')
    } finally { setBusy(false) }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="card w-full max-w-sm">
        <h1 className="text-xl font-semibold">{copy.title}</h1>
        <p className="text-sm text-slate-600 mt-1 mb-4">{copy.desc}</p>
        {user && user.role !== role ? (
          <div role="alert" className="text-sm space-y-3">
            <p>You are signed in to the {user.role === 'VC' ? 'Vice Chancellor' : 'Dean'} portal as {user.name}.</p>
            <div className="flex gap-2">
              <Link className="btn-primary" to={homeFor(user)}>Return to my portal</Link>
              <button className="btn-secondary" onClick={() => logout()}>Sign out</button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3" noValidate>
            <div>
              <label className="label" htmlFor="username">Username</label>
              <input id="username" className="input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <div className="flex gap-2">
                <input id="password" className="input" type={show ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                <button type="button" className="btn-secondary" aria-pressed={show} onClick={() => setShow(!show)}>{show ? 'Hide' : 'Show'}</button>
              </div>
            </div>
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
            <button className="btn-primary w-full justify-center" disabled={busy || !username || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
        )}
        <p className="text-xs text-slate-500 mt-4"><Link className="underline" to="/">Back to portal selection</Link></p>
      </div>
    </main>
  )
}
