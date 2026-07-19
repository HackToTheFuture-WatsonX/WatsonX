import { create } from 'zustand'

interface ChatStore {
  /** Whether the floating chat bubble is enabled (persisted to backend config). */
  enabled: boolean
  /** Whether the chat panel is currently expanded/open. */
  open: boolean
  /** Whether ICA is configured on the backend (drives enable gating). */
  icaConfigured: boolean
  /** True once we've loaded state from the backend at least once. */
  hydrated: boolean

  setOpen: (v: boolean) => void
  toggleOpen: () => void
  /** Attempt to toggle enabled. Persists to backend. Returns false if blocked (ICA not configured). */
  setEnabled: (v: boolean) => Promise<boolean>
  /** Load enabled + icaConfigured from the backend (settings + status). */
  hydrate: () => Promise<void>
}

async function persistEnabled(enabled: boolean): Promise<void> {
  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: { settings: { chat_enabled: enabled } } }),
    })
  } catch {
    /* best-effort; keep local state */
  }
}

export const useChatStore = create<ChatStore>()((set, get) => ({
  enabled: false,
  open: false,
  icaConfigured: false,
  hydrated: false,

  setOpen: (v) => set({ open: v }),
  toggleOpen: () => set((s) => ({ open: !s.open })),

  setEnabled: async (v) => {
    // Turning ON requires ICA to be configured.
    if (v && !get().icaConfigured) {
      return false
    }
    set({ enabled: v, open: v ? get().open : false })
    await persistEnabled(v)
    return true
  },

  hydrate: async () => {
    try {
      const [cfgRes, statusRes] = await Promise.all([
        fetch('/api/settings').then((r) => r.json()).catch(() => null),
        fetch('/api/settings/status').then((r) => r.json()).catch(() => null),
      ])

      const icaConfigured: boolean = !!statusRes?.ica?.configured
      const storedEnabled: boolean | undefined = cfgRes?.config?.settings?.chat_enabled

      // Default: disabled unless ICA is configured. If a stored value exists, honour it,
      // but never leave it enabled when ICA is no longer configured.
      let enabled: boolean
      if (typeof storedEnabled === 'boolean') {
        enabled = storedEnabled && icaConfigured
      } else {
        enabled = icaConfigured
      }

      set({ icaConfigured, enabled, hydrated: true })
    } catch {
      set({ hydrated: true })
    }
  },
}))
