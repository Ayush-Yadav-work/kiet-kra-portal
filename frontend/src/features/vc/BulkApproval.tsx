import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import { ErrorBox } from '../../components/ui'
import Preview from '../report-builder/Preview'

// VC Phase 2 bulk approval (D-075). The server freezes the manifest; this component only confirms it once and then asks
// the server to process the next ≤50 items until none remain. Progress shown is what the server committed.

type Outcome = 'PENDING' | 'APPROVED' | 'SKIPPED' | 'CONFLICT' | 'FAILED'
export interface BulkItem { position: number; submission: string; revision: string; revision_sequence: number; department: string; kra: number
  period: string; outcome: Outcome; reason: string }
export interface BulkRun { id: string; scope: 'SELECTION' | 'FILTERED'; scope_label: string; filters: Record<string, string | number>; total: number
  processed: number; remaining: number; counts: Record<Exclude<Outcome, 'PENDING'>, number>; confirmed_at: string | null; completed_at: string | null
  expires_at: string; expired: boolean; resumable: boolean; batch_size: number; excluded?: { submission: string; reason: string }[]
  items?: { total: number; results: BulkItem[] }; batch?: BulkItem[] }
export type Prepare = { scope: 'selection'; items: { submission: string; revision: string }[]; filters: Record<string, string> }
  | { scope: 'filtered'; filters: Record<string, string> }

