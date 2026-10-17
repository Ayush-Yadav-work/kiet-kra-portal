import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, ApiError } from '../../api/client'
import { ErrorBox, Loading } from '../../components/ui'

// Phase 5A (D-065, D-066): VC-only draft assignments for the current and future years; finalized assignments are read-only.
type Year = { label: string; locked: boolean; current: boolean; finalized_assignments: number; drafts_pending: number; drafts_finalized: number }
type Tpl = { key: string; version: number; title: string; problem: string | null }
type Draft = { id: string; department: { code: string; name: string }; kra: { number: number; activity_text: string }; target_text: string
  template: { key: string; version: number; title: string }; copied_from_year: string | null; finalized: boolean }
type Final = { id: string; department: { code: string }; kra: { number: number; activity_text: string }; target_text: string; template: { key: string; version: number } | null }
type Kra = { number: number; activity_text: string }
type Dept = { code: string; name: string }

const errText = (e: unknown) => (e instanceof ApiError ? e.message : 'Request failed')

function DraftRow({ d, templates, onChanged }: { d: Draft; templates: Tpl[]; onChanged: () => void }) {
  const [target, setTarget] = useState(d.target_text)
  const [tpl, setTpl] = useState(`${d.template.key}|${d.template.version}`)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const dirty = target !== d.target_text || tpl !== `${d.template.key}|${d.template.version}`
  async function save() {
    setBusy(true); setError('')
    const [key, version] = tpl.split('|')
    try { await api(`/admin/drafts/${d.id}/`, { method: 'PATCH', body: { target_text: target, template_key: key, template_version: Number(version) } }); onChanged() }
    catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }
  async function remove() {
    if (!window.confirm(`Delete the draft for ${d.department.code} KRA ${d.kra.number}?`)) return
    try { await api(`/admin/drafts/${d.id}/`, { method: 'DELETE' }); onChanged() } catch (e) { setError(errText(e)) }
  }
  return (
    <tr className="border-t border-slate-100 align-top">
      <td className="p-1">KRA {d.kra.number}<p className="text-xs text-slate-500">{d.kra.activity_text.replace(/^KRA \d+:\s*/, '').slice(0, 90)}</p></td>
      <td className="p-1">
        {d.finalized ? <span className="whitespace-pre-wrap">{d.target_text}</span>
          : <textarea aria-label={`Target for KRA ${d.kra.number}`} className="input" rows={2} maxLength={500} value={target} onChange={(e) => setTarget(e.target.value)} />}
        <ErrorBox error={error} />
      </td>
      <td className="p-1 text-xs">
        {d.finalized ? `${d.template.key} v${d.template.version}` : (
          <select aria-label={`Template for KRA ${d.kra.number}`} className="input" value={tpl} onChange={(e) => setTpl(e.target.value)}>
            {templates.filter((t) => !t.problem || `${t.key}|${t.version}` === tpl).map((t) => <option key={`${t.key}|${t.version}`} value={`${t.key}|${t.version}`}>{t.key} v{t.version} — {t.title}</option>)}
          </select>)}
        {d.copied_from_year && <p className="mt-1 text-slate-500">Copied from {d.copied_from_year}</p>}
      </td>
      <td className="p-1 whitespace-nowrap">
        {d.finalized ? <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-900">Finalized</span> : <>
          <button className="btn-primary" disabled={!dirty || busy} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>{' '}
          <button className="btn-secondary" onClick={remove}>Delete</button></>}
      </td>
    </tr>
  )
}

