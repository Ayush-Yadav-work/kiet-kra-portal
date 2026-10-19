import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import { ErrorBox } from '../../components/ui'

// "Announce to pending departments" (D-077): proposes recipients and a factual message for chosen opened periods and
// saves an editable draft. Publication happens only from the announcement editor, after review.
type Opened = { period_id: number; label: string }
type Proposal = { eligible: string[]; counts: Record<string, number>; periods: string[]; title: string; body: string }

export default function PendingNotice({ year, opened, fixedPeriod, departments, kra, onClose }:
  { year: string; opened: Opened[]; fixedPeriod: number | null; departments: string[]; kra: string; onClose: () => void }) {
  const nav = useNavigate()
  const [ids, setIds] = useState<number[]>(fixedPeriod ? [fixedPeriod] : [])
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const body = (extra = {}) => ({ year, period_ids: ids, departments, kras: kra ? [Number(kra)] : [], ...extra })
  async function check() {
    setBusy(true); setError(''); setProposal(null)
    try { setProposal(await api<Proposal>('/announcements/pending-draft/', { method: 'POST', body: body({ preview: true }) })) }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Failed') } finally { setBusy(false) }
  }
  async function create() {
    setBusy(true); setError('')
    try { const r = await api<{ id: string }>('/announcements/pending-draft/', { method: 'POST', body: body() }); nav(`/vc/announcements/${r.id}`) }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Failed'); setBusy(false) }
  }
  return (
    <section role="region" aria-label="Announce to pending departments" className="grid gap-3 rounded-[10px] border-2 border-action bg-white p-4">
      <div className="flex items-start justify-between gap-2"><h2 className="text-lg font-bold text-heading">Announce to pending departments</h2>
        <button type="button" className="btn-quiet min-h-9 text-sm" onClick={onClose}>Close</button></div>
      <p className="text-sm text-muted">Departments with at least one report that is not submitted, still a draft, rejected or returned for correction in the
        chosen opened periods{kra ? ` (KRA ${kra})` : ''}{departments.length ? ` among ${departments.join(', ')}` : ''}. Awaiting review, approved and not-due reports
        do not count. This creates an editable draft; it never publishes or reopens reporting.</p>
      {fixedPeriod ? null : (
        <fieldset className="grid gap-1"><legend className="text-sm font-semibold text-heading">Which opened periods does the notice concern?</legend>
          {opened.length === 0 && <p className="text-sm">No period of {year} has opened yet.</p>}
          {opened.map((p) => <label key={p.period_id} className="flex items-center gap-2 text-[15px]"><input type="checkbox" className="h-5 w-5" checked={ids.includes(p.period_id)}
            onChange={() => { setProposal(null); setIds(ids.includes(p.period_id) ? ids.filter((x) => x !== p.period_id) : [...ids, p.period_id]) }} />{p.label}</label>)}
        </fieldset>
      )}
      <ErrorBox error={error} />
      <button type="button" className="btn-secondary w-fit" disabled={busy || !ids.length} onClick={check}>Find pending departments</button>
      {proposal && (
        <div className="grid gap-2">
          <p><b>{proposal.eligible.length} department(s):</b> {proposal.eligible.map((c) => `${c} (${proposal.counts[c]} pending)`).join(', ')}</p>
          <p className="text-sm font-semibold">Suggested message (editable in the draft):</p>
          <p className="whitespace-pre-wrap rounded bg-subtle p-3 text-sm"><b>{proposal.title}</b>{'\n'}{proposal.body}</p>
          <button type="button" className="btn-primary w-fit" disabled={busy || !proposal.eligible.length} onClick={create}>Create draft announcement</button>
        </div>
      )}
    </section>
  )
}
