import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import { Icon } from '../../components/icons'
import { EmptyState, IconSelect, PageHero, Pager, Panel } from '../../components/page'
import { ErrorBox, Loading } from '../../components/ui'
import { type Notice, NoticeText } from './common'

type State = 'DRAFT' | 'PUBLISHED' | 'WITHDRAWN'
interface VCNotice extends Notice { state: State; expired: boolean; edit_version: number; revision: number
  audience: { all: boolean; departments: string[] }; recipients: string[]; read_count: number; created_at: string; updated_at: string
  withdrawn_at: string | null; pending_scope: { year: string; periods: string[]; kras: number[] } | null }
type Revision = { number: number; kind: string; content_version: number; title: string; body: string; created_at: string; audience: string[]; by: string; pinned: boolean; expires_at: string | null }
const LABEL = (n: VCNotice) => n.state === 'PUBLISHED' ? (n.expired ? 'Expired' : 'Published') : n.state === 'DRAFT' ? 'Draft' : 'Withdrawn'

const STATE_PILL: Record<string, string> = { Published: 'bg-ok-bg text-ok', Draft: 'bg-neutral-bg text-neutral', Expired: 'bg-warn-bg text-warn', Withdrawn: 'bg-err-bg text-err' }
const COUNTS = [['', 'Total announcements', 'doc', 'bg-info-bg text-action'], ['ACTIVE', 'Published (active)', 'check', 'bg-ok-bg text-ok'],
  ['DRAFT', 'Drafts', 'pencil', 'bg-warn-bg text-warn'], ['WITHDRAWN', 'Withdrawn', 'xcircle', 'bg-err-bg text-err']] as const

export function VCAnnouncementList() {
  const [state, setState] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<{ total: number; page: number; page_size: number; results: VCNotice[] } | null>(null)
  const [totals, setTotals] = useState<Record<string, number> | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {  // headline counts come from the API's own totals per state (one small request each)
    Promise.all(COUNTS.map(([st]) => api<{ total: number }>(`/announcements/${st ? `?state=${st}` : ''}`).then((r) => [st, r.total] as const)))
      .then((r) => setTotals(Object.fromEntries(r))).catch(() => setTotals(null))
  }, [])
  useEffect(() => {
    let live = true
    setData(null)
    api<NonNullable<typeof data>>(`/announcements/?page=${page}${state ? `&state=${state}` : ''}`).then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : 'Failed to load'))
    return () => { live = false }
  }, [state, page])
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <div className="grid gap-[18px]">
      <PageHero icon="megaphone" photo={false} title="Announcements" description="In-portal notices to all or selected departments. No email or SMS is sent."
        aside={<Link to="/vc/announcements/new" className="btn-primary min-h-12 w-full px-5 sm:w-auto"><Icon name="plus" />New announcement</Link>} />
      {totals && <section aria-label="Announcement totals" className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-4">
        {COUNTS.map(([st, label, icon, tone]) => <div key={st} className="panel flex items-center gap-3.5 px-4 py-4">
          <span aria-hidden="true" className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl ${tone}`}><Icon name={icon} /></span>
          <span className="min-w-0"><span className="block text-sm text-muted">{label}</span><span className="text-2xl font-bold text-heading">{totals[st]}</span></span></div>)}
      </section>}
      <ErrorBox error={error} />
      <Panel title="Announcements" icon="doc" labelledBy="ann-list" className="overflow-hidden"
        description="Manage every announcement. Read = Deans who opened the current version."
        actions={<IconSelect label="Show" icon="list" className="w-full sm:w-60" value={state} onChange={(e) => { setState(e.target.value); setPage(1) }}>
          <option value="">All</option><option value="DRAFT">Drafts</option><option value="ACTIVE">Published (active)</option>
          <option value="EXPIRED">Expired</option><option value="WITHDRAWN">Withdrawn</option></IconSelect>}>
        {!data ? (!error && <Loading />) : data.results.length === 0 ? <EmptyState icon="megaphone" title="No announcements.">{state ? 'None in this view.' : 'Create the first one with New announcement.'}</EmptyState> : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[880px] text-[15px]"><caption className="sr-only">Announcements</caption>
              <thead className="thead-soft"><tr>{['Title', 'State', 'Audience', 'Read', 'Updated', 'Action'].map((h) =>
                <th key={h} scope="col" className="border-y border-line px-4 py-3">{h}</th>)}</tr></thead>
              <tbody>{data.results.map((n) => <tr key={n.id} className="border-b border-line align-top last:border-b-0">
                <td className="w-[36%] min-w-64 px-4 py-3"><span className="flex items-start gap-2">{n.pinned && <span className="shrink-0 text-accent-btn" title="Pinned"><Icon name="pin" size={18} /></span>}
                  <span className="min-w-0 break-words"><Link className="font-semibold text-action underline-offset-2 hover:underline" to={`/vc/announcements/${n.id}`}>{n.title}</Link>
                    {n.pinned && <span className="ml-2 rounded-full bg-err-bg px-2 py-0.5 text-xs font-semibold text-err">Pinned</span>}
                    {/* wraps to two lines inside its own column (a one-line `truncate` here could not shrink and ran across the next columns) */}
                    <span className="mt-0.5 line-clamp-2 text-sm text-muted">{n.body}</span></span></span></td>
                <td className="whitespace-nowrap px-4 py-3"><span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${STATE_PILL[LABEL(n)]}`}>
                  <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />{LABEL(n)}</span></td>
                <td className="w-[24%] min-w-44 px-4 py-3 text-sm"><span className="flex items-start gap-1.5"><span className="shrink-0 text-muted" aria-hidden="true"><Icon name="people" size={18} /></span>
                  <span className="min-w-0 break-words">{n.state === 'DRAFT' ? (n.audience.all ? 'All departments' : n.audience.departments.join(', ')) : n.recipients.join(', ')}</span></span></td>
                <td className="px-4 py-3">{n.state === 'DRAFT' ? '—' : `${n.read_count}`}</td>
                <td className="whitespace-nowrap px-4 py-3 text-sm">{fmtDateTime(n.updated_at)}</td>
                <td className="px-4 py-3"><Link className="btn-secondary min-h-9 text-sm" to={`/vc/announcements/${n.id}`}>{n.state === 'WITHDRAWN' ? 'View' : 'Open'}<span className="sr-only"> {n.title}</span></Link></td></tr>)}</tbody></table>
          </div>
        )}
        {data && <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm md:px-5">
          <span className="text-muted">{data.total} announcement{data.total === 1 ? '' : 's'} · page {data.page} of {pages}</span>
          <Pager page={data.page} pages={pages} onPage={setPage} label="Announcement pages" /></div>}
      </Panel>
    </div>
  )
}

