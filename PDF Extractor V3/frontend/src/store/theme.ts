import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ThemeStore {
  isDark:  boolean
  toggle:  () => void
  setDark: (v: boolean) => void
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      isDark: true,
      toggle:  () => set((s) => {
        const next = !s.isDark
        document.documentElement.classList.toggle('dark', next)
        return { isDark: next }
      }),
      setDark: (v) => {
        document.documentElement.classList.toggle('dark', v)
        set({ isDark: v })
      },
    }),
    { name: 'v3-theme' },
  ),
)

// Initialise class on load
const stored = JSON.parse(localStorage.getItem('v3-theme') || '{}')
const isDark  = stored?.state?.isDark !== false
document.documentElement.classList.toggle('dark', isDark)
