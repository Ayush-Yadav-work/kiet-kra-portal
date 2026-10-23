import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useFieldArray, useWatch, type Control, type UseFormGetValues, type UseFormRegister, type UseFormSetValue } from 'react-hook-form'
import type { Field, Payload, Schema } from '../../api/types'
import { tabKeys } from '../../components/ui'

type Errors = Record<string, string[]>
interface Ctx {
  control: Control<Payload>; register: UseFormRegister<Payload>; setValue: UseFormSetValue<Payload>
  getValues: UseFormGetValues<Payload>; disabled: boolean; errors: Errors; deanName: string
}

export function emptyValue(f: Field): unknown {
  return f.type === 'table' || f.type === 'multiselect' || f.type === 'ratings' ? [] : f.type === 'checklist' || f.type === 'term' ? {} : ''
}
export function emptyActivity(schema: Schema) {
  return Object.fromEntries(schema.sections.flatMap((s) => s.fields).map((f) => [f.id, emptyValue(f)]))
}
const intOrBlank = (v: unknown) => (v === '' || v === null || v === undefined ? '' : Number(v))
// Decimals stay the exact entered text so the server can reject (never silently round) extra places.
const decimalText = (v: unknown) => (v === null || v === undefined ? '' : String(v).trim())

function FieldError({ path, errors }: { path: string; errors: Errors }) {
  const msgs = errors[path]
  return msgs ? <p id={`${path}-err`} className="mt-1 text-xs text-red-700">{msgs.join(' ')}</p> : null
}

/** Visible "*" plus screen-reader text; shown only while the field applies (inactive fields are never required). */
function Req({ on }: { on?: boolean }) {
  return on ? <><span className="text-red-700" aria-hidden> *</span><span className="sr-only"> (required for submission)</span></> : null
}

type When = { field: string; in?: string[]; contains?: string }
/** Same rule as the server's `applies` (backend/apps/reports/schema.py). */
export function applies(cond: When | undefined, obj: Record<string, unknown> | undefined) {
  if (!cond) return true
  const v = obj?.[cond.field]
  return cond.contains !== undefined ? Array.isArray(v) && v.includes(cond.contains) : (cond.in ?? []).includes(v as string)
}

function Label({ f, htmlFor }: { f: Field; htmlFor?: string }) {
  return <label className="label" htmlFor={htmlFor}>{f.label}<Req on={f.required && !f.auto} /></label>
}

/** Year of study / semester dropdowns (D-079). An earlier free-text entry that could not be matched stays visible until replaced. */
function Term({ f, name, ctx, ariaLabel }: { f: Field; name: string; ctx: Ctx; ariaLabel?: string }) {
  const v = useWatch({ control: ctx.control, name: name as never }) as unknown as Record<string, string> | undefined
  const legacy = v?.legacy && !f.parts!.every((p) => v[p.id]) ? v.legacy : ''
  return (
    <div role="group" aria-label={ariaLabel ?? f.label} aria-describedby={ctx.errors[name] ? `${name}-err` : undefined}>
      <div className="flex flex-wrap gap-2">
        {f.parts!.map((p) => (
          <label key={p.id} className="grid min-w-[9rem] flex-1 gap-0.5 text-xs font-medium text-slate-600">{p.label}
            <select id={f.parts!.indexOf(p) === 0 ? name : undefined} className="input" disabled={ctx.disabled} aria-invalid={!!ctx.errors[name]}
              {...ctx.register(`${name}.${p.id}` as never)}>
              <option value="">Select {p.label.toLowerCase()}…</option>
              {p.options.map((o) => <option key={o}>{o}</option>)}
            </select>
          </label>
        ))}
      </div>
      {legacy && <p className="mt-1 rounded bg-amber-50 p-1.5 text-xs text-amber-900">Earlier entry: “{legacy}” — it could not be matched to the options. Select the values above; it is kept until you do.</p>}
    </div>
  )
}

/** The reporting department's Head/Dean: always the signed-in Dean's profile name, snapshotted on submission (D-079). */
function DeanName({ name, ctx }: { name: string; ctx: Ctx }) {
  return ctx.deanName
    ? <input id={name} className="input bg-slate-50" value={ctx.deanName} readOnly aria-readonly />
    : <p id={name} className="rounded bg-amber-50 p-2 text-sm text-amber-900" role="note">Your account profile has no full name, so this cannot be filled in. Drafts still save; ask the administrator to correct your profile before submitting.</p>
}

