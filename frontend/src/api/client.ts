// Same-origin JSON client. Session cookie is HttpOnly; CSRF token is read from the csrftoken cookie.
export class ApiError extends Error {
  status: number
  code: string
  fieldErrors: Record<string, string[]>
  body: Record<string, unknown>
  constructor(status: number, body: Record<string, unknown>) {
    super(String(body.message || `Request failed (${status})`))
    this.status = status
    this.code = String(body.code || 'error')
    this.fieldErrors = (body.field_errors as Record<string, string[]>) || {}
    this.body = body
  }
}

function csrfToken() {
  return document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const method = opts.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (opts.body instanceof FormData) body = opts.body
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  if (method !== 'GET') headers['X-CSRFToken'] = csrfToken()
  let res: Response
  try {
    res = await fetch(`/api/v1${path}`, { method, headers, body, credentials: 'same-origin', signal: opts.signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, { code: 'network', message: 'Cannot reach the server. Check your connection.' })
  }
  const data = res.headers.get('content-type')?.includes('json') ? await res.json() : {}
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('kra:unauthenticated'))
    throw new ApiError(res.status, data)
  }
  return data as T
}

export const ensureCsrf = () => api('/auth/csrf/')

export function fmtDateTime(iso?: string | null) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' }) + ' IST'
}
export function fmtBytes(n?: number | null) {
  if (n == null) return ''
  return n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`
}
