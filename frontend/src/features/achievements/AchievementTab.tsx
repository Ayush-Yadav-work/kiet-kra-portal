import type { SubmissionDetail } from '../../api/types'
import { StatusBadge } from '../../components/ui'

/** One achievement value + remarks per period; text kept as entered, no totals or percentages (plan 3.3). */
export default function AchievementTab({ detail, values, onChange, disabled, errors }: {
  detail: SubmissionDetail
  values: { achievement_text: string; remarks: string }
  onChange?: (k: 'achievement_text' | 'remarks', v: string) => void
  disabled: boolean
  errors: Record<string, string[]>
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="card space-y-3">
        <p className="text-sm"><span className="font-medium">Fixed annual target ({detail.assignment.year}):</span> <span className="whitespace-pre-wrap">{detail.assignment.target_text}</span></p>
        <div>
          <label className="label" htmlFor="ach">Achievement for {detail.period.label}{!detail.is_nil && <span className="text-red-700"> *</span>}</label>
          <input id="ach" className="input" maxLength={500} disabled={disabled} value={values.achievement_text}
            onChange={(e) => onChange?.('achievement_text', e.target.value)} placeholder="As entered: a number, percentage, NA or description" />
          {errors.achievement_text && <p className="mt-1 text-xs text-red-700">{errors.achievement_text.join(' ')}</p>}
          <p className="mt-1 text-xs text-slate-500">Enter what was actually achieved this period. The portal does not total or calculate percentages.</p>
        </div>
        <div>
          <label className="label" htmlFor="rem">Progress / remarks</label>
          <textarea id="rem" className="input" rows={4} disabled={disabled} value={values.remarks} onChange={(e) => onChange?.('remarks', e.target.value)} />
        </div>
      </section>
      <section className="card">
        <h3 className="mb-2 font-semibold">All periods — {detail.assignment.year}</h3>
        <table className="w-full text-sm">
          <thead><tr className="text-left"><th className="p-1">Period</th><th className="p-1">Achievement</th><th className="p-1">Status</th></tr></thead>
          <tbody>
            {detail.period_entries.map((e) => (
              <tr key={e.period.id} className={`border-t border-slate-100 ${e.period.id === detail.period.id ? 'bg-blue-50' : ''}`}>
                <td className="p-1">{e.period.label}</td>
                <td className="p-1 whitespace-pre-wrap">{e.period.id === detail.period.id ? values.achievement_text : e.achievement_text}{e.is_nil && ' (Nil)'}</td>
                <td className="p-1">{e.applicability === 'NOT_ASSIGNED' ? <span className="text-sm text-muted">Not assigned for this period</span>
                  : e.applicability === 'NOT_DUE' ? <span className="text-sm text-muted">Not due</span> : <StatusBadge status={e.display_status} />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
