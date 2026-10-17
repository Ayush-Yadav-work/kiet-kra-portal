import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import type { Assignment, Period, SubmissionSummary } from '../../api/types'
import { ErrorBox, Loading, StatusBadge, timeLeft, useServerClock } from '../../components/ui'

interface Row extends Assignment { submission: SubmissionSummary }
interface GrantRow { id: string; expires_at: string; kra_number: number; period: string; assignment_id: string; period_id: number; status: string }
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
    <div className="flex flex-wrap gap-3">
      <label className="grid w-full gap-1 text-sm font-semibold text-heading sm:w-auto">Academic year{' '}
        <select className="input sm:w-auto" value={year} onChange={(e) => onChange(e.target.value, '')}>
          {YEARS.map((y) => <option key={y}>{y}</option>)}
        </select>
      </label>
      <label className="grid w-full gap-1 text-sm font-semibold text-heading sm:w-auto">Reporting period{' '}
        <select className="input sm:w-auto" value={period} onChange={(e) => onChange(year, e.target.value)}>
          {periods.map((p) => <option key={p.id} value={p.id}>{p.label}{p.is_open ? ' (open)' : p.is_closed ? ' (closed)' : ' (upcoming)'}</option>)}
        </select>
      </label>
    </div>
  )
}

function ReopenBanner() {
  const [data, setData] = useState<{ server_time: string; results: GrantRow[] } | null>(null)
  useEffect(() => { api<typeof data>('/reopen-grants/active/').then(setData).catch(() => setData(null)) }, [])
  const now = useServerClock(data?.server_time)
  const live = data?.results.filter((g) => new Date(g.expires_at).getTime() > now) ?? []
  if (!live.length) return null
  return (
    <section role="alert" className="mb-4 rounded-lg border-2 border-amber-500 bg-amber-50 p-4">
      <h2 className="font-semibold text-amber-900">Reopened KRAs — Action Required</h2>
      <ul className="mt-2 space-y-1 text-sm">
        {live.map((g) => (
          <li key={g.id} className="flex flex-wrap items-center gap-2">
            <Link className="underline font-medium" to={`/dean/kra/${g.assignment_id}/${g.period_id}`}>KRA {g.kra_number}</Link>
            <span>{g.period}</span>
            <span className="font-semibold text-amber-900">{timeLeft(g.expires_at, now)}</span>
            <span className="text-slate-600">(until {fmtDateTime(g.expires_at)})</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function DeanDashboard() {
  const [params, setParams] = useSearchParams()
  const year = params.get('year') || '2026-27'
  const periods = usePeriods(year)
  const periodId = params.get('period') || String((periods.find((p) => p.is_open) ?? periods[0])?.id ?? '')
  const [rows, setRows] = useState<Row[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!periodId) return
    setRows(null)
    let live = true  // ignore a slower response for a previously selected period
    api<{ results: Row[] }>(`/assignments/?year=${year}&period=${periodId}`)
      .then((r) => live && setRows(r.results))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : 'Failed to load'))
    return () => { live = false }
  }, [year, periodId])

  const rejected = rows?.filter((r) => r.submission.display_status === 'REJECTED') ?? []
  return (
    <div>
      <ReopenBanner />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold">My KRA assignments</h1>
        <YearPeriodPicker year={year} period={periodId} periods={periods} onChange={(y, p) => setParams(p ? { year: y, period: p } : { year: y })} />
      </div>
      <ErrorBox error={error} />
      {rejected.length > 0 && (
        <section className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3">
          <h2 className="font-semibold text-red-900">Returned / rejected reports</h2>
          <ul className="mt-1 text-sm space-y-1">
            {rejected.map((r) => (
              <li key={r.id}><Link className="underline" to={`/dean/kra/${r.id}/${periodId}`}>KRA {r.kra.number}</Link>: {r.submission.latest_decision?.reason}</li>
            ))}
          </ul>
        </section>
      )}
      {!rows ? <Loading /> : (
        <div className="overflow-x-auto card p-0">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr><th className="p-2">KRA</th><th className="p-2">Activity</th><th className="p-2">Annual target</th><th className="p-2">Status</th><th className="p-2"></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-200 align-top">
                  <td className="p-2 font-medium">{r.kra.number}</td>
                  <td className="p-2 max-w-xl">{r.kra.activity_text.replace(/^KRA \d+:\s*/, '')}</td>
                  <td className="p-2 whitespace-pre-wrap">{r.target_text}</td>
                  <td className="p-2"><StatusBadge status={r.submission.display_status} />{r.submission.is_nil && <span className="ml-1 text-xs">(Nil)</span>}</td>
                  <td className="p-2">
                    {r.template ? <Link className="btn-secondary" to={`/dean/kra/${r.id}/${periodId}`}>Open</Link>
                      : <span className="text-xs text-slate-500">Template pending (Phase 4)</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
