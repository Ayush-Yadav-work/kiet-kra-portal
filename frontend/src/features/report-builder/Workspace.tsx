import { useCallback, useEffect, useMemo, useState, useSyncExternalStore, type FormEvent } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useBlocker, useParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import type { Applicability, Assignment, Payload, Period, ReopenRequest, Schema, SubmissionDetail } from '../../api/types'
import { ErrorBox, Loading, StatusBadge, tabKeys, timeLeft, useServerClock } from '../../components/ui'
import AchievementTab from '../achievements/AchievementTab'
import EvidenceTab from '../evidence/EvidenceTab'
import Preview from './Preview'
import { SaveQueue } from './saveQueue'
import SchemaForm, { emptyActivity } from './SchemaForm'

type Tab = 'report' | 'evidence' | 'achievement'

export function ReopenRequestForm({ path, onDone }: { path: string; onDone: () => void }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try { await api(path, { method: 'POST', body: { reason } }); onDone() } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  return (
    <form onSubmit={submit} className="card space-y-2">
      <h3 className="font-semibold">Request reopening</h3>
      <p className="text-sm text-slate-600">The period is closed. If the VC approves, you get exactly 72 hours to edit and submit.</p>
      <label className="label" htmlFor="rr">Reason</label>
      <textarea id="rr" className="input" rows={3} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />
      <ErrorBox error={error} />
      <button className="btn-primary" disabled={busy || !reason.trim()}>{busy ? 'Sending…' : 'Send request'}</button>
    </form>
  )
}

export function WorkspaceHeader({ d, status }: { d: SubmissionDetail; status?: SubmissionDetail['display_status'] }) {
  const now = useServerClock(d.server_time)
  return (
    <div className="card mb-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold">KRA {d.assignment.kra.number} — {d.assignment.department.name}</h1>
          <p className="text-sm text-slate-700">{d.assignment.kra.activity_text.replace(/^KRA \d+:\s*/, '')}</p>
          <p className="mt-1 text-sm">Academic year <b>{d.assignment.year}</b> · <b>{d.period.label}</b> · Annual target: <b className="whitespace-pre-wrap">{d.assignment.target_text}</b></p>
          <p className="text-xs text-slate-500">NBA {d.assignment.kra.nba_ref || '—'} · NAAC {d.assignment.kra.naac_ref || '—'}</p>
        </div>
        <div className="text-right text-sm">
          <StatusBadge status={status ?? d.display_status} />{d.is_nil && <span className="ml-1">(Nil)</span>}
          <p className="mt-1 text-xs text-slate-600">
            {d.active_grant ? <span className="font-semibold text-amber-800">Reopened · {timeLeft(d.active_grant.expires_at, now)}</span>
              : d.period.is_open ? `Open until ${fmtDateTime(d.period.closes_at)}` : d.period.is_closed ? 'Period closed' : `Opens ${fmtDateTime(d.period.opens_at)}`}
          </p>
        </div>
      </div>
      {d.latest_decision && d.latest_decision.decision !== 'APPROVE' && (
        <p className="mt-2 rounded bg-red-50 p-2 text-sm text-red-900">
          <b>{d.latest_decision.decision === 'RETURN' ? 'Returned for correction' : 'Rejected'}</b> by {d.latest_decision.reviewer_name} on {fmtDateTime(d.latest_decision.created_at)}: {d.latest_decision.reason}
        </p>
      )}
    </div>
  )
}

function SaveIndicator({ q }: { q: SaveQueue }) {
  const state = useSyncExternalStore((cb) => q.subscribe(cb), () => q.state)
  const text = { idle: '', dirty: 'Unsaved changes', saving: 'Saving…', saved: 'Saved', failed: 'Save failed — will retry on next change', conflict: 'Conflict' }[state]
  const cls = state === 'failed' || state === 'conflict' ? 'text-red-700' : state === 'saved' ? 'text-green-700' : 'text-slate-600'
  return <span role="status" aria-live="polite" className={`text-sm ${cls}`}>{text}{state === 'saved' && q.savedAt ? ` ${new Date(q.savedAt).toLocaleTimeString('en-IN')}` : ''}</span>
}

