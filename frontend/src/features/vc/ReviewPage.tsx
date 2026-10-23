import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import type { Decision, Grant, SubmissionDetail } from '../../api/types'
import { ErrorBox, tabKeys } from '../../components/ui'
import AchievementTab from '../achievements/AchievementTab'
import Preview from '../report-builder/Preview'
import { SubmissionLoader, WorkspaceHeader } from '../report-builder/Workspace'

interface History { revisions: { id: string; sequence: number; submitted_at: string; submitted_by: string; is_nil: boolean; achievement_text: string; evidence_count: number; decisions: Decision[] }[]; grants: Grant[] }

function DecisionForm({ d, onDone }: { d: SubmissionDetail; onDone: () => void }) {
  const [decision, setDecision] = useState<'APPROVE' | 'REJECT' | 'RETURN'>(d.status === 'APPROVED' ? 'RETURN' : 'APPROVE')
  const [reason, setReason] = useState('')
  const [grant, setGrant] = useState(true) // C1: checked by default when offered
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const needsReason = decision !== 'APPROVE'
  const offerGrant = needsReason && d.grant_option_available

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await api(`/submissions/${d.id}/review/`, { method: 'POST', body: { revision: d.current_revision!.id, decision, reason, grant_reopen: offerGrant && grant } })
      onDone()
    } catch (err) { setError(err instanceof ApiError ? err.message : 'Failed') } finally { setBusy(false) }
  }
  if (d.status !== 'SUBMITTED' && d.status !== 'APPROVED') return null
  return (
    <form className="card space-y-2" onSubmit={submit}>
      <h3 className="font-semibold">Decision on revision {d.current_revision?.sequence}</h3>
      <div className="flex flex-wrap gap-3 text-sm">
        {d.status === 'SUBMITTED' ? (
          <>
            <label><input type="radio" checked={decision === 'APPROVE'} onChange={() => setDecision('APPROVE')} /> Approve</label>
            <label><input type="radio" checked={decision === 'REJECT'} onChange={() => setDecision('REJECT')} /> Reject</label>
          </>
        ) : <label><input type="radio" checked readOnly /> Return approved report for correction</label>}
      </div>
      {needsReason && (
        <div>
          <label className="label" htmlFor="reason">Reason (shown to the Dean) <span className="text-red-700">*</span></label>
          <textarea id="reason" className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
      )}
      {offerGrant && (
        <label className="flex items-start gap-2 rounded bg-amber-50 p-2 text-sm">
          <input type="checkbox" checked={grant} onChange={(e) => setGrant(e.target.checked)} className="mt-1" />
          <span><b>Grant 72 hours to resubmit</b> — the period {d.period.is_closed ? 'is closed' : 'closes within 72 hours'}. If unchecked, the Dean must request reopening.</span>
        </label>
      )}
      <ErrorBox error={error} />
      <button className={decision === 'APPROVE' ? 'btn-primary' : 'btn-danger'} disabled={busy || (needsReason && !reason.trim())}>
        {busy ? 'Saving…' : decision === 'APPROVE' ? 'Approve' : decision === 'REJECT' ? 'Reject' : 'Return for correction'}
      </button>
    </form>
  )
}

