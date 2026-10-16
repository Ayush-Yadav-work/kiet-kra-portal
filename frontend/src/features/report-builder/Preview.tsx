import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../../api/client'

/**
 * Server-rendered HTML preview in a sandboxed iframe (plan 8.6–8.7, C7).
 * Debounced ~750 ms; stale responses are aborted; scroll position is restored after each update.
 * The sandbox allows same-origin only (to read/restore scroll) and never scripts.
 */
export default function Preview({ submissionId, draft, revision }: { submissionId: string; draft?: unknown; revision?: string }) {
  const frame = useRef<HTMLIFrameElement>(null)
  const scroll = useRef(0)
  const [html, setHtml] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [zoom, setZoom] = useState('fit')
  const key = JSON.stringify(draft ?? null) + (revision ?? '')

  useEffect(() => {
    const ctrl = new AbortController()
    const t = setTimeout(async () => {
      setBusy(true)
      try {
        const body = revision ? { revision } : (draft as object) ?? {}
        const r = await api<{ html: string }>(`/submissions/${submissionId}/preview/`, { method: 'POST', body, signal: ctrl.signal })
        scroll.current = frame.current?.contentWindow?.scrollY ?? scroll.current
        setHtml(r.html)
        setError('')
      } catch (e) {
        if ((e as Error).name !== 'AbortError') setError(e instanceof ApiError ? `Preview not updated: ${e.message}` : 'Preview failed')
      } finally { if (!ctrl.signal.aborted) setBusy(false) }
    }, 750)
    return () => { clearTimeout(t); ctrl.abort() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submissionId, key])

  function applyZoom() {
    const doc = frame.current?.contentDocument
    const page = doc?.querySelector<HTMLElement>('.page')
    if (!doc || !page) return
    const fit = (frame.current!.clientWidth - 24) / (page.offsetWidth || 1)
    doc.body.style.zoom = String(zoom === 'fit' ? Math.min(fit, 1) : Number(zoom))
  }
  useEffect(applyZoom) // re-apply when zoom changes

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-1 pb-1 text-xs text-slate-500">
        <span>Live HTML preview — page breaks may differ from the final PDF</span>
        <span className="flex items-center gap-2">
          <span aria-live="polite">{busy ? 'Updating…' : ''}</span>
          <select aria-label="Preview zoom" className="rounded border border-slate-300 px-1" value={zoom} onChange={(e) => setZoom(e.target.value)}>
            <option value="fit">Fit width</option><option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option>
          </select>
        </span>
      </div>
      {error && <p className="text-xs text-red-700">{error}</p>}
      <iframe ref={frame} title="Report preview" sandbox="allow-same-origin" srcDoc={html}
        onLoad={() => { applyZoom(); frame.current?.contentWindow?.scrollTo(0, scroll.current) }}
        className="min-h-[70vh] w-full flex-1 rounded border border-slate-300 bg-slate-200" />
    </div>
  )
}
