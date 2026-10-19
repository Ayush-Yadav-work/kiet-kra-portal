import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import { Icon } from '../../components/icons'
import { ErrorBox, Loading } from '../../components/ui'
import { usePeriods } from '../dean/DeanDashboard'
import PendingNotice from './PendingNotice'

// VC features plan v2.3 §6–8 (D-074): approved applicable report slots ÷ expected applicable report slots. Charts are plain
// HTML/CSS with text and table equivalents (no chart library); the PDF draws the same figures server-side.
type Bucket = 'NOT_SUBMITTED' | 'DRAFT' | 'AWAITING_REVIEW' | 'RETURNED' | 'REJECTED' | 'APPROVED' | 'NOT_DUE'
type Rate = { approved: number; expected: number; remaining: number; assignments: number; rate: number | null; rate_label: string }
type TrendPoint = { period_id: number; index: number; label: string; opened: boolean; approved: number; expected: number; rate_label: string }
type Detail = { department: string; kra_number: number; kra_text: string; period: string; target_text: string; status: Bucket; status_label: string
  achievement_text: string; achievement_source: 'submitted' | 'draft' | 'none'; is_nil: boolean; reopened: boolean }
type Data = { as_of: string; drafts_pending: number; summary: Rate; breakdown: Record<Bucket, number>; labels: Record<Bucket, string>
  departments: (Rate & { code: string; name: string; breakdown: Record<Bucket, number> })[]; trend: TrendPoint[]
  department_trends: Record<string, TrendPoint[]>; matrix: { kras: number[]; rows: { department: string; cells: ({ approved: number; expected: number; bucket: string | null } | null)[] }[] }
  details: { total: number; page: number; page_size: number; results: Detail[] }; filters: { scope: string; scope_label: string } }

const BUCKETS: Bucket[] = ['APPROVED', 'AWAITING_REVIEW', 'DRAFT', 'RETURNED', 'REJECTED', 'NOT_SUBMITTED', 'NOT_DUE']
const COLOR: Record<Bucket, string> = { APPROVED: 'bg-ok', AWAITING_REVIEW: 'bg-info', DRAFT: 'bg-[#B7791F]', RETURNED: 'bg-[#B45309]', REJECTED: 'bg-err',
  NOT_SUBMITTED: 'bg-[#7A8899]', NOT_DUE: 'bg-[#D0D7DE]' }
const YEARS = ['2026-27', '2027-28', '2028-29']
const pct = (a: number, e: number) => (e ? Math.round((a / e) * 1000) / 10 : 0)

