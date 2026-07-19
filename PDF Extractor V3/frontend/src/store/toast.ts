import { create } from 'zustand'

export type ToastKind = 'info' | 'success' | 'warning' | 'error'

export interface ToastItem {
  id: number
  message: string
  kind: ToastKind
}

interface ToastStore {
  toasts: ToastItem[]
  show: (message: string, kind?: ToastKind, durationMs?: number) => void
  dismiss: (id: number) => void
}

let _seq = 1

export const useToastStore = create<ToastStore>()((set, get) => ({
  toasts: [],
  show: (message, kind = 'info', durationMs = 4000) => {
    const id = _seq++
    set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }))
    if (durationMs > 0) {
      setTimeout(() => get().dismiss(id), durationMs)
    }
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
