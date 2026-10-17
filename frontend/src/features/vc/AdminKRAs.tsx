import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../../api/client'
import { ErrorBox, Loading } from '../../components/ui'

// Phase 5A (D-065): a new KRA reuses an installed report layout; a new layout needs a software update.
type Tpl = { key: string; version: number; title: string; problem: string | null; used_by_kras: number[] }
type Kra = { number: number; activity_text: string; nba_ref: string; naac_ref: string; active: boolean; default_template: { key: string; version: number; title: string } | null }

export default function AdminKRAs() {
  const [kras, setKras] = useState<Kra[] | null>(null)
  const [templates, setTemplates] = useState<Tpl[]>([])
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({})
  const [message, setMessage] = useState('')
  const [form, setForm] = useState({ title: '', nba_ref: '', naac_ref: '', template: '', confirm: false })
  const [busy, setBusy] = useState(false)
  const load = useCallback(() => {
    api<Kra[]>('/admin/kras/').then(setKras).catch((e) => setError(e.message))
    api<Tpl[]>('/admin/templates/').then(setTemplates).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load])
  const chosen = templates.find((t) => `${t.key}|${t.version}` === form.template)

  async function create(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setFieldErrors({}); setMessage('')
    const [key, version] = form.template.split('|')
    try {
      const k = await api<Kra>('/admin/kras/', { method: 'POST', body: { title: form.title, nba_ref: form.nba_ref, naac_ref: form.naac_ref,
        template_key: key, template_version: Number(version), confirm_layout: form.confirm } })
      setMessage(`Created KRA ${k.number}. Add department targets for a future year under Assignments.`)
      setForm({ title: '', nba_ref: '', naac_ref: '', template: '', confirm: false }); load()
    } catch (err) {
      if (err instanceof ApiError) { setError(err.message); setFieldErrors(err.fieldErrors) } else setError('Request failed')
    } finally { setBusy(false) }
  }

  if (!kras) return error ? <ErrorBox error={error} /> : <Loading />
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">KRAs</h1>
      <form onSubmit={create} className="card space-y-2 text-sm">
        <h2 className="font-semibold">Create a KRA</h2>
        <label className="block">Activity text<textarea aria-label="Activity text" className="input" rows={2} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        {fieldErrors.title && <p className="text-xs text-red-700">{fieldErrors.title.join(' ')}</p>}
        <div className="flex gap-2">
          <label>NBA ref<input aria-label="NBA ref" className="input" maxLength={20} value={form.nba_ref} onChange={(e) => setForm({ ...form, nba_ref: e.target.value })} /></label>
          <label>NAAC ref<input aria-label="NAAC ref" className="input" maxLength={20} value={form.naac_ref} onChange={(e) => setForm({ ...form, naac_ref: e.target.value })} /></label>
        </div>
        <label className="block">Report layout (installed template)
          <select aria-label="Report layout" className="input" value={form.template} onChange={(e) => setForm({ ...form, template: e.target.value, confirm: false })}>
            <option value="">Choose…</option>
            {templates.map((t) => <option key={`${t.key}|${t.version}`} value={`${t.key}|${t.version}`} disabled={!!t.problem}>
              {t.key} v{t.version} — {t.title}{t.used_by_kras.length ? ` (used by KRA ${t.used_by_kras.join(', ')})` : ''}{t.problem ? ` — unavailable: ${t.problem}` : ''}</option>)}
          </select></label>
        {fieldErrors.template && <p className="text-xs text-red-700">{fieldErrors.template.join(' ')}</p>}
        {chosen && (
          <label className="flex items-start gap-2 rounded bg-amber-50 p-2">
            <input type="checkbox" checked={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.checked })} />
            <span>I confirm this activity is reported with the existing layout "<b>{chosen.title}</b>" — its headings and fields stay as they are.
              A different layout needs a software update.</span>
          </label>)}
        {fieldErrors.confirm_layout && <p className="text-xs text-red-700">{fieldErrors.confirm_layout.join(' ')}</p>}
        <ErrorBox error={error} />
        {message && <p role="status" className="rounded bg-green-50 p-2 text-green-900">{message}</p>}
        <button className="btn-primary" disabled={busy || !form.title.trim() || !form.template}>{busy ? 'Creating…' : 'Create KRA'}</button>
      </form>
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="bg-slate-100 text-left"><th className="p-1">KRA</th><th className="p-1">Activity</th><th className="p-1">NBA / NAAC</th><th className="p-1">Layout</th></tr></thead>
          <tbody>{kras.map((k) => <tr key={k.number} className="border-t border-slate-100 align-top">
            <td className="p-1">{k.number}</td><td className="p-1">{k.activity_text.replace(/^KRA \d+:\s*/, '')}</td>
            <td className="p-1 text-xs">{k.nba_ref || '—'} / {k.naac_ref || '—'}</td>
            <td className="p-1 text-xs">{k.default_template ? `${k.default_template.key} v${k.default_template.version}` : '—'}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}