export default function Analytics() {
  const [params, setParams] = useSearchParams()
  const year = params.get('year') || '2026-27'
  const scope = params.get('scope') || 'ytd'
  const periods = usePeriods(year)
  const period = params.get('period') || String((periods.find((p) => p.is_open) ?? periods[0])?.id ?? '')
  const depts = params.getAll('department')
  const kra = params.get('kra') || ''
  const status = params.get('status') || ''
  const page = params.get('page') || '1'
  const [allDepts, setAllDepts] = useState<{ code: string; name: string }[]>([])
  const [kraList, setKraList] = useState<number[]>([])
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)
  const [exporting, setExporting] = useState('')
  const [exportError, setExportError] = useState('')
  const [announce, setAnnounce] = useState(false)

  const query = (extra: Record<string, string> = {}) => {
    const q = new URLSearchParams({ year, scope, ...(scope === 'period' && period ? { period } : {}), ...(kra ? { kra } : {}), ...(status ? { status } : {}), page, ...extra })
    depts.forEach((d) => q.append('department', d))
    return q
  }
  const set = (patch: Record<string, string | string[]>) => {
    const n = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) { n.delete(k); (Array.isArray(v) ? v : [v]).filter(Boolean).forEach((x) => n.append(k, x)) }
    if (!('page' in patch)) n.delete('page')
    setParams(n)
  }
  useEffect(() => {
    api<{ code: string; name: string }[]>('/departments/').then(setAllDepts).catch(() => {})
    api<{ number: number }[]>('/kras/').then((k) => setKraList(k.map((x) => x.number))).catch(() => {})
  }, [])
  useEffect(() => {
    if (scope === 'period' && !period) return
    let live = true  // a slower response for earlier filters never replaces the current one
    setData(null); setError('')
    api<Data>(`/analytics/?${query()}`).then((d) => live && setData(d)).catch((e) => live && setError(e instanceof ApiError ? e.message : 'Failed to load'))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, period, nonce])

  async function exportFile(kind: 'pdf' | 'csv') {
    setExporting(kind); setExportError('')
    try {
      const q = query({ kind }); q.delete('page')
      const res = await fetch(`/api/v1/analytics/export/?${q}`, { credentials: 'same-origin' })
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.message || 'Export failed') }
      const url = URL.createObjectURL(await res.blob()); const a = document.createElement('a'); a.href = url
      a.download = (res.headers.get('Content-Disposition') ?? '').match(/filename="([^"]+)"/)?.[1] ?? `KRA_analytics.${kind}`
      a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setExportError(e instanceof Error ? e.message : 'Export failed') } finally { setExporting('') }
  }

  const fld = 'grid gap-1.5 text-sm font-semibold text-heading'
  const compare = depts.length >= 2
  return (
    <div className="grid gap-[18px]">
      <div>
        <h1 className="text-[28px] font-bold leading-tight md:text-4xl">Report approval analytics</h1>
        <p className="mt-1 text-muted">Completion = approved report slots ÷ expected report slots. One slot is one finalised assignment in one reporting period
          from its start period. Targets are text and are not scored.</p>
      </div>

      <section aria-label="Analytics filters" className="flex flex-wrap items-end gap-3 rounded-[10px] border border-line bg-white p-4">
        <label className={`${fld} w-full sm:w-36`}>Academic year
          <select className="input" value={year} onChange={(e) => set({ year: e.target.value, period: '' })}>{YEARS.map((y) => <option key={y}>{y}</option>)}</select></label>
        <label className={`${fld} w-full sm:w-52`}>Scope
          <select className="input" value={scope} onChange={(e) => set({ scope: e.target.value })}>
            <option value="period">Bimonthly period</option><option value="ytd">Year to date</option><option value="year">Full academic year</option></select></label>
        {scope === 'period' && <label className={`${fld} w-full sm:w-80`}>Reporting period
          <select className="input" value={period} onChange={(e) => set({ period: e.target.value })}>
            {periods.map((p) => <option key={p.id} value={p.id}>{p.label}{p.is_open ? ' (open)' : p.is_closed ? ' (closed)' : ' (not due)'}</option>)}</select></label>}
        <label className={`${fld} w-full sm:w-32`}>KRA
          <select className="input" value={kra} onChange={(e) => set({ kra: e.target.value })}>
            <option value="">All</option>{kraList.map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
        <details className="relative w-full rounded-lg border border-control bg-white sm:w-72">
          <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-heading">Departments: {depts.length ? `${depts.length} selected` : 'all'}</summary>
          <div className="absolute left-0 right-0 top-full z-10 mt-1 grid max-h-64 gap-1 overflow-auto rounded-lg border border-line bg-white p-3 text-sm shadow-lg">
            <div className="mb-1 flex gap-2"><button type="button" className="btn-quiet min-h-8 text-sm" onClick={() => set({ department: allDepts.map((d) => d.code) })}>Select all</button>
              <button type="button" className="btn-quiet min-h-8 text-sm" onClick={() => set({ department: [] })}>All (no filter)</button></div>
            {allDepts.map((d) => <label key={d.code} className="flex items-center gap-2"><input type="checkbox" checked={depts.includes(d.code)}
              onChange={() => set({ department: depts.includes(d.code) ? depts.filter((x) => x !== d.code) : [...depts, d.code] })} />{d.code} — {d.name}</label>)}
          </div>
        </details>
        <div className="flex w-full flex-wrap gap-2 sm:ml-auto sm:w-auto">
          <button type="button" className="btn-primary" disabled={!!exporting || !data} onClick={() => exportFile('pdf')}><Icon name="download" />{exporting === 'pdf' ? 'Preparing PDF…' : 'Export PDF'}</button>
          <button type="button" className="btn-secondary" disabled={!!exporting || !data} onClick={() => exportFile('csv')}>{exporting === 'csv' ? 'Preparing CSV…' : 'Export CSV'}</button>
          <button type="button" className="btn-secondary" disabled={!data || (scope === 'period' && !data.trend.find((t) => String(t.period_id) === period)?.opened)}
            onClick={() => setAnnounce(true)}>Announce to pending departments</button>
        </div>
        <p className="w-full text-sm text-muted">Exports recompute every matching report slot at download time with these filters. {scope === 'ytd' ? 'Year to date counts periods that have opened, including the current one.'
          : scope === 'year' ? 'Full year counts all six periods; future periods are Not due but still expected.' : 'A period that has not opened shows its planned count and Not due.'}</p>
      </section>
      <ErrorBox error={exportError} />
      {announce && data && <PendingNotice year={year} opened={data.trend.filter((t) => t.opened)} fixedPeriod={scope === 'period' ? Number(period) : null}
        departments={depts} kra={kra} onClose={() => setAnnounce(false)} />}
      {error ? <div className="grid gap-2"><ErrorBox error={error} /><button className="btn-secondary w-fit" onClick={() => setNonce((n) => n + 1)}>Try again</button></div>
        : !data ? <Loading /> : (<>
        <section aria-label="Summary" className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-[10px] border border-[#B9CDE0] bg-white p-4 sm:col-span-2">
            <p className="text-sm text-muted">{data.filters.scope_label} — report approval completion</p>
            <p className="text-3xl font-bold text-heading">{data.summary.rate_label}</p>
            <p className="text-[15px]">{data.summary.approved} of {data.summary.expected} reports approved</p>
          </div>
          <div className="rounded-[10px] border border-line bg-white p-4"><p className="text-sm text-muted">Remaining to approve</p><p className="text-3xl font-bold text-heading">{data.summary.remaining}</p>
            <p className="text-sm text-muted">{data.summary.assignments} finalised assignments</p></div>
          <div className="rounded-[10px] border border-line bg-white p-4"><p className="text-sm text-muted">Unpublished draft allocations</p><p className="text-3xl font-bold text-heading">{data.drafts_pending}</p>
            <p className="text-sm text-muted">Excluded until finalised</p></div>
          <p className="text-sm text-muted sm:col-span-2 xl:col-span-4">Data as of {fmtDateTime(data.as_of)}. The detail status filter below never changes these rates.</p>
        </section>

        <section aria-labelledby="wb" className="rounded-[10px] border border-line bg-white p-4">
          <h2 id="wb" className="mb-3 text-xl font-bold">Workflow breakdown</h2>
          <div aria-hidden="true" className="flex h-4 overflow-hidden rounded bg-subtle">{BUCKETS.map((b) => data.breakdown[b] > 0 &&
            <span key={b} className={COLOR[b]} style={{ width: `${(data.breakdown[b] / Math.max(1, data.summary.expected)) * 100}%` }} />)}</div>
          <ul className="mt-3 grid gap-x-6 gap-y-1 text-[15px] sm:grid-cols-2 lg:grid-cols-4">{BUCKETS.map((b) => <li key={b} className="flex items-center gap-2">
            <span aria-hidden="true" className={`inline-block h-3 w-3 rounded-sm ${COLOR[b]}`} /><b className="text-heading">{data.breakdown[b]}</b> {data.labels[b]}</li>)}</ul>
        </section>

        <section aria-labelledby="dc" className="rounded-[10px] border border-line bg-white p-4">
          <h2 id="dc" className="mb-1 text-xl font-bold">Departments{compare ? ' — comparison' : ''}</h2>
          <p className="mb-3 text-sm text-muted">Counts are shown with every rate: departments have different numbers of assignments. N/A = no assignment in this filter.</p>
          <ul className="grid gap-2">{data.departments.map((d) => <li key={d.code} className="grid items-center gap-x-3 sm:grid-cols-[7rem_minmax(0,1fr)_14rem]">
            <span className="font-semibold text-heading">{d.code}</span>
            <span aria-hidden="true" className="h-3 overflow-hidden rounded bg-subtle"><span className="block h-3 bg-brand" style={{ width: `${pct(d.approved, d.expected)}%` }} /></span>
            <span className="text-sm">{d.assignments === 0 ? 'N/A — no assignments' : d.expected === 0 ? d.rate_label : `${d.approved} / ${d.expected} — ${d.rate_label}`}</span></li>)}</ul>
          {compare && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm"><caption className="mb-1 text-left font-semibold text-heading">Approved / expected by reporting period</caption>
                <thead className="bg-subtle text-left"><tr><th className="p-2">Department</th>{data.trend.map((t) => <th key={t.period_id} className="p-2">P{t.index}</th>)}</tr></thead>
                <tbody>{depts.map((code) => <tr key={code} className="border-t border-line"><td className="p-2 font-semibold">{code}</td>
                  {(data.department_trends[code] ?? []).map((t) => <td key={t.period_id} className="p-2">{!t.opened ? 'Not due' : t.expected ? `${t.approved}/${t.expected}` : 'N/A'}</td>)}</tr>)}</tbody></table>
            </div>)}
        </section>

        <section aria-labelledby="tr" className="rounded-[10px] border border-line bg-white p-4">
          <h2 id="tr" className="mb-3 text-xl font-bold">Approval by reporting period</h2>
          <div aria-hidden="true" className="flex h-36 items-end gap-3 border-b border-control px-1">{data.trend.map((t) =>
            <div key={t.period_id} className="flex h-full flex-1 flex-col items-center justify-end">
              {t.opened ? <span className="w-3/4 rounded-t bg-brand" style={{ height: `${pct(t.approved, t.expected)}%` }} />
                : <span className="w-3/4 rounded-t border border-dashed border-control py-1 text-center text-[11px] text-muted">Not due</span>}</div>)}</div>
          <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3 lg:grid-cols-6">{data.trend.map((t) =>
            <li key={t.period_id}><b className="text-heading">P{t.index}</b>: {t.opened ? `${t.approved}/${t.expected} — ${t.rate_label}` : `Not due (${t.expected} planned)`}</li>)}</ul>
        </section>

        <section aria-labelledby="mx" className="overflow-hidden rounded-[10px] border border-line bg-white">
          <h2 id="mx" className="px-4 pt-4 text-xl font-bold">Department × KRA</h2>
          <p className="px-4 pb-2 text-sm text-muted">{scope === 'period' ? 'Status in the selected period.' : 'Approved / expected report slots.'} N/A = not assigned.</p>
          <div className="overflow-x-auto"><table className="text-sm">
            <thead className="bg-subtle"><tr><th scope="col" className="sticky left-0 bg-subtle p-2 text-left">Dept.</th>{data.matrix.kras.map((k) => <th scope="col" key={k} className="p-2">{k}</th>)}</tr></thead>
            <tbody>{data.matrix.rows.map((r) => <tr key={r.department} className="border-t border-line"><th scope="row" className="sticky left-0 bg-white p-2 text-left">{r.department}</th>
              {r.cells.map((c, i) => <td key={i} className="whitespace-nowrap p-2 text-center">{c === null ? 'N/A' : scope === 'period'
                ? (data.labels[c.bucket as Bucket] ?? 'Not assigned') : `${c.approved}/${c.expected}`}</td>)}</tr>)}</tbody></table></div>
        </section>

        <section aria-labelledby="dt" className="overflow-hidden rounded-[10px] border border-line bg-white">
          <div className="flex flex-wrap items-end justify-between gap-3 px-4 pt-4">
            <h2 id="dt" className="text-xl font-bold">Report slots</h2>
            <label className={`${fld} w-full sm:w-56`}>Status (this table only)
              <select className="input" value={status} onChange={(e) => set({ status: e.target.value })}>
                <option value="">All statuses</option>{BUCKETS.map((b) => <option key={b} value={b}>{data.labels[b]}</option>)}</select></label>
          </div>
          {data.details.total === 0 ? <p className="p-5 text-muted">No report slots match these filters.</p> : (
            <div className="mt-3 overflow-x-auto"><table role="table" className="report-table w-full text-[15px]">
              <thead role="rowgroup" className="bg-subtle text-left"><tr role="row">{['Dept.', 'KRA', 'Period', 'Annual target', 'Achievement', 'Status'].map((h) =>
                <th role="columnheader" key={h} className="border-y border-line px-3.5 py-2.5 font-semibold text-heading">{h}</th>)}</tr></thead>
              <tbody role="rowgroup">{data.details.results.map((r, i) => <tr role="row" key={i} className="border-b border-line align-top last:border-b-0">
                <td role="cell" data-col="head" className="whitespace-nowrap px-3.5 py-3 font-bold text-heading">{r.department}<span className="md:hidden"> · KRA {r.kra_number}</span></td>
                <td role="cell" data-col="wide" className="px-3.5 py-3 text-sm"><b className="mr-1 text-heading max-md:hidden">{r.kra_number}</b>{r.kra_text.replace(/^KRA \d+:\s*/, '')}</td>
                <td role="cell" data-col="wide" className="whitespace-nowrap px-3.5 py-3 text-sm">{r.period}</td>
                <td role="cell" data-col="wide" data-label="Annual target" className="w-48 whitespace-pre-wrap px-3.5 py-3">{r.target_text}</td>
                <td role="cell" data-col="wide" className="px-3.5 py-3"><span className="whitespace-pre-wrap">{r.achievement_text || '—'}</span>
                  {r.achievement_source === 'draft' && <span className="mt-1 block text-[13px] font-semibold text-warn">Unsubmitted draft — not reviewed</span>}</td>
                <td role="cell" data-col="status" className="whitespace-nowrap px-3.5 py-3"><span className="text-sm font-semibold">{r.status_label}</span>
                  {r.is_nil && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading">Nil</span>}
                  {r.reopened && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading">Reopened</span>}</td>
              </tr>)}</tbody></table></div>)}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm">
            <span className="text-muted">{data.details.total} report slots · page {data.details.page} of {Math.max(1, Math.ceil(data.details.total / data.details.page_size))}</span>
            <span className="flex gap-2"><button className="btn-secondary min-h-9 text-sm" disabled={data.details.page <= 1} onClick={() => set({ page: String(data.details.page - 1) })}>Previous</button>
              <button className="btn-secondary min-h-9 text-sm" disabled={data.details.page * data.details.page_size >= data.details.total} onClick={() => set({ page: String(data.details.page + 1) })}>Next</button></span>
          </div>
        </section>
      </>)}
    </div>
  )
}
