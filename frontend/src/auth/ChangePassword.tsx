import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { User } from '../api/types'
import { homeFor, useAuth } from './AuthContext'
import { LoginLayout } from './LoginPage'

export default function ChangePassword() {
  const { user, setUser } = useAuth()
  const nav = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  if (!user) return <Navigate to="/" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (next !== confirm) { setErrors({ confirm: ['Passwords do not match.'] }); return }
    setBusy(true); setErrors({}); setMsg('')
    try {
      const u = await api<User>('/auth/change-password/', { method: 'POST', body: { current_password: current, new_password: next } })
      setUser(u)
      nav(homeFor(u), { replace: true })
    } catch (err) {
      if (err instanceof ApiError) { setErrors(err.fieldErrors); setMsg(err.message) }
    } finally { setBusy(false) }
  }

  const fe = (k: string) => errors[k]?.map((m) => <p key={m} id={`${k}-err`} className="mt-1 text-sm text-err">{m}</p>)
  const desc = (k: string) => (errors[k] ? `${k}-err` : undefined)
  return (
    <LoginLayout title="Change password" subtitle={user.must_change_password ? 'You must set a new password before continuing.' : `Signed in as ${user.name}.`}>
      <form className="grid w-full gap-3.5 text-left" onSubmit={submit}>
        <div><label className="label" htmlFor="cur">Current password</label><input id="cur" type="password" className="input" autoComplete="current-password" value={current} aria-invalid={!!errors.current_password} aria-describedby={desc('current_password')} onChange={(e) => setCurrent(e.target.value)} />{fe('current_password')}</div>
        <div><label className="label" htmlFor="new">New password (min 10 characters)</label><input id="new" type="password" className="input" autoComplete="new-password" value={next} aria-invalid={!!errors.new_password} aria-describedby={desc('new_password')} onChange={(e) => setNext(e.target.value)} />{fe('new_password')}</div>
        <div><label className="label" htmlFor="conf">Confirm new password</label><input id="conf" type="password" className="input" autoComplete="new-password" value={confirm} aria-invalid={!!errors.confirm} aria-describedby={desc('confirm')} onChange={(e) => setConfirm(e.target.value)} />{fe('confirm')}</div>
        {msg && <p role="alert" className="text-sm text-err"><b>Error:</b> {msg}</p>}
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button>
          {!user.must_change_password && <button type="button" className="btn-secondary" onClick={() => nav(homeFor(user))}>Cancel</button>}
        </div>
      </form>
    </LoginLayout>
  )
}