function Review({ d, reload }: { d: SubmissionDetail; reload: () => void }) {
  const back = (useLocation().state as { back?: string } | null)?.back ?? '/vc/dashboard'  // keeps the progress filters
  const rev = d.current_revision
  const [tab, setTab] = useState<'report' | 'evidence' | 'achievement' | 'history'>('report')
  const [history, setHistory] = useState<History | null>(null)
  useEffect(() => { api<History>(`/submissions/${d.id}/history/`).then(setHistory).catch(() => {}) }, [d.id])
  return (
    <div>
      <Link className="text-sm underline" to={back}>← Progress</Link>
      <WorkspaceHeader d={d} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-2 flex flex-wrap gap-1">
            <div role="tablist" aria-label="Submission sections" className="flex flex-wrap gap-1" onKeyDown={tabKeys}>
              {(['report', 'evidence', 'achievement', 'history'] as const).map((t) => (
                <button key={t} id={`rv-tab-${t}`} role="tab" aria-selected={tab === t} aria-controls="rv-panel" tabIndex={tab === t ? 0 : -1}
                  className={tab === t ? 'btn-primary' : 'btn-secondary'} onClick={() => setTab(t)}>{t[0].toUpperCase() + t.slice(1)}</button>
              ))}
            </div>
            <a className="btn-secondary ml-auto" href={`/api/v1/submissions/${d.id}/export/?inline=1`} target="_blank" rel="noopener">PDF<span className="sr-only"> (opens in a new tab)</span></a>
          </div>
          <div role="tabpanel" id="rv-panel" aria-labelledby={`rv-tab-${tab}`}>
          {tab === 'report' && (d.current_revision
            ? <Preview submissionId={d.id} revision={d.current_revision.id} />
            : <p className="card text-sm">Not submitted yet.</p>)}
          {tab === 'evidence' && (rev ? (
            <div className="card text-sm">
              <p className="mb-2 font-medium">Evidence at submission (revision {rev.sequence})</p>
              {rev.evidence.length === 0 ? <p className="text-slate-600">No evidence was attached.</p> : (
                <ul className="space-y-1">{rev.evidence.map((e) => <li key={e.id}><b>{e.category}</b> — {e.label}{' · '}
                  {e.drive_url ? <a className="underline" href={e.drive_url} target="_blank" rel="noopener noreferrer">Drive link</a>
                    : <a className="underline" href={`/api/v1/evidence/${e.id}/download/`}>{e.original_filename || 'Download'}</a>}</li>)}</ul>)}
            </div>) : <p className="card text-sm">Not submitted yet.</p>)}
          {tab === 'achievement' && (
            <div>
              <p className="mb-2 text-sm text-slate-600">{rev ? `As submitted in revision ${rev.sequence}${rev.is_nil ? ' (Nil report)' : ''}.` : 'Not submitted yet.'}</p>
              <AchievementTab detail={d} values={{ achievement_text: rev?.achievement_text ?? '', remarks: rev?.remarks ?? '' }} disabled errors={{}} />
            </div>)}
          {tab === 'history' && history && (
            <div className="card space-y-3 text-sm">
              {history.revisions.length === 0 && <p>No revisions yet.</p>}
              {history.revisions.map((r) => (
                <div key={r.id} className="border-b border-slate-100 pb-2">
                  <p><b>Revision {r.sequence}</b> submitted {fmtDateTime(r.submitted_at)} by {r.submitted_by}{r.is_nil && ' (Nil)'} · {r.evidence_count} evidence item(s) ·{' '}
                    <a className="underline" href={`/api/v1/submissions/${d.id}/export/?revision=${r.id}&inline=1`} target="_blank" rel="noopener">PDF</a></p>
                  {r.decisions.map((x) => <p key={x.id} className="ml-4">{x.decision} by {x.reviewer_name}, {fmtDateTime(x.created_at)}{x.reason && `: ${x.reason}`}{x.granted_reopen && ' · 72-hour grant'}</p>)}
                </div>
              ))}
              {history.grants.map((g) => <p key={g.id}>Grant ({g.source === 'REVIEW' ? 'with review decision' : 'on request'}): {fmtDateTime(g.starts_at)} → {fmtDateTime(g.expires_at)}{g.active && ' · active'}</p>)}
            </div>
          )}
          </div>
        </div>
        <div><DecisionForm d={d} onDone={reload} /></div>
      </div>
    </div>
  )
}

export default function ReviewPage() {
  const { submissionId } = useParams()
  return <SubmissionLoader id={submissionId!} render={(d, _s, reload) => <Review d={d} reload={reload} />} />
}
