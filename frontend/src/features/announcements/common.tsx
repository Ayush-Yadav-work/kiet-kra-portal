import { Fragment } from 'react'

// Announcements are plain text (D-077): React escapes everything; only http(s) URLs become links.
export interface Notice { id: string; title: string; body: string; pinned: boolean; expires_at: string | null; published_at: string | null
  content_updated_at: string | null; content_version: number; updated: boolean; read?: boolean }

const URL_RE = /(https?:\/\/[^\s<>"']+)/g

export function NoticeText({ text }: { text: string }) {
  return (
    <p className="whitespace-pre-wrap break-words">{text.split(URL_RE).map((part, i) => i % 2
      ? <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="text-action underline">{part}<span className="sr-only"> (opens in a new tab)</span></a>
      : <Fragment key={i}>{part}</Fragment>)}</p>
  )
}

export function NoticeBadges({ n }: { n: Notice }) {
  return (
    <>
      {n.pinned && <span className="rounded bg-subtle px-1.5 py-0.5 text-xs font-bold text-heading">Pinned</span>}
      {n.read === false && <span className="rounded bg-accent-btn px-1.5 py-0.5 text-xs font-bold text-white">Unread</span>}
      {n.updated && <span className="rounded border border-control px-1.5 py-0.5 text-xs font-semibold text-heading">Updated</span>}
    </>
  )
}