function normalize(p: Payload | undefined, schema: Schema, editable: boolean): Payload {
  const acts = p?.activities ?? []
  return { activities: acts.length ? acts.map((a) => ({ ...emptyActivity(schema), ...a })) : editable ? [emptyActivity(schema)] : [] }
}

/** Submission dates are shown as dates in Asia/Kolkata (D-079), e.g. "24 October 2026". */
const istDate = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata' })

function Editor({ d, schema, reload }: { d: SubmissionDetail; schema: Schema; reload: () => void }) {
  const q = useMemo(() => new SaveQueue(d.id, d.edit_version), [d.id, d.edit_version])
  useEffect(() => () => q.dispose(), [q])
  useEffect(() => {  // read-only report: pick up VC decisions (e.g. on a reopening request) when the Dean returns; never while editing
    if (d.editable) return
    window.addEventListener('focus', reload)
    return () => window.removeEventListener('focus', reload)
  }, [d.editable, reload])
  const qState = useSyncExternalStore((cb) => q.subscribe(cb), () => q.state)
  const form = useForm<Payload>({ defaultValues: normalize(d.payload, schema, d.editable) })
  const [draft, setDraft] = useState<Payload>(() => form.getValues())
  const [ach, setAch] = useState({ achievement_text: d.achievement_text, remarks: d.remarks })
  const [nil, setNil] = useState({ is_nil: d.is_nil, nil_reason: d.nil_reason })
  const [tab, setTab] = useState<Tab>('report')
  const [view, setView] = useState<'form' | 'preview'>('form')
  // Submit/validate errors persist until the next check; save errors always reflect the latest save attempt.
  const [submitErrors, setErrors] = useState<Record<string, string[]>>({})
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const editable = d.editable

  useEffect(() => {
    const sub = form.watch((values) => {
      const v = structuredClone(values) as Payload
      setDraft(v)
      if (editable) q.enqueue({ payload: v })
    })
    return () => sub.unsubscribe()
  }, [form, q, editable])

  const errors = { ...submitErrors, ...q.fieldErrors }

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (q.hasPending) { e.preventDefault() } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [q])
  const blocker = useBlocker(() => q.hasPending)
  useEffect(() => {
    if (blocker.state !== 'blocked') return
    q.flush().then((ok) => {
      if (ok || window.confirm('Some changes could not be saved. Leave anyway and lose them?')) blocker.proceed()
      else blocker.reset()
    })
  }, [blocker, q])

  const setAchField = (k: 'achievement_text' | 'remarks', v: string) => { setAch((a) => ({ ...a, [k]: v })); q.enqueue({ [k]: v }) }
  const setNilField = (patch: Partial<typeof nil>) => { setNil((n) => ({ ...n, ...patch })); q.enqueue(patch, 800) }

  async function switchTab(t: Tab) {
    const ok = await q.flush() // C3: flush before switching tabs
    if (!ok && editable) setMessage('Latest changes are not saved yet; they are kept on this page.')
    setTab(t)
  }

  async function keepMine() {
    const fresh = await api<SubmissionDetail>(`/submissions/${d.id}/`)
    await q.resolveKeepMine(fresh.edit_version)
  }

  async function pdfPreview() {
    setMessage('')
    if (!(await q.flush())) { setMessage('Save your changes before generating the PDF.'); return }
    window.open(`/api/v1/submissions/${d.id}/export/?inline=1`, '_blank', 'noopener')
  }

  async function submit() {
    setBusy(true); setMessage('')
    try {
      if (!(await q.flush())) { setMessage('Changes could not be saved; fix that before submitting.'); return }
      const v = await api<{ valid: boolean; field_errors: Record<string, string[]> }>(`/submissions/${d.id}/validate/`, { method: 'POST' })
      setErrors(v.field_errors)
      if (!v.valid) {
        const where = Object.keys(v.field_errors)
        const t = where.some((k) => k === 'evidence') ? 'evidence' : where.some((k) => k === 'achievement_text') && where.length === 1 ? 'achievement' : 'report'
        setTab(t)
        setMessage(`Cannot submit yet: ${where.length} item(s) need attention (${[...new Set(where.map((k) => k.split('.')[0] === 'activities' ? 'report fields' : k.replace('_', ' ')))].join(', ')}).`)
        return
      }
      if (!window.confirm('Submit this report to the VC? You cannot edit it after submission unless it is returned.')) return
      await api(`/submissions/${d.id}/submit/`, { method: 'POST', body: { edit_version: q.version } })
      reload()
    } catch (e) {
      if (e instanceof ApiError) { setErrors(e.fieldErrors); setMessage(e.message) } else setMessage('Submit failed.')
    } finally { setBusy(false) }
  }

  const ctx = { control: form.control, register: form.register, setValue: form.setValue, getValues: form.getValues, disabled: !editable, errors, deanName: d.dean_name }
  return (
    <div>
      {/* C11: first successful save turns "Not submitted" into Draft without a reload */}
      <WorkspaceHeader d={d} status={d.display_status === 'NOT_SUBMITTED' && q.version > d.edit_version ? 'DRAFT' : undefined} />
      {qState === 'conflict' && (
        <div role="alert" className="mb-3 rounded border border-red-300 bg-red-50 p-3 text-sm">
          <p className="font-medium text-red-900">{q.error}</p>
          <div className="mt-2 flex gap-2">
            <button className="btn-primary" onClick={keepMine}>Keep my values and save them</button>
            <button className="btn-secondary" onClick={() => { if (window.confirm('Discard your unsaved values and load the saved copy?')) { q.resolveTakeServer(0); reload() } }}>Load the saved copy</button>
          </div>
        </div>
      )}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div role="tablist" aria-label="Report sections" className="flex gap-1" onKeyDown={tabKeys}>
          {(['report', 'evidence', 'achievement'] as Tab[]).map((t) => (
            <button key={t} id={`ws-tab-${t}`} role="tab" aria-selected={tab === t} aria-controls={`ws-panel-${t}`} tabIndex={tab === t ? 0 : -1}
              className={tab === t ? 'btn-primary' : 'btn-secondary'} onClick={() => switchTab(t)}>
              {t === 'report' ? 'Report' : t === 'evidence' ? 'Evidence' : 'Achievement'}
              {t === 'evidence' && errors.evidence && <><span className={tab === t ? 'text-red-300' : 'text-red-700'} aria-hidden> ●</span><span className="sr-only"> (needs attention)</span></>}
            </button>
          ))}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {editable && <SaveIndicator q={q} />}
          {editable && <button className="btn-secondary" onClick={() => q.flush()}>Save draft</button>}
          <button className="btn-secondary" onClick={pdfPreview}>Final PDF preview</button>
          {editable && <button className="btn-primary" disabled={busy} onClick={submit}>{busy ? 'Checking…' : d.status === 'REJECTED' ? 'Resubmit' : 'Submit'}</button>}
        </div>
      </div>
      <ErrorBox error={message} />
      {errors.dean_name && <p role="alert" className="mb-3 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">{errors.dean_name.join(' ')}</p>}
      {!editable && <p className="mb-3 rounded bg-slate-100 p-2 text-sm">Read-only: {d.status === 'SUBMITTED' ? 'submitted and awaiting VC review.' : d.status === 'APPROVED' ? 'approved by the VC.' : 'the reporting window is closed.'}</p>}
      {d.can_request_reopen && <div className="mb-3"><ReopenRequestForm path={`/submissions/${d.id}/reopen-requests/`} onDone={reload} /></div>}
      <ReopenRequests requests={d.reopen_requests} />

      <div hidden={tab !== 'report'} role="tabpanel" id="ws-panel-report" aria-labelledby="ws-tab-report">
        <div className="mb-2 flex gap-2 lg:hidden">
          <button className={view === 'form' ? 'btn-primary' : 'btn-secondary'} aria-pressed={view === 'form'} onClick={() => setView('form')}>Form</button>
          <button className={view === 'preview' ? 'btn-primary' : 'btn-secondary'} aria-pressed={view === 'preview'} onClick={() => setView('preview')}>Preview</button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className={`min-w-0 ${view === 'preview' ? 'hidden lg:block' : ''}`}>
            <div className="card mb-3">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input type="checkbox" disabled={!editable} checked={nil.is_nil} onChange={(e) => setNilField({ is_nil: e.target.checked })} />
                Nil submission — no activity for this KRA in this period
              </label>
              {nil.is_nil && (
                <div className="mt-2">
                  <label className="label" htmlFor="nilr">Reason for Nil <span className="text-red-700">*</span></label>
                  <textarea id="nilr" className="input" rows={3} disabled={!editable} value={nil.nil_reason} onChange={(e) => setNilField({ nil_reason: e.target.value })} />
                  {errors.nil_reason && <p className="mt-1 text-xs text-red-700">{errors.nil_reason.join(' ')}</p>}
                  <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-2 text-sm">
                    <dt className="font-medium">Head/Dean:</dt>
                    <dd>{d.dean_name || <span className="text-amber-900">Not available: your account profile has no full name. Ask the administrator to correct it before submitting.</span>}</dd>
                    <dt className="font-medium">Date:</dt>
                    <dd>{!editable && d.current_revision ? istDate(d.current_revision.submitted_at)
                      : d.current_revision ? `Set on resubmission (previous submission: ${istDate(d.current_revision.submitted_at)})` : 'Set on submission'}</dd>
                  </dl>
                  <p className="mt-1 text-xs text-slate-500">A Nil report still goes to the VC for review. No event evidence is required. Entered event details are kept but not submitted.</p>
                </div>
              )}
            </div>
            <div hidden={nil.is_nil}><SchemaForm schema={schema} ctx={ctx} /></div>
          </div>
          <div className={`min-w-0 lg:sticky lg:top-2 lg:h-[calc(100vh-1rem)] ${view === 'form' ? 'hidden lg:block' : ''}`}>
            <Preview submissionId={d.id} draft={editable ? { payload: draft, ...nil, achievement_text: ach.achievement_text } : undefined} />
          </div>
        </div>
      </div>
      <div hidden={tab !== 'evidence'} role="tabpanel" id="ws-panel-evidence" aria-labelledby="ws-tab-evidence">
        <EvidenceTab submissionId={d.id} canEdit={editable} />
      </div>
      <div hidden={tab !== 'achievement'} role="tabpanel" id="ws-panel-achievement" aria-labelledby="ws-tab-achievement">
        <AchievementTab detail={d} values={ach} onChange={setAchField} disabled={!editable} errors={errors} />
      </div>
    </div>
  )
}

