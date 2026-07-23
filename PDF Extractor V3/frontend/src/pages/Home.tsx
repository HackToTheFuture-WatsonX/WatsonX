import { useNavigate } from 'react-router-dom'
import { FolderSearch, RefreshCw, Cog, Eye, ClipboardCheck } from 'lucide-react'

const CARDS = [
  { icon: FolderSearch, label: 'Scan Local Folder',    desc: 'Scan Local Folder for PDFs\nand view their status.',         to: '/scan',    color: '#6C63FF' },
  { icon: RefreshCw,    label: 'Sync Box to Local',    desc: 'Download PDFs from Box\ninto the Local Folder.',             to: '/sync',    color: '#0D9488' },
  { icon: Cog,          label: 'Extract Files',         desc: 'Run extraction and upload\noutputs to Box.',                 to: '/extract', color: '#22C55E' },
  { icon: Eye,          label: 'View Extracted Files',  desc: 'Browse extracted Word / Excel\nand JSON files by type.',    to: '/view',    color: '#F59E0B' },
  { icon: ClipboardCheck, label: 'Audit Resource',      desc: 'Master list of extracted reports\nexportable to Excel.',    to: '/audit',   color: '#A78BFA' },
]

export default function Home() {
  const nav = useNavigate()
  return (
    <div className="p-7">
      {/* Hero */}
      <div className="rounded-xl bg-[#1A1040] border border-[#2D1F6E] px-9 py-8 mb-7">
        <div className="inline-flex items-center gap-2 bg-[#2A1860] border border-[#4A3090]
                        rounded-full px-3 py-1 text-[#A78BFA] text-xs font-bold mb-4">
          <span className="w-1.5 h-1.5 rounded-full bg-[#A78BFA]" />
          IBM WatsonX · Powered
        </div>
        <h1 className="text-3xl font-bold text-white leading-tight mb-2">
          Clear Check
        </h1>
        <p className="text-[#7B8DB8] text-sm max-w-xl">
          Sync, scan, extract and analyze background check PDFs — powered by IBM Box
          and AI-grounded report lookup.
        </p>
      </div>

      {/* Section label */}
      <div className="flex items-center gap-3 mb-4">
        <span className="section-label">Quick Access</span>
        <div className="flex-1 h-px bg-border-light dark:bg-border-dark" />
      </div>

      {/* Cards */}
      <div className="flex flex-wrap gap-4">
        {CARDS.map(({ icon: Icon, label, desc, to, color }) => (
          <div
            key={to}
            onClick={() => nav(to)}
            className="card w-52 cursor-pointer group hover:border-accent transition-all duration-150"
            style={{ borderColor: 'transparent' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = color)}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}
          >
            {/* Accent bar */}
            <div className="h-1 rounded-t-xl -mx-px -mt-px" style={{ background: color }} />
            <div className="p-4">
              {/* Icon badge */}
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
                style={{ background: `${color}22`, border: `1px solid ${color}44` }}
              >
                <Icon size={18} style={{ color }} />
              </div>
              <p className="font-semibold text-sm text-gray-900 dark:text-white mb-1">{label}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 whitespace-pre-line leading-relaxed">{desc}</p>
              <p className="text-xs font-bold mt-3" style={{ color }}>Open →</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
