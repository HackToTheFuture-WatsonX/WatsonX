import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Home, FolderSearch, RefreshCw, Cog, Eye,
  BarChart2, MessageSquare, SlidersHorizontal,
  Sun, Moon, PanelLeftClose, PanelLeftOpen,
} from 'lucide-react'
import { useThemeStore } from '../store/theme'
import { useChatStore } from '../store/chat'
import { useToastStore } from '../store/toast'

const NAV = [
  { to: '/',         icon: Home,         label: 'Home' },
  { to: '/scan',     icon: FolderSearch, label: 'Scan Local Folder' },
  { to: '/sync',     icon: RefreshCw,    label: 'Sync Box to Local' },
  { to: '/extract',  icon: Cog,          label: 'Extract Files' },
  { to: '/view',     icon: Eye,          label: 'View Extracted Files' },
  { to: '/insights', icon: BarChart2,    label: 'Insights' },
]

const SYSTEM = [
  { to: '/settings', icon: SlidersHorizontal, label: 'Settings' },
]

function NavItem({
  to, icon: Icon, label, collapsed,
}: { to: string; icon: any; label: string; collapsed: boolean }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 py-2.5 mx-2 rounded-lg text-sm font-medium transition-all
         ${collapsed ? 'justify-center px-0' : 'px-4'}
         ${isActive
           ? 'bg-accent text-white font-semibold'
           : 'text-[#8B9DC0] hover:bg-sidebar-hover hover:text-white'
         }`
      }
    >
      <Icon size={16} className="shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
      {collapsed && <Tooltip text={label} />}
    </NavLink>
  )
}

/** Hover tooltip shown when the sidebar is collapsed. */
function Tooltip({ text }: { text: string }) {
  return (
    <span
      className="pointer-events-none absolute left-full ml-2 z-50 whitespace-nowrap
                 rounded-md bg-[#0B1220] text-white text-xs font-medium px-2.5 py-1.5
                 shadow-lg border border-[#1E2D4A]
                 opacity-0 -translate-x-1 transition-all duration-150
                 group-hover:opacity-100 group-hover:translate-x-0"
    >
      {text}
    </span>
  )
}

function SectionLabel({ text, collapsed }: { text: string; collapsed: boolean }) {
  if (collapsed) return <div className="h-px bg-[#1E2D4A] mx-3 my-2" />
  return (
    <p className="text-[10px] font-bold tracking-widest text-[#3A4D6A] px-6 mb-2 uppercase">{text}</p>
  )
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { isDark, toggle } = useThemeStore()
  const { enabled, icaConfigured, setEnabled } = useChatStore()
  const showToast = useToastStore((s) => s.show)

  async function handleChatToggle() {
    const next = !enabled
    const ok = await setEnabled(next)
    if (!ok) {
      showToast('Please configure the ICA chat assistant in Settings first.', 'warning')
    }
  }

  return (
    <aside
      className={`${collapsed ? 'w-16' : 'w-60'} min-h-screen bg-sidebar flex flex-col shrink-0
                  transition-[width] duration-200 ease-in-out`}
    >
      {/* Brand + collapse toggle */}
      <div className={`flex items-center py-6 ${collapsed ? 'justify-center px-0' : 'gap-3 px-5'}`}>
        <div className="w-9 h-9 bg-accent rounded-lg flex items-center justify-center shrink-0">
          <span className="text-white font-bold text-base">✓</span>
        </div>
        {!collapsed && (
          <div className="flex-1 min-w-0">
            <div className="text-white font-bold text-sm leading-tight">BG Check</div>
            <div className="text-accent2 text-xs">Automation  V3</div>
          </div>
        )}
      </div>

      {/* Collapse button */}
      <button
        onClick={() => setCollapsed(c => !c)}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className={`group relative flex items-center gap-3 py-2 mx-2 mb-1 rounded-lg text-sm
                    text-[#8B9DC0] hover:bg-sidebar-hover hover:text-white transition-all
                    ${collapsed ? 'justify-center px-0' : 'px-4'}`}
      >
        {collapsed ? <PanelLeftOpen size={16} className="shrink-0" /> : <PanelLeftClose size={16} className="shrink-0" />}
        {!collapsed && <span>Collapse</span>}
        {collapsed && <Tooltip text="Expand sidebar" />}
      </button>

      <div className="h-px bg-[#1E2D4A] mx-4 mb-3" />

      {/* Navigation */}
      <SectionLabel text="Navigation" collapsed={collapsed} />
      <nav className="flex flex-col gap-0.5">
        {NAV.map((n) => <NavItem key={n.to} {...n} collapsed={collapsed} />)}
      </nav>

      <div className="h-px bg-[#1E2D4A] mx-4 my-3" />

      {/* Assistant — chat enable switch */}
      <SectionLabel text="Assistant" collapsed={collapsed} />
      <button
        onClick={handleChatToggle}
        title={collapsed ? 'AI Chat Assistant' : undefined}
        className={`group relative flex items-center py-2.5 mx-2 rounded-lg text-sm font-medium transition-all
                    text-[#8B9DC0] hover:bg-sidebar-hover hover:text-white
                    ${collapsed ? 'justify-center px-0' : 'gap-3 px-4'}`}
      >
        <MessageSquare size={16} className="shrink-0" />
        {!collapsed && <span className="flex-1 text-left truncate">Chat with AI</span>}
        {!collapsed && (
          <span
            className={`relative w-9 h-5 rounded-full transition-colors shrink-0
                        ${enabled ? 'bg-accent' : 'bg-[#2A3B5A]'}`}
          >
            <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform
                              ${enabled ? 'translate-x-4' : ''}`} />
          </span>
        )}
        {collapsed && (
          <span className={`absolute top-1 right-1 w-2 h-2 rounded-full ${enabled ? 'bg-accent' : 'bg-[#2A3B5A]'}`} />
        )}
        {collapsed && <Tooltip text={enabled ? 'Chat: On' : 'Chat: Off'} />}
      </button>
      {!collapsed && !icaConfigured && (
        <p className="text-[10px] text-[#3A4D6A] px-6 mt-1 leading-snug">
          Configure ICA in Settings to enable.
        </p>
      )}

      <div className="h-px bg-[#1E2D4A] mx-4 my-3" />

      {/* System */}
      <SectionLabel text="System" collapsed={collapsed} />
      <nav className="flex flex-col gap-0.5">
        {SYSTEM.map((n) => <NavItem key={n.to} {...n} collapsed={collapsed} />)}
      </nav>

      {/* Theme toggle */}
      <button
        onClick={toggle}
        title={collapsed ? (isDark ? 'Light mode' : 'Dark mode') : undefined}
        className={`group relative flex items-center py-2.5 mx-2 mt-1 rounded-lg text-sm font-medium transition-all
                    text-[#8B9DC0] hover:bg-sidebar-hover hover:text-white
                    ${collapsed ? 'justify-center px-0' : 'gap-3 px-4'}`}
      >
        {isDark ? <Sun size={16} className="shrink-0" /> : <Moon size={16} className="shrink-0" />}
        {!collapsed && <span className="flex-1 text-left">{isDark ? 'Light Mode' : 'Dark Mode'}</span>}
        {collapsed && <Tooltip text={isDark ? 'Light mode' : 'Dark mode'} />}
      </button>

      {/* Version badge */}
      <div className={`mt-auto mb-3 ${collapsed ? 'mx-2' : 'mx-3'}`}>
        {collapsed ? (
          <div className="bg-[#060A14] border border-[#1A2540] rounded-lg py-2 text-center">
            <div className="text-accent2 text-[10px] font-bold">v3</div>
          </div>
        ) : (
          <div className="bg-[#060A14] border border-[#1A2540] rounded-lg px-4 py-3 text-center">
            <div className="text-accent2 text-xs font-bold">v3.0.0  ·  stable</div>
            <div className="text-[#2A4060] text-[10px] mt-0.5">PDF Extractor V3</div>
          </div>
        )}
      </div>
    </aside>
  )
}
