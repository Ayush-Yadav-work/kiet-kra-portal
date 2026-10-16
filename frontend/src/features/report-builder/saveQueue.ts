import { api, ApiError } from '../../api/client'

export type SaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'failed' | 'conflict'
export type Changes = Partial<{ payload: unknown; achievement_text: string; remarks: string; is_nil: boolean; nil_reason: string }>

/**
 * One client-side queue for report, achievement and remarks saves (plan 3.1, C3):
 * at most one request in flight, always sending the latest known edit_version.
 * Pending changes are merged; on failure or 409 they are retained, never discarded.
 */
export class SaveQueue {
  private pending: Changes | null = null
  private running: Promise<void> | null = null
  private timer: ReturnType<typeof setTimeout> | null = null
  state: SaveState = 'idle'
  error = ''
  fieldErrors: Record<string, string[]> = {}
  savedAt: string | null = null
  private listeners = new Set<() => void>()
  private submissionId: string
  version: number

  constructor(submissionId: string, version: number) {
    this.submissionId = submissionId
    this.version = version
  }

  subscribe(fn: () => void) { this.listeners.add(fn); return () => { this.listeners.delete(fn) } }
  private emit() { this.listeners.forEach((f) => f()) }
  private set(state: SaveState) { this.state = state; this.emit() }

  get hasPending() { return this.pending !== null || this.running !== null }

  /** Queue changes and autosave after `delay` ms of quiet. */
  enqueue(changes: Changes, delay = 1500) {
    this.pending = { ...(this.pending ?? {}), ...changes }
    if (this.state !== 'conflict') this.set('dirty')
    if (this.timer) clearTimeout(this.timer)
    if (this.state !== 'conflict') this.timer = setTimeout(() => { void this.run() }, delay)
  }

  private async run(): Promise<void> {
    if (this.running) return this.running
    this.running = (async () => {
      while (this.pending && this.state !== 'conflict') {
        const batch = this.pending
        this.pending = null
        this.set('saving')
        try {
          const r = await api<{ edit_version: number; saved_at: string }>(`/submissions/${this.submissionId}/draft/`, {
            method: 'PATCH', body: { ...batch, edit_version: this.version },
          })
          this.version = r.edit_version
          this.savedAt = r.saved_at
          this.fieldErrors = {}
          this.error = ''
          if (!this.pending) this.set('saved')
        } catch (e) {
          this.pending = { ...batch, ...(this.pending ?? {}) } // keep typed values
          const err = e instanceof ApiError ? e : null
          this.error = err?.message ?? 'Save failed.'
          this.fieldErrors = err?.fieldErrors ?? {}
          this.set(err?.status === 409 && err.code === 'version_conflict' ? 'conflict' : 'failed')
          break
        }
      }
    })()
    try { await this.running } finally { this.running = null }
  }

  /** Save everything now; resolves true when nothing is left unsaved (used before tab switches/leaving). */
  async flush(): Promise<boolean> {
    if (this.timer) { clearTimeout(this.timer); this.timer = null }
    if (this.running) await this.running
    if (this.pending && this.state !== 'conflict') await this.run()
    return this.pending === null && this.state !== 'conflict' && this.state !== 'failed'
  }

  /** After a 409 the user chose to keep their values: adopt the server version and resend. */
  async resolveKeepMine(serverVersion: number) {
    this.version = serverVersion
    this.set('dirty')
    return this.flush()
  }

  /** After a 409 the user chose the saved copy: drop pending local changes explicitly. */
  resolveTakeServer(serverVersion: number) {
    this.version = serverVersion
    this.pending = null
    this.set('saved')
  }

  dispose() { if (this.timer) clearTimeout(this.timer); this.listeners.clear() }
}