export default function AdminAssignments() {
  const [years, setYears] = useState<Year[] | null>(null)
  const [year, setYear] = useState('')
  const [dept, setDept] = useState('CSE')
  const [depts, setDepts] = useState<Dept[]>([])
  const [kras, setKras] = useState<Kra[]>([])
  const [templates, setTemplates] = useState<Tpl[]>([])
  const [drafts, setDrafts] = useState<Draft[] | null>(null)
  const [finals, setFinals] = useState<Final[] | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [conflicts, setConflicts] = useState<{ department: string; kra: number; reason: string }[]>([])
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [allDrafts, setAllDrafts] = useState<Draft[]>([])
  const [newDraft, setNewDraft] = useState({ kra: '', target_text: '' })

  const loadYears = useCallback(() => api<Year[]>('/admin/years/').then((ys) => { setYears(ys); setYear((cur) => cur || (ys.find((y) => !y.locked)?.label ?? ys[0]?.label ?? '')) }).catch((e) => setError(errText(e))), [])
  useEffect(() => {
    loadYears()
    api<Dept[]>('/departments/').then(setDepts).catch(() => {})
    api<Kra[]>('/kras/').then(setKras).catch(() => {})
    api<Tpl[]>('/admin/templates/').then(setTemplates).catch(() => {})
  }, [loadYears])
  const current = years?.find((y) => y.label === year)
  const load = useCallback(() => {
    if (!year) return
    setDrafts(null); setFinals(null)
    api<Draft[]>(`/admin/drafts/?year=${year}&department=${dept}`).then(setDrafts).catch((e) => setError(errText(e)))
    api<Draft[]>(`/admin/drafts/?year=${year}`).then(setAllDrafts).catch(() => {})
    api<{ results: Final[] }>(`/assignments/?year=${year}`).then((r) => setFinals(r.results.filter((a) => a.department.code === dept))).catch((e) => setError(errText(e)))
  }, [year, dept])
  useEffect(() => { load() }, [load])
  const refresh = () => { loadYears(); load() }

  const pending = useMemo(() => allDrafts.filter((d) => !d.finalized), [allDrafts])
  const byDept = useMemo(() => pending.reduce<Record<string, number>>((m, d) => ({ ...m, [d.department.code]: (m[d.department.code] ?? 0) + 1 }), {}), [pending])
  const earlier = years?.filter((y) => y.label < year && y.finalized_assignments > 0) ?? []

  async function copyFrom(source: string) {
    setBusy(true); setError(''); setMessage(''); setConflicts([])
    try {
      const r = await api<{ created: number; conflicts: { department: string; kra: number; reason: string }[] }>(`/admin/years/${year}/copy/`, { method: 'POST', body: { source_year: source } })
      setMessage(`Copied ${r.created} assignment(s) from ${source} into ${year} drafts.${r.conflicts.length ? ` ${r.conflicts.length} left unchanged (already drafted or finalized) — listed below.` : ''}`)
      setConflicts(r.conflicts); refresh()
    } catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }
  async function finalize() {
    setBusy(true); setError(''); setMessage('')
    try {
      const r = await api<{ finalized: number }>(`/admin/years/${year}/finalize/`, { method: 'POST', body: { expected_pending: pending.length } })
      setMessage(`Finalized ${r.finalized} assignment(s) for ${year}. Their targets and templates are now fixed.`); setReview(false); refresh()
    } catch (e) { setError(errText(e)); setReview(false); refresh() } finally { setBusy(false) }
  }
  async function addDraft(e: FormEvent) {
    e.preventDefault(); setError('')
    try {
      await api('/admin/drafts/', { method: 'POST', body: { year, department: dept, kra: Number(newDraft.kra), target_text: newDraft.target_text } })
      setNewDraft({ kra: '', target_text: '' }); refresh()
    } catch (err) { setError(errText(err)) }
  }

  if (!years) return error ? <ErrorBox error={error} /> : <Loading />
  const drafted = new Set(drafts?.map((d) => d.kra.number))
  const finalizedNums = new Set(finals?.map((a) => a.kra.number))
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">KRA assignments and targets</h1>
      <div className="card flex flex-wrap items-end gap-3">
        <label className="text-sm">Academic year
          <select aria-label="Academic year" className="input" value={year} onChange={(e) => { setYear(e.target.value); setConflicts([]); setMessage(''); setReview(false) }}>
            {years.map((y) => <option key={y.label} value={y.label}>{y.label}{y.locked ? ' (ended — read-only)' : y.current ? ' (current year)' : ''}</option>)}
          </select></label>
        <label className="text-sm">Department
          <select aria-label="Department" className="input" value={dept} onChange={(e) => setDept(e.target.value)}>
            {depts.map((d) => <option key={d.code} value={d.code}>{d.code} — {d.name}</option>)}
          </select></label>
        {current && <p className="text-sm text-slate-600">Finalized: <b>{current.finalized_assignments}</b> · Drafts pending: <b>{current.drafts_pending}</b> · Drafts finalized: <b>{current.drafts_finalized}</b></p>}
      </div>
      <ErrorBox error={error} />
      {message && <p role="status" className="rounded bg-green-50 p-2 text-sm text-green-900">{message}</p>}

      {current && !current.locked && (
        <div className="card space-y-2">
          <h2 className="font-semibold">Prepare {year}</h2>
          {current.current && <p className="text-sm text-slate-600">Current year: only department/KRA pairs without an assignment can be added. Deans see them at once; reporting periods that have already closed stay closed.</p>}
          <div className="flex flex-wrap gap-2">
            {earlier.length ? earlier.map((y) => <button key={y.label} className="btn-secondary" disabled={busy} onClick={() => copyFrom(y.label)}>Copy {y.label} assignments into drafts</button>)
              : <p className="text-sm text-slate-600">No earlier year with finalized assignments to copy.</p>}
            <button className="btn-primary" disabled={busy || pending.length === 0} onClick={() => setReview(true)}>Review and finalize ({pending.length} pending)</button>
          </div>
          {conflicts.length > 0 && (
            <details open className="text-sm"><summary>{conflicts.length} not copied (existing draft or finalized assignment kept)</summary>
              <ul className="mt-1 max-h-40 list-disc overflow-auto pl-5">{conflicts.map((c) => <li key={`${c.department}-${c.kra}`}>{c.department} KRA {c.kra}: {c.reason}</li>)}</ul>
              <p className="text-xs text-slate-500">To replace one, delete or edit its draft below; finalized assignments cannot be replaced.</p></details>)}
          {review && (
            <div role="region" aria-label="Finalize review" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">
              <p className="font-medium">Finalize {pending.length} draft assignment(s) for {year}?</p>
              <p>By department: {Object.entries(byDept).map(([k, v]) => `${k} ${v}`).join(' · ')}</p>
              <p className="mt-1">After finalizing, Deans see these assignments and the targets and templates cannot be changed.</p>
              <div className="mt-2 flex gap-2"><button className="btn-primary" disabled={busy} onClick={finalize}>{busy ? 'Finalizing…' : 'Confirm finalize'}</button>
                <button className="btn-secondary" onClick={() => setReview(false)}>Cancel</button></div>
            </div>)}
        </div>)}

      {current && !current.locked && (
        <div className="card">
          <h2 className="mb-2 font-semibold">{dept} drafts for {year}</h2>
          {drafts === null ? <Loading /> : drafts.length === 0 ? <p className="text-sm text-slate-600">No drafts for {dept} yet. Copy an earlier year or add one below.</p> : (
            <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-sm">
              <thead><tr className="bg-slate-100 text-left"><th className="w-1/4 p-1">KRA</th><th className="w-1/3 p-1">Target text (exact)</th><th className="p-1">Template</th><th /></tr></thead>
              <tbody>{drafts.map((d) => <DraftRow key={`${d.id}-${d.target_text}-${d.template.key}-${d.finalized}`} d={d} templates={templates} onChanged={refresh} />)}</tbody>
            </table></div>)}
          {drafts !== null && finals !== null && ( // options depend on what is already drafted/finalized
          <form onSubmit={addDraft} className="mt-3 flex flex-wrap items-end gap-2 text-sm">
            <label>KRA<select aria-label="New draft KRA" className="input" value={newDraft.kra} onChange={(e) => setNewDraft({ ...newDraft, kra: e.target.value })}>
              <option value="">Choose…</option>
              {kras.filter((k) => !drafted.has(k.number) && !finalizedNums.has(k.number)).map((k) => <option key={k.number} value={k.number}>KRA {k.number}</option>)}
            </select></label>
            <label className="grow">Target text<input aria-label="New draft target" className="input" maxLength={500} value={newDraft.target_text} onChange={(e) => setNewDraft({ ...newDraft, target_text: e.target.value })} /></label>
            <button className="btn-secondary" disabled={!newDraft.kra || !newDraft.target_text.trim()}>Add draft</button>
          </form>)}
        </div>)}

      <div className="card">
        <h2 className="mb-2 font-semibold">Finalized {dept} assignments for {year} (read-only)</h2>
        {finals === null ? <Loading /> : finals.length === 0 ? <p className="text-sm text-slate-600">None finalized yet.</p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
            <thead><tr className="bg-slate-100 text-left"><th className="p-1">KRA</th><th className="p-1">Target</th><th className="p-1">Template</th></tr></thead>
            <tbody>{finals.map((a) => <tr key={a.id} className="border-t border-slate-100 align-top"><td className="p-1">KRA {a.kra.number}</td>
              <td className="p-1 whitespace-pre-wrap">{a.target_text}</td><td className="p-1 text-xs">{a.template ? `${a.template.key} v${a.template.version}` : '—'}</td></tr>)}</tbody>
          </table></div>)}
      </div>
    </div>
  )
}
