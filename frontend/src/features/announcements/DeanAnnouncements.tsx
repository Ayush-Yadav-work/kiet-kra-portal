import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, fmtDateTime } from '../../api/client'
import { ErrorBox, Loading } from '../../components/ui'
import { type Notice, NoticeBadges, NoticeText } from './common'

type Page = { total: number; page: number; page_size: number; results: Notice[]; unread_count: number }
export const UNREAD_EVENT = 'kra:announcements-read'

/** Dean inbox: pinned first, then newest. Loading the list never marks anything read. */
export function DeanInbox() {
  const [page, setPage] = useState(1)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [data, setData] = useState<Page | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    setData(null)
    api<Page>(`/announcements/?page=${page}${unreadOnly ? '&unread=1' : ''}`).then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : 'Failed to load'))
    return () => { live = false }
  }, [page, unreadOnly])
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-[28px] font-bold leading-tight md:text-4xl">Announcements</h1>
          <p className="mt-1 text-muted">Notices from the Vice Chancellor for your department.{data ? ` ${data.unread_count} unread.` : ''}</p></div>
        <label className="flex items-center gap-2 text-[15px]"><input type="checkbox" className="h-5 w-5" checked={unreadOnly}
          onChange={(e) => { setUnreadOnly(e.target.checked); setPage(1) }} />Unread only</label>
      </div>
      <ErrorBox error={error} />
      {!data ? (!error && <Loading />) : data.results.length === 0 ? <p className="rounded-[10px] border border-line bg-white p-5 text-muted">No announcements.</p> : (
        <ul className="grid gap-2">
          {data.results.map((n) => (
            <li key={n.id}>
              <Link to={`/dean/announcements/${n.id}`} className={`block rounded-[10px] border bg-white p-4 hover:border-action ${n.read ? 'border-line' : 'border-action'}`}>
                <span className="flex flex-wrap items-center gap-2"><b className="text-lg text-heading">{n.title}</b><NoticeBadges n={n} /></span>
                <span className="mt-1 block text-sm text-muted">{fmtDateTime(n.content_updated_at || n.published_at)}{n.expires_at ? ` · until ${fmtDateTime(n.expires_at)}` : ''}</span>
                <span className="mt-1 line-clamp-2 block text-[15px]">{n.body}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {data && data.total > data.page_size && (
        <div className="flex items-center justify-between text-sm"><span>Page {data.page} of {pages}</span>
          <span className="flex gap-2"><button className="btn-secondary min-h-9 text-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <button className="btn-secondary min-h-9 text-sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button></span></div>
      )}
    </div>
  )
}

/** Opening a notice marks exactly the displayed content version read; if it changed meanwhile, the new text is shown first. */
export function DeanNotice() {
  const { id } = useParams()
  const [n, setN] = useState<Notice | null>(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    let live = true
    async function open() {
      try {
        let cur = await api<Notice>(`/announcements/${id}/`)
        if (!live) return
        setN(cur)
        for (let i = 0; i < 2 && !cur.read; i++) {
          try {
            await api(`/announcements/${id}/read/`, { method: 'POST', body: { content_version: cur.content_version } })
            window.dispatchEvent(new Event(UNREAD_EVENT))
            break
          } catch (e) {
            if (!(e instanceof ApiError && e.code === 'stale_read')) throw e
            cur = await api<Notice>(`/announcements/${id}/`)  // updated while opening: show the new text, then mark it
            if (!live) return
            setN(cur); setNote('This announcement was updated while you were opening it; the latest version is shown.')
          }
        }
      } catch (e) { if (live) setError(e instanceof ApiError && e.status === 404 ? 'This announcement is not available.' : 'Failed to load') }
    }
    open()
    return () => { live = false }
  }, [id])
  useEffect(() => { if (n) heading.current?.focus() }, [n?.id])  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="grid max-w-3xl gap-3">
      <Link to="/dean/announcements" className="text-sm text-action underline">← All announcements</Link>
      <ErrorBox error={error} />
      {!n ? (!error && <Loading />) : (
        <article className="grid gap-3 rounded-[10px] border border-line bg-white p-5">
          <h1 ref={heading} tabIndex={-1} className="text-2xl font-bold text-heading">{n.title}</h1>
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">{n.pinned && <span className="rounded bg-subtle px-1.5 py-0.5 text-xs font-bold text-heading">Pinned</span>}
            {n.updated ? 'Updated ' : 'Published '}{fmtDateTime(n.content_updated_at || n.published_at)}{n.expires_at ? ` · visible until ${fmtDateTime(n.expires_at)}` : ''}</p>
          {note && <p role="status" className="rounded bg-warn-bg px-3 py-2 text-sm text-warn">{note}</p>}
          <div className="text-[16px] leading-relaxed"><NoticeText text={n.body} /></div>
        </article>
      )}
    </div>
  )
}

/** Compact dashboard notices: pinned first, at most three, with a link to the inbox. */
export function DashboardNotices() {
  const [data, setData] = useState<Page | null>(null)
  useEffect(() => { api<Page>('/announcements/').then(setData).catch(() => {}) }, [])
  if (!data || data.total === 0) return null
  return (
    <section aria-labelledby="notices-h" className="grid gap-2 rounded-[10px] border border-line bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="notices-h" className="text-lg font-bold text-heading">Announcements{data.unread_count ? ` · ${data.unread_count} unread` : ''}</h2>
        <Link to="/dean/announcements" className="text-sm text-action underline">View all</Link>
      </div>
      <ul className="grid gap-1.5">{data.results.slice(0, 3).map((n) => (
        <li key={n.id} className="flex flex-wrap items-center gap-2"><Link to={`/dean/announcements/${n.id}`} className={`underline ${n.read ? '' : 'font-bold text-heading'}`}>{n.title}</Link>
          <NoticeBadges n={n} /></li>))}</ul>
    </section>
  )
}
