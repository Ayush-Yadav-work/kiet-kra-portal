import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import type { DisplayStatus } from '../../api/types'
import { ErrorBox, Loading, StatusBadge, statusLabel } from '../../components/ui'
import { usePeriods, YearPeriodPicker } from '../dean/DeanDashboard'

interface Row { assignment_id: string; department: string; kra_number: number; kra_text: string; target_text: string; has_template: boolean; submission_id: string | null; display_status: DisplayStatus; achievement_text: string; is_nil: boolean }
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
  const set = (patch: Record<string, string>) => {
    const next = Object.fromEntries([...params.entries(), ['year', year], ['period', period], ...Object.entries(patch)].filter(([, v]) => v))
    if (!('page' in patch)) delete next.page
    setParams(next)
  }
  useEffect(() => { api<typeof departments>('/departments/').then(setDepartments).catch(() => {}) }, [])
  useEffect(() => {
    if (!period) return
    const q = new URLSearchParams({ year, period, department: get('department'), kra: get('kra'), status: get('status'), search: get('search'), page: get('page', '1') })
    setData(null); setError('')
    api<Progress>(`/progress/?${q}`).then(setData).catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, period])

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold">Institution KRA status</h1>
        <YearPeriodPicker year={year} period={period} periods={periods} onChange={(y, p) => setParams(p ? { year: y, period: p } : { year: y })} />
      </div>
      {data && (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-7">
          <div className="card"><p className="text-xs text-slate-500">Assigned</p><p className="text-2xl font-semibold">{data.assigned}</p></div>
          {STATUSES.map((s) => (
            <button key={s} className={`card text-left ${get('status') === s ? 'ring-2 ring-blue-600' : ''}`} onClick={() => set({ status: get('status') === s ? '' : s })}>
              <p className="text-xs text-slate-500">{statusLabel(s)}</p><p className="text-2xl font-semibold">{data.counts[s]}</p>
            </button>
          ))}
          <Link to="/vc/reopen-requests" className="card"><p className="text-xs text-slate-500">Pending reopen requests</p><p className="text-2xl font-semibold">{data.pending_reopen_requests}</p></Link>
        </div>
      )}
      <div className="mb-3 flex flex-wrap gap-2">
        <select aria-label="Department" className="input w-auto" value={get('department')} onChange={(e) => set({ department: e.target.value })}>
          <option value="">All departments</option>{departments.map((d) => <option key={d.code} value={d.code}>{d.code}</option>)}
        </select>
        <input aria-label="KRA number" className="input w-28" type="number" min={1} max={45} placeholder="KRA #" value={get('kra')} onChange={(e) => set({ kra: e.target.value })} />
        <input aria-label="Search activity" className="input w-56" placeholder="Search activity text" defaultValue={get('search')} onKeyDown={(e) => { if (e.key === 'Enter') set({ search: (e.target as HTMLInputElement).value }) }} />
        <select aria-label="Status" className="input w-auto" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
        </select>
      </div>
      <ErrorBox error={error} />
      {!data ? <Loading /> : data.results.length === 0 ? <p className="card text-sm text-slate-500">No assignments match these filters.</p> : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left"><tr><th className="p-2">Dept</th><th className="p-2">KRA</th><th className="p-2">Annual target</th><th className="p-2">Achievement</th><th className="p-2">Status</th><th className="p-2" /></tr></thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.assignment_id} className="border-t border-slate-200 align-top">
                  <td className="p-2">{r.department}</td>
                  <td className="p-2" title={r.kra_text}>{r.kra_number}</td>
                  <td className="p-2 whitespace-pre-wrap">{r.target_text}</td>
                  <td className="p-2 whitespace-pre-wrap">{r.achievement_text}{r.is_nil && ' (Nil)'}</td>
                  <td className="p-2"><StatusBadge status={r.display_status} /></td>
                  <td className="p-2">{r.submission_id && r.display_status !== 'NOT_SUBMITTED' && <Link className="btn-secondary" to={`/vc/review/${r.submission_id}`}>Review</Link>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-2 text-sm">
            <span>{data.total} rows</span>
            <span className="flex gap-2">
              <button className="btn-secondary" disabled={data.page <= 1} onClick={() => set({ page: String(data.page - 1) })}>Previous</button>
              <button className="btn-secondary" disabled={data.page * data.page_size >= data.total} onClick={() => set({ page: String(data.page + 1) })}>Next</button>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
