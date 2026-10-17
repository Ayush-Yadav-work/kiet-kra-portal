// Minimal inline icons (no icon library installed). Decorative: always aria-hidden; the surrounding control carries the text/name.
const PATHS = {
  person: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" /></>,
  people: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c0-3.6 2.9-6.2 6.5-6.2s6.5 2.6 6.5 6.2" /><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14.2c1.9.9 3 2.9 3 5.8" /></>,
  lock: <><rect x="5" y="10.5" width="14" height="10" rx="2" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" /></>,
  eye: <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  eyeOff: <><path d="M3 3l18 18M10.6 6.1A9.8 9.8 0 0 1 12 6c6.4 0 10 6 10 6a17 17 0 0 1-3.2 3.9M6.2 6.6C3.6 8.3 2 12 2 12s3.6 7 10 7a9.6 9.6 0 0 0 4.2-.9" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></>,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  home: <path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  list: <path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01" />,
  doc: <><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></>,
  circle: <circle cx="12" cy="12" r="8" />,
  pencil: <path d="M4 20h4l11-11-4-4L4 16z" />,
  send: <><path d="M21 3L3 10l7 3 3 7z" /><path d="M10 13l11-10" /></>,
  undo: <><path d="M9 14L4 9l5-5" /><path d="M4 9h11a5 5 0 0 1 0 10h-3" /></>,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  calendar: <><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" /></>,
  download: <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />,
}
export type IconName = keyof typeof PATHS

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" className="shrink-0">{PATHS[name]}</svg>
  )
}
