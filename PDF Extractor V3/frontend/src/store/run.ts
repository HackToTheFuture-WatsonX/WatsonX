import { create } from 'zustand'
import { io, Socket } from 'socket.io-client'
import { useToastStore } from './toast'

/**
 * run.ts — shared run-state for Sync / Scan / Extract.
 *
 * Why a global store instead of per-page useState?
 * The Sync/Scan/Extract pages used to keep `running`, `logs`, `results`, etc.
 * in local component state. Navigating away unmounted the component and reset
 * that state, so a long-running job appeared "finished" (button clickable
 * again) and its live output was lost. This store lives outside the React tree
 * so run-state survives navigation, and it subscribes to Socket.IO events ONCE
 * (via bindSocket, called from App) so progress keeps accumulating even when no
 * page is mounted. Each page just reads/writes this store and rehydrates from
 * the backend /status endpoints on mount.
 */

function apiBase(): string {
  const port = (window as any).__V3_API_PORT__ ?? 8765
  return `http://127.0.0.1:${port}`
}

async function apiPost(path: string): Promise<any> {
  try {
    const res = await fetch(`${apiBase()}${path}`, { method: 'POST' })
    return await res.json()
  } catch {
    return null
  }
}

async function apiGet(path: string): Promise<any> {
  try {
    const res = await fetch(`${apiBase()}${path}`)
    return await res.json()
  } catch {
    return null
  }
}

export interface ExtractResult {
  status: 'ok' | 'error'
  fname: string
  ref?: string
  word?: string
  excel?: string
  json?: string
  upload?: string
  error?: string
}

interface SyncSummary { downloaded: number; skipped: number; errors: string[] }
interface ExtractSummary { completed: number; failed: number; total: number }
interface ScanSummary {
  found: number; total: number; pending: number; completed: number;
  error?: string; cancelled?: boolean
}

interface RunStore {
  // ── Sync ──
  syncRunning: boolean
  syncLogs: string[]
  syncSummary: SyncSummary | null
  startSync: () => Promise<void>
  cancelSync: () => Promise<void>

  // ── Scan ──
  scanRunning: boolean
  scanFound: number
  scanSummary: ScanSummary | null
  startScan: () => Promise<void>
  cancelScan: () => Promise<void>

  // ── Extract ──
  extractRunning: boolean
  extractProgress: number
  extractResults: ExtractResult[]
  extractSummary: ExtractSummary | null
  startExtract: () => Promise<void>
  cancelExtract: () => Promise<void>

  /** Rehydrate running flags from the backend (called on page mount). */
  hydrate: () => Promise<void>
  /** Subscribe to socket events once. Called from App on startup. */
  bindSocket: () => void
}

let _socket: Socket | null = null

export const useRunStore = create<RunStore>()((set, get) => ({
  // ── Sync ──
  syncRunning: false,
  syncLogs: [],
  syncSummary: null,
  startSync: async () => {
    if (get().syncRunning) return
    set({ syncRunning: true, syncLogs: [], syncSummary: null })
    const r = await apiPost('/api/sync/run')
    if (r?.status === 'already_running') set({ syncRunning: true })
  },
  cancelSync: async () => { await apiPost('/api/sync/cancel') },

  // ── Scan ──
  scanRunning: false,
  scanFound: 0,
  scanSummary: null,
  startScan: async () => {
    if (get().scanRunning) return
    set({ scanRunning: true, scanFound: 0, scanSummary: null })
    const r = await apiPost('/api/scan/run')
    if (r?.status === 'already_running') set({ scanRunning: true })
  },
  cancelScan: async () => { await apiPost('/api/scan/cancel') },

  // ── Extract ──
  extractRunning: false,
  extractProgress: 0,
  extractResults: [],
  extractSummary: null,
  startExtract: async () => {
    if (get().extractRunning) return
    set({ extractRunning: true, extractProgress: 0, extractResults: [], extractSummary: null })
    const r = await apiPost('/api/extract/run')
    if (r?.status === 'already_running') set({ extractRunning: true })
  },
  cancelExtract: async () => { await apiPost('/api/extract/cancel') },

  hydrate: async () => {
    const [syncS, scanS, extractS] = await Promise.all([
      apiGet('/api/sync/status'),
      apiGet('/api/scan/status'),
      apiGet('/api/extract/status'),
    ])
    set({
      syncRunning:    !!syncS?.running,
      scanRunning:    !!scanS?.running,
      extractRunning: !!extractS?.running,
    })
  },

  bindSocket: () => {
    if (_socket) return
    const port = (window as any).__V3_API_PORT__ ?? 8765
    _socket = io(`http://127.0.0.1:${port}`, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 10,
    })

    // ── Sync events ──
    _socket.on('sync:log', (d: { message: string }) => {
      set((s) => ({ syncLogs: [...s.syncLogs, d.message] }))
    })
    _socket.on('sync:done', (d: any) => {
      set({ syncRunning: false })
      if (d?.cancelled) return
      if (d?.error) {
        set((s) => ({ syncLogs: [...s.syncLogs, `⚠ ${d.error}`] }))
        useToastStore.getState().show(`Sync error: ${d.error}`, 'error', 0)
      } else {
        set({ syncSummary: d })
      }
    })

    // ── Scan events ──
    _socket.on('scan:progress', (d: { found: number }) => {
      set({ scanFound: d.found })
    })
    _socket.on('scan:done', (d: ScanSummary) => {
      set({ scanRunning: false, scanSummary: d })
      if (d?.error) useToastStore.getState().show(`Scan error: ${d.error}`, 'error', 0)
    })

    // ── Extract events ──
    _socket.on('extract:progress', (d: { percent: number }) => {
      set({ extractProgress: d.percent })
    })
    _socket.on('extract:result', (d: ExtractResult) => {
      set((s) => ({ extractResults: [...s.extractResults, d] }))
    })
    _socket.on('extract:done', (d: ExtractSummary & { cancelled?: boolean }) => {
      set({ extractRunning: false, extractSummary: d })
    })
  },
}))
