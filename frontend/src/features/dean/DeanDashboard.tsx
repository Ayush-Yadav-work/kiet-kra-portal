import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import type { Applicability, Assignment, DisplayStatus, Period, ReopenRequest, SubmissionSummary } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Icon } from '../../components/icons'
import { ErrorBox, Loading, StatCard, StatusBadge, statusLabel, timeLeft, useServerClock } from '../../components/ui'
import { DashboardNotices } from '../announcements/DeanAnnouncements'
import { IconSelect, PageHero } from '../../components/page'

interface Row extends Assignment { submission: SubmissionSummary; applicability: Applicability | null; latest_reopen_request: ReopenRequest | null }
interface GrantRow { id: string; expires_at: string; kra_number: number; period: string; assignment_id: string; period_id: number; status: string; source: string }
const YEARS = ['2026-27', '2027-28', '2028-29']

export function usePeriods(year: string) {
  const [periods, setPeriods] = useState<Period[]>([])
  useEffect(() => {
    let live = true  // ignore a slower response for a previously selected year
    api<{ results: Period[] }>(`/periods/?year=${year}`).then((r) => live && setPeriods(r.results)).catch(() => live && setPeriods([]))
    return () => { live = false }
  }, [year])
  return periods
}

export function YearPeriodPicker({ year, period, periods, onChange }: { year: string; period: string; periods: Period[]; onChange: (y: string, p: string) => void }) {
  return (
    <div className="flex w-full flex-wrap gap-3 sm:w-auto">
      <IconSelect label="Academic year" icon="calendar" className="w-full sm:w-[180px]" value={year} onChange={(e) => onChange(e.target.value, '')}>
        {YEARS.map((y) => <option key={y}>{y}</option>)}
      </IconSelect>
      <IconSelect label="Reporting period" icon="calendar" className="w-full sm:w-[370px]" value={period} onChange={(e) => onChange(year, e.target.value)}>
        {periods.map((p) => <option key={p.id} value={p.id}>{p.label}{p.is_open ? ' (open)' : p.is_closed ? ' (closed)' : ' (upcoming)'}</option>)}
      </IconSelect>
    </div>
  )
}

interface Assignments { server_time: string; results: Row[] }
const STATUSES: DisplayStatus[] = ['NOT_SUBMITTED', 'DRAFT', 'SUBMITTED', 'REJECTED', 'APPROVED']
type Item = { key: string; ref: string; title: string; detail: string; deadline: [string, string]; to: string; action: string; primary: boolean }

