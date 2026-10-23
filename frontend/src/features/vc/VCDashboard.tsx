import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import type { DisplayStatus } from '../../api/types'
import { Icon } from '../../components/icons'
import { ErrorBox, Loading, StatCard, StatusBadge, statusLabel } from '../../components/ui'
import { DeptChip, EmptyState, IconSelect, PageHero, Pager } from '../../components/page'
import { usePeriods, YearPeriodPicker } from '../dean/DeanDashboard'
import { BulkPanel, type BulkRun, type Prepare, PreviewDrawer, type PreviewTarget } from './BulkApproval'

interface Row { assignment_id: string; department: string; kra_number: number; kra_text: string; target_text: string; has_template: boolean; submission_id: string | null; display_status: DisplayStatus; achievement_text: string; is_nil: boolean
  achievement_source: 'submitted' | 'none'; revision_sequence: number | null; submitted_at: string | null
  revision_id: string | null; nil_reason: string; evidence_count: number | null }
interface Progress { counts: Record<DisplayStatus, number>; assigned: number; pending_reopen_requests: number; total: number; page: number; page_size: number; results: Row[] }
// Draft privacy (D-078): the VC sees no Draft status — a saved but unsubmitted report is Not submitted.
const STATUSES: DisplayStatus[] = ['NOT_SUBMITTED', 'SUBMITTED', 'REJECTED', 'APPROVED']

