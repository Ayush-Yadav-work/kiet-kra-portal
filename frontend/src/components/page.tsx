import type { ReactNode, SelectHTMLAttributes } from 'react'
import banner from '../assets/campus-banner.jpg'
import { Icon, type IconName } from './icons'

// Redesign v2 page furniture (docs/ui-redesign-v2-review.md). Portal pages only: report previews and PDFs never use it.

/** Full-width page band under the header: title block on the left, the campus photograph faded in on the right (decorative). */
export function PageHero({ eyebrow, title, description, chip, aside, icon, photo = true, children }: {
  eyebrow?: string; title: string; description?: ReactNode; chip?: ReactNode; aside?: ReactNode; icon?: IconName; photo?: boolean; children?: ReactNode
}) {
  return (
    <div className="relative isolate -mx-4 -mt-4 mb-1 px-4 pb-2 pt-6 md:-mx-7 md:-mt-6 md:px-7 md:pt-8">
      <div aria-hidden="true" className="absolute inset-x-0 top-0 -z-10 h-[calc(100%-2.5rem)] bg-gradient-to-b from-[#E4EDF6] to-canvas">
        {photo && <div className="absolute inset-y-0 right-0 hidden w-[62%] bg-cover bg-[position:right_38%] [mask-image:linear-gradient(to_right,transparent_0,transparent_12%,#000_60%)] md:block"
          style={{ backgroundImage: `url(${banner})` }} />}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className={`flex max-w-3xl items-start gap-4 ${photo ? "lg:max-w-[48%]" : ""}`}>
          {icon && <span aria-hidden="true" className="hidden h-16 w-16 shrink-0 place-items-center rounded-full bg-[#DCE8F5] text-action sm:grid"><Icon name={icon} size={30} /></span>}
          <div>
            {eyebrow && <p className="mb-1 text-sm font-semibold uppercase tracking-[.08em] text-muted">{eyebrow}</p>}
            <h1 className="text-[28px] font-bold leading-tight md:text-[38px]">{title}</h1>
            {description && <div className="mt-1.5 text-[15px] text-muted md:text-base">{description}</div>}
            {chip && <div className="mt-3 inline-flex rounded-full bg-white/90 px-3.5 py-1 text-sm font-medium text-heading shadow-sm">{chip}</div>}
          </div>
        </div>
        {aside && <div className="w-full rounded-xl bg-white/95 p-3 shadow-[0_6px_20px_rgba(12,45,71,.12)] sm:w-auto">{aside}</div>}
      </div>
      {children && <div className="mt-5">{children}</div>}
    </div>
  )
}

/** White panel with an optional icon heading. */
export function Panel({ title, icon, description, actions, children, className = '', labelledBy }: {
  title?: ReactNode; icon?: IconName; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; labelledBy?: string
}) {
  return (
    <section aria-labelledby={title ? labelledBy : undefined} className={`panel ${className}`}>
      {title && (
        <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-4 md:px-5">
          <div className="flex items-start gap-3">
            {icon && <span aria-hidden="true" className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-info-bg text-action"><Icon name={icon} /></span>}
            <div><h2 id={labelledBy} className="text-lg font-bold md:text-xl">{title}</h2>{description && <p className="text-sm text-muted">{description}</p>}</div>
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

const CHIP = ['bg-[#E6F0FA] text-[#085290]', 'bg-[#E8F5EC] text-[#166534]', 'bg-[#FFF1DC] text-[#8A4B00]', 'bg-[#F1ECFE] text-[#5B21B6]',
  'bg-[#FDECEC] text-[#B91C1C]', 'bg-[#E0F2F1] text-[#0F5F59]', 'bg-[#FCE7F3] text-[#9D174D]', 'bg-[#EEF2F5] text-[#3B4A5C]']
/** Department code as a coloured pill; the colour is a stable hash of the code (decoration only, the text carries the meaning). */
export function DeptChip({ code }: { code: string }) {
  const h = [...code].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 7)
  return <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${CHIP[h % CHIP.length]}`}>{code}</span>
}

/** Numbered pagination (first, last and the pages around the current one). */
export function Pager({ page, pages, onPage, label = 'Pages' }: { page: number; pages: number; onPage: (p: number) => void; label?: string }) {
  if (pages <= 1) return null
  const nums = [...new Set([1, page - 1, page, page + 1, pages])].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b)
  const btn = 'grid h-9 min-w-9 place-items-center rounded-lg border px-2 text-sm font-semibold'
  return (
    <nav aria-label={label} className="flex flex-wrap items-center gap-1.5">
      <button type="button" className={`${btn} border-line bg-white text-action disabled:text-[#9AA7B6]`} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
        <Icon name="chevronLeft" size={18} /></button>
      {nums.map((n, i) => <span key={n} className="flex items-center gap-1.5">
        {i > 0 && n - nums[i - 1] > 1 && <span aria-hidden="true" className="px-0.5 text-muted">…</span>}
        <button type="button" aria-label={`Page ${n}`} aria-current={n === page ? 'page' : undefined} onClick={() => onPage(n)}
          className={`${btn} ${n === page ? 'border-action bg-action text-white' : 'border-line bg-white text-heading hover:border-action'}`}>{n}</button></span>)}
      <button type="button" className={`${btn} border-line bg-white text-action disabled:text-[#9AA7B6]`} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
        <Icon name="chevronRight" size={18} /></button>
    </nav>
  )
}

export function EmptyState({ icon = 'doc', title, children }: { icon?: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="grid justify-items-center gap-1.5 px-5 py-10 text-center">
      <span aria-hidden="true" className="grid h-12 w-12 place-items-center rounded-full bg-subtle text-muted"><Icon name={icon} size={24} /></span>
      <p className="font-semibold text-heading">{title}</p>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
    </div>
  )
}

/** Small labelled select with a leading icon (filters). */
export function IconSelect({ label, icon, children, className = '', ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; icon: IconName }) {
  return (
    <label className={`grid gap-1.5 text-sm font-semibold text-heading ${className}`}>{label}
      <span className="relative block">
        <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"><Icon name={icon} size={18} /></span>
        <select className="input pl-10" {...rest}>{children}</select>
      </span>
    </label>
  )
}