export default function DeanDashboard() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const year = params.get('year') || '2026-27'
  const periods = usePeriods(year)
  const periodId = params.get('period') || String((periods.find((p) => p.is_open) ?? periods[0])?.id ?? '')
  const period = periods.find((p) => String(p.id) === periodId)
  const [data, setData] = useState<Assignments | null>(null)
  const [error, setError] = useState('')
  const [grants, setGrants] = useState<{ server_time: string; results: GrantRow[] } | null>(null)
  const [refresh, setRefresh] = useState(0)
  const status = (STATUSES as string[]).includes(params.get('status') ?? '') ? params.get('status') as DisplayStatus : null
  const loaded = useRef('')

  useEffect(() => {  // VC decisions made meanwhile (e.g. a denied reopening request) appear when the Dean returns to the tab
    const again = () => setRefresh((n) => n + 1)
    window.addEventListener('focus', again)
    return () => window.removeEventListener('focus', again)
  }, [])
  useEffect(() => { api<typeof grants>('/reopen-grants/active/').then(setGrants).catch(() => setGrants(null)) }, [refresh])
  useEffect(() => {
    if (!periodId) return
    const key = `${year}/${periodId}`
    if (loaded.current !== key) { setData(null); setError('') }  // new year/period: never show the previous one's rows
    let live = true  // ignore a slower response for a previously selected period
    api<Assignments>(`/assignments/?year=${year}&period=${periodId}`)
      .then((r) => { if (live) { loaded.current = key; setData(r) } })
      .catch((e) => live && setError(e instanceof ApiError ? e.message : 'Failed to load'))
    return () => { live = false }
  }, [year, periodId, refresh])
  const now = useServerClock(data?.server_time ?? grants?.server_time)

  const rows = data?.results
  const short = period ? `P${period.index}` : ''
  const liveGrants = grants?.results.filter((g) => new Date(g.expires_at).getTime() > now) ?? []
  const grantFor = (r: Row) => liveGrants.find((g) => g.assignment_id === r.id && String(g.period_id) === periodId)
  const editable = (r: Row) => !!period?.is_open || !!grantFor(r)
  const to = (r: Row) => `/dean/kra/${r.id}/${periodId}`

  // Attention: the dashboard's existing sources only — rejected/returned reports of this period and active reopening grants.
  const items: Item[] = []
  for (const r of rows?.filter((x) => x.submission.display_status === 'REJECTED') ?? []) {
    const d = r.submission.latest_decision, g = grantFor(r)
    items.push({
      key: r.id, ref: `KRA ${r.kra.number} · ${short}`,
      title: d?.decision === 'RETURN' ? 'Returned for correction by the Vice Chancellor' : 'Rejected by the Vice Chancellor',
      detail: d ? `“${d.reason}” — ${fmtDateTime(d.created_at)}` : '',
      deadline: g ? ['Reopening ends', fmtDateTime(g.expires_at)] : period?.is_open ? ['Period closes', fmtDateTime(period.closes_at)] : ['Period closed', 'Request reopening from the report'],
      to: to(r), action: editable(r) ? 'Correct & resubmit' : 'Open report', primary: editable(r),
    })
  }
  for (const r of rows ?? []) {  // a denied reopening request stays listed until a newer request supersedes it
    const q = r.latest_reopen_request
    if (q?.state !== 'DENIED') continue
    items.push({
      key: `deny-${q.id}`, ref: `KRA ${r.kra.number} · ${short}`, title: 'Reopening request denied by the Vice Chancellor',
      detail: `“${q.decision_reason}” — ${fmtDateTime(q.decided_at)}`, deadline: ['Requested', fmtDateTime(q.requested_at)],
      to: to(r), action: 'View request history', primary: false,
    })
  }
  for (const g of liveGrants) {
    if (items.some((i) => i.key === g.assignment_id && String(g.period_id) === periodId)) continue
    items.push({ key: g.id, ref: `KRA ${g.kra_number} · ${g.period.split(':')[0]}`, title: `${g.source === 'PUBLICATION' ? 'Assigned late — reporting window' : 'Reopened for correction'} — ${timeLeft(g.expires_at, now).replace('Expires in ', '')} left`,
      detail: `Current status: ${statusLabel(g.status as DisplayStatus)}`, deadline: ['Reopening ends', fmtDateTime(g.expires_at)],
      to: `/dean/kra/${g.assignment_id}/${g.period_id}`, action: 'Open report', primary: false })
  }

  const assigned = rows?.filter((r) => r.applicability !== 'NOT_ASSIGNED') ?? []  // only obligations of this period are counted (D-073)
  const counts = Object.fromEntries(STATUSES.map((s) => [s, assigned.filter((r) => r.submission.display_status === s).length])) as Record<DisplayStatus, number>
  const shown = status ? assigned.filter((r) => r.submission.display_status === status) : rows ?? []  // counts above never change with the filter
  const setStatus = (s: DisplayStatus | null) => setParams(Object.fromEntries(Object.entries({ year, period: periodId, status: s ?? '' }).filter(([, v]) => v)))
  const days = period?.is_open ? Math.ceil((new Date(period.closes_at).getTime() - now) / 86_400_000) : 0

  return (
    <div className="grid gap-[18px]">
      <PageHero eyebrow="Welcome back," title="KRA Reports" description={`Your department's KRA reports for each reporting period.`}
        chip={<>{user?.department?.name} · {year}</>}
        aside={<YearPeriodPicker year={year} period={periodId} periods={periods}
          onChange={(y, p) => setParams((cur) => Object.fromEntries(Object.entries({ year: y, period: p, status: cur.get('status') ?? '' }).filter(([, v]) => v)))} />} />
      <DashboardNotices />

      {period && (
        <p className="flex flex-wrap gap-x-3 gap-y-1 text-[15px]">
          {period.is_open ? <><b className="text-ok">{short} is open</b><span>Submissions close <b className="text-heading">{fmtDateTime(period.closes_at)}</b></span>
            <span className="text-muted">{days <= 1 ? 'Closes within a day' : `${days} days left`}</span></>
            : period.is_closed ? <><b className="text-heading">{short} is closed</b><span>Closed {fmtDateTime(period.closes_at)}. Reopening can be requested from a report.</span></>
            : <><b className="text-heading">{short} has not opened yet</b><span>Opens {fmtDateTime(period.opens_at)}</span></>}
        </p>
      )}

      <ErrorBox error={error} />
      {!rows ? (!error && <Loading />) : (<>
        <section aria-labelledby="sum-h">
          <h2 id="sum-h" className="sr-only">{short} reports by status</h2>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6 xl:gap-3.5">
            <StatCard kind="ASSIGNED" value={assigned.length} label="Assigned" total={assigned.length} pressed={!status} onClick={() => setStatus(null)} />
            {STATUSES.map((s) => <StatCard key={s} kind={s} value={counts[s]} label={statusLabel(s)} total={assigned.length} pressed={status === s}
              onClick={() => setStatus(status === s ? null : s)} />)}
          </div>
          <p className="mt-2 text-sm text-muted">Select a card to list only those reports; select it again (or Assigned) to show all.</p>
        </section>

        {items.length > 0 && (
          <section aria-labelledby="attn-h" className="panel px-4 pb-1 pt-4 md:px-5">
            <div className="flex items-center gap-3.5 pb-3">
              <span aria-hidden="true" className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent-btn text-xl font-extrabold text-white">!</span>
              <div><h2 id="attn-h" className="text-xl font-bold">Needs your attention ({items.length})</h2>
                <p className="text-sm text-muted">Reopened reports, reports returned by the Vice Chancellor and denied reopening requests. Reports are also counted in the status totals above.</p></div>
            </div>
            <ul>
              {items.map((i) => (
                <li key={i.key} className="relative grid items-center gap-x-6 gap-y-1.5 border-t border-line py-3.5 pl-4 before:absolute before:inset-y-2.5 before:left-0 before:w-1 before:rounded before:bg-accent lg:grid-cols-[9rem_minmax(0,1fr)_14rem_11rem]">
                  <span className="font-bold text-heading">{i.ref}</span>
                  <span><b className="block text-heading">{i.title}</b><span className="text-sm text-muted">{i.detail}</span></span>
                  <span className="flex items-start gap-2.5 text-sm lg:border-l lg:border-line lg:pl-5"><span className="text-muted"><Icon name="calendar" /></span>
                    <span><b className="block font-semibold text-heading">{i.deadline[0]}</b>{i.deadline[1]}</span></span>
                  <Link className={`${i.primary ? 'btn-primary' : 'btn-secondary'} min-h-9 text-sm`} to={i.to}>{i.action}<span className="sr-only"> — {i.ref}</span></Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section aria-labelledby="rep-h" className="panel overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2.5 px-4 py-4 md:px-5">
            <h2 id="rep-h" className="flex items-center gap-3 text-xl font-bold md:text-2xl">{short} Reports <span className="rounded-full bg-neutral-bg px-3 py-0.5 text-sm font-medium">{status ? `${statusLabel(status)}: ${shown.length}` : `${assigned.length} assigned`}</span></h2>
            <p className="text-sm text-muted">Targets are shown exactly as assigned.</p>
          </div>
          {rows.length === 0 ? <p className="border-t border-line p-5 text-muted">No KRAs are assigned to your department for {year}.</p>
            : shown.length === 0 ? <p role="status" className="border-t border-line p-5 text-muted">No {short} reports are {statusLabel(status!).toLowerCase()}.{' '}
              <button type="button" className="font-semibold text-action underline" onClick={() => setStatus(null)}>Show all reports</button></p> : (
            <div className="overflow-x-auto">
              <table role="table" className="report-table w-full text-[15px]">
                <thead role="rowgroup" className="thead-soft">
                  <tr role="row">{['KRA', 'Activity', 'Annual target', 'Status', 'Details'].map((h) => <th role="columnheader" key={h} className="whitespace-nowrap border-y border-line px-3.5 py-2.5 font-semibold text-heading">{h}</th>)}
                    <th role="columnheader" className="border-y border-line px-3.5 py-2.5 text-center font-semibold text-heading">Action</th></tr>
                </thead>
                <tbody role="rowgroup">
                  {shown.map((r) => {
                    const st = r.submission.display_status, d = r.submission.latest_decision
                    const detail = st === 'REJECTED' && d ? <>{d.decision === 'RETURN' ? 'Returned' : 'Rejected'} {fmtDateTime(d.created_at)}<span className="block text-[13px] text-muted">by {d.reviewer_name}</span></>
                      : st === 'SUBMITTED' ? 'Awaiting VC review' : st === 'APPROVED' ? 'Approved by the VC' : st === 'DRAFT' ? 'Not yet submitted' : '—'
                    const label = st === 'SUBMITTED' || st === 'APPROVED' ? 'View' : !editable(r) ? 'Open report' : st === 'REJECTED' ? 'Correct & resubmit' : st === 'DRAFT' ? 'Continue draft' : 'Start report'
                    return (
                      <tr role="row" key={r.id} className="border-b border-line align-middle last:border-b-0">
                        <td role="cell" data-col="head" className="w-16 px-3.5 py-3 font-bold text-heading"><span className="md:hidden">KRA </span>{r.kra.number}</td>
                        <td role="cell" data-col="wide" className="px-3.5 py-3">{r.kra.activity_text.replace(/^KRA \d+:\s*/, '')}</td>
                        <td role="cell" data-col="wide" data-label="Annual target" className="w-56 whitespace-pre-wrap px-3.5 py-3">{r.target_text}</td>
                        <td role="cell" data-col="status" className="whitespace-nowrap px-3.5 py-3">{r.applicability === 'NOT_ASSIGNED'
                          ? <span className="text-sm text-muted">Not assigned for this period</span> : r.applicability === 'NOT_DUE' ? <span className="text-sm text-muted">Not due</span> : <StatusBadge status={st} />}
                          {r.submission.is_nil && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading" title="Nil report">Nil</span>}</td>
                        <td role="cell" data-col="wide" className="w-56 px-3.5 py-3 text-sm">{r.applicability === 'NOT_ASSIGNED' ? `Applies from ${r.effective_start_period?.label}`
                          : r.applicability === 'NOT_DUE' ? 'Period has not opened' : detail}</td>
                        <td role="cell" data-col="action" className="w-48 px-3.5 py-3 text-center">
                          {r.applicability !== 'APPLICABLE' ? <span className="text-sm text-muted">—</span>
                            : !r.template ? <span className="text-sm text-muted">Template pending</span>
                            : label === 'View' ? <Link className="font-semibold underline underline-offset-2" to={to(r)}>View<span className="sr-only"> KRA {r.kra.number}</span></Link>
                            : <Link className="btn-secondary min-h-9 w-full border-action text-sm" to={to(r)}>{label}<span className="sr-only"> — KRA {r.kra.number}</span></Link>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="border-t border-line px-4 py-3 text-sm text-muted md:px-5">{status ? `Showing ${shown.length} ${statusLabel(status).toLowerCase()} of ${assigned.length} assigned KRAs` : `Showing all ${rows.length} KRAs`} in KRA order.</p>
        </section>
      </>)}
    </div>
  )
}