export default function VCDashboard() {
  const [params, setParams] = useSearchParams()
  const get = (k: string, d = '') => params.get(k) || d
  const year = get('year', '2026-27')
  const periods = usePeriods(year)
  const period = get('period') || String((periods.find((p) => p.is_open) ?? periods[0])?.id ?? '')
  const [departments, setDepartments] = useState<{ code: string; name: string }[]>([])
  const [data, setData] = useState<Progress | null>(null)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const location = useLocation()
  const [selected, setSelected] = useState<Map<string, string>>(new Map())  // submission -> exact submitted revision
  const [bulk, setBulk] = useState<{ request: Prepare | null; resume: BulkRun | null } | null>(null)
  const [resumable, setResumable] = useState<BulkRun | null>(null)
  const [preview, setPreview] = useState<PreviewTarget | null>(null)
  const [reload, setReload] = useState(0)
  const closePreview = useCallback(() => setPreview(null), [])
  const set = (patch: Record<string, string>) => {
    // merge first, then drop empty values, so choosing "All …" clears that filter
    const next = Object.fromEntries(Object.entries({ ...Object.fromEntries(params.entries()), year, period, ...patch }).filter(([, v]) => v))
    if (!('page' in patch)) delete next.page
    setParams(next)
  }
  const filterQuery = () => new URLSearchParams(Object.entries({ year, period, department: get('department'), kra: get('kra'), status: get('status'), search: get('search'), page: get('page', '1') }).filter(([, v]) => v))
  useEffect(() => { api<typeof departments>('/departments/').then(setDepartments).catch(() => {}) }, [])
  useEffect(() => {  // an approval run interrupted earlier (closed tab, lost session) can be resumed
    api<{ results: BulkRun[] }>('/bulk-approvals/').then((r) => setResumable(r.results.find((b) => b.resumable) ?? null)).catch(() => {})
  }, [reload])
  const scopeKey = JSON.stringify([year, period, get('department'), get('kra'), get('search')])
  useEffect(() => { setSelected(new Map()) }, [scopeKey])  // a selection belongs to the filters it was made under
  async function exportPdf() {  // all filtered rows, not just this page (D-068)
    setExporting(true); setExportError('')
    try {
      const q = filterQuery(); q.delete('page')
      const res = await fetch(`/api/v1/progress/export/?${q}`, { credentials: 'same-origin' })
      if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.message || 'Export failed') }
      const url = URL.createObjectURL(await res.blob())
      const a = document.createElement('a'); a.href = url
      a.download = (res.headers.get('Content-Disposition') ?? '').match(/filename="([^"]+)"/)?.[1] ?? 'KRA_progress.pdf'
      a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setExportError(e instanceof Error ? e.message : 'Export failed') } finally { setExporting(false) }
  }
  useEffect(() => {
    if (!period) return
    const q = filterQuery()
    setData(null); setError('')
    let live = true  // a slower earlier response must not overwrite the current filters' result (Phase 6A)
    api<Progress>(`/progress/?${q}`).then((d) => live && setData(d)).catch((e) => live && setError(e instanceof ApiError ? e.message : 'Failed to load'))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, period, reload])

  const statusSel = (get('status') === 'DRAFT' ? 'NOT_SUBMITTED' : get('status')) as DisplayStatus | ''  // old bookmarks
  const filtered = !!(get('department') || get('kra') || get('search') || statusSel)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const eligible = (data?.results ?? []).filter((r) => r.display_status === 'SUBMITTED' && r.revision_id && r.submission_id)
  const pageSelected = eligible.length > 0 && eligible.every((r) => selected.has(r.submission_id!))
  const toggle = (r: Row) => setSelected((m) => { const n = new Map(m); if (n.has(r.submission_id!)) n.delete(r.submission_id!); else n.set(r.submission_id!, r.revision_id!); return n })
  const togglePage = () => setSelected((m) => { const n = new Map(m); eligible.forEach((r) => { if (pageSelected) n.delete(r.submission_id!); else n.set(r.submission_id!, r.revision_id!) }); return n })
  const scopeFilters = () => Object.fromEntries(Object.entries({ year, period, department: get('department'), kra: get('kra'), search: get('search') }).filter(([, v]) => v))
  const awaiting = data?.counts.SUBMITTED ?? 0
  const targetOf = (r: Row): PreviewTarget => ({ submission: r.submission_id!, revision: r.revision_id!, title: `${r.department} · KRA ${r.kra_number}`,
    status: statusLabel(r.display_status), sequence: r.revision_sequence })
  const previewable = (data?.results ?? []).filter((r) => r.revision_id && r.submission_id)
  const at = preview ? previewable.findIndex((r) => r.revision_id === preview.revision) : -1
  const fld = 'grid gap-1.5 text-sm font-semibold text-heading'
  return (
    <div className="grid gap-[18px]">
      <PageHero eyebrow="Welcome back," title="Institution KRA status" description="Overview of KRA report submissions across all departments."
        chip={<>All departments · {year}</>}
        aside={<YearPeriodPicker year={year} period={period} periods={periods} onChange={(y, p) => setParams(p ? { year: y, period: p } : { year: y })} />} />

      <section aria-labelledby="vc-sum" className="grid gap-2">
        <h2 id="vc-sum" className="sr-only">Report counts</h2>
        {data && (
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:gap-3 xl:grid-cols-6">
            <StatCard kind="ASSIGNED" value={data.assigned} label="Assigned" total={data.assigned} />
            {STATUSES.map((s) => <StatCard key={s} kind={s} value={data.counts[s]} label={statusLabel(s)} total={data.assigned} pressed={statusSel === s}
              onClick={() => set({ status: statusSel === s ? '' : s })} />)}
            <Link to="/vc/reopen-requests" className="flex items-center gap-3 rounded-xl border border-[#E3E9EF] bg-white px-3.5 py-3 shadow-[0_2px_8px_rgba(12,45,71,.06)] hover:border-action md:px-4">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent-btn text-lg font-extrabold text-white md:h-11 md:w-11" aria-hidden="true">!</span>
              <span className="min-w-0 break-words"><span className="block text-2xl font-bold leading-tight text-heading md:text-[28px]">{data.pending_reopen_requests}</span><span className="text-sm text-ink md:text-[15px]">Pending reopen requests</span></span>
            </Link>
          </div>
        )}
        <p className="text-sm text-muted">Status counts apply every filter except Status; select a status card or the Status filter to list only those rows.</p>
      </section>

      <section aria-label="Filters" className="panel flex flex-wrap items-end gap-3 p-4 md:p-5">
        <IconSelect label="Department" icon="building" className="w-full sm:w-52" value={get('department')} onChange={(e) => set({ department: e.target.value })}>
          <option value="">All departments</option>{departments.map((d) => <option key={d.code} value={d.code}>{d.code}</option>)}
        </IconSelect>
        <label className={`${fld} w-full sm:w-32`}>KRA number
          <span className="relative block"><span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"><Icon name="layers" size={18} /></span>
            <input className="input pl-10" type="number" min={1} max={45} placeholder="All" value={get('kra')} onChange={(e) => set({ kra: e.target.value })} /></span></label>
        <label className={`${fld} w-full sm:w-72`}>Search activity
          <span className="relative block"><span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"><Icon name="search" size={18} /></span>
            <input className="input pl-10" placeholder="Search in the activity, then Enter" defaultValue={get('search')} key={get('search')}
              onKeyDown={(e) => { if (e.key === 'Enter') set({ search: (e.target as HTMLInputElement).value }) }} /></span></label>
        <IconSelect label="Status" icon="list" className="w-full sm:w-52" value={statusSel} onChange={(e) => set({ status: e.target.value })}>
          <option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
        </IconSelect>
        {filtered && <button type="button" className="btn-quiet" onClick={() => setParams({ year, period })}>Clear filters</button>}
        <button type="button" className="btn-primary min-h-11 w-full bg-brand hover:bg-heading sm:ml-auto sm:w-auto" disabled={exporting || !data} onClick={exportPdf} aria-describedby="export-note">
          <Icon name="download" />{exporting ? 'Preparing PDF…' : `Export PDF${data ? ` (${data.total} rows)` : ''}`}</button>
        <p id="export-note" className="w-full text-sm text-muted">The PDF contains every row matching these filters, not only this page.</p>
      </section>

      {resumable && !bulk && (
        <div role="status" className="flex flex-wrap items-center gap-3 rounded-xl border border-warn bg-warn-bg px-4 py-3 text-[15px]">
          <span>An approval run was interrupted: processed {resumable.processed} of {resumable.total}. Recorded approvals are kept.</span>
          <button type="button" className="btn-primary min-h-9 text-sm" onClick={() => setBulk({ request: null, resume: resumable })}>Resume</button>
        </div>
      )}
      {bulk && <BulkPanel request={bulk.request} resume={bulk.resume} onDone={() => { setSelected(new Map()); setReload((n) => n + 1) }}
        onClose={() => { setBulk(null); setReload((n) => n + 1) }} />}
      {!bulk && data && awaiting > 0 && (
        <section aria-label="Bulk approval" className="panel flex flex-wrap items-center gap-2 px-4 py-3">
          <span className="text-[15px]"><b>{selected.size}</b> selected</span>
          {eligible.length > 0 && <button type="button" className="btn-quiet min-h-9 text-sm md:hidden" onClick={togglePage}>
            {pageSelected ? 'Unselect this page' : `Select this page (${eligible.length})`}</button>}
          <button type="button" className="btn-primary min-h-9 text-sm" disabled={!selected.size}
            onClick={() => setBulk({ request: { scope: 'selection', items: [...selected].map(([submission, revision]) => ({ submission, revision })), filters: scopeFilters() }, resume: null })}>
            Approve selected ({selected.size})</button>
          <button type="button" className="btn-secondary min-h-9 text-sm"
            onClick={() => setBulk({ request: { scope: 'filtered', filters: scopeFilters() }, resume: null })}>
            Approve all matching filters ({awaiting} awaiting review)</button>
          {selected.size > 0 && <button type="button" className="btn-quiet min-h-9 text-sm" onClick={() => setSelected(new Map())}>Clear selection</button>}
          <p className="w-full text-sm text-muted">“All matching filters” includes every report awaiting review on all pages for this year, period and filters, not only this page.</p>
        </section>
      )}
      <ErrorBox error={error || exportError} />
      {!data ? (!error && <Loading />) : data.results.length === 0
        ? <div className="panel"><EmptyState icon="search" title="No assignments match these filters.">Change or clear the filters above.</EmptyState></div> : (
        <section aria-label="Reports" className="panel overflow-hidden">
          <div className="flex flex-wrap items-start justify-between gap-3 px-4 pb-3 pt-4 md:px-5">
            <div className="flex items-start gap-3"><span aria-hidden="true" className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-info-bg text-action"><Icon name="building" /></span>
              <div><h2 className="text-lg font-bold md:text-xl">Department-wise KRA status</h2>
                <p className="text-sm text-muted">One row per KRA for each department. Use the filters above to narrow the list.</p></div></div>
            <span className="rounded-lg bg-subtle px-3 py-1.5 text-sm font-medium text-heading">Total rows: {data.total}</span>
          </div>
          <div className="overflow-x-auto">
            <table role="table" className="report-table w-full text-[15px] md:min-w-[960px]">
              <thead role="rowgroup" className="thead-soft">
                <tr role="row"><th role="columnheader" className="w-10 border-b border-line px-2 py-2.5">
                  {eligible.length > 0 && <input type="checkbox" className="h-5 w-5" checked={pageSelected} onChange={togglePage} aria-label="Select this page (reports awaiting review)" />}</th>
                  {['Dept', 'KRA', 'Annual target', 'Achievement (this period)', 'Status'].map((h) => <th role="columnheader" key={h} className="whitespace-nowrap border-b border-line px-3.5 py-2.5 font-semibold text-heading">{h}</th>)}
                  <th role="columnheader" className="border-b border-line px-3.5 py-2.5 text-center font-semibold text-heading">Action</th></tr>
              </thead>
              <tbody role="rowgroup">
                {data.results.map((r) => (
                  <tr role="row" key={r.assignment_id} className="border-b border-line align-top last:border-b-0">
                    <td role="cell" data-col="select" className="w-10 px-2 py-3">{r.display_status === 'SUBMITTED' && r.revision_id && r.submission_id &&
                      <input type="checkbox" className="h-5 w-5" checked={selected.has(r.submission_id)} onChange={() => toggle(r)}
                        aria-label={`Select ${r.department} KRA ${r.kra_number} for approval`} />}</td>
                    <td role="cell" data-col="head" className="whitespace-nowrap px-3.5 py-3 font-bold text-heading"><DeptChip code={r.department} /><span className="md:hidden"> · KRA {r.kra_number}</span></td>
                    <td role="cell" data-col="wide" className="px-3.5 py-3"><b className="mr-1 text-heading max-md:hidden">{r.kra_number}</b>
                      <span className="text-sm">{r.kra_text.replace(/^KRA \d+:\s*/, '')}</span></td>
                    <td role="cell" data-col="wide" data-label="Annual target" className="w-48 whitespace-pre-wrap px-3.5 py-3">{r.target_text}</td>
                    <td role="cell" data-col="wide" className="px-3.5 py-3">
                      <span className="whitespace-pre-wrap">{r.achievement_text || '—'}</span>
                      {r.is_nil && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading" title="Nil report">Nil</span>}
                      {r.is_nil && r.nil_reason && <span className="mt-1 block whitespace-pre-wrap text-[13px]">Nil reason: {r.nil_reason}</span>}
                      {r.achievement_source === 'submitted' && r.evidence_count != null && <span className="mt-1 block text-[13px] text-muted">Evidence items submitted: {r.evidence_count}</span>}
                      {r.achievement_source === 'submitted' && <span className="mt-1 block text-[13px] text-muted">Submitted revision {r.revision_sequence}{r.submitted_at ? ` · ${fmtDateTime(r.submitted_at)}` : ''}</span>}
                    </td>
                    <td role="cell" data-col="status" className="whitespace-nowrap px-3.5 py-3"><StatusBadge status={r.display_status} /></td>
                    <td role="cell" data-col="action" className="w-40 px-3.5 py-3 text-center">
                      {r.submission_id && r.display_status !== 'NOT_SUBMITTED'
                        ? <Link className={`${r.display_status === 'SUBMITTED' ? 'btn-primary' : 'btn-secondary border-action'} min-h-9 w-full text-sm`} to={`/vc/review/${r.submission_id}`}
                            state={{ back: location.pathname + location.search }}>{r.display_status === 'SUBMITTED' ? 'Review' : 'View & history'}</Link>
                        : <span className="text-sm text-muted">No report yet</span>}
                      {r.revision_id && r.submission_id && <button type="button" className="btn-quiet mt-1 min-h-9 w-full text-sm"
                        onClick={() => setPreview(targetOf(r))}>
                        Quick preview<span className="sr-only"> of {r.department} KRA {r.kra_number}</span></button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm md:px-5">
            <span className="text-muted"><span>{data.total} rows</span> · page {data.page} of {pages}</span>
            <Pager page={data.page} pages={pages} onPage={(n) => set({ page: String(n) })} label="Report pages" />
          </div>
        </section>
      )}
      {preview && <PreviewDrawer target={preview} onClose={closePreview}
        onPrev={at > 0 ? () => setPreview(targetOf(previewable[at - 1])) : undefined}
        onNext={at >= 0 && at < previewable.length - 1 ? () => setPreview(targetOf(previewable[at + 1])) : undefined} />}
    </div>
  )
}
