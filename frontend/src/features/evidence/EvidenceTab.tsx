import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, fmtBytes, fmtDateTime } from '../../api/client'
import { ErrorBox, Loading } from '../../components/ui'

interface Item {
  id: string; source_type: 'FILE' | 'DRIVE_LINK'; category: string; label: string; description: string
  original_filename: string | null; mime: string | null; bytes: number | null; drive_url: string | null
  uploaded_at: string; uploaded_by: string; removed: boolean
}
interface Data {
  results: Item[]; editable: boolean; categories: string[]; required: string[]; note: string
  usage: { active_bytes: number; history_bytes: number; max_file_bytes: number; max_active_bytes: number; max_history_bytes: number }
}

/** Evidence is separate from the report PDF and never changes edit_version (plan 3.2, C3). */
export default function EvidenceTab({ submissionId, canEdit, onChange }: { submissionId: string; canEdit: boolean; onChange?: () => void }) {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'FILE' | 'DRIVE_LINK'>('FILE')
  const [category, setCategory] = useState('')
  const [label, setLabel] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [formKey, setFormKey] = useState(0)

  const load = useCallback(() => api<Data>(`/submissions/${submissionId}/evidence/`).then(setData).catch((e) => setError(e.message)), [submissionId])
  useEffect(() => { load() }, [load])

  async function add(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      if (mode === 'FILE') {
        if (!file) throw new ApiError(400, { message: 'Choose a file.' })
        if (data && file.size > data.usage.max_file_bytes) throw new ApiError(413, { message: `Files must be at most ${fmtBytes(data.usage.max_file_bytes)}.` })
        const fd = new FormData()
        fd.append('file', file); fd.append('category', category); fd.append('label', label); fd.append('description', description)
        await api(`/submissions/${submissionId}/evidence/`, { method: 'POST', body: fd })
      } else {
        await api(`/submissions/${submissionId}/evidence/`, { method: 'POST', body: { source_type: 'DRIVE_LINK', drive_url: url, category, label, description } })
      }
      setLabel(''); setDescription(''); setFile(null); setUrl(''); setFormKey((k) => k + 1)
      await load(); onChange?.()
    } catch (err) {
      setError(err instanceof ApiError ? [err.message, ...Object.values(err.fieldErrors).flat()].join(' ') : 'Upload failed')
    } finally { setBusy(false) }
  }

  async function removeItem(item: Item) {
    if (!window.confirm(`Remove "${item.label}" from this report? Submitted revisions keep their copy.`)) return
    try { await api(`/evidence/${item.id}/`, { method: 'DELETE' }); await load(); onChange?.() } catch (e) { setError((e as Error).message) }
  }

  if (!data) return error ? <ErrorBox error={error} /> : <Loading />
  const present = new Set(data.results.map((r) => r.category))
  const editable = canEdit && data.editable
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <section className="lg:col-span-2 card">
        <h2 className="mb-2 font-semibold">Evidence ({data.results.length})</h2>
        <p className="mb-2 text-xs text-slate-600">
          Active files: {fmtBytes(data.usage.active_bytes)} of {fmtBytes(data.usage.max_active_bytes)} · upload history {fmtBytes(data.usage.history_bytes)} of {fmtBytes(data.usage.max_history_bytes)}.
          Evidence is downloaded separately and is never added to the report PDF.
        </p>
        <ErrorBox error={error} />
        {data.results.length === 0 ? <p className="text-sm text-slate-500">No evidence added yet.</p> : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start gap-2 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{r.label} <span className="text-xs font-normal text-slate-500">— {r.category}</span></p>
                  <p className="text-xs text-slate-500">
                    {r.source_type === 'FILE' ? `${r.original_filename} · ${fmtBytes(r.bytes)}` : 'Google Drive link'} · {fmtDateTime(r.uploaded_at)} · {r.uploaded_by}
                  </p>
                  {r.description && <p className="text-xs">{r.description}</p>}
                </div>
                {r.source_type === 'FILE' ? (
                  <>
                    <a className="btn-secondary" href={`/api/v1/evidence/${r.id}/download/?inline=1`} target="_blank" rel="noopener">Open</a>
                    <a className="btn-secondary" href={`/api/v1/evidence/${r.id}/download/`}>Download</a>
                  </>
                ) : <a className="btn-secondary" href={r.drive_url!} target="_blank" rel="noopener noreferrer">Open link</a>}
                {editable && <button className="btn-secondary" onClick={() => removeItem(r)}>Remove</button>}
              </li>
            ))}
          </ul>
        )}
      </section>
      <aside className="space-y-4">
        <section className="card text-sm">
          <h3 className="font-semibold">Minimum evidence for submission</h3>
          <ul className="mt-1 space-y-0.5">
            {data.required.map((c) => <li key={c}>{present.has(c) ? '✓' : '○'} {c}</li>)}
          </ul>
          <p className="mt-2 text-xs text-slate-500">{data.note}</p>
        </section>
        {editable && (
          <form key={formKey} className="card space-y-2" onSubmit={add}>
            <h3 className="font-semibold">Add evidence</h3>
            <div className="flex gap-3 text-sm" role="radiogroup" aria-label="Evidence type">
              <label><input type="radio" checked={mode === 'FILE'} onChange={() => setMode('FILE')} /> File (PDF/JPEG/PNG)</label>
              <label><input type="radio" checked={mode === 'DRIVE_LINK'} onChange={() => setMode('DRIVE_LINK')} /> Google Drive link</label>
            </div>
            <div><label className="label" htmlFor="ev-cat">Category</label>
              <select id="ev-cat" className="input" value={category} onChange={(e) => setCategory(e.target.value)} required>
                <option value="">— Select —</option>{data.categories.map((c) => <option key={c}>{c}</option>)}
              </select></div>
            <div><label className="label" htmlFor="ev-label">Label</label><input id="ev-label" className="input" maxLength={200} value={label} onChange={(e) => setLabel(e.target.value)} required /></div>
            {mode === 'FILE' ? (
              <div><label className="label" htmlFor="ev-file">File (max {fmtBytes(data.usage.max_file_bytes)})</label>
                <input id="ev-file" type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
            ) : (
              <div><label className="label" htmlFor="ev-url">Drive link</label>
                <input id="ev-url" className="input" type="url" placeholder="https://drive.google.com/…" value={url} onChange={(e) => setUrl(e.target.value)} />
                <p className="mt-1 text-xs text-amber-800">Make sure the VC can open this link — Drive sharing permissions apply. The portal only checks that it is a Google Drive address.</p></div>
            )}
            <div><label className="label" htmlFor="ev-desc">Description (optional)</label><textarea id="ev-desc" className="input" rows={2} maxLength={1000} value={description} onChange={(e) => setDescription(e.target.value)} /></div>
            <button className="btn-primary" disabled={busy || !category || !label}>{busy ? 'Uploading…' : 'Add evidence'}</button>
          </form>
        )}
      </aside>
    </div>
  )
}