export function VCAnnouncementEditor() {
  const { id } = useParams()
  const isNew = id === 'new'
  const nav = useNavigate()
  const [n, setN] = useState<VCNotice | null>(null)
  const [depts, setDepts] = useState<{ code: string; name: string }[]>([])
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [all, setAll] = useState(true)
  const [codes, setCodes] = useState<string[]>([])
  const [pinned, setPinned] = useState(false)
  const [expires, setExpires] = useState('')
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({})
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState<string[] | null>(null)
  const [eligibility, setEligibility] = useState<{ newly_pending: string[]; no_longer_pending: string[]; eligible: string[] } | null>(null)
  const [history, setHistory] = useState<Revision[] | null>(null)

  const load = (x: VCNotice) => {
    setN(x); setTitle(x.title); setBody(x.body); setAll(x.audience.all); setCodes(x.audience.departments); setPinned(x.pinned)
    setExpires(x.expires_at ? new Date(x.expires_at).toLocaleString('sv-SE', { timeZone: 'Asia/Kolkata' }).slice(0, 16).replace(' ', 'T') : '')
  }
  useEffect(() => { api<typeof depts>('/departments/').then(setDepts).catch(() => {}) }, [])
  useEffect(() => {
    if (isNew) return
    api<VCNotice>(`/announcements/${id}/`).then(load).catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load'))
  }, [id, isNew])

  const payload = () => ({ title, body, pinned, expires_at: expires || null, audience: all ? { all: true } : { departments: codes } })
  async function run<T>(fn: () => Promise<T>, done: string) {
    setBusy(true); setError(''); setFieldErrors({}); setMsg('')
    try { const r = await fn(); setMsg(done); return r } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message); setFieldErrors(e.fieldErrors)
        if (e.code === 'version_conflict' && e.body.current) load(e.body.current as VCNotice)
        if (e.code === 'eligibility_changed') setEligibility(e.body as never)
      } else setError('Request failed')
    } finally { setBusy(false) }
  }
  async function save() {
    if (isNew) {
      const r = await run(() => api<VCNotice>('/announcements/', { method: 'POST', body: payload() }), 'Draft saved.')
      if (r) nav(`/vc/announcements/${r.id}`, { replace: true })
      return
    }
    const r = await run(() => api<VCNotice>(`/announcements/${id}/`, { method: 'PATCH', body: { ...payload(), edit_version: n!.edit_version } }),
      n?.state === 'PUBLISHED' ? 'Changes published. Title or message changes show as unread to recipients; audience, pin and expiry changes do not.' : 'Draft saved.')
    if (r) { load(r); setHistory(null) }
  }
  async function reviewPublish() {
    const r = await run(() => api<{ departments: { code: string }[] }>('/announcements/recipients-preview/', { method: 'POST', body: { audience: payload().audience } }), '')
    if (r) setConfirming(r.departments.map((d) => d.code))
  }
  async function publish(acknowledge = false) {
    const r = await run(() => api<VCNotice>(`/announcements/${id}/publish/`, { method: 'POST', body: { edit_version: n!.edit_version, acknowledge_eligibility: acknowledge } }),
      'Published. Recipients see it in their Announcements inbox.')
    if (r) { load(r); setConfirming(null); setEligibility(null) }
  }
  async function withdraw() {
    if (!window.confirm('Withdraw this announcement? Departments will no longer see it; its history is kept.')) return
    const r = await run(() => api<VCNotice>(`/announcements/${id}/withdraw/`, { method: 'POST', body: { edit_version: n!.edit_version } }), 'Withdrawn.')
    if (r) load(r)
  }
  async function remove() {
    if (!window.confirm('Delete this draft?')) return
    const r = await run(() => api(`/announcements/${id}/`, { method: 'DELETE', body: { edit_version: n!.edit_version } }), '')
    if (r !== undefined) nav('/vc/announcements')
  }
  const showHistory = () => api<{ results: Revision[] }>(`/announcements/${id}/revisions/`).then((r) => setHistory(r.results)).catch(() => {})

  if (!isNew && !n) return error ? <ErrorBox error={error} /> : <Loading />
  const editable = isNew || n!.state !== 'WITHDRAWN'
  const fe = (k: string) => fieldErrors[k]?.join(' ')
  const fld = 'grid gap-1.5 text-sm font-semibold text-heading'
  return (
    <div className="grid gap-4">
      <Link to="/vc/announcements" className="text-sm text-action underline">← All announcements</Link>
      <h1 className="text-[28px] font-bold leading-tight md:text-4xl">{isNew ? 'New announcement' : n!.title}</h1>
      {n && <p className="text-muted">{LABEL(n)}{n.published_at ? ` · published ${fmtDateTime(n.published_at)}` : ''}{n.state !== 'DRAFT' ? ` · ${n.recipients.length} department(s) · read by ${n.read_count} (current version)` : ''}</p>}
      {n?.pending_scope && n.state === 'DRAFT' && <p className="rounded bg-warn-bg px-3 py-2 text-sm text-warn">Prepared from Analytics for departments with pending reports
        ({n.pending_scope.year}: {n.pending_scope.periods.join('; ')}). Review the recipients and text before publishing; recipients are checked again on publication.
        This notice does not reopen reporting windows.</p>}
      <ErrorBox error={error} />
      {msg && <p role="status" className="rounded bg-ok-bg px-3 py-2 text-sm">{msg}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-label="Announcement details" className="grid gap-3 panel p-4">
          <label className={fld}>Title<input className="input" value={title} maxLength={200} disabled={!editable} onChange={(e) => setTitle(e.target.value)} aria-invalid={!!fe('title')} />
            {fe('title') && <span className="text-err">{fe('title')}</span>}</label>
          <label className={fld}>Message (plain text; http/https links allowed)<textarea className="input min-h-40" value={body} maxLength={10000} disabled={!editable}
            onChange={(e) => setBody(e.target.value)} aria-invalid={!!fe('body')} />{fe('body') && <span className="text-err">{fe('body')}</span>}</label>
          <fieldset className="grid gap-2" disabled={!editable}><legend className="text-sm font-semibold text-heading">Audience</legend>
            <label className="flex items-center gap-2"><input type="radio" name="aud" checked={all} onChange={() => setAll(true)} />All departments (fixed when published)</label>
            <label className="flex items-center gap-2"><input type="radio" name="aud" checked={!all} onChange={() => setAll(false)} />Selected departments</label>
            {!all && <div className="grid max-h-56 gap-1 overflow-auto rounded border border-line p-2 text-sm">{depts.map((d) => (
              <label key={d.code} className="flex items-center gap-2"><input type="checkbox" checked={codes.includes(d.code)}
                onChange={() => setCodes(codes.includes(d.code) ? codes.filter((c) => c !== d.code) : [...codes, d.code])} />{d.code} — {d.name}</label>))}</div>}
            {fe('audience') && <span className="text-sm text-err">{fe('audience')}</span>}
          </fieldset>
          <label className="flex items-center gap-2 text-[15px]"><input type="checkbox" className="h-5 w-5" checked={pinned} disabled={!editable} onChange={(e) => setPinned(e.target.checked)} />Pin to the top of Deans’ notices</label>
          <label className={fld}>Visible until (optional, IST)<input type="datetime-local" className="input" value={expires} disabled={!editable} onChange={(e) => setExpires(e.target.value)} />
            {fe('expires_at') && <span className="text-err">{fe('expires_at')}</span>}</label>
          {editable && <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary" disabled={busy} onClick={save}>{n?.state === 'PUBLISHED' ? 'Save and update' : 'Save draft'}</button>
            {n?.state === 'DRAFT' && <button type="button" className="btn-secondary" disabled={busy} onClick={reviewPublish}>Review and publish</button>}
            {n?.state === 'DRAFT' && <button type="button" className="btn-quiet" disabled={busy} onClick={remove}>Delete draft</button>}
            {n?.state === 'PUBLISHED' && <button type="button" className="btn-danger" disabled={busy} onClick={withdraw}>Withdraw</button>}
          </div>}
          {n?.state === 'DRAFT' && <p className="text-sm text-muted">Save changes before publishing; publication uses the saved draft.</p>}
        </section>
        <section aria-labelledby="pv-h" className="grid content-start gap-2 panel p-4">
          <h2 id="pv-h" className="text-lg font-bold text-heading">Preview (as Deans see it)</h2>
          <h3 className="text-xl font-bold text-heading">{title || 'Title'}</h3>
          <NoticeText text={body || 'Message'} />
        </section>
      </div>
      {confirming && (
        <section role="region" aria-label="Publish review" className="grid gap-2 panel border-2 border-action p-4">
          <p><b>Publish to {confirming.length} department(s):</b> {confirming.join(', ')}</p>
          {eligibility && <div className="rounded bg-warn-bg p-3 text-sm text-warn">
            <p>The departments with pending reports changed since this draft was prepared.</p>
            {!!eligibility.newly_pending.length && <p>Now pending but not in the audience: {eligibility.newly_pending.join(', ')}</p>}
            {!!eligibility.no_longer_pending.length && <p>No longer pending but in the audience: {eligibility.no_longer_pending.join(', ')}</p>}
            <p>Edit the audience and save, or publish to the audience shown above.</p></div>}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary" disabled={busy} onClick={() => publish(!!eligibility)}>{eligibility ? 'Publish to the audience shown' : 'Publish now'}</button>
            <button type="button" className="btn-secondary" onClick={() => { setConfirming(null); setEligibility(null) }}>Cancel</button></div>
        </section>
      )}
      {n && n.state !== 'DRAFT' && (history ? (
        <section aria-labelledby="hist-h" className="grid gap-2 panel p-4">
          <h2 id="hist-h" className="text-lg font-bold text-heading">History</h2>
          <ol className="grid gap-2 text-sm">{history.map((h) => <li key={h.number} className="border-t border-line pt-2">
            <b>{h.number}. {h.kind}</b> · {fmtDateTime(h.created_at)} · {h.by} · content version {h.content_version} · audience {h.audience.join(', ')}{h.pinned ? ' · pinned' : ''}
            <span className="block text-muted">{h.title}</span></li>)}</ol>
        </section>) : <button type="button" className="btn-quiet w-fit" onClick={showHistory}>Show history</button>)}
    </div>
  )
}
