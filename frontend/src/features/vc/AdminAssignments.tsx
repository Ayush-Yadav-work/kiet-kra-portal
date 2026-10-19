import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import { ErrorBox, Loading } from '../../components/ui'

// VC features plan v2.3 Phase 1 (D-073): annual allocations — Unallocated (no row) / Draft / Removed / Finalised.
type State = 'UNALLOCATED' | 'DRAFT' | 'REMOVED' | 'FINALISED'
type Alloc = { id: string | null; assignment_id: string | null; state: Exclude<State, 'UNALLOCATED'>; department: string; kra: number; target_text: string
  previous_target: string | null; source_year: string | null; edit_version: number | null; finalised_at: string | null; finalised_by: string | null
  removed_by: string | null; effective_start_period: { index: number; label: string } | null }
type PeriodShort = { id: number; index: number; label: string; opens_at: string; closes_at: string }
type Data = { year: { label: string; state: 'preparation' | 'active' | 'closed'; drafts: number; removed: number; finalised: number }
  previous_year: string | null; departments: { code: string; name: string }[]; allocations: Alloc[]
  kras: { number: number; activity_text: string; installed: boolean; active: boolean }[]
  start: { kind: string; default: string | null; choices: Record<string, { period: PeriodShort; grant: boolean }> } }
type Row = (Alloc | (Omit<Alloc, 'state'> & { state: 'UNALLOCATED' })) & { key: string }
type CopyPlan = Record<'create' | 'drafts_preserved' | 'finalised_skipped' | 'removed_preserved' | 'unavailable', { department: string; kra: number; reason?: string }[]>
type Preview = { token: string; count: number; kind: string; choice: string; grant: boolean; grant_expires_at: string | null
  effective_start_period: PeriodShort; applicable_periods: PeriodShort[]; choices: Record<string, { period: PeriodShort; grant: boolean }>
  rows: { id: string; department: string; kra: number; previous_target: string | null; target_text: string }[] }
type Conflict = { id?: string; department?: string; kra?: number; reason: string }

const YEARS = ['2026-27', '2027-28', '2028-29']
const FILTERS = [['ALL', 'All allocations'], ['CHANGED', 'Changed targets'], ['UNFINISHED', 'Unfinished drafts'], ['FINALISED', 'Finalised'],
  ['REMOVED', 'Removed'], ['UNALLOCATED', 'Unallocated']] as const
type Filter = typeof FILTERS[number][0]
const STATE_STYLE: Record<State, [string, string]> = { UNALLOCATED: ['Unallocated', 'bg-neutral-bg text-neutral'], DRAFT: ['Draft', 'bg-warn-bg text-warn'],
  REMOVED: ['Removed', 'bg-err-bg text-err'], FINALISED: ['Finalised', 'bg-ok-bg text-ok'] }
const PAGE = 60
const changed = (r: Row) => r.state !== 'UNALLOCATED' && r.previous_target !== null && r.previous_target !== r.target_text
const isNew = (r: Row) => r.state !== 'UNALLOCATED' && r.previous_target === null

