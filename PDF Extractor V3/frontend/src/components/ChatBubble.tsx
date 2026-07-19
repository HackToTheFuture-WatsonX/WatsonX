import { useState, useRef, useEffect } from 'react'
import { Send, Trash2, MessageSquare, X } from 'lucide-react'
import Spinner from './ui/Spinner'
import { useApi } from '../hooks/useApi'
import { useChatStore } from '../store/chat'
import type { ChatMessage, LinksPayload } from '../types'

function renderMarkdown(text: string): JSX.Element[] {
  return text.split('\n').map((line, i) => {
    if (/^\s*---+\s*$/.test(line)) {
      return <hr key={i} className="border-border-light dark:border-border-dark my-2" />
    }
    const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/)
    return (
      <span key={i} className="block">
        {parts.map((p, j) => {
          if (p.startsWith('**') && p.endsWith('**'))
            return <strong key={j}>{p.slice(2, -2)}</strong>
          if (p.startsWith('*') && p.endsWith('*'))
            return <em key={j}>{p.slice(1, -1)}</em>
          return p
        })}
      </span>
    )
  })
}

function LinksCard({ payload }: { payload: LinksPayload }) {
  const { post } = useApi()
  return (
    <div className="mt-2 space-y-2">
      <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 whitespace-pre-line">{payload.header}</p>
      {payload.items.map((item, i) => (
        item.status === 'ok' ? (
          <div key={i} className="card border-l-4 border-l-green p-3">
            <p className="text-xs font-semibold text-gray-900 dark:text-white">{item.fname}</p>
            <p className="text-xs text-gray-500 mt-0.5">Ref: {item.ref}</p>
            <div className="flex gap-2 mt-2">
              {item.word  && <button onClick={() => post('/api/view/open', { path: item.word  })} className="text-accent text-xs underline">Word</button>}
              {item.excel && <button onClick={() => post('/api/view/open', { path: item.excel })} className="text-teal text-xs underline">Excel</button>}
              {item.json  && <button onClick={() => post('/api/view/open', { path: item.json  })} className="text-accent2 text-xs underline">JSON</button>}
            </div>
          </div>
        ) : (
          <div key={i} className="card border-l-4 border-l-red-400 p-3">
            <p className="text-xs text-red-400">{item.fname}: {item.error}</p>
          </div>
        )
      ))}
    </div>
  )
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'

  const LINKS_RE = /\u00a7LINKS\u00a7([\s\S]*?)\u00a7LINKS\u00a7/
  const match    = msg.content.match(LINKS_RE)
  if (match) {
    try {
      const payload: LinksPayload = JSON.parse(match[1])
      return (
        <div className="flex gap-3">
          <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center shrink-0 mt-0.5 text-xs">◇</div>
          <div className="flex-1"><LinksCard payload={payload} /></div>
        </div>
      )
    } catch { /**/ }
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold
                        ${isUser ? 'bg-accent text-white' : msg.role === 'system' ? 'bg-accent2/30 text-accent2' : 'bg-green/20 text-green'}`}>
        {isUser ? 'Y' : '◇'}
      </div>
      <div className={`max-w-[16rem] text-sm leading-relaxed px-4 py-2.5 rounded-xl
                        ${isUser
                          ? 'bg-accent text-white ml-auto'
                          : msg.role === 'system'
                            ? 'bg-accent2/10 text-accent2 italic'
                            : 'bg-card-light dark:bg-card-dark border border-border-light dark:border-border-dark text-gray-800 dark:text-gray-100'
                        }`}
      >
        {isUser ? msg.content : renderMarkdown(msg.content)}
      </div>
    </div>
  )
}

const WELCOME: ChatMessage = {
  role: 'system',
  content: "Hello! I'm Detective Conan, your AI Assistant (V3).\n\nProcess flow:  Scan → Sync → Extract → Chat\n\n• 'look up [name]'  |  'status of [ref]'\n• 'scan'  |  'sync'  |  'extract'\n• 'logs this week'  |  'file status'",
}

export default function ChatBubble() {
  const { enabled, open, setOpen, toggleOpen } = useChatStore()
  const { post, loading } = useApi()
  const [history, setHistory] = useState<ChatMessage[]>([WELCOME])
  const [input,   setInput]   = useState('')
  const [busy,    setBusy]    = useState(false)
  const [model,   setModel]   = useState('—')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, open])

  useEffect(() => {
    fetch('/api/health').then(() => {
      setModel('ICA Agent · Llama 3.1 14b')
    }).catch(() => setModel('Backend offline'))
  }, [])

  async function send() {
    const msg = input.trim()
    if (!msg || busy) return
    setInput(''); setBusy(true)
    const userMsg: ChatMessage = { role: 'user', content: msg }
    setHistory(prev => [...prev, userMsg])
    const r = await post<{ reply: string }>('/api/chat/send', {
      message: msg,
      history: [...history, userMsg].filter(m => m.role !== 'system'),
    })
    setBusy(false)
    if (r) setHistory(prev => [...prev, { role: 'assistant', content: r.reply }])
  }

  // Hidden entirely when the chat bubble is disabled.
  if (!enabled) return null

  return (
    <>
      {/* Floating launcher button */}
      <button
        onClick={toggleOpen}
        className="fixed bottom-5 right-5 z-50 w-14 h-14 rounded-full bg-accent hover:bg-accent-dark
                   text-white shadow-xl flex items-center justify-center transition-all
                   hover:scale-105 active:scale-95"
        title={open ? 'Close assistant' : 'Chat with AI'}
      >
        {open ? <X size={22} /> : <MessageSquare size={22} />}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-5 z-50 w-[24rem] max-w-[calc(100vw-2.5rem)]
                        h-[32rem] max-h-[calc(100vh-8rem)] flex flex-col
                        rounded-2xl overflow-hidden shadow-2xl
                        border border-border-light dark:border-border-dark
                        bg-card-light dark:bg-card-dark">
          {/* Header */}
          <div className="shrink-0 border-b border-border-light dark:border-border-dark
                          bg-card-light dark:bg-card-dark px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="relative w-9 h-9 bg-accent rounded-full flex items-center justify-center text-white font-bold">
                ◇
                <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green rounded-full border-2 border-white dark:border-card-dark" />
              </div>
              <div>
                <p className="font-bold text-sm text-gray-900 dark:text-white leading-tight">Detective Conan</p>
                <p className="text-[10px] text-gray-500 dark:text-gray-400">{model}</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setHistory([WELCOME])}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200
                           hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                title="Clear conversation"
              >
                <Trash2 size={15} />
              </button>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200
                           hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                title="Close"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 bg-[#F8F9FF] dark:bg-bg-dark">
            {history.map((m, i) => <MessageBubble key={i} msg={m} />)}
            {busy && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-green/20 flex items-center justify-center text-xs text-green shrink-0">◇</div>
                <div className="card px-4 py-3 flex items-center gap-2 text-sm text-gray-400">
                  <Spinner size={14} /> Thinking…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input bar */}
          <div className="shrink-0 bg-card-light dark:bg-card-dark border-t border-border-light dark:border-border-dark p-3">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), send())}
                placeholder="Ask about a report, 'scan', 'look up [name]'…"
                className="flex-1 bg-[#F0F2F8] dark:bg-white/5 border border-border-light dark:border-border-dark
                           rounded-xl px-3.5 py-2 text-sm outline-none
                           focus:border-accent dark:focus:border-accent transition-colors
                           text-gray-900 dark:text-white placeholder-gray-400"
              />
              <button
                onClick={send}
                disabled={busy || loading || !input.trim()}
                className="bg-accent hover:bg-accent-dark disabled:opacity-40 text-white
                           rounded-xl px-3.5 py-2 transition-colors flex items-center gap-1.5"
              >
                <Send size={15} />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
