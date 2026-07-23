import { useState, useCallback } from 'react'

function getBase(): string {
  const port = (window as any).__V3_API_PORT__ ?? 8765
  return `http://127.0.0.1:${port}`
}

// Exposed so Diagnostics UIs can display the resolved API base without
// having to reach into window internals themselves.
export function apiBase(): string { return getBase() }

export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  const get = useCallback(async <T>(path: string): Promise<T | null> => {
    setLoading(true); setError(null)
    try {
      const res  = await fetch(`${getBase()}${path}`)
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      return await res.json() as T
    } catch (e: any) {
      setError(e.message ?? 'Request failed')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const post = useCallback(async <T>(path: string, body?: object): Promise<T | null> => {
    setLoading(true); setError(null)
    try {
      const res = await fetch(`${getBase()}${path}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    body ? JSON.stringify(body) : undefined,
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      return await res.json() as T
    } catch (e: any) {
      setError(e.message ?? 'Request failed')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  // Upload one or more files as multipart/form-data. Do NOT set Content-Type
  // manually — the browser sets it (with the boundary) when body is FormData.
  //
  // Returns a rich outcome object so callers can render the truth of what just
  // happened (URL, HTTP status, raw body) on-screen — critical in packaged
  // Electron builds where DevTools is unreachable.
  const upload = useCallback(async <T>(
    path: string,
    files: FileList | File[],
    fieldName = 'files',
  ): Promise<{
    data: T | null
    error: string | null
    url: string
    status: number | 'network-error'
    body: string
  }> => {
    setLoading(true); setError(null)
    const url = `${getBase()}${path}`
    try {
      const form = new FormData()
      const list = Array.from(files)
      for (const f of list) form.append(fieldName, f, f.name)
      console.log(`[upload] POST ${url} — ${list.length} file(s)`, list.map(f => `${f.name} (${f.size}B)`))
      const res = await fetch(url, { method: 'POST', body: form })
      // Read the body regardless of status so we can surface server errors.
      const rawBody = await res.text()
      const bodyPreview = rawBody.slice(0, 500)
      if (!res.ok) {
        const detail = rawBody ? ` — ${bodyPreview}` : ''
        const msg = `HTTP ${res.status} ${res.statusText}${detail}`
        console.error(`[upload] failed:`, msg)
        setError(msg)
        return { data: null, error: msg, url, status: res.status, body: bodyPreview }
      }
      let data: T
      try { data = JSON.parse(rawBody) as T }
      catch (e: any) {
        const msg = `Bad JSON from server: ${e.message ?? e}`
        console.error(`[upload] ${msg}`, rawBody)
        setError(msg)
        return { data: null, error: msg, url, status: res.status, body: bodyPreview }
      }
      return { data, error: null, url, status: res.status, body: bodyPreview }
    } catch (e: any) {
      const msg = e?.message ?? 'Upload failed (network error)'
      console.error(`[upload] exception:`, e)
      setError(msg)
      return { data: null, error: msg, url, status: 'network-error', body: msg }
    } finally {
      setLoading(false)
    }
  }, [])

  return { get, post, upload, loading, error }
}