export default function AdminAssignments() {
  const [params, setParams] = useSearchParams()
  const year = params.get('year') || '2027-28'
  const kra = params.get('kra') || ''
  const view = (params.get('view') || 'ALL') as Filter
  const setParam = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); n.delete('page'); setParams(n) }
  const page = Number(params.get('page') || 1)
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState('')
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [edits, setEdits] = useState<Record<string, string>>({})  // unsaved target edits survive filter changes
  const [selected, setSelected] = useState<Set<string>>(new Set())  // draft ids: scope of the draft actions below
  const [toAllocate, setToAllocate] = useState<Set<string>>(new Set())  // "kra|dept" of unallocated pairs
  const [bulk, setBulk] = useState({ text: '', preview: null as null | { department: string; kra: number; old: string; new: string }[] })
  const [copyPlan, setCopyPlan] = useState<{ plan: CopyPlan; thenFinalise: boolean } | null>(null)
  const [fin, setFin] = useState<Preview | null>(null)
  const [accept, setAccept] = useState(false)

  const load = useCallback((signal?: AbortSignal) => {
    setData(null); setError('')
    return api<Data>(`/admin/allocations/?year=${year}`, { signal }).then((d) => { if (!signal?.aborted) setData(d) })
      .catch((e) => { if (!signal?.aborted) setError(e instanceof ApiError ? e.message : 'Failed to load') })
  }, [year])
  useEffect(() => { const c = new AbortController(); load(c.signal); setSelected(new Set()); setToAllocate(new Set()); setFin(null); setCopyPlan(null); return () => c.abort() }, [load])
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (Object.keys(edits).length) e.preventDefault() }
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn)
  }, [edits])

  const rows = useMemo<Row[]>(() => {
    if (!data) return []
    const by = new Map(data.allocations.map((a) => [`${a.kra}|${a.department}`, a]))
    const kras = data.kras.filter((k) => (kra ? k.number === Number(kra) : by.size === 0 || data.allocations.some((a) => a.kra === k.number)))
    const out: Row[] = []
    for (const k of kras) for (const d of data.departments) {
      const a = by.get(`${k.number}|${d.code}`)
      out.push(a ? { ...a, key: a.id ?? a.assignment_id! } : { id: null, assignment_id: null, state: 'UNALLOCATED', department: d.code, kra: k.number, target_text: '',
        previous_target: null, source_year: null, edit_version: null, finalised_at: null, finalised_by: null, removed_by: null, effective_start_period: null, key: `${k.number}|${d.code}` })
    }
    return out
  }, [data, kra])
  const match = (r: Row, f: Filter) => f === 'ALL' || (f === 'CHANGED' ? changed(r) : f === 'UNFINISHED' ? r.state === 'DRAFT' : r.state === f)
  const counts = Object.fromEntries(FILTERS.map(([f]) => [f, rows.filter((r) => match(r, f)).length])) as Record<Filter, number>
  const shown = rows.filter((r) => match(r, view))
  const pageRows = shown.slice((page - 1) * PAGE, page * PAGE)
  const versions = (ids: Set<string>) => (data?.allocations ?? []).filter((a) => a.id && ids.has(a.id)).map((a) => ({ id: a.id!, edit_version: a.edit_version! }))
  const outside = [...selected].filter((id) => !shown.some((r) => r.id === id)).length
  const editable = data?.year.state !== 'closed'
  const kraText = (n: number) => data?.kras.find((k) => k.number === n)?.activity_text.replace(/^KRA \d+:\s*/, '') ?? ''

  async function run(fn: () => Promise<string>) {
    setBusy(true); setError(''); setConflicts([]); setMessage('')
    try { setMessage(await fn()) } catch (e) {
      if (e instanceof ApiError) { setError(e.message); setConflicts((e.body.conflicts as Conflict[] | undefined) ?? []) } else setError('Request failed')
    } finally { setBusy(false) }
  }
  const reload = async () => { await load(); }
  const saveRow = (r: Alloc) => run(async () => {
    await api(`/admin/drafts/${r.id}/`, { method: 'PATCH', body: { target_text: edits[r.id!], edit_version: r.edit_version } })
    setEdits((e) => { const n = { ...e }; delete n[r.id!]; return n }); await reload(); return `Saved the ${r.department} KRA ${r.kra} draft target.`
  })
  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, key: string) => { const n = new Set(set); if (n.has(key)) n.delete(key); else n.add(key); setter(n) }

  async function previewCopy(thenFinalise: boolean) {
    await run(async () => {
      const plan = await api<CopyPlan>(`/admin/years/${year}/copy/?preview=1`, { method: 'POST', body: { source_year: data!.previous_year } })
      setCopyPlan({ plan, thenFinalise }); return ''
    })
  }
  async function confirmCopy() {
    const then = copyPlan?.thenFinalise
    await run(async () => {
      const r = await api<{ created: number }>(`/admin/years/${year}/copy/`, { method: 'POST', body: { source_year: data!.previous_year } })
      setCopyPlan(null); await reload(); return `Created ${r.created} draft allocation(s) from ${data!.previous_year}; existing drafts, removed drafts and finalised assignments were left unchanged.`
    })
    if (then) {  // "Send previous year KRAs": copy, then open the final review of every draft — never publishes silently
      const d = await api<Data>(`/admin/allocations/?year=${year}`)
      setData(d)
      const ids = new Set(d.allocations.filter((a) => a.state === 'DRAFT').map((a) => a.id!))
      setSelected(ids); openFinalise(undefined, ids, d)
    }
  }
  const allocate = () => run(async () => {
    const byKra = new Map<number, string[]>()
    for (const key of toAllocate) { const [k, d] = key.split('|'); byKra.set(Number(k), [...(byKra.get(Number(k)) ?? []), d]) }
    let n = 0
    for (const [k, depts] of byKra) n += (await api<{ created: string[] }>('/admin/drafts/', { method: 'POST', body: { year, kra: k, departments: depts } })).created.length
    setToAllocate(new Set()); await reload(); return `Created ${n} draft allocation(s) for the selected departments only.`
  })
  const previewBulk = () => run(async () => {
    const r = await api<{ affected: { department: string; kra: number; old: string; new: string }[] }>('/admin/drafts/bulk-target/', { method: 'POST', body: { items: versions(selected), target_text: bulk.text, apply: false } })
    setBulk((b) => ({ ...b, preview: r.affected })); return ''
  })
  const applyBulk = () => run(async () => {
    await api('/admin/drafts/bulk-target/', { method: 'POST', body: { items: versions(selected), target_text: bulk.text, apply: true } })
    setBulk({ text: '', preview: null }); await reload(); return `Applied the target to ${selected.size} selected draft(s).`
  })
  const removeOrRestore = (ids: Set<string>, restore: boolean) => run(async () => {
    await api(`/admin/drafts/${restore ? 'restore' : 'remove'}/`, { method: 'POST', body: { items: versions(ids) } })
    setSelected(new Set()); await reload(); return restore ? 'Restored.' : `Removed ${ids.size} draft(s) from this year's setup; restore them from the Removed view.`
  })
  async function openFinalise(choice?: string, ids = selected, d = data) {
    setBusy(true); setError(''); setConflicts([]); setAccept(false)
    try {
      const items = (d?.allocations ?? []).filter((a) => a.id && ids.has(a.id)).map((a) => ({ id: a.id!, edit_version: a.edit_version! }))
      setFin(await api<Preview>(`/admin/years/${year}/finalise/preview/`, { method: 'POST', body: { items, start: choice } }))
    } catch (e) {
      setFin(null)
      if (e instanceof ApiError) { setError(e.message); setConflicts((e.body.conflicts as Conflict[] | undefined) ?? []) }
    } finally { setBusy(false) }
  }
  const confirmFinalise = () => run(async () => {
    const r = await api<{ finalised: number; already_finalised: boolean }>(`/admin/years/${year}/finalise/`, { method: 'POST', body: { token: fin!.token } })
    setFin(null); setSelected(new Set()); await reload()
    return `${r.already_finalised ? 'Already finalised' : 'Finalised and sent'} ${r.finalised} assignment(s) for ${year}. Their targets are locked and visible to the selected Deans.`
  })

  const fld = 'grid gap-1.5 text-sm font-semibold text-heading'
  return (
    <div className="grid gap-[18px]">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div>
          <h1 className="text-[28px] font-bold leading-tight md:text-4xl">Annual assignments</h1>
          <p className="mt-1 text-muted">Department targets per KRA. Drafts are visible only to you; finalising locks a target and makes it visible to that Dean.</p>
        </div>
        <div className="flex w-full flex-wrap gap-4 sm:w-auto">
          <label className={`${fld} w-full sm:w-40`}>Academic year
            <select className="input" value={year} onChange={(e) => setParams({ year: e.target.value })}>{YEARS.map((y) => <option key={y}>{y}</option>)}</select></label>
          <label className={`${fld} w-full sm:w-72`}>KRA
            <select className="input" value={kra} onChange={(e) => setParam('kra', e.target.value)}>
              <option value="">All allocated KRAs</option>
              {data?.kras.filter((k) => k.active).map((k) => <option key={k.number} value={k.number} disabled={!k.installed}>KRA {k.number}{k.installed ? '' : ' (not installed)'}</option>)}
            </select></label>
        </div>
      </div>

      <ErrorBox error={error} />
      {conflicts.length > 0 && <ul className="rounded-lg border border-err bg-err-bg p-3 text-sm text-[#7F1D1D]">{conflicts.slice(0, 20).map((c, i) =>
        <li key={i}>{c.department ? `${c.department} KRA ${c.kra}` : c.id}: {c.reason}</li>)}</ul>}
      {message && <p role="status" className="rounded-lg border-l-4 border-ok bg-ok-bg px-3 py-2 text-sm text-[#14532D]">{message}</p>}
      {!data ? (!error && <Loading />) : (<>
        <section aria-label="Year setup" className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-[10px] border border-line bg-white p-4">
          <p className="text-[15px]"><b className="text-heading">{data.year.label}</b> — {data.year.state === 'preparation' ? 'in preparation' : data.year.state === 'active' ? 'active year' : 'closed (read-only)'}
            {' · '}{data.year.drafts} draft · {data.year.removed} removed · {data.year.finalised} finalised</p>
          {editable && data.previous_year && <div className="flex flex-wrap gap-2 sm:ml-auto">
            <button className="btn-secondary" disabled={busy} onClick={() => previewCopy(false)}>Copy previous year setup</button>
            <button className="btn-secondary" disabled={busy} onClick={() => previewCopy(true)}>Send previous year KRAs</button></div>}
          {data.year.drafts > 0 && <p className="w-full text-sm text-muted">Unfinished drafts are not obligations: Deans do not see them and they are excluded from analytics until finalised.</p>}
        </section>

        {copyPlan && (
          <section aria-label="Copy review" className="rounded-[10px] border border-action bg-white p-4 text-sm">
            <h2 className="mb-2 text-lg font-bold">Copy {data.previous_year} → {year}</h2>
            <ul className="grid gap-1 sm:grid-cols-2">
              <li><b>{copyPlan.plan.create.length}</b> new draft allocations to create (exact department targets)</li>
              <li><b>{copyPlan.plan.drafts_preserved.length}</b> existing drafts kept unchanged</li>
              <li><b>{copyPlan.plan.finalised_skipped.length}</b> finalised assignments skipped</li>
              <li><b>{copyPlan.plan.removed_preserved.length}</b> removed drafts stay removed</li>
              <li><b>{copyPlan.plan.unavailable.length}</b> need resolution (inactive department/KRA or template not installed)</li>
            </ul>
            <p className="mt-2 text-muted">Reports, achievements, evidence, review status and grants are never copied.{copyPlan.thenFinalise && ' Next you will review the drafts before anything is sent.'}</p>
            <div className="mt-3 flex gap-2"><button className="btn-primary" disabled={busy} onClick={confirmCopy}>{copyPlan.thenFinalise ? 'Copy and review for sending' : `Create ${copyPlan.plan.create.length} drafts`}</button>
              <button className="btn-quiet" onClick={() => setCopyPlan(null)}>Cancel</button></div>
          </section>
        )}

        <div role="group" aria-label="Allocation filter" className="flex flex-wrap gap-2">
          {FILTERS.map(([f, label]) => <button key={f} type="button" aria-pressed={view === f} onClick={() => setParam('view', f === 'ALL' ? '' : f)}
            className={`${view === f ? 'btn-primary' : 'btn-secondary'} min-h-9 text-sm`}>{label} ({counts[f]})</button>)}
        </div>
        <p className="text-sm text-muted">Counts cover {kra ? `KRA ${kra}` : 'all allocated KRAs'} of {year}. Changed = new target differs from the stored {data.previous_year ?? 'previous-year'} target.</p>

        {editable && (selected.size > 0 || toAllocate.size > 0) && (
          <section aria-label="Selected actions" className="grid gap-3 rounded-[10px] border border-line bg-white p-4 text-sm">
            {toAllocate.size > 0 && <div className="flex flex-wrap items-center gap-3"><b>{toAllocate.size} unallocated department(s) selected.</b>
              <button className="btn-primary min-h-9 text-sm" disabled={busy} onClick={allocate}>Create drafts for the {toAllocate.size} selected departments</button>
              <button className="btn-quiet text-sm" onClick={() => setToAllocate(new Set())}>Clear</button></div>}
            {selected.size > 0 && <>
              <p><b>{selected.size} draft(s) selected</b>{outside > 0 && ` — ${outside} outside the current filter`}. Actions below apply to exactly these drafts.</p>
              <div className="flex flex-wrap items-end gap-2">
                <label className={`${fld} min-w-64 flex-1`}>Target for the selected drafts
                  <input className="input" value={bulk.text} onChange={(e) => setBulk({ text: e.target.value, preview: null })} /></label>
                <button className="btn-secondary min-h-9 text-sm" disabled={busy || !bulk.text.trim()} onClick={previewBulk}>Preview target change</button>
                <button className="btn-secondary min-h-9 text-sm" disabled={busy} onClick={() => removeOrRestore(selected, false)}>Remove {selected.size} from this year's draft</button>
                <button className="btn-primary min-h-9 text-sm" disabled={busy} onClick={() => openFinalise()}>Review and finalise {selected.size}</button>
                <button className="btn-quiet text-sm" onClick={() => setSelected(new Set())}>Clear selection</button>
              </div>
              {bulk.preview && <div className="rounded-lg bg-subtle p-3">
                <p className="mb-1 font-semibold">These {bulk.preview.length} drafts will change:</p>
                <ul className="max-h-40 overflow-auto">{bulk.preview.map((b) => <li key={`${b.kra}|${b.department}`}>{b.department} KRA {b.kra}: “{b.old}” → “{b.new}”</li>)}</ul>
                <button className="btn-primary mt-2 min-h-9 text-sm" disabled={busy} onClick={applyBulk}>Apply to these {bulk.preview.length} drafts</button></div>}
            </>}
          </section>
        )}

        {fin && (
          <section aria-label="Finalise review" className="rounded-[10px] border-2 border-action bg-white p-4 text-sm">
            <h2 className="mb-1 text-lg font-bold">Finalise and send {fin.count} assignment(s) for {year}</h2>
            <p>These targets become <b>locked</b> and visible to the selected Deans. Reporting starts in <b>{fin.effective_start_period.label}</b>
              {' '}({fin.applicable_periods.length} reporting period{fin.applicable_periods.length === 1 ? '' : 's'}: {fin.applicable_periods.map((p) => `P${p.index} due ${fmtDateTime(p.closes_at)}`).join('; ')}).</p>
            {Object.keys(fin.choices).length > 1 && <fieldset className="mt-2 grid gap-1"><legend className="font-semibold text-heading">Fewer than 72 hours remain in the current period. Start in:</legend>
              {Object.entries(fin.choices).map(([k, c]) => <label key={k} className="flex items-center gap-2"><input type="radio" name="start" checked={fin.choice === k} onChange={() => openFinalise(k)} />
                {c.period.label}{c.grant ? ' — current period, with a 72-hour reporting window from finalisation' : ' — next period (no report for the current one)'}</label>)}</fieldset>}
            {fin.grant && <label className="mt-2 flex items-start gap-2 rounded bg-warn-bg p-2"><input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
              <span>Each Dean gets a 72-hour window to report for {fin.effective_start_period.label}, ending {fin.grant_expires_at && fmtDateTime(fin.grant_expires_at)}.</span></label>}
            <div className="mt-2 max-h-64 overflow-auto"><table className="w-full text-sm"><thead className="bg-subtle text-left"><tr><th className="p-1.5">Department</th><th className="p-1.5">KRA</th><th className="p-1.5">Previous target</th><th className="p-1.5">New target</th></tr></thead>
              <tbody>{fin.rows.map((r) => <tr key={r.id} className="border-t border-line align-top"><td className="p-1.5">{r.department}</td><td className="p-1.5">{r.kra}</td>
                <td className="whitespace-pre-wrap p-1.5">{r.previous_target ?? '—'}</td><td className="whitespace-pre-wrap p-1.5">{r.target_text}</td></tr>)}</tbody></table></div>
            <div className="mt-3 flex gap-2"><button className="btn-primary" disabled={busy || (fin.grant && !accept)} onClick={confirmFinalise}>Finalise and send {fin.count}</button>
              <button className="btn-quiet" onClick={() => setFin(null)}>Cancel</button></div>
          </section>
        )}

        <section aria-label="Allocations" className="overflow-hidden rounded-[10px] border border-line bg-white">
          <div className="overflow-x-auto">
            <table role="table" className="report-table w-full text-[15px]">
              <thead role="rowgroup" className="bg-subtle text-left"><tr role="row">
                <th role="columnheader" className="w-10 border-b border-line px-3 py-2.5"><span className="sr-only">Select</span></th>
                {['Department', 'KRA', 'Previous-year target', 'New-year target', 'State', 'Actions'].map((h) => <th role="columnheader" key={h} className="border-b border-line px-3 py-2.5 font-semibold text-heading">{h}</th>)}</tr></thead>
              <tbody role="rowgroup">
                {pageRows.map((r) => {
                  const [stateLabel, stateCls] = STATE_STYLE[r.state]
                  return (
                    <tr role="row" key={r.key} className="border-b border-line align-top last:border-b-0">
                      <td role="cell" data-col="status" className="px-3 py-3">{editable && r.state === 'DRAFT' && r.id
                        ? <input type="checkbox" aria-label={`Select ${r.department} KRA ${r.kra} draft`} checked={selected.has(r.id)} onChange={() => toggle(selected, setSelected, r.id!)} />
                        : editable && r.state === 'UNALLOCATED' && data.kras.find((k) => k.number === r.kra)?.installed
                          ? <input type="checkbox" aria-label={`Allocate KRA ${r.kra} to ${r.department}`} checked={toAllocate.has(r.key)} onChange={() => toggle(toAllocate, setToAllocate, r.key)} /> : null}</td>
                      <td role="cell" data-col="head" className="whitespace-nowrap px-3 py-3 font-bold text-heading">{r.department}<span className="md:hidden"> · KRA {r.kra}</span></td>
                      <td role="cell" data-col="wide" className="px-3 py-3 text-sm"><b className="text-heading max-md:hidden">{r.kra}</b> {kraText(r.kra)}</td>
                      <td role="cell" data-col="wide" data-label="Previous" className="w-52 whitespace-pre-wrap px-3 py-3 text-sm">{r.previous_target ?? '—'}</td>
                      <td role="cell" data-col="wide" className="w-72 px-3 py-3">{r.state === 'DRAFT' && editable && r.id
                        ? <><label className="sr-only" htmlFor={`t-${r.id}`}>New target for {r.department} KRA {r.kra}</label>
                          <textarea id={`t-${r.id}`} className="input text-[15px]" rows={2} value={edits[r.id] ?? r.target_text} onChange={(e) => setEdits({ ...edits, [r.id!]: e.target.value })} />
                          {edits[r.id] !== undefined && edits[r.id] !== r.target_text && <span className="text-xs font-semibold text-warn">Unsaved change</span>}</>
                        : <span className="whitespace-pre-wrap">{r.state === 'UNALLOCATED' ? '—' : r.target_text}</span>}</td>
                      <td role="cell" data-col="wide" className="px-3 py-3"><span className={`inline-block whitespace-nowrap rounded-full px-3 py-0.5 text-[13px] font-semibold ${stateCls}`}>{stateLabel}</span>
                        {changed(r) && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading">Changed</span>}
                        {isNew(r) && <span className="ml-1.5 rounded border border-control px-1 text-xs font-bold text-heading">New</span>}
                        {r.state === 'FINALISED' && <span className="mt-1 block text-[13px] text-muted">{r.finalised_by} · {r.finalised_at && fmtDateTime(r.finalised_at)}{r.effective_start_period ? ` · from P${r.effective_start_period.index}` : ' · all periods'}</span>}
                        {r.state === 'REMOVED' && <span className="mt-1 block text-[13px] text-muted">Removed by {r.removed_by}</span>}</td>
                      <td role="cell" data-col="action" className="w-32 px-3 py-3">{editable && r.state === 'DRAFT' && r.id && edits[r.id] !== undefined && edits[r.id] !== r.target_text
                        ? <button className="btn-primary min-h-9 w-full text-sm" disabled={busy} onClick={() => saveRow(r as Alloc)}>Save<span className="sr-only"> {r.department} KRA {r.kra}</span></button>
                        : editable && r.state === 'REMOVED' && r.id ? <button className="btn-secondary min-h-9 w-full text-sm" disabled={busy} onClick={() => removeOrRestore(new Set([r.id!]), true)}>Restore<span className="sr-only"> {r.department} KRA {r.kra}</span></button> : null}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {shown.length === 0 && <p className="p-5 text-muted">{rows.length === 0 ? `No allocations for ${year} yet. Copy the previous year or choose a KRA to allocate it to departments.` : 'No allocations match this filter.'}</p>}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm">
            <span className="text-muted">{shown.length} row(s) · page {page} of {Math.max(1, Math.ceil(shown.length / PAGE))}</span>
            <span className="flex gap-2"><button className="btn-secondary min-h-9 text-sm" disabled={page <= 1} onClick={() => setParam('page', String(page - 1))}>Previous</button>
              <button className="btn-secondary min-h-9 text-sm" disabled={page * PAGE >= shown.length} onClick={() => setParam('page', String(page + 1))}>Next</button></span>
          </div>
        </section>
      </>)}
    </div>
  )
}
