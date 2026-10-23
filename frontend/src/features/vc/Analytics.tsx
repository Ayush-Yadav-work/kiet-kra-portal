import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import { Icon, type IconName } from '../../components/icons'
import { DeptChip, EmptyState, IconSelect, PageHero, Pager } from '../../components/page'
import { ErrorBox, Loading } from '../../components/ui'
import { usePeriods } from '../dean/DeanDashboard'
import PendingNotice from './PendingNotice'

// VC features plan v2.3 §6–8 (D-074): approved applicable report slots ÷ expected applicable report slots. Charts are plain
// HTML/CSS with text and table equivalents (no chart library); the PDF draws the same figures server-side.
// Draft privacy (D-078): a saved but unsubmitted draft is reported as Not submitted; there is no Draft bucket for the VC.
type Bucket = 'NOT_SUBMITTED' | 'AWAITING_REVIEW' | 'RETURNED' | 'REJECTED' | 'APPROVED' | 'NOT_DUE'
type Rate = { approved: number; expected: number; remaining: number; assignments: number; rate: number | null; rate_label: string }
type TrendPoint = { period_id: number; index: number; label: string; opened: boolean; approved: number; expected: number; rate_label: string }
type Detail = { department: string; kra_number: number; kra_text: string; period: string; target_text: string; status: Bucket; status_label: string
  achievement_text: string; achievement_source: 'submitted' | 'none'; is_nil: boolean; reopened: boolean }
type Data = { as_of: string; drafts_pending: number; summary: Rate; breakdown: Record<Bucket, number>; labels: Record<Bucket, string>
  departments: (Rate & { code: string; name: string; breakdown: Record<Bucket, number> })[]; trend: TrendPoint[]
  department_trends: Record<string, TrendPoint[]>; matrix: { kras: number[]; rows: { department: string; cells: ({ approved: number; expected: number; bucket: string | null } | null)[] }[] }
  details: { total: number; page: number; page_size: number; results: Detail[] }; filters: { scope: string; scope_label: string } }

const BUCKETS: Bucket[] = ['APPROVED', 'AWAITING_REVIEW', 'RETURNED', 'REJECTED', 'NOT_SUBMITTED', 'NOT_DUE']
const COLOR: Record<Bucket, string> = { APPROVED: 'bg-ok', AWAITING_REVIEW: 'bg-info', RETURNED: 'bg-[#B45309]', REJECTED: 'bg-err',
  NOT_SUBMITTED: 'bg-[#7A8899]', NOT_DUE: 'bg-[#D0D7DE]' }
const YEARS = ['2026-27', '2027-28', '2028-29']
const pct = (a: number, e: number) => (e ? Math.round((a / e) * 1000) / 10 : 0)
const PILL: Record<Bucket, string> = { APPROVED: 'bg-ok-bg text-ok', AWAITING_REVIEW: 'bg-info-bg text-info', RETURNED: 'bg-warn-bg text-warn',
  REJECTED: 'bg-err-bg text-err', NOT_SUBMITTED: 'bg-neutral-bg text-neutral', NOT_DUE: 'bg-subtle text-muted' }
const HEAT: [string, string][] = [['0%', 'bg-[#FBE7E7]'], ['1–25%', 'bg-[#FFF3DA]'], ['26–50%', 'bg-[#FCE3AE]'], ['51–75%', 'bg-[#D9F1E1]'], ['76–100%', 'bg-[#B6E3C5]'], ['Not due / N/A', 'bg-[#EEF2F5]']]
/** Cell background only (the text always states the value): approved share, or the period bucket. */
function cellTone(c: { approved: number; expected: number; bucket: string | null } | null, scope: string) {
  if (c === null) return 'bg-[#EEF2F5] text-muted'
  if (scope === 'period') return c.bucket && c.bucket in PILL ? PILL[c.bucket as Bucket] : 'bg-[#EEF2F5] text-muted'
  if (!c.expected) return 'bg-[#EEF2F5] text-muted'
  const r = c.approved / c.expected
  return r === 0 ? 'bg-[#FBE7E7] text-heading' : r <= 0.25 ? 'bg-[#FFF3DA] text-heading' : r <= 0.5 ? 'bg-[#FCE3AE] text-heading' : r <= 0.75 ? 'bg-[#D9F1E1] text-heading' : 'bg-[#B6E3C5] text-heading'
}