function Scalar({ f, name, ctx, ariaLabel }: { f: Field; name: string; ctx: Ctx; ariaLabel?: string }) {
  if (f.auto === 'dean_name') return <DeanName name={name} ctx={ctx} />
  if (f.type === 'term') return <Term f={f} name={name} ctx={ctx} ariaLabel={ariaLabel} />
  const common = { id: name, disabled: ctx.disabled, 'aria-label': ariaLabel, 'aria-invalid': !!ctx.errors[name], 'aria-describedby': ctx.errors[name] ? `${name}-err` : undefined, className: 'input' }
  const reg = (opts = {}) => ctx.register(name as never, opts)
  switch (f.type) {
    case 'longtext':
      return <textarea {...common} rows={5} maxLength={f.max_length} placeholder={f.placeholder} {...reg()} />
    case 'integer':
      return <input {...common} type="number" inputMode="numeric" step={1} min={f.min} max={f.max} {...reg({ setValueAs: intOrBlank })} />
    case 'decimal':
      return <input {...common} type="text" inputMode="decimal" placeholder={f.placeholder ?? `${f.min ?? ''}–${f.max ?? ''}`} {...reg({ setValueAs: decimalText })} />
    case 'date':
      return <input {...common} type="date" {...reg()} />
    case 'select':
      return (
        <select {...common} {...reg()}>
          <option value="">— Select —</option>
          {f.options!.map((o) => <option key={o}>{o}</option>)}
        </select>
      )
    default:
      return (
        <>
          <input {...common} type="text" maxLength={f.max_length} placeholder={f.placeholder} list={f.suggestions ? `${name}-sugg` : undefined} {...reg()} />
          {f.suggestions && <datalist id={`${name}-sugg`}>{f.suggestions.map((s) => <option key={s} value={s} />)}</datalist>}
        </>
      )
  }
}

/** Column that applies only for some values of another column in the same row (e.g. payment fields). */
function ConditionalCell({ c, rowName, ctx, ariaLabel }: { c: Field; rowName: string; ctx: Ctx; ariaLabel?: string }) {
  const name = `${rowName}.${c.id}`
  const ctrl = useWatch({ control: ctx.control, name: `${rowName}.${c.when!.field}` as never }) as unknown as string
  const applies = c.when!.in.includes(ctrl)
  useEffect(() => {
    if (!applies && !ctx.disabled && !c.keep_inactive) { // keep_inactive: saved value kept, ignored on submit (D-049)
      const cur = ctx.getValues(name as never) as unknown
      if (cur !== '' && cur !== undefined && cur !== null) ctx.setValue(name as never, '' as never, { shouldDirty: true })
    }
  }, [applies, name, ctx, c.keep_inactive])
  if (!applies) return <input className="input" value={c.keep_inactive && ctx.getValues(name as never) ? 'NA (entered value kept, not used)' : 'NA'} disabled readOnly aria-label={`${c.label}: not applicable`} />
  return <Scalar f={c} name={name} ctx={ctx} ariaLabel={ariaLabel} />
}

function Cell({ c, rowName, ctx, ariaLabel }: { c: Field; rowName: string; ctx: Ctx; ariaLabel?: string }) {
  return c.when ? <ConditionalCell c={c} rowName={rowName} ctx={ctx} ariaLabel={ariaLabel} /> : <Scalar f={c} name={`${rowName}.${c.id}`} ctx={ctx} ariaLabel={ariaLabel} />
}

/** Card-editor label: the required marker follows the row's current answers (e.g. KRA 32 payment fields). */
function CardLabel({ c, rowName, ctx, htmlFor }: { c: Field; rowName: string; ctx: Ctx; htmlFor: string }) {
  const row = useWatch({ control: ctx.control, name: rowName as never }) as unknown as Record<string, unknown> | undefined
  return <label className="label" htmlFor={htmlFor}>{c.label}<Req on={c.required && applies(c.when, row)} /></label>
}