/** Reopening requests of this report: the newest one is the current state; earlier decisions stay in the history. */
function ReopenRequests({ requests }: { requests: ReopenRequest[] }) {
  if (!requests.length) return null
  const [latest, ...older] = requests  // newest first (server ordering)
  const tone = latest.state === 'DENIED' ? 'border-err bg-err-bg' : latest.state === 'APPROVED' ? 'border-ok bg-ok-bg' : 'border-warn bg-warn-bg'
  const line = (r: ReopenRequest) => <>Requested {fmtDateTime(r.requested_at)} by {r.requested_by}: “{r.reason}”
    {r.state !== 'PENDING' && <span className="block">{r.state === 'DENIED' ? 'Denied' : 'Approved'} {fmtDateTime(r.decided_at)} by {r.decided_by}{r.decision_reason ? `: “${r.decision_reason}”` : ''}</span>}</>
  return (
    <section aria-label="Reopening request" className={`mb-3 rounded border-l-4 p-3 text-sm ${tone}`}>
      <p className="font-semibold text-heading">{latest.state === 'DENIED' ? 'Reopening request denied by the Vice Chancellor'
        : latest.state === 'APPROVED' ? 'Reopening request approved' : 'Reopening request pending VC decision'} — KRA {latest.kra_number} · {latest.period}</p>
      {latest.state === 'DENIED' && <p className="mt-1">Reason: <span className="whitespace-pre-wrap">{latest.decision_reason}</span></p>}
      <p className="mt-1 text-muted">{line(latest)}</p>
      {older.length > 0 && <details className="mt-2"><summary className="cursor-pointer font-semibold">Earlier requests ({older.length})</summary>
        <ol className="mt-1 grid gap-1.5">{older.map((r) => <li key={r.id}><b>{r.state === 'DENIED' ? 'Denied' : r.state === 'APPROVED' ? 'Approved' : 'Pending'}.</b> {line(r)}</li>)}</ol></details>}
    </section>
  )
}