export default function Analytics() {
  const [params, setParams] = useSearchParams()
  const year = params.get('year') || '2026-27'
  const scope = params.get('scope') || 'ytd'
  const periods = usePeriods(year)
  const period = params.get('period') || String((periods.find((p) => p.is_open) ?? periods[0])?.id ?? '')
  const depts = params.getAll('department')
  const kra = params.get('kra') || ''
  const status = params.get('status') === 'DRAFT' ? 'NOT_SUBMITTED' : params.get('status') || ''  // old bookmarks (D-078)
  const page = params.get('page') || '1'
  const [allDepts, setAllDepts] = useState<{ code: string; name: string }[]>([])
  const [kraList, setKraList] = useState<number[]>([])
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)
  const [exporting, setExporting] = useState('')
  const [exportError, setExportError] = useState('')
  const [announce, setAnnounce] = useState(false)
  const deptMenu = useRef<HTMLDetailsElement>(null)
  const [menuFit, setMenuFit] = useState({ up: false, max: 320 })
  const fitMenu = useCallback(() => {  // keep the open list inside the viewport: open upward when there is more room above
    const d = deptMenu.current
    if (!d?.open) return
    const r = d.getBoundingClientRect(), below = window.innerHeight - r.bottom - 12, above = r.top - 12
    const up = below < 220 && above > below
    setMenuFit({ up, max: Math.max(120, Math.min(320, up ? above : below)) })
  }, [])
  useEffect(() => {
    window.addEventListener('resize', fitMenu); window.addEventListener('scroll', fitMenu, true)
    return () => { window.removeEventListener('resize', fitMenu); window.removeEventListener('scroll', fitMenu, true) }
  }, [fitMenu])
  useEffect(() => {  // the department list behaves like a menu: an outside click or Escape closes it
    const close = (e: Event) => {
      const d = deptMenu.current
      if (d?.open && (e instanceof KeyboardEvent ? e.key === 'Escape' : !d.contains(e.target as Node))) { d.open = false; if (e instanceof KeyboardEvent) d.querySelector('summary')?.focus() }
    }
    document.addEventListener('mousedown', close); document.addEventListener('keydown', close)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close) }
  }, [])

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

  const compare = depts.length >= 2
  const pages = data ? Math.max(1, Math.ceil(data.details.total / data.details.page_size)) : 1
  const exp = data?.summary.expected ?? 0
  const metric = (label: string, value: number, icon: IconName, tone: string, bar: string) => ({ label, value, icon, tone, bar })
  const metrics = data ? [
    metric('Approved', data.breakdown.APPROVED, 'check', 'bg-ok-bg text-ok', 'bg-[#3FA466]'),
    metric('Awaiting review', data.breakdown.AWAITING_REVIEW, 'clock', 'bg-info-bg text-info', 'bg-[#5B9BD8]'),
    metric('Rejected or returned', data.breakdown.REJECTED + data.breakdown.RETURNED, 'xcircle', 'bg-err-bg text-err', 'bg-[#E46F6F]'),
    metric('Not submitted', data.breakdown.NOT_SUBMITTED, 'doc', 'bg-neutral-bg text-neutral', 'bg-[#7A8899]'),
    metric('Not due', data.breakdown.NOT_DUE, 'calendar', 'bg-subtle text-muted', 'bg-[#AEB9C6]'),
  ] : []
  const maxBucket = data ? Math.max(1, ...BUCKETS.map((b) => data.breakdown[b])) : 1
  return (
    <div className="grid gap-[18px]">
      <PageHero eyebrow="Analytics" title="Report approval analytics"
        description={<>Track the completion and approval status of KRA reports across departments and reporting periods.
          <span className="mt-1 block text-sm">Completion = approved report slots ÷ expected report slots (one slot is one finalised assignment in one reporting period
          from its start period). Targets are text and are not scored.</span></>}>
        <section aria-label="Analytics filters" className="panel flex flex-wrap items-end gap-3 p-4 md:p-5">
          <IconSelect label="Academic year" icon="calendar" className="w-full sm:w-40" value={year} onChange={(e) => set({ year: e.target.value, period: '' })}>
            {YEARS.map((y) => <option key={y}>{y}</option>)}</IconSelect>
          <IconSelect label="Scope" icon="calendar" className="w-full sm:w-52" value={scope} onChange={(e) => set({ scope: e.target.value })}>
            <option value="period">Bimonthly period</option><option value="ytd">Year to date</option><option value="year">Full academic year</option></IconSelect>
          {scope === 'period' && <IconSelect label="Reporting period" icon="calendar" className="w-full sm:w-80" value={period} onChange={(e) => set({ period: e.target.value })}>
            {periods.map((p) => <option key={p.id} value={p.id}>{p.label}{p.is_open ? ' (open)' : p.is_closed ? ' (closed)' : ' (not due)'}</option>)}</IconSelect>}
          <IconSelect label="KRA" icon="layers" className="w-full sm:w-32" value={kra} onChange={(e) => set({ kra: e.target.value })}>
            <option value="">All</option>{kraList.map((n) => <option key={n} value={n}>{n}</option>)}</IconSelect>
          <details ref={deptMenu} onToggle={fitMenu} className="relative w-full rounded-lg border border-control bg-white sm:w-64">
            <summary className="flex min-h-10 cursor-pointer items-center gap-2 px-3 py-2 text-sm font-semibold text-heading"><span className="text-muted" aria-hidden="true"><Icon name="building" size={18} /></span>Departments: {depts.length ? `${depts.length} selected` : 'all'}</summary>
            <div style={{ maxHeight: menuFit.max }} className={`absolute left-0 right-0 z-10 grid content-start gap-1 overflow-y-auto overscroll-contain rounded-lg border border-line bg-white p-3 text-sm shadow-lg ${menuFit.up ? 'bottom-full mb-1' : 'top-full mt-1'}`}>
              <div className="mb-1 flex gap-2"><button type="button" className="btn-quiet min-h-8 text-sm" onClick={() => set({ department: allDepts.map((d) => d.code) })}>Select all</button>
                <button type="button" className="btn-quiet min-h-8 text-sm" onClick={() => set({ department: [] })}>All (no filter)</button></div>
              {allDepts.map((d) => <label key={d.code} className={`flex min-h-9 cursor-pointer items-start gap-2.5 rounded-md px-2 py-1.5 hover:bg-subtle ${depts.includes(d.code) ? 'bg-info-bg font-semibold text-heading' : ''}`}>
                <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0" checked={depts.includes(d.code)}
                  onChange={() => set({ department: depts.includes(d.code) ? depts.filter((x) => x !== d.code) : [...depts, d.code] })} /><span className="min-w-0 break-words">{d.code} — {d.name}</span></label>)}
            </div>
          </details>
          <div className="flex w-full flex-wrap gap-2 xl:ml-auto xl:w-auto">
            <button type="button" className="btn-primary bg-brand hover:bg-heading" disabled={!!exporting || !data} onClick={() => exportFile('pdf')}><Icon name="download" />{exporting === 'pdf' ? 'Preparing PDF…' : 'Export PDF'}</button>
            <button type="button" className="btn-secondary" disabled={!!exporting || !data} onClick={() => exportFile('csv')}><Icon name="doc" />{exporting === 'csv' ? 'Preparing CSV…' : 'Export CSV'}</button>
            <button type="button" className="btn-secondary" disabled={!data || (scope === 'period' && !data.trend.find((t) => String(t.period_id) === period)?.opened)}
              onClick={() => setAnnounce(true)}><Icon name="megaphone" />Announce to pending departments</button>
          </div>
          <p className="w-full text-sm text-muted">Exports recompute every matching report slot at download time with these filters. {scope === 'ytd' ? 'Year to date counts periods that have opened, including the current one.'
            : scope === 'year' ? 'Full year counts all six periods; future periods are Not due but still expected.' : 'A period that has not opened shows its planned count and Not due.'}</p>
        </section>
      </PageHero>
      <ErrorBox error={exportError} />
      {announce && data && <PendingNotice year={year} opened={data.trend.filter((t) => t.opened)} fixedPeriod={scope === 'period' ? Number(period) : null}
        departments={depts} kra={kra} onClose={() => setAnnounce(false)} />}
      {error ? <div className="grid gap-2"><ErrorBox error={error} /><button className="btn-secondary w-fit" onClick={() => setNonce((n) => n + 1)}>Try again</button></div>
        : !data ? <Loading /> : (<>
        <section aria-label="Summary" className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5 xl:gap-3">
          {metrics.map((m) => <div key={m.label} className="panel px-4 py-3.5">
            <div className="flex items-center gap-3"><span aria-hidden="true" className={`grid h-11 w-11 shrink-0 place-items-center rounded-full ${m.tone}`}><Icon name={m.icon} /></span>
              <span className="min-w-0 break-words"><span className="block text-[28px] font-bold leading-tight text-heading">{m.value}</span><span className="text-sm">{m.label}</span></span></div>
            <span className="mt-2 block text-right text-[13px] font-semibold text-heading">{pct(m.value, exp).toFixed(1)}%</span>
            <span aria-hidden="true" className="mt-1 block h-1.5 overflow-hidden rounded-full bg-[#E8EEF4]"><span className={`block h-full rounded-full ${m.bar}`} style={{ width: `${pct(m.value, exp)}%` }} /></span>
          </div>)}
        </section>

        <div className="grid gap-[18px] xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <section aria-labelledby="wb" className="panel p-4 md:p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h2 id="wb" className="flex items-center gap-2 text-lg font-bold"><span className="text-action" aria-hidden="true"><Icon name="chart" /></span>Submission status overview</h2>
              <span className="rounded-full bg-info-bg px-3 py-0.5 text-sm font-semibold text-info">{data.filters.scope_label}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-baseline gap-x-3">
              <p className="text-3xl font-bold text-heading">{data.summary.rate_label}</p>
              <p className="text-[15px]">{data.summary.approved} of {data.summary.expected} reports approved</p>
            </div>
            <p className="text-sm text-muted">{data.summary.remaining} remaining to approve · {data.summary.assignments} finalised assignments · {data.drafts_pending} unpublished draft allocation(s) excluded until finalised</p>
            <div aria-hidden="true" className="mt-4 flex h-44 items-end gap-2 border-b border-control px-1">{BUCKETS.map((b) =>
              <div key={b} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                <span className="text-xs font-semibold text-heading">{data.breakdown[b]}</span>
                <span className={`w-full max-w-12 rounded-t ${COLOR[b]}`} style={{ height: `${Math.max((data.breakdown[b] / maxBucket) * 100, data.breakdown[b] ? 2 : 0.5)}%` }} /></div>)}</div>
            <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">{BUCKETS.map((b) => <li key={b} className="flex items-center gap-2">
              <span aria-hidden="true" className={`inline-block h-3 w-3 shrink-0 rounded-sm ${COLOR[b]}`} /><b className="text-heading">{data.breakdown[b]}</b> {data.labels[b]}</li>)}</ul>
            <p className="mt-2 text-xs text-muted">Data as of {fmtDateTime(data.as_of)}. The detail status filter below never changes these rates.</p>
          </section>

          <section aria-labelledby="dc" className="panel p-4 md:p-5">
            <h2 id="dc" className="flex items-center gap-2 text-lg font-bold"><span className="text-action" aria-hidden="true"><Icon name="building" /></span>Department progress{compare ? ' — comparison' : ''}</h2>
            <p className="mb-3 text-sm text-muted">Counts are shown with every rate: departments have different numbers of assignments. N/A = no assignment in this filter.</p>
            <ul className="grid gap-2.5">{data.departments.map((d) => <li key={d.code} className="grid items-center gap-x-3 gap-y-1 sm:grid-cols-[minmax(0,19rem)_minmax(0,1fr)_8.5rem]">
              <span className="flex min-w-0 items-center gap-2"><DeptChip code={d.code} /><span className="truncate text-sm" title={d.name}>{d.name}</span></span>
              <span aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-[#E8EEF4]"><span className="block h-full rounded-full bg-action" style={{ width: `${pct(d.approved, d.expected)}%` }} /></span>
              <span className="text-sm sm:text-right">{d.assignments === 0 ? 'N/A — no assignments' : d.expected === 0 ? d.rate_label : `${d.approved} / ${d.expected} — ${d.rate_label}`}</span></li>)}</ul>
            {compare && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm"><caption className="mb-1 text-left font-semibold text-heading">Approved / expected by reporting period</caption>
                  <thead className="thead-soft"><tr><th className="p-2">Department</th>{data.trend.map((t) => <th key={t.period_id} className="p-2">P{t.index}</th>)}</tr></thead>
                  <tbody>{depts.map((code) => <tr key={code} className="border-t border-line"><td className="p-2 font-semibold">{code}</td>
                    {(data.department_trends[code] ?? []).map((t) => <td key={t.period_id} className="p-2">{!t.opened ? 'Not due' : t.expected ? `${t.approved}/${t.expected}` : 'N/A'}</td>)}</tr>)}</tbody></table>
              </div>)}
          </section>
        </div>

        <section aria-labelledby="tr" className="panel p-4 md:p-5">
          <h2 id="tr" className="mb-3 flex items-center gap-2 text-lg font-bold"><span className="text-action" aria-hidden="true"><Icon name="calendar" /></span>Approval by reporting period</h2>
          <div aria-hidden="true" className="flex h-36 items-end gap-3 border-b border-control px-1">{data.trend.map((t) =>
            <div key={t.period_id} className="flex h-full flex-1 flex-col items-center justify-end">
              {t.opened ? <span className="w-3/4 max-w-24 rounded-t bg-action" style={{ height: `${Math.max(pct(t.approved, t.expected), 1)}%` }} />
                : <span className="w-3/4 max-w-24 rounded-t border border-dashed border-control py-1 text-center text-[11px] text-muted">Not due</span>}</div>)}</div>
          <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3 lg:grid-cols-6">{data.trend.map((t) =>
            <li key={t.period_id}><b className="text-heading">P{t.index}</b>: {t.opened ? `${t.approved}/${t.expected} — ${t.rate_label}` : `Not due (${t.expected} planned)`}</li>)}</ul>
        </section>

        <section aria-labelledby="mx" className="panel overflow-hidden">
          <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-4 md:px-5">
            <div><h2 id="mx" className="flex items-center gap-2 text-lg font-bold"><span className="text-action" aria-hidden="true"><Icon name="grid" /></span>Department × KRA</h2>
              <p className="pb-2 text-sm text-muted">{scope === 'period' ? 'Status in the selected period.' : 'Approved / expected report slots.'} N/A = not assigned.</p></div>
            {scope !== 'period' && <ul aria-label="Cell colours" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">{HEAT.map(([label, cls]) =>
              <li key={label} className="flex items-center gap-1.5"><span aria-hidden="true" className={`inline-block h-3 w-3 rounded-sm ${cls}`} />{label}</li>)}</ul>}
          </div>
          <div className="overflow-x-auto px-2 pb-3 md:px-3"><table className="text-[13px]">
            <thead><tr><th scope="col" className="sticky left-0 bg-white p-1.5 text-left font-semibold text-heading">Dept.</th>{data.matrix.kras.map((k) => <th scope="col" key={k} className="p-1.5 font-semibold text-heading">{k}</th>)}</tr></thead>
            <tbody>{data.matrix.rows.map((r) => <tr key={r.department}><th scope="row" className="sticky left-0 whitespace-nowrap bg-white p-1.5 text-left font-semibold text-heading">{r.department}</th>
              {r.cells.map((c, i) => <td key={i} className="p-0.5"><span className={`block whitespace-nowrap rounded px-1.5 py-1 text-center ${cellTone(c, scope)}`}>{c === null ? 'N/A' : scope === 'period'
                ? (data.labels[c.bucket as Bucket] ?? 'Not assigned') : `${c.approved}/${c.expected}`}</span></td>)}</tr>)}</tbody></table></div>
        </section>

        <section aria-labelledby="dt" className="panel overflow-hidden">
          <div className="flex flex-wrap items-end justify-between gap-3 px-4 pt-4 md:px-5">
            <h2 id="dt" className="flex items-center gap-2 text-lg font-bold"><span className="text-action" aria-hidden="true"><Icon name="doc" /></span>Report slots</h2>
            <IconSelect label="Status (this table only)" icon="list" className="w-full sm:w-60" value={status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All statuses</option>{BUCKETS.map((b) => <option key={b} value={b}>{data.labels[b]}</option>)}</IconSelect>
          </div>
          {data.details.total === 0 ? <EmptyState icon="search" title="No report slots match these filters." /> : (
            <div className="mt-3 overflow-x-auto"><table role="table" className="report-table w-full text-[15px] md:min-w-[960px]">
              <thead role="rowgroup" className="thead-soft"><tr role="row">{['Dept.', 'KRA', 'Period', 'Annual target', 'Achievement', 'Status'].map((h) =>
                <th role="columnheader" key={h} className="border-y border-line px-3.5 py-2.5">{h}</th>)}</tr></thead>
              <tbody role="rowgroup">{data.details.results.map((r, i) => <tr role="row" key={i} className="border-b border-line align-top last:border-b-0">
                <td role="cell" data-col="head" className="whitespace-nowrap px-3.5 py-3 font-bold text-heading"><DeptChip code={r.department} /><span className="md:hidden"> · KRA {r.kra_number}</span></td>
                <td role="cell" data-col="wide" className="px-3.5 py-3 text-sm"><b className="mr-1 text-heading max-md:hidden">{r.kra_number}</b>{r.kra_text.replace(/^KRA \d+:\s*/, '')}</td>
                <td role="cell" data-col="wide" className="whitespace-nowrap px-3.5 py-3 text-sm">{r.period}</td>
                <td role="cell" data-col="wide" data-label="Annual target" className="w-48 whitespace-pre-wrap px-3.5 py-3">{r.target_text}</td>
                <td role="cell" data-col="wide" className="px-3.5 py-3"><span className="whitespace-pre-wrap">{r.achievement_text || '—'}</span>
</td>
                <td role="cell" data-col="status" className="whitespace-nowrap px-3.5 py-3"><span className={`inline-block rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${PILL[r.status]}`}>{r.status_label}</span>
                  {r.is_nil && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading">Nil</span>}
                  {r.reopened && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading">Reopened</span>}</td>
              </tr>)}</tbody></table></div>)}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm md:px-5">
            <span className="text-muted">{data.details.total} report slots · page {data.details.page} of {pages}</span>
            <Pager page={data.details.page} pages={pages} onPage={(n) => set({ page: String(n) })} label="Report slot pages" />
          </div>
        </section>
      </>)}
    </div>
  )
}
