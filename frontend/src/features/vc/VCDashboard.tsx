import { useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import type { DisplayStatus } from '../../api/types'
import { Icon } from '../../components/icons'
import { ErrorBox, Loading, StatCard, StatusBadge, statusLabel } from '../../components/ui'
import { usePeriods, YearPeriodPicker } from '../dean/DeanDashboard'

interface Row { assignment_id: string; department: string; kra_number: number; kra_text: string; target_text: string; has_template: boolean; submission_id: string | null; display_status: DisplayStatus; achievement_text: string; is_nil: boolean
  achievement_source: 'submitted' | 'draft' | 'none'; revision_sequence: number | null; submitted_at: string | null; changed_since_submission: boolean }
interface Progress { counts: Record<DisplayStatus, number>; assigned: number; pending_reopen_requests: number; total: number; page: number; page_size: number; results: Row[] }
const STATUSES: DisplayStatus[] = ['NOT_SUBMITTED', 'DRAFT', 'SUBMITTED', 'REJECTED', 'APPROVED']

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
  const set = (patch: Record<string, string>) => {
    // merge first, then drop empty values, so choosing "All …" clears that filter
    const next = Object.fromEntries(Object.entries({ ...Object.fromEntries(params.entries()), year, period, ...patch }).filter(([, v]) => v))
    if (!('page' in patch)) delete next.page
    setParams(next)
  }
  const filterQuery = () => new URLSearchParams(Object.entries({ year, period, department: get('department'), kra: get('kra'), status: get('status'), search: get('search'), page: get('page', '1') }).filter(([, v]) => v))
  useEffect(() => { api<typeof departments>('/departments/').then(setDepartments).catch(() => {}) }, [])
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
  }, [params, period])

  const statusSel = get('status') as DisplayStatus | ''
  const filtered = !!(get('department') || get('kra') || get('search') || statusSel)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const fld = 'grid gap-1.5 text-sm font-semibold text-heading'
  return (
    <div className="grid gap-[18px]">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div>
          <h1 className="text-[28px] font-bold leading-tight md:text-4xl">Institution KRA status</h1>
          <p className="mt-1 text-base text-muted md:text-xl">All departments · {year}</p>
        </div>
        <YearPeriodPicker year={year} period={period} periods={periods} onChange={(y, p) => setParams(p ? { year: y, period: p } : { year: y })} />
      </div>

      <section aria-labelledby="vc-sum" className="grid gap-2">
        <h2 id="vc-sum" className="sr-only">Report counts</h2>
        {data && (
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4 lg:gap-3 2xl:grid-cols-7">
            <StatCard kind="ASSIGNED" value={data.assigned} label="Assigned" />
            {STATUSES.map((s) => <StatCard key={s} kind={s} value={data.counts[s]} label={statusLabel(s)} pressed={statusSel === s}
              onClick={() => set({ status: statusSel === s ? '' : s })} />)}
            <Link to="/vc/reopen-requests" className="flex items-center gap-3 rounded-[10px] border border-line bg-white px-3 py-3 hover:border-action md:px-4">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent-btn text-lg font-extrabold text-white md:h-11 md:w-11" aria-hidden="true">!</span>
              <span><span className="block text-2xl font-bold leading-tight text-heading md:text-[28px]">{data.pending_reopen_requests}</span><span className="text-sm text-ink md:text-[15px]">Pending reopen requests</span></span>
            </Link>
          </div>
        )}
        <p className="text-sm text-muted">Status counts apply every filter except Status; select a status card or the Status filter to list only those rows.</p>
      </section>

      <section aria-label="Filters" className="flex flex-wrap items-end gap-3 rounded-[10px] border border-line bg-white p-4">
        <label className={`${fld} w-full sm:w-44`}>Department
          <select className="input" value={get('department')} onChange={(e) => set({ department: e.target.value })}>
            <option value="">All departments</option>{departments.map((d) => <option key={d.code} value={d.code}>{d.code}</option>)}
          </select></label>
        <label className={`${fld} w-full sm:w-28`}>KRA number
          <input className="input" type="number" min={1} max={45} placeholder="Any" value={get('kra')} onChange={(e) => set({ kra: e.target.value })} /></label>
        <label className={`${fld} w-full sm:w-64`}>Search activity
          <input className="input" placeholder="Words in the activity, then Enter" defaultValue={get('search')} key={get('search')}
            onKeyDown={(e) => { if (e.key === 'Enter') set({ search: (e.target as HTMLInputElement).value }) }} /></label>
        <label className={`${fld} w-full sm:w-48`}>Status
          <select className="input" value={statusSel} onChange={(e) => set({ status: e.target.value })}>
            <option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
          </select></label>
        {filtered && <button type="button" className="btn-quiet" onClick={() => setParams({ year, period })}>Clear filters</button>}
        <button type="button" className="btn-primary w-full sm:ml-auto sm:w-auto" disabled={exporting || !data} onClick={exportPdf} aria-describedby="export-note">
          <Icon name="download" />{exporting ? 'Preparing PDF…' : `Export PDF${data ? ` (${data.total} rows)` : ''}`}</button>
        <p id="export-note" className="w-full text-sm text-muted">The PDF contains every row matching these filters, not only this page.</p>
      </section>

      <ErrorBox error={error || exportError} />
      {!data ? (!error && <Loading />) : data.results.length === 0 ? <p className="rounded-[10px] border border-line bg-white p-5 text-muted">No assignments match these filters.</p> : (
        <section aria-label="Reports" className="overflow-hidden rounded-[10px] border border-line bg-white">
          <div className="overflow-x-auto">
            <table role="table" className="report-table w-full text-[15px]">
              <thead role="rowgroup" className="bg-subtle text-left">
                <tr role="row">{['Dept', 'KRA', 'Annual target', 'Achievement (this period)', 'Status'].map((h) => <th role="columnheader" key={h} className="whitespace-nowrap border-b border-line px-3.5 py-2.5 font-semibold text-heading">{h}</th>)}
                  <th role="columnheader" className="border-b border-line px-3.5 py-2.5 text-center font-semibold text-heading">Action</th></tr>
              </thead>
              <tbody role="rowgroup">
                {data.results.map((r) => (
                  <tr role="row" key={r.assignment_id} className="border-b border-line align-top last:border-b-0">
                    <td role="cell" data-col="head" className="whitespace-nowrap px-3.5 py-3 font-bold text-heading">{r.department}<span className="md:hidden"> · KRA {r.kra_number}</span></td>
                    <td role="cell" data-col="wide" className="px-3.5 py-3"><b className="mr-1 text-heading max-md:hidden">{r.kra_number}</b>
                      <span className="text-sm">{r.kra_text.replace(/^KRA \d+:\s*/, '')}</span></td>
                    <td role="cell" data-col="wide" data-label="Annual target" className="w-48 whitespace-pre-wrap px-3.5 py-3">{r.target_text}</td>
                    <td role="cell" data-col="wide" className="px-3.5 py-3">
                      <span className="whitespace-pre-wrap">{r.achievement_text || '—'}</span>
                      {r.is_nil && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading" title="Nil report">Nil</span>}
                      {r.achievement_source === 'submitted' && <span className="mt-1 block text-[13px] text-muted">Submitted revision {r.revision_sequence}{r.submitted_at ? ` · ${fmtDateTime(r.submitted_at)}` : ''}</span>}
                      {r.achievement_source === 'draft' && <span className="mt-1 inline-block rounded bg-warn-bg px-2 py-0.5 text-[13px] font-semibold text-warn">Unsubmitted draft — not reviewed</span>}
                      {r.changed_since_submission && <span className="mt-1 block text-[13px] font-semibold text-warn">Edited after submission; not resubmitted</span>}
                    </td>
                    <td role="cell" data-col="status" className="whitespace-nowrap px-3.5 py-3"><StatusBadge status={r.display_status} /></td>
                    <td role="cell" data-col="action" className="w-40 px-3.5 py-3 text-center">
                      {r.submission_id && r.display_status !== 'NOT_SUBMITTED'
                        ? <Link className={`${r.display_status === 'SUBMITTED' ? 'btn-primary' : 'btn-secondary border-action'} min-h-9 w-full text-sm`} to={`/vc/review/${r.submission_id}`}
                            state={{ back: location.pathname + location.search }}>{r.display_status === 'SUBMITTED' ? 'Review' : 'View & history'}</Link>
                        : <span className="text-sm text-muted">No report yet</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm md:px-5">
            <span className="text-muted"><span>{data.total} rows</span> · page {data.page} of {pages}</span>
            <span className="flex gap-2">
              <button className="btn-secondary min-h-9 text-sm" disabled={data.page <= 1} onClick={() => set({ page: String(data.page - 1) })}>Previous</button>
              <button className="btn-secondary min-h-9 text-sm" disabled={data.page * data.page_size >= data.total} onClick={() => set({ page: String(data.page + 1) })}>Next</button>
            </span>
          </div>
        </section>
      )}
    </div>
  )
}
