import { useEffect, useState } from 'react'
import { useFieldArray, useWatch, type Control, type UseFormGetValues, type UseFormRegister, type UseFormSetValue } from 'react-hook-form'
import type { Field, Payload, Schema } from '../../api/types'

type Errors = Record<string, string[]>
interface Ctx {
  control: Control<Payload>; register: UseFormRegister<Payload>; setValue: UseFormSetValue<Payload>
  getValues: UseFormGetValues<Payload>; disabled: boolean; errors: Errors
}

export function emptyValue(f: Field): unknown {
  return f.type === 'table' || f.type === 'multiselect' || f.type === 'ratings' ? [] : f.type === 'checklist' ? {} : ''
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

function Label({ f, htmlFor }: { f: Field; htmlFor?: string }) {
  return (
    <label className="label" htmlFor={htmlFor}>
      {f.label}{f.required && <span className="text-red-700" aria-hidden> *</span>}
      {f.required && <span className="sr-only"> (required for submission)</span>}
    </label>
  )
}

function Scalar({ f, name, ctx }: { f: Field; name: string; ctx: Ctx }) {
  const common = { id: name, disabled: ctx.disabled, 'aria-invalid': !!ctx.errors[name], 'aria-describedby': ctx.errors[name] ? `${name}-err` : undefined, className: 'input' }
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
function ConditionalCell({ c, rowName, ctx }: { c: Field; rowName: string; ctx: Ctx }) {
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
  return <Scalar f={c} name={name} ctx={ctx} />
}

function Cell({ c, rowName, ctx }: { c: Field; rowName: string; ctx: Ctx }) {
  return c.when ? <ConditionalCell c={c} rowName={rowName} ctx={ctx} /> : <Scalar f={c} name={`${rowName}.${c.id}`} ctx={ctx} />
}

function MultiSelect({ f, name, ctx }: { f: Field; name: string; ctx: Ctx }) {
  return (
    <fieldset aria-invalid={!!ctx.errors[name]}>
      <legend className="label">{f.label}{f.required && <span className="text-red-700"> *</span>}</legend>
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
    <fieldset>
      <legend className="label">{f.label}{f.required && <span className="text-red-700"> *</span>}</legend>
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
    <fieldset>
      <legend className="label">{f.label}{f.required && <span className="text-red-700"> *</span>}</legend>
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
                    aria-invalid={!!ctx.errors[p]} {...ctx.register(p as never, { setValueAs: decimalText })} />
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
                      <label className="label" htmlFor={p}>{c.label}{c.required && <span className="text-red-700"> *</span>}</label>
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
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead><tr className="bg-slate-100 text-left"><th className="w-10 p-1">Sl.</th>{cols.map((c) => <th key={c.id} className="p-1">{c.label}{c.required && <span className="text-red-700"> *</span>}</th>)}<th /></tr></thead>
            <tbody>
              {fields.map((row, i) => (
                <tr key={row.id} className="border-t border-slate-100 align-top">
                  <td className="p-1">{i + 1}</td>
                  {cols.map((c) => {
                    const p = `${name}.${i}.${c.id}`
                    return <td key={c.id} className="p-1"><span className="sr-only">{c.label} row {i + 1}</span><Cell c={c} rowName={`${name}.${i}`} ctx={ctx} /><FieldError path={p} errors={ctx.errors} /></td>
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
        <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label={`${label}s in this report`}>
          {fields.map((a, i) => (
            <button key={a.id} type="button" role="tab" aria-selected={open === i} onClick={() => setOpen(i)}
              className={open === i ? 'btn-primary' : 'btn-secondary'}>
              {label} {i + 1}{Object.keys(ctx.errors).some((k) => k.startsWith(`activities.${i}.`)) && <span className="text-red-300"> ●</span>}
            </button>
          ))}
          {!ctx.disabled && (
            <button type="button" className="btn-secondary" disabled={fields.length >= schema.activity.max}
              onClick={() => { append(emptyActivity(schema) as never); setOpen(fields.length) }}>+ Add {label.toLowerCase()}</button>
          )}
        </div>
      )}
      {fields.map((a, i) => (
        <div key={a.id} hidden={open !== i}>
          <nav className="mb-3 flex flex-wrap gap-2 text-xs" aria-label="Sections">
            {schema.sections.map((s) => <a key={s.id} className="underline text-blue-800" href={`#sec-${i}-${s.id}`}>{s.title}</a>)}
          </nav>
          {schema.sections.map((s) => (
            <section key={s.id} id={`sec-${i}-${s.id}`} className="card mb-3">
              <h3 className="mb-2 font-semibold">{s.title}</h3>
              {s.intro && <p className="mb-2 text-sm text-slate-600">{s.intro}</p>}
              {s.fields.map((f) => <FieldView key={f.id} f={f} name={`activities.${i}.${f.id}`} ctx={ctx} />)}
            </section>
          ))}
          {!single && !ctx.disabled && fields.length > 1 && <button type="button" className="btn-danger" onClick={() => removeActivity(i)}>Remove {label.toLowerCase()} {i + 1}</button>}
        </div>
      ))}
    </div>
  )
}
