import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { ErrorBox, Loading } from '../../components/ui'

// VC Phase 1 (D-073): the catalogue is developer-installed — the VC reads it here and allocates targets under Annual assignments.
type Kra = { number: number; activity_text: string; nba_ref: string; naac_ref: string; active: boolean; installed: boolean
  default_template: { key: string; version: number; title: string } | null }

export default function AdminKRAs() {
  const [kras, setKras] = useState<Kra[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { api<Kra[]>('/admin/kras/').then(setKras).catch((e) => setError(e.message)) }, [])

  if (!kras) return error ? <ErrorBox error={error} /> : <Loading />
  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-[28px] font-bold leading-tight md:text-4xl">Installed KRAs</h1>
        <p className="mt-1 text-muted">Each KRA has a developer-built report form, live preview, validation and PDF. New KRAs and report formats are added
          through a software update; set department targets under Annual assignments.</p>
      </div>
      <div className="overflow-x-auto rounded-[10px] border border-line bg-white">
        <table className="w-full min-w-[640px] text-[15px]">
          <thead className="bg-subtle text-left"><tr>{['KRA', 'Activity', 'NBA / NAAC', 'Report format'].map((h) => <th key={h} className="border-b border-line px-3.5 py-2.5 font-semibold text-heading">{h}</th>)}</tr></thead>
          <tbody>{kras.map((k) => <tr key={k.number} className="border-b border-line align-top last:border-b-0">
            <td className="px-3.5 py-3 font-bold text-heading">{k.number}</td><td className="px-3.5 py-3">{k.activity_text.replace(/^KRA \d+:\s*/, '')}</td>
            <td className="px-3.5 py-3 text-sm">{k.nba_ref || '—'} / {k.naac_ref || '—'}</td>
            <td className="px-3.5 py-3 text-sm">{k.default_template ? `${k.default_template.title}` : '—'}{!k.installed && <span className="block text-err">Not installed — cannot be allocated</span>}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}
