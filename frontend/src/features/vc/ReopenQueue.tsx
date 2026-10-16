import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import type { ReopenRequest } from '../../api/types'
import { ErrorBox, Loading } from '../../components/ui'

export default function ReopenQueue() {
  const [state, setState] = useState('PENDING')
  const [rows, setRows] = useState<ReopenRequest[] | null>(null)
  const [error, setError] = useState('')
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const load = useCallback(() => {
    setRows(null)
    api<ReopenRequest[]>(`/reopen-requests/${state ? `?state=${state}` : ''}`).then(setRows).catch((e) => setError(e.message))
  }, [state])
  useEffect(() => { load() }, [load])

  async function decide(r: ReopenRequest, approve: boolean) {
    setError('')
    try {
      await api(`/reopen-requests/${r.id}/decision/`, { method: 'POST', body: { approve, reason: reasons[r.id] ?? '' } })
      load()
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Failed') }
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Reopening requests</h1>
        <select aria-label="State" className="input w-auto" value={state} onChange={(e) => setState(e.target.value)}>
          <option value="PENDING">Pending</option><option value="APPROVED">Approved</option><option value="DENIED">Denied</option><option value="">All</option>
        </select>
      </div>
      <ErrorBox error={error} />
      {!rows ? <Loading /> : rows.length === 0 ? <p className="card text-sm text-slate-500">No requests.</p> : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.id} className="card text-sm">
              <p><b>{r.department}</b> · KRA {r.kra_number} · {r.period} ({r.year}) · requested {fmtDateTime(r.requested_at)} by {r.requested_by}</p>
              <p className="mt-1">Reason: {r.reason}</p>
              {r.state === 'PENDING' ? (
                <div className="mt-2 flex flex-wrap items-end gap-2">
                  <input aria-label="Decision reason" className="input max-w-md" placeholder="Reason (required to deny)" value={reasons[r.id] ?? ''} onChange={(e) => setReasons({ ...reasons, [r.id]: e.target.value })} />
                  <button className="btn-primary" onClick={() => decide(r, true)}>Approve — grant 72 hours</button>
                  <button className="btn-danger" disabled={!(reasons[r.id] ?? '').trim()} onClick={() => decide(r, false)}>Deny</button>
                </div>
              ) : <p className="mt-1 text-slate-600">{r.state} by {r.decided_by} on {fmtDateTime(r.decided_at)}{r.decision_reason && `: ${r.decision_reason}`}</p>}
              <Link className="mt-1 inline-block underline" to={`/vc/review/${r.submission_id}`}>Open submission</Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
