import { useEffect, useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import { Icon, type IconName } from '../../components/icons'
import { EmptyState, PageHero } from '../../components/page'
import { ErrorBox, Loading } from '../../components/ui'

// VC Phase 1 (D-073): the catalogue is developer-installed — the VC reads it here and allocates targets under Annual assignments.
type Kra = { number: number; activity_text: string; nba_ref: string; naac_ref: string; active: boolean; installed: boolean
  default_template: { key: string; version: number; title: string } | null }

const FAMILY = ['bg-[#E6F0FA] text-[#085290]', 'bg-[#E8F5EC] text-[#166534]', 'bg-[#FFF1DC] text-[#8A4B00]', 'bg-[#F1ECFE] text-[#5B21B6]',
  'bg-[#FCE7F3] text-[#9D174D]', 'bg-[#E0F2F1] text-[#0F5F59]']
/** Pill colour per report-format family (template key without its trailing number), so related formats look alike. */
const familyTone = (key: string) => FAMILY[[...key.replace(/[\d_-]+$/, '')].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 7) % FAMILY.length]

function InfoCard({ icon, tone, title, children }: { icon: IconName; tone: string; title: string; children: ReactNode }) {
  return (
    <div className="panel flex items-center gap-4 px-4 py-4 md:px-5">
      <span aria-hidden="true" className={`grid h-14 w-14 shrink-0 place-items-center rounded-full ${tone}`}><Icon name={icon} size={26} /></span>
      <div className="min-w-0 break-words"><p className="text-lg font-bold text-heading">{title}</p><p className="text-sm text-muted">{children}</p></div>
    </div>
  )
}

export default function AdminKRAs() {
  const [kras, setKras] = useState<Kra[] | null>(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  useEffect(() => { api<Kra[]>('/admin/kras/').then(setKras).catch((e) => setError(e.message)) }, [])

  const needle = q.trim().toLowerCase()
  const shown = (kras ?? []).filter((k) => !needle || `${k.number} ${k.activity_text} ${k.nba_ref} ${k.naac_ref} ${k.default_template?.title ?? ''}`.toLowerCase().includes(needle))
  const installed = (kras ?? []).filter((k) => k.installed).length
  return (
    <div className="grid gap-[18px]">
      <PageHero title="Installed KRAs" photo={false} description="Each KRA has a developer-built report form, live preview, validation and PDF. New KRAs and report formats are added
        through a software update; set department targets under Annual assignments." />
      <ErrorBox error={error} />
      {!kras ? (!error && <Loading />) : (<>
        <section aria-label="Catalogue summary" className="grid gap-3 md:grid-cols-3">
          <InfoCard icon="doc" tone="bg-info-bg text-action" title={`${installed} installed KRAs`}>{kras.length - installed ? `${kras.length - installed} listed but not installed` : 'All listed KRAs have a report format'}</InfoCard>
          <InfoCard icon="layers" tone="bg-[#FFF1DC] text-[#B45309]" title="Standardised report formats">Every department reports a KRA in the same format.</InfoCard>
          <InfoCard icon="shield" tone="bg-ok-bg text-ok" title="Developer-managed catalogue">Formats change only through a software update, never here.</InfoCard>
        </section>
        <label className="relative block max-w-xl">
          <span className="sr-only">Search KRAs</span>
          <span aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"><Icon name="search" /></span>
          <input type="search" className="input min-h-12 bg-white pl-11" placeholder="Search KRA, activity, NBA / NAAC or report format" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <section aria-label="KRA catalogue" className="panel overflow-hidden">
          {shown.length === 0 ? <EmptyState icon="search" title="No KRA matches this search.">Try a KRA number or a word from the activity.</EmptyState> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-[15px]">
                <caption className="sr-only">Installed KRAs ({shown.length} shown)</caption>
                <thead className="thead-soft"><tr>{['KRA', 'Activity', 'NBA / NAAC', 'Report format'].map((h) => <th key={h} scope="col" className="border-b border-line px-4 py-3">{h}</th>)}</tr></thead>
                <tbody>{shown.map((k) => <tr key={k.number} className="border-b border-line align-top last:border-b-0 even:bg-[#FAFCFE]">
                  <td className="px-4 py-3 font-bold text-heading">{k.number}</td>
                  <td className="px-4 py-3 text-sm">{k.activity_text.replace(/^KRA \d+:\s*/, '')}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{k.nba_ref || '—'} / {k.naac_ref || '—'}</td>
                  <td className="px-4 py-3 text-sm">{k.default_template
                    ? <span className={`inline-block rounded-lg px-2.5 py-1 text-[13px] font-medium ${familyTone(k.default_template.key)}`}>{k.default_template.title}</span> : '—'}
                    {!k.installed && <span className="mt-1 block text-err">Not installed — cannot be allocated</span>}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
      </>)}
    </div>
  )
}