export function SubmissionLoader({ id, render }: { id: string; render: (d: SubmissionDetail, schema: Schema, reload: () => void) => React.ReactNode }) {
  const [state, setState] = useState<{ d: SubmissionDetail; schema: Schema; n: number } | null>(null)
  const [error, setError] = useState('')
  // Each completed load remounts the editor (key = n). A load whose effect was cleaned up (StrictMode's double run, an
  // unmount) is aborted so it cannot remount over the user's tab selection and unsaved input.
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const d = await api<SubmissionDetail>(`/submissions/${id}/`, { signal })
      const t = d.assignment.template!
      const s = await api<{ schema: Schema }>(`/templates/${t.key}/${t.version}/`, { signal })
      if (!signal?.aborted) setState((prev) => ({ d, schema: s.schema, n: (prev?.n ?? 0) + 1 }))
    } catch (e) { if (!signal?.aborted) setError((e as Error).message) }
  }, [id])
  useEffect(() => { const c = new AbortController(); load(c.signal); return () => c.abort() }, [load])
  const reload = useCallback(() => { load() }, [load])
  if (error) return <ErrorBox error={error} />
  if (!state) return <Loading />
  return <div key={state.n}>{render(state.d, state.schema, reload)}</div>
}

export default function WorkspaceRoute() {
  const { assignmentId, periodId } = useParams()
  const [info, setInfo] = useState<{ assignment: Assignment; period: Period; submission_id: string | null; can_request_reopen?: boolean; applicability: Applicability } | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const base = `/assignments/${assignmentId}/periods/${periodId}/`
      let r = await api<NonNullable<typeof info>>(base, { signal })
      if (!r.submission_id && r.period.is_open && r.assignment.template && r.applicability === 'APPLICABLE') {
        const c = await api<{ submission_id: string }>(base, { method: 'POST', signal }) // Dean action creates the row (D-017)
        r = { ...r, submission_id: c.submission_id }
      }
      if (!signal?.aborted) setInfo(r) // a stale response for the previous KRA/period never replaces the current one
    } catch (e) { if (!signal?.aborted) setError((e as Error).message) }
  }, [assignmentId, periodId])
  useEffect(() => { const c = new AbortController(); load(c.signal); return () => c.abort() }, [load])

  if (error) return <ErrorBox error={error} />
  if (!info) return <Loading />
  if (info.submission_id) return <SubmissionLoader key={info.submission_id} id={info.submission_id} render={(d, s, reload) => <Editor d={d} schema={s} reload={reload} />} />
  return (
    <div className="space-y-3">
      <Link className="underline text-sm" to="/dean/dashboard">← Back</Link>
      <div className="card">
        <h1 className="text-lg font-semibold">KRA {info.assignment.kra.number} — {info.period.label}</h1>
        {info.applicability === 'NOT_ASSIGNED'
          ? <p className="text-sm"><b className="text-heading">Not assigned for this period.</b> This KRA applies to your department from {info.assignment.effective_start_period?.label}.</p>
          : <p className="text-sm"><StatusBadge status="NOT_SUBMITTED" /> {info.period.is_closed ? 'This period is closed and no report was started.' : 'Not due — this period has not opened yet.'}</p>}
      </div>
      {info.can_request_reopen && info.assignment.template && (
        <ReopenRequestForm path={`/assignments/${assignmentId}/periods/${periodId}/reopen-requests/`} onDone={() => load()} />
      )}
    </div>
  )
}