function MultiSelect({ f, name, ctx }: { f: Field; name: string; ctx: Ctx }) {
  return (
    <fieldset aria-invalid={!!ctx.errors[name]} aria-describedby={ctx.errors[name] ? `${name}-err` : undefined}>
      <legend className="label">{f.label}<Req on={f.required} /></legend>
      <div className="grid gap-1 sm:grid-cols-2">
        {f.options!.map((o) => (
          <label key={o} className="flex items-start gap-2 text-sm">
            <input type="checkbox" value={o} disabled={ctx.disabled} {...ctx.register(name as never)} className="mt-1" />{o}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Checklist({ f, name, ctx }: { f: Field; name: string; ctx: Ctx }) {
  return (
    <fieldset aria-describedby={ctx.errors[name] ? `${name}-err` : undefined}>
      <legend className="label">{f.label}<Req on={f.required} /></legend>
      <table className="w-full text-sm">
        <tbody>
          {f.items!.map((item, i) => (
            <tr key={item} className="border-t border-slate-100">
              <td className="py-1 pr-2">{i + 1}. {item}</td>
              {['Yes', 'No'].map((v) => (
                <td key={v} className="w-14">
                  <label className="flex items-center gap-1">
                    <input type="radio" value={v} disabled={ctx.disabled} {...ctx.register(`${name}.${item}` as never)} />{v}
                  </label>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </fieldset>
  )
}

/** Consolidated averages per survey statement, entered by the Dean (plan 5.4): no tick boxes, no averaging. */
function Ratings({ f, name, ctx }: { f: Field; name: string; ctx: Ctx }) {
  const lo = f.scale![0], hi = f.scale![f.scale!.length - 1]
  return (
    <fieldset aria-describedby={ctx.errors[name] ? `${name}-err` : undefined}>
      <legend className="label">{f.label}<Req on={f.required} /></legend>
      <p className="mb-2 text-xs text-slate-500">Scale {lo}–{hi}: {f.scale_labels?.join(' · ')}. Enter the college-prepared average, up to {f.decimal_places ?? 2} decimals.</p>
      <table className="w-full text-sm">
        <thead><tr className="text-left"><th className="w-8 p-1">S No.</th><th className="p-1">Statement</th><th className="w-28 p-1">Average ({lo}–{hi})</th></tr></thead>
        <tbody>
          {f.items!.map((item, n) => {
            const p = `${name}.${n}`
            return (
              <tr key={n} className="border-t border-slate-100 align-top">
                <td className="p-1">{n + 1}.</td>
                <td className="p-1"><label htmlFor={p}>{item}</label></td>
                <td className="p-1">
                  <input id={p} className="input" type="text" inputMode="decimal" placeholder={`${lo}–${hi}`} disabled={ctx.disabled}
                    aria-invalid={!!ctx.errors[p]} aria-describedby={ctx.errors[p] ? `${p}-err` : undefined} {...ctx.register(p as never, { setValueAs: decimalText })} />
                  <FieldError path={p} errors={ctx.errors} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </fieldset>
  )
}

function Table({ f, name, ctx }: { f: Field; name: string; ctx: Ctx }) {
  const { fields, append, remove } = useFieldArray({ control: ctx.control, name: name as never })
  const values = useWatch({ control: ctx.control, name: name as never }) as Record<string, unknown>[] | undefined
  const max = f.max_rows ?? 100
  const cols = f.columns!.filter((c) => c.type !== 'auto') // auto columns are filled from the report on render
  const cards = f.editor === 'cards' || cols.length > 7
  function removeRow(i: number) {
    const row = values?.[i] ?? {}
    const populated = Object.values(row).some((v) => v !== '' && v !== null && v !== undefined)
    if (!populated || window.confirm(`Remove row ${i + 1}? Its entered values will be lost.`)) remove(i)
  }
  const removeBtn = (i: number) => !ctx.disabled && <button type="button" className="btn-secondary" aria-label={`Remove row ${i + 1}`} onClick={() => removeRow(i)}>✕</button>
  return (
    <div>
      <Label f={f} />
      {cards ? (
        <ol className="space-y-3">
          {fields.map((row, i) => (
            <li key={row.id} className="rounded border border-slate-200 p-3">
              <div className="mb-2 flex items-center justify-between"><span className="text-sm font-semibold">Record {i + 1}</span>{removeBtn(i)}</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {cols.map((c) => {
                  const p = `${name}.${i}.${c.id}`
                  return (
                    <div key={c.id} className={c.type === 'longtext' ? 'sm:col-span-2' : ''}>
                      <CardLabel c={c} rowName={`${name}.${i}`} ctx={ctx} htmlFor={p} />
                      <Cell c={c} rowName={`${name}.${i}`} ctx={ctx} />
                      {c.help && <p className="mt-1 text-xs text-slate-500">{c.help}</p>}
                      <FieldError path={p} errors={ctx.errors} />
                    </div>
                  )
                })}
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <div className="relative overflow-x-auto">{/* relative: contains the sr-only header text */}
          <table className="w-full min-w-[640px] text-sm">
            <thead><tr className="bg-slate-100 text-left"><th className="w-10 p-1">Sl.</th>{cols.map((c) => <th key={c.id} className="p-1">{c.label}<Req on={c.required && !c.when} />{c.required && c.when && <span className="text-xs font-normal text-slate-600"> (required where applicable)</span>}</th>)}<th /></tr></thead>
            <tbody>
              {fields.map((row, i) => (
                <tr key={row.id} className="border-t border-slate-100 align-top">
                  <td className="p-1">{i + 1}</td>
                  {cols.map((c) => {
                    const p = `${name}.${i}.${c.id}`
                    return <td key={c.id} className="p-1"><Cell c={c} rowName={`${name}.${i}`} ctx={ctx} ariaLabel={`${c.label}, row ${i + 1}`} /><FieldError path={p} errors={ctx.errors} /></td>
                  })}
                  <td className="p-1">{removeBtn(i)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!ctx.disabled && (
        <button type="button" className="btn-secondary mt-2" disabled={fields.length >= max}
          onClick={() => append(Object.fromEntries(cols.map((c) => [c.id, emptyValue(c)])) as never)}>
          + Add {cards ? 'record' : 'row'} {fields.length >= max && `(max ${max})`}
        </button>
      )}
      {f.columns!.some((c) => c.type === 'auto') && (
        <p className="mt-1 text-xs text-slate-500">{f.columns!.filter((c) => c.type === 'auto').map((c) => c.label).join(' and ')} are filled from this report automatically.</p>
      )}
    </div>
  )
}

function FieldView({ f, name, ctx }: { f: Field; name: string; ctx: Ctx }) {
  const [showGuide, setShowGuide] = useState(false)
  let body
  if (f.type === 'table') body = <Table f={f} name={name} ctx={ctx} />
  else if (f.type === 'multiselect') body = <MultiSelect f={f} name={name} ctx={ctx} />
  else if (f.type === 'checklist') body = <Checklist f={f} name={name} ctx={ctx} />
  else if (f.type === 'ratings') body = <Ratings f={f} name={name} ctx={ctx} />
  else body = <><Label f={f} htmlFor={name} /><Scalar f={f} name={name} ctx={ctx} /></>
  return (
    <div className="mb-3">
      {body}
      {f.help && <p className="mt-1 text-xs text-slate-500">{f.help}</p>}
      {f.guidance && (
        <div className="mt-1 text-xs">
          <button type="button" className="underline text-slate-600" aria-expanded={showGuide} onClick={() => setShowGuide(!showGuide)}>Template guidance</button>
          {showGuide && <p className="mt-1 rounded bg-slate-50 p-2 text-slate-600">{f.guidance}</p>}
        </div>
      )}
      <FieldError path={name} errors={ctx.errors} />
    </div>
  )
}

/** Fields whose `when` does not apply are hidden, never cleared: values stay in the draft and revision payload, are skipped by submit validation and are not printed (D-048, KRA 9). */
function InactiveNote({ section, act }: { section: Field[]; act: Record<string, unknown> | undefined }) {
  const n = section.filter((f) => !applies(f.when, act)).length
  if (!n) return null
  return (
    <p className="rounded bg-slate-50 p-2 text-sm text-slate-700">
      {n === section.length ? 'This section does not apply to your current answers' : `${n} field(s) here do not apply to your current answers`}.
      {' '}Values entered earlier are retained (in the draft and in any submitted revision), but are not checked for submission or included in the printed report.
    </p>
  )
}

/** Smooth unless the user asked for reduced motion. */
export const scrollBehavior = (): ScrollBehavior => (window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth')

/** Scroll a heading's section into view and move focus to the heading (it is tabIndex -1), without a second jump. */
export function jumpTo(id: string, focusId = id + '-h') {
  document.getElementById(id)?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
  document.getElementById(focusId)?.focus({ preventScroll: true })
}

/** "Jump to section" for the open event/course: chips from the template (sections with at least one applicable field),
 * a compact select on phones; the section in view is marked with aria-current, never a completion state. */
function SectionNav({ items }: { items: { id: string; title: string }[] }) {
  const [current, setCurrent] = useState(items[0]?.id)
  const held = useRef(0) // a clicked section stays current while its jump settles (the last sections cannot reach the top)
  const key = items.map((s) => s.id).join('|')
  useEffect(() => {
    const els = items.map((s) => document.getElementById(s.id)).filter((e): e is HTMLElement => !!e)
    const io = new IntersectionObserver((entries) => {
      const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
      if (top && Date.now() > held.current) setCurrent(top.target.id)
    }, { rootMargin: '0px 0px -65% 0px' })
    els.forEach((e) => io.observe(e))
    return () => io.disconnect()
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!items.length) return null
  const go = (id: string) => { held.current = Date.now() + 1000; setCurrent(id); jumpTo(id) }
  return (
    <nav aria-label="Sections" className="mb-4 rounded-xl border border-line bg-subtle px-3 py-2.5">
      <label htmlFor={`${items[0].id}-jump`} className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted sm:hidden">Jump to section</label>
      <p className="mb-1.5 hidden text-xs font-semibold uppercase tracking-wide text-muted sm:block" aria-hidden>Jump to section</p>
      <select id={`${items[0].id}-jump`} className="input sm:hidden" value={current} onChange={(e) => go(e.target.value)}>
        {items.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
      </select>
      <ul className="hidden flex-wrap gap-1.5 sm:flex">
        {items.map((s) => (
          <li key={s.id} className="max-w-full">
            <a href={`#${s.id}`} aria-current={current === s.id ? 'location' : undefined} onClick={(e) => { e.preventDefault(); go(s.id) }}
              className={`block rounded-full border px-3 py-1 text-[13px] leading-snug no-underline transition-colors ${current === s.id
                ? 'border-action bg-info-bg font-semibold text-action' : 'border-[#CBD6E1] bg-white text-heading hover:border-action hover:text-action'}`}>
              {s.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function SectionCard({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={id + '-h'} className="card mb-3 scroll-mt-4">
      <h3 id={id + '-h'} tabIndex={-1} className="mb-3 border-b border-line pb-2 text-base font-semibold text-heading">{title}</h3>
      {children}
    </section>
  )
}

export default function SchemaForm({ schema, ctx }: { schema: Schema; ctx: Ctx }) {
  const { fields, append, remove } = useFieldArray({ control: ctx.control, name: 'activities' })
  const values = useWatch({ control: ctx.control, name: 'activities' })
  const [open, setOpen] = useState(0)
  const label = schema.activity.label
  const single = schema.activity.max === 1 // one consolidated record set per period: no event tabs
  function removeActivity(i: number) {
    const name = String(values?.[i]?.event_name || `${label} ${i + 1}`)
    if (window.confirm(`Remove "${name}" and everything entered for it?`)) { remove(i); setOpen(0) }
  }
  return (
    <div>
      <FieldError path="activities" errors={ctx.errors} />
      {!single && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-white p-2.5">
          <div className="flex flex-wrap gap-2" role="tablist" aria-label={`${label}s in this report`} onKeyDown={tabKeys}>
            {fields.map((a, i) => (
              <button key={a.id} id={`act-tab-${i}`} type="button" role="tab" aria-selected={open === i} aria-controls={`act-panel-${i}`}
                tabIndex={open === i ? 0 : -1} onClick={() => setOpen(i)} className={open === i ? 'btn-primary' : 'btn-secondary'}>
                {label} {i + 1}{Object.keys(ctx.errors).some((k) => k.startsWith(`activities.${i}.`)) && <><span className={open === i ? 'text-red-300' : 'text-red-700'} aria-hidden> ●</span><span className="sr-only"> (has errors)</span></>}
              </button>
            ))}
          </div>
          {!ctx.disabled && (
            <button type="button" className="btn-secondary" disabled={fields.length >= schema.activity.max}
              onClick={() => { append(emptyActivity(schema) as never); setOpen(fields.length) }}>+ Add {label.toLowerCase()}</button>
          )}
        </div>
      )}
      {fields.map((a, i) => {
        const act = values?.[i] as Record<string, unknown>
        const sid = (s: { id: string }) => `sec-${a.id}-${s.id}` // field-array key: stable across adds/removals
        return (
        <div key={a.id} hidden={open !== i} {...(single ? {} : { role: 'tabpanel', id: `act-panel-${i}`, 'aria-labelledby': `act-tab-${i}` })}>
          {open === i && <SectionNav items={schema.sections.filter((s) => s.fields.some((f) => applies(f.when, act))).map((s) => ({ id: sid(s), title: s.title }))} />}
          {schema.sections.map((s) => (
            <SectionCard key={s.id} id={sid(s)} title={s.title}>
              {s.intro && <p className="mb-2 text-sm text-slate-600">{s.intro}</p>}
              {s.fields.filter((f) => applies(f.when, act)).map((f) => <FieldView key={f.id} f={f} name={`activities.${i}.${f.id}`} ctx={ctx} />)}
              <InactiveNote section={s.fields} act={act} />
            </SectionCard>
          ))}
          {!single && !ctx.disabled && fields.length > 1 && <button type="button" className="btn-danger" onClick={() => removeActivity(i)}>Remove {label.toLowerCase()} {i + 1}</button>}
        </div>
        )
      })}
    </div>
  )
}
