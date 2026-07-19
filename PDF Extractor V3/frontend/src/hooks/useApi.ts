import { useState, useCallback } from 'react'

function getBase(): string {
  const port = (window as any).__V3_API_PORT__ ?? 8765
  return `http://127.0.0.1:${port}`
}

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

  return { get, post, loading, error }
}