const OUTCOME_LABEL: Record<Outcome, string> = { PENDING: 'Not processed', APPROVED: 'Approved', SKIPPED: 'Skipped', CONFLICT: 'Conflict', FAILED: 'Failed' }
const newKey = () => (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`).slice(0, 64)

export function BulkPanel({ request, resume, onDone, onClose }: { request: Prepare | null; resume: BulkRun | null; onDone: () => void; onClose: () => void }) {
  const [run, setRun] = useState<BulkRun | null>(resume)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [problems, setProblems] = useState<BulkItem[] | null>(null)
  const key = useRef(newKey())  // one key per opened panel: a double click or lost response returns the same manifest
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [])

  useEffect(() => {
    if (!request || resume) return
    let live = true
    api<BulkRun>('/bulk-approvals/', { method: 'POST', body: { idempotency_key: key.current, ...request } })
      .then((r) => live && setRun(r)).catch((e) => live && setError(e instanceof ApiError ? e.message : 'Could not prepare the selection'))
    return () => { live = false }
  }, [request, resume])

  async function processAll(id: string) {
    setBusy(true); setError('')
    try {
      for (;;) {  // sequential requests; each returns committed outcomes and the remaining count
        const r = await api<BulkRun>(`/bulk-approvals/${id}/process/`, { method: 'POST' })
        setRun(r)
        if (!r.remaining || !r.batch?.length) break
      }
      onDone()
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401
        ? 'Your session ended. Sign in again, then choose Resume: approvals already recorded are kept.'
        : `${e instanceof ApiError ? e.message : 'Processing stopped'}. Approvals already recorded are kept; choose Resume to continue.`)
    } finally { setBusy(false) }
  }

  async function confirm() {
    if (!run) return
    setBusy(true); setError('')
    try {
      const r = await api<BulkRun>(`/bulk-approvals/${run.id}/confirm/`, { method: 'POST' })
      setRun({ ...run, ...r })
      await processAll(run.id)
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Could not confirm'); setBusy(false) }
  }

  async function showProblems() {
    if (!run) return
    const all: BulkItem[] = []
    for (const o of ['CONFLICT', 'SKIPPED', 'FAILED', 'PENDING'] as const) {
      const r = await api<BulkRun>(`/bulk-approvals/${run.id}/?outcome=${o}`)
      all.push(...(r.items?.results ?? []))
    }
    setProblems(all)
  }

  async function retryFailed() {
    if (!run) return
    setError('')
    try {
      const r = await api<BulkRun>(`/bulk-approvals/${run.id}/retry/`, { method: 'POST', body: { idempotency_key: newKey() } })
      setProblems(null); setRun(r)
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Retry failed') }
  }

  const f = run?.filters ?? {}
  const scopeText = [f.year, f.period, f.department && f.department !== 'All' ? f.department : 'all departments',
    f.kra && f.kra !== 'All' ? `KRA ${f.kra}` : '', f.search ? `“${f.search}”` : ''].filter(Boolean).join(' · ')
  const pct = run ? Math.round((run.processed / Math.max(run.total, 1)) * 100) : 0
  const finished = !!run?.confirmed_at && run.remaining === 0
  return (
    <section role="region" aria-labelledby="bulk-h" className="grid gap-3 rounded-[10px] border-2 border-action bg-white p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 id="bulk-h" ref={heading} tabIndex={-1} className="text-xl font-bold text-heading">Bulk approval</h2>
        {!busy && <button type="button" className="btn-quiet min-h-9 text-sm" onClick={onClose}>Close</button>}
      </div>
      <ErrorBox error={error} />
      {!run ? (!error && <p role="status">Preparing the exact list of reports…</p>) : (
        <>
          <p className="text-[15px]"><b>{run.scope_label}</b> — {run.total} report{run.total === 1 ? '' : 's'} awaiting review{scopeText ? ` · ${scopeText}` : ''}.
            Each report's exact submitted revision is fixed now; reports submitted later are not added, and a report that changes is reported, not approved.</p>
          {!!run.excluded?.length && <details className="text-sm"><summary className="cursor-pointer font-semibold text-warn">{run.excluded.length} selected report(s) left out</summary>
            <ul className="mt-1 list-disc pl-5">{run.excluded.map((x) => <li key={x.submission}>{x.reason}</li>)}</ul></details>}
          {!run.confirmed_at && !run.expired && (
            <>
              {run.items && <details className="text-sm"><summary className="cursor-pointer font-semibold">Show the reports ({run.total})</summary>
                <ul className="mt-1 grid max-h-56 gap-0.5 overflow-auto pl-1">{run.items.results.map((i) =>
                  <li key={i.submission}>{i.department} · KRA {i.kra} · {i.period} · revision {i.revision_sequence}</li>)}
                  {run.items.total > run.items.results.length && <li className="text-muted">…and {run.items.total - run.items.results.length} more</li>}</ul></details>}
              <p className="text-sm text-muted">Approval covers each report's achievement, report and evidence together, recorded as approved by you.
                Processed in steps of {run.batch_size}; keep this page open until it finishes.</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-primary" disabled={busy} onClick={confirm}>Approve {run.total} report{run.total === 1 ? '' : 's'}</button>
                <button type="button" className="btn-secondary" disabled={busy} onClick={onClose}>Cancel</button>
              </div>
            </>
          )}
          {!run.confirmed_at && run.expired && <p className="text-warn">This selection expired before it was confirmed. Close and select again.</p>}
          {run.confirmed_at && (
            <div className="grid gap-2">
              <div className="h-3 overflow-hidden rounded-full bg-subtle" aria-hidden="true"><div className="h-full bg-action" style={{ width: `${pct}%` }} /></div>
              <p role="status" aria-live="polite" className="font-semibold text-heading">
                {finished ? `Finished: processed ${run.total} of ${run.total}.` : `Processed ${run.processed} of ${run.total}.`}</p>
              <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
                <li>Approved: <b>{run.counts.APPROVED}</b></li><li>Conflicts: <b>{run.counts.CONFLICT}</b></li>
                <li>Skipped: <b>{run.counts.SKIPPED}</b></li><li>Failed: <b>{run.counts.FAILED}</b></li></ul>
              {!finished && !busy && run.resumable && <button type="button" className="btn-primary w-fit" onClick={() => processAll(run.id)}>Resume ({run.remaining} left)</button>}
              {finished && run.counts.APPROVED > 0 && <p className="text-sm text-muted">Approved PDFs are generated in the background; downloads show “Preparing” until ready.</p>}
              {finished && run.processed > run.counts.APPROVED && !problems && <button type="button" className="btn-secondary w-fit" onClick={showProblems}>Show reports not approved</button>}
              {problems && (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px] text-sm"><caption className="sr-only">Reports not approved</caption>
                    <thead className="bg-subtle text-left"><tr>{['Report', 'Outcome', 'Reason'].map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}</tr></thead>
                    <tbody>{problems.map((i) => <tr key={i.submission} className="border-t border-line align-top">
                      <td className="px-2 py-1.5"><Link className="underline" to={`/vc/review/${i.submission}`}>{i.department} · KRA {i.kra} · {i.period}</Link></td>
                      <td className="px-2 py-1.5 font-semibold">{OUTCOME_LABEL[i.outcome]}</td><td className="px-2 py-1.5">{i.reason}</td></tr>)}</tbody></table>
                  {run.counts.FAILED > 0 && <button type="button" className="btn-secondary mt-2" onClick={retryFailed}>Review a retry of {run.counts.FAILED} failed report(s)</button>}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}

export interface PreviewTarget { submission: string; revision: string; title: string; status: string; sequence: number | null }

export function PreviewDrawer({ target, onClose, onPrev, onNext }: { target: PreviewTarget; onClose: () => void; onPrev?: () => void; onNext?: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [target.submission])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])
  return (
    <aside aria-labelledby="qp-h" className="fixed inset-0 z-30 flex flex-col gap-2 border-l border-line bg-white p-3 shadow-2xl md:left-auto md:w-[min(720px,55vw)] md:p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 id="qp-h" ref={heading} tabIndex={-1} className="text-lg font-bold text-heading">{target.title}</h2>
          <p className="text-sm text-muted">Submitted revision {target.sequence ?? '—'} · {target.status}. Quick preview of that exact revision; it does not change any approval.</p>
        </div>
        <button type="button" className="btn-secondary min-h-9 text-sm" onClick={onClose}>Close preview</button>
      </div>
      <div className="flex flex-wrap gap-2 text-sm">
        <a className="btn-secondary min-h-9 text-sm" href={`/api/v1/submissions/${target.submission}/export/?revision=${target.revision}&inline=1`} target="_blank" rel="noopener">
          Download exact-revision PDF<span className="sr-only"> (opens in a new tab)</span></a>
        <Link className="btn-quiet min-h-9 text-sm" to={`/vc/review/${target.submission}`}>Open full review</Link>
        <span className="ml-auto flex gap-2">
          <button type="button" className="btn-secondary min-h-9 text-sm" disabled={!onPrev} onClick={onPrev}>Previous report</button>
          <button type="button" className="btn-secondary min-h-9 text-sm" disabled={!onNext} onClick={onNext}>Next report</button></span>
      </div>
      <div className="min-h-0 flex-1"><Preview key={target.revision} submissionId={target.submission} revision={target.revision} /></div>
    </aside>
  )
}
