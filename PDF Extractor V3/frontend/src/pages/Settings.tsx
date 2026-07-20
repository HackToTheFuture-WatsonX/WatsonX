import { Ban, Box as BoxIcon, CheckCircle2, KeyRound, Loader2, LogIn, MessageSquare, Save, Trash2, Upload, XCircle } from 'lucide-react'

import type { Dispatch, SetStateAction } from 'react'
import { useEffect, useRef, useState } from 'react'

import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Spinner from '../components/ui/Spinner'
import { useApi } from '../hooks/useApi'
import { useChatStore } from '../store/chat'
import type { AppConfig, SettingsStatus } from '../types'



type TestState = { ok: boolean; msg: string } | null

// One streamed progress line from a connection test.
type StepState = 'run' | 'ok' | 'error' | 'done'
type Step = { step: string; state: StepState; detail?: string; error?: string }

// Live progress for a streaming test: the accumulated step log plus whether the
// stream is still running and how it finished.
type StreamState = {
  steps: Step[]
  running: boolean
  outcome: 'ok' | 'error' | null
} | null

function apiBase(): string {
  const port = (window as any).__V3_API_PORT__ ?? 8765
  return `http://127.0.0.1:${port}`
}

// The "identity" of a running step line, used to coalesce repeated heartbeat
// updates (e.g. "Waiting for ICA response… (60s / up to 300s)") into a single
// line that updates in place. We key off the text before the first "…" or "("
// so successive polls collapse onto one row instead of flooding the log.
function stepKey(message: string): string {
  const cut = message.search(/[…(]/)
  return (cut === -1 ? message : message.slice(0, cut)).trim()
}

// Append a step to the log, coalescing consecutive running heartbeats that
// share the same prefix so the panel updates the existing line in place.
function appendStep(steps: Step[], data: Step): Step[] {
  const last = steps[steps.length - 1]
  if (
    last &&
    last.state === 'run' &&
    data.state === 'run' &&
    stepKey(last.step) === stepKey(data.step)
  ) {
    // Replace the previous heartbeat with the newer one.
    return [...steps.slice(0, -1), data]
  }
  return [...steps, data]
}


export default function Settings() {
  const { get, post, loading } = useApi()
  const [cfg, setCfg] = useState<AppConfig | null>(null)
  const [status, setStatus] = useState<SettingsStatus | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved]   = useState(false)
  const [jwtText, setJwtText] = useState('')
  const [jwtMsg, setJwtMsg]   = useState<TestState>(null)
  const [boxTest, setBoxTest] = useState<StreamState>(null)
  const [icaTest, setIcaTest] = useState<StreamState>(null)
  const [icaLoginMsg, setIcaLoginMsg] = useState<TestState>(null)
  const [busy, setBusy]       = useState<string | null>(null)

  // Keep a handle on the active SSE connection so we can close it on unmount or
  // when a new test starts.
  const esRef = useRef<EventSource | null>(null)
  // Remember which test owns the active connection so Cancel can reset the
  // right StepLog panel.
  const activeTestRef = useRef<{ key: string; setState: Dispatch<SetStateAction<StreamState>> } | null>(null)


  const canAutoLogin = typeof window !== 'undefined' && !!window.electronAPI?.icaLogin


  async function load() {
    const res = await get<{ config: AppConfig }>('/api/settings')
    if (res) setCfg(res.config)
    const st = await get<SettingsStatus>('/api/settings/status')
    if (st) setStatus(st)
    // Re-hydrate the global chat store so the sidebar's "Chat with AI" gate
    // (icaConfigured) reflects the freshly-saved config WITHOUT a full app
    // reload. Called on every load() — which runs after save / sign-in /
    // clear / JWT upload — so configuring ICA immediately enables chat.
    void useChatStore.getState().hydrate()
  }


  useEffect(() => { load() }, [])

  // Close any live SSE connection when the page unmounts.
  useEffect(() => () => { esRef.current?.close(); esRef.current = null }, [])

  function patch<K extends keyof AppConfig>(section: K, key: string, value: any) {
    setCfg(prev => prev ? { ...prev, [section]: { ...(prev[section] as any), [key]: value } } : prev)
    setSaved(false)
  }
  function patchTop(key: keyof AppConfig, value: any) {
    setCfg(prev => prev ? { ...prev, [key]: value } : prev)
    setSaved(false)
  }

  async function handleSave() {
    if (!cfg) return
    setSaving(true); setSaved(false)
    const res = await post<{ status: string; config: AppConfig }>('/api/settings', { config: cfg })
    setSaving(false)
    if (res?.config) { setCfg(res.config); setSaved(true); load() }
  }

  // Persist a config object immediately (used by the Clear buttons so a cleared
  // section is wiped from config.json right away, not just in the form).
  async function persistCfg(next: AppConfig) {
    setCfg(next); setSaved(false)
    const res = await post<{ status: string; config: AppConfig }>('/api/settings', { config: next })
    if (res?.config) { setCfg(res.config); load() }
  }

  // ── Per-section clear helpers ───────────────────────────────────────────────
  // Each blanks its section's fields and saves. Sending "" (not the mask marker)
  // tells the backend to actually clear the stored value. The Box JWT file lives
  // in a SEPARATE file (box_jwt_config.json), so clearing config fields never
  // touches it.
  function clearBox() {
    if (!cfg) return
    setBusy('clear-box')
    persistCfg({ ...cfg, box: { ...cfg.box, folder_id: '', archive_folder_id: '', output_folder_id: '' } })
      .finally(() => setBusy(null))
  }
  function clearIca() {
    if (!cfg) return
    setBusy('clear-ica')
    setIcaLoginMsg(null); setIcaTest(null)
    persistCfg({
      ...cfg,
      ica: { ...cfg.ica, full_cookie: '', team_id: '', team_name: '', assistant_id: '', chat_id: '', base_url: '' },
    }).finally(() => setBusy(null))
  }
  function clearPdfPassword() {
    if (!cfg) return
    setBusy('clear-pdf')
    persistCfg({ ...cfg, pdf_password: '' }).finally(() => setBusy(null))
  }
  function clearOptions() {
    if (!cfg) return
    setBusy('clear-options')
    persistCfg({
      ...cfg,
      settings: {
        ...cfg.settings,
        search_subfolders: false,
        overwrite_existing_exports: false,
        log_activity: false,
        file_extension: '',
      },
      sync: { ...cfg.sync, auto_sync_enabled: false, auto_sync_interval_minutes: 0 },
    }).finally(() => setBusy(null))
  }

  // Clear ALL config fields (Box, ICA, PDF password, Options) in one shot. This
  // clears config FIELDS ONLY — the Box JWT file is left in place on purpose.
  function clearAll() {
    if (!cfg) return
    if (typeof window !== 'undefined' && !window.confirm(
      'Clear ALL settings fields (Box, ICA, PDF password, Options)?\n\nThe Box JWT file is kept in place. This cannot be undone.'
    )) return
    setBusy('clear-all')
    setIcaLoginMsg(null); setIcaTest(null); setBoxTest(null); setJwtMsg(null)
    persistCfg({
      ...cfg,
      pdf_password: '',
      box: { ...cfg.box, folder_id: '', archive_folder_id: '', output_folder_id: '' },
      ica: { ...cfg.ica, full_cookie: '', team_id: '', team_name: '', assistant_id: '', chat_id: '', base_url: '' },
      settings: {
        ...cfg.settings,
        search_subfolders: false,
        overwrite_existing_exports: false,
        log_activity: false,
        file_extension: '',
      },
      sync: { ...cfg.sync, auto_sync_enabled: false, auto_sync_interval_minutes: 0 },
    }).finally(() => setBusy(null))
  }


  async function uploadJwt() {
    if (!jwtText.trim()) return
    setBusy('jwt'); setJwtMsg(null)
    // Persist the current in-memory cfg FIRST so any unsaved folder IDs the user
    // typed aren't discarded by the load() below. The JWT file (jwtText) lives in
    // a separate box_jwt_config.json and separate state, so a plain load() would
    // otherwise reset cfg to the last-saved values and wipe the user's edits.
    if (cfg) await post<{ status: string; config: AppConfig }>('/api/settings', { config: cfg })
    const res = await post<{ status: string; error?: string }>('/api/settings/jwt', { content: jwtText })
    setBusy(null)
    if (res?.status === 'saved') { setJwtMsg({ ok: true, msg: 'JWT config saved ✓' }); setJwtText(''); load() }
    else setJwtMsg({ ok: false, msg: res?.error ?? 'Upload failed' })
  }


  // Run a streaming connection test: open an SSE connection and accumulate the
  // human-readable "step" events the backend emits so the user sees live
  // progress instead of a blank spinner. The stream ends on a "done" (success)
  // or "error" (failure) event.
  function runStreamTest(
    path: string,
    busyKey: string,
    setState: Dispatch<SetStateAction<StreamState>>,
  ) {

    // Tear down any test already running.
    esRef.current?.close()
    esRef.current = null

    setBusy(busyKey)
    setState({ steps: [], running: true, outcome: null })

    const es = new EventSource(`${apiBase()}${path}`)
    esRef.current = es
    // Track which panel owns this connection so Cancel resets the right one.
    activeTestRef.current = { key: busyKey, setState }

    const finish = (outcome: 'ok' | 'error', extraStep?: Step) => {
      es.close()
      if (esRef.current === es) esRef.current = null
      if (activeTestRef.current?.setState === setState) activeTestRef.current = null
      setState(prev => {
        const base = prev ?? { steps: [], running: true, outcome: null }
        const steps = extraStep ? appendStep(base.steps, extraStep) : base.steps
        return { steps, running: false, outcome }
      })
      setBusy(null)
    }

    es.onmessage = (ev: MessageEvent) => {
      let data: Step
      try {
        data = JSON.parse(ev.data) as Step
      } catch {
        return
      }
      setState(prev => {
        const base = prev ?? { steps: [], running: true, outcome: null }
        return { ...base, steps: appendStep(base.steps, data) }
      })
      if (data.state === 'done') finish('ok')
      else if (data.state === 'error') finish('error')
    }


    es.onerror = () => {
      // Only surface an error if we hadn't already reached a terminal event.
      setState(prev => {
        if (!prev || !prev.running) return prev
        finish('error', {
          step: 'Connection to the server was lost.',
          state: 'error',
          error: 'The stream ended unexpectedly.',
        })
        return prev
      })
    }
  }

  // Cancel the running test: closing the EventSource stops the client from
  // receiving further events, and for a synchronous FastAPI generator the
  // client disconnect raises GeneratorExit at the next yield so the backend
  // loop halts within a heartbeat interval. Mark the panel as a cancelled
  // (error) outcome so the user gets clear feedback.
  function cancelTest() {
    const active = activeTestRef.current
    esRef.current?.close()
    esRef.current = null
    activeTestRef.current = null
    if (active) {
      active.setState(prev => {
        if (!prev) return prev
        return {
          steps: appendStep(prev.steps, {
            step: 'Test cancelled.',
            state: 'error',
            error: 'Stopped by user.',
          }),
          running: false,
          outcome: 'error',
        }
      })
    }
    setBusy(null)
  }

  function testBox() {
    if (busy === 'box') { cancelTest(); return }
    runStreamTest('/api/settings/test/box/stream', 'box', setBoxTest)
  }

  function testIca() {
    if (busy === 'ica') { cancelTest(); return }
    runStreamTest('/api/settings/test/ica/stream', 'ica', setIcaTest)
  }


  // One-click browser-assisted ICA login. Opens an Electron window pointed at
  // IBM Consulting Advantage; the user signs in normally (IBMid/SSO) and starts
  // a chat, and the main process auto-captures the session cookie + team/chat
  // identifiers from the outgoing API request headers.
  async function signInIca() {
    if (!cfg) return
    if (!window.electronAPI?.icaLogin) {
      setIcaLoginMsg({ ok: false, msg: 'Auto-login is only available in the desktop app.' })
      return
    }
    setBusy('ica-login'); setIcaLoginMsg(null); setIcaTest(null)
    try {
      const res = await window.electronAPI.icaLogin()
      if (res.status === 'ok') {
        const c = res.captured
        // Merge captured values into config; only overwrite when a value was
        // actually captured so we never blank out a field the user already set.
        const nextIca = {
          ...cfg.ica,
          full_cookie: c.full_cookie || cfg.ica.full_cookie,
          team_id:     c.team_id     || cfg.ica.team_id,
          team_name:   c.team_name   || cfg.ica.team_name,
          chat_id:     c.chat_id     || cfg.ica.chat_id,
          base_url:    c.base_url    || cfg.ica.base_url,
        }
        const nextCfg = { ...cfg, ica: nextIca }
        setCfg(nextCfg)

        // Persist immediately so a Test ICA / extraction works without a
        // separate Save click.
        const saveRes = await post<{ status: string; config: AppConfig }>('/api/settings', { config: nextCfg })
        if (saveRes?.config) { setCfg(saveRes.config); load() }

        const missing: string[] = []
        if (!nextIca.full_cookie) missing.push('cookie')
        if (!nextIca.team_id)     missing.push('team ID')
        if (!nextIca.chat_id)     missing.push('chat ID')
        if (missing.length) {
          setIcaLoginMsg({ ok: false, msg: `Captured partial credentials — missing ${missing.join(', ')}. In the login window, open a chat and SEND ONE MESSAGE, then try again.` })
        } else {
          setIcaLoginMsg({ ok: true, msg: 'Signed in — ICA credentials captured & saved ✓ You can now Test ICA.' })
        }
      } else if (res.status === 'cancelled') {
        setIcaLoginMsg({ ok: false, msg: 'Login window closed before a message was sent. Sign in, open a chat and send one message so the chat is initialised, then it captures automatically.' })

      } else {
        setIcaLoginMsg({ ok: false, msg: res.error || 'Login failed.' })
      }
    } catch (e: any) {
      setIcaLoginMsg({ ok: false, msg: String(e?.message ?? e) })
    } finally {
      setBusy(null)
    }
  }

  if (!cfg) {
    return (
      <div className="p-7 max-w-4xl flex items-center gap-2 text-gray-500">
        <Spinner size={16} /> Loading settings…
      </div>
    )
  }

  return (
    <div className="p-7 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-sub mt-0.5">Configure Box, ICA and extraction options</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={clearAll} disabled={busy === 'clear-all' || saving || loading}>
            {busy === 'clear-all' ? <Spinner size={14} /> : <Trash2 size={14} />}
            Clear All
          </Button>
          <Button variant="green" onClick={handleSave} disabled={saving || loading}>
            {saving ? <Spinner size={14} /> : <Save size={14} />}
            {saving ? 'Saving…' : 'Save Settings'}
          </Button>
        </div>
      </div>


      {saved && (
        <div className="mb-4 flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
          <CheckCircle2 size={16} /> Settings saved successfully.
        </div>
      )}

      {/* Status overview */}
      {status && (
        <div className="mb-6 flex flex-wrap gap-3">
          <StatusPill label="Box" ok={status.box.configured} />
          <StatusPill label="JWT" ok={status.box.jwt_uploaded} />
          <StatusPill label="ICA" ok={status.ica.configured} />
          <StatusPill label="PDF Password" ok={status.pdf_password} />
          <StatusPill label="Ready" ok={status.ready} />
        </div>
      )}

      {/* PDF Password */}
      <Card className="mb-5">
        <SectionHead icon={<KeyRound size={16} />} title="PDF Password" sub="Password used to open protected PDFs during extraction"
          action={<ClearButton onClick={clearPdfPassword} busy={busy === 'clear-pdf'} />} />
        <Field label="PDF Password" type="password"
          value={cfg.pdf_password}
          onChange={v => patchTop('pdf_password', v)} />
      </Card>

      {/* Box */}
      <Card className="mb-5">
        <SectionHead icon={<BoxIcon size={16} />} title="IBM Box" sub="JWT credentials + folder IDs for syncing and uploading"
          action={<ClearButton onClick={clearBox} busy={busy === 'clear-box'} />} />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Field label="Source Folder ID" value={cfg.box.folder_id}
            onChange={v => patch('box', 'folder_id', v)} />
          <Field label="Archive Folder ID" value={cfg.box.archive_folder_id}
            onChange={v => patch('box', 'archive_folder_id', v)} />
          <Field label="Output Folder ID" value={cfg.box.output_folder_id}
            onChange={v => patch('box', 'output_folder_id', v)} />
        </div>

        <div className="mt-4">
          <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
            Box JWT Config JSON
          </label>
          <textarea
            className="w-full h-28 rounded-lg border border-border-light dark:border-border-dark
                       bg-white dark:bg-[#0D1117] px-3 py-2 text-xs font-mono
                       text-gray-800 dark:text-gray-200 focus:outline-none focus:border-accent"
            placeholder='Paste the contents of your Box JWT config file (boxAppSettings…)'
            value={jwtText}
            onChange={e => setJwtText(e.target.value)}
          />
          <div className="mt-2 flex items-center gap-3">
            <Button variant="primary" size="sm" onClick={uploadJwt} disabled={busy === 'jwt' || !jwtText.trim()}>
              {busy === 'jwt' ? <Spinner size={12} /> : <Upload size={12} />} Upload JWT
            </Button>
            <Button variant={busy === 'box' ? 'danger' : 'ghost'} size="sm" onClick={testBox}>
              {busy === 'box'
                ? <><Ban size={12} /> Cancel</>
                : <><CheckCircle2 size={12} /> Test Box</>}
            </Button>
            {jwtMsg && <TestMsg state={jwtMsg} />}
          </div>
          {boxTest && <StepLog stream={boxTest} />}
        </div>
      </Card>


      {/* ICA */}
      <Card className="mb-5">
        <SectionHead icon={<MessageSquare size={16} />} title="IBM Consulting Advantage (ICA)" sub="Cookie + team/chat identifiers for the AI assistant"
          action={<ClearButton onClick={clearIca} busy={busy === 'clear-ica'} />} />

        {/* One-click browser-assisted login */}
        <div className="mb-4 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" size="sm" onClick={signInIca}
              // disabled={busy === 'ica-login' || !canAutoLogin}
            >
              {busy === 'ica-login' ? <Spinner size={12} /> : <LogIn size={12} />}
              {busy === 'ica-login' ? 'Waiting for sign-in…' : 'Sign in to ICA'}
            </Button>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {canAutoLogin
                ? 'Opens IBM Consulting Advantage — sign in, open a chat and send one message. Credentials are captured automatically once the chat is initialised.'
                : 'Auto-login is only available in the desktop app.'}
            </span>
          </div>
          {icaLoginMsg && <div className="mt-2"><TestMsg state={icaLoginMsg} /></div>}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

          <Field label="Team ID" value={cfg.ica.team_id}
            onChange={v => patch('ica', 'team_id', v)} />
          <Field label="Team Name" value={cfg.ica.team_name}
            onChange={v => patch('ica', 'team_name', v)} />
          <Field label="Assistant ID" value={cfg.ica.assistant_id}
            onChange={v => patch('ica', 'assistant_id', v)} />
          <Field label="Chat ID" value={cfg.ica.chat_id}
            onChange={v => patch('ica', 'chat_id', v)} />
        </div>
        <div className="mt-3">
          <Field label="Base URL" value={cfg.ica.base_url}
            onChange={v => patch('ica', 'base_url', v)} />
        </div>
        <div className="mt-3">
          <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
            Full Cookie
          </label>
          <textarea
            className="w-full h-24 rounded-lg border border-border-light dark:border-border-dark
                       bg-white dark:bg-[#0D1117] px-3 py-2 text-xs font-mono
                       text-gray-800 dark:text-gray-200 focus:outline-none focus:border-accent"
            placeholder="Paste your full ICA session cookie…"
            value={cfg.ica.full_cookie}
            onChange={e => patch('ica', 'full_cookie', e.target.value)}
          />
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button variant={busy === 'ica' ? 'danger' : 'ghost'} size="sm" onClick={testIca}>
            {busy === 'ica'
              ? <><Ban size={12} /> Cancel</>
              : <><CheckCircle2 size={12} /> Test ICA</>}
          </Button>
        </div>
        {icaTest && <StepLog stream={icaTest} />}
      </Card>

      {/* Options */}
      <Card className="mb-5">
        <SectionHead icon={<KeyRound size={16} />} title="Extraction & Sync Options" sub="Behaviour toggles for scanning and syncing"
          action={<ClearButton onClick={clearOptions} busy={busy === 'clear-options'} />} />
        <div className="space-y-2">
          <Toggle label="Search subfolders when scanning"
            checked={cfg.settings.search_subfolders}
            onChange={v => patch('settings', 'search_subfolders', v)} />
          <Toggle label="Overwrite existing exports"
            checked={cfg.settings.overwrite_existing_exports}
            onChange={v => patch('settings', 'overwrite_existing_exports', v)} />
          <Toggle label="Log activity to history"
            checked={cfg.settings.log_activity}
            onChange={v => patch('settings', 'log_activity', v)} />
          <Toggle label="Enable automatic Box sync"
            checked={cfg.sync.auto_sync_enabled}
            onChange={v => patch('sync', 'auto_sync_enabled', v)} />
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="File Extension" value={cfg.settings.file_extension}
            onChange={v => patch('settings', 'file_extension', v)} />
          <Field label="Auto-Sync Interval (minutes)" type="number"
            value={String(cfg.sync.auto_sync_interval_minutes)}
            onChange={v => patch('sync', 'auto_sync_interval_minutes', Number(v) || 0)} />
        </div>
      </Card>
    </div>
  )
}

// ── Small presentational helpers ─────────────────────────────────────────────
// `action` renders at the right edge of the header row — used for the per-section
// "Clear" button so it lines up neatly with the section title.
function SectionHead({ icon, title, sub, action }: { icon: React.ReactNode; title: string; sub: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="w-8 h-8 rounded-lg bg-accent/10 text-accent flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div className="flex-1">
        <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">{title}</h2>
        <p className="text-xs text-gray-500 dark:text-gray-400">{sub}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

// Small reusable "Clear" button for a settings section.
function ClearButton({ onClick, busy }: { onClick: () => void; busy: boolean }) {
  return (
    <Button variant="ghost" size="sm" onClick={onClick} disabled={busy}>
      {busy ? <Spinner size={12} /> : <Trash2 size={12} />} Clear
    </Button>
  )
}


function Field({
  label, value, onChange, type = 'text',
}: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        className="w-full rounded-lg border border-border-light dark:border-border-dark
                   bg-white dark:bg-[#0D1117] px-3 py-2 text-sm
                   text-gray-800 dark:text-gray-200 focus:outline-none focus:border-accent"
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  )
}

function Toggle({
  label, checked, onChange,
}: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer select-none">
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5 rounded-full transition-colors shrink-0
                    ${checked ? 'bg-accent' : 'bg-gray-300 dark:bg-gray-600'}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform
                          ${checked ? 'translate-x-5' : ''}`} />
      </button>
      <span className="text-sm text-gray-700 dark:text-gray-300">{label}</span>
    </label>
  )
}

function StatusPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold
                      ${ok ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                           : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}`}>
      {ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />} {label}
    </span>
  )
}

function TestMsg({ state }: { state: { ok: boolean; msg: string } }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium
                      ${state.ok ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
      {state.ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />} {state.msg}
    </span>
  )
}

// Live, human-readable progress log for a streaming connection test. Renders
// each step the backend emits: a spinner while a step is running, a green check
// for completed/successful steps, and a red X for failures. The terminal
// detail/error text is shown inline so the user can see the final result.
function StepLog({ stream }: { stream: NonNullable<StreamState> }) {
  const { steps, running, outcome } = stream

  // Auto-scroll the (scrollable) log to the bottom as new steps arrive so the
  // latest heartbeat/result is always visible without manual scrolling.
  const scrollRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [steps, running])

  return (
    <div className="mt-3 rounded-lg border border-border-light dark:border-border-dark
                    bg-gray-50 dark:bg-[#0D1117] px-4 py-3">
      <div ref={scrollRef} className="max-h-48 overflow-y-auto">
        <ul className="space-y-1.5">
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1
          // Only the most recent "run" step should show a live spinner; earlier
          // run steps have effectively completed once a newer step arrives.
          const showSpinner = s.state === 'run' && isLast && running
          const isError = s.state === 'error'
          const isDone = s.state === 'ok' || s.state === 'done'
          return (
            <li key={i} className="flex items-start gap-2 text-xs">
              <span className="mt-0.5 shrink-0">
                {showSpinner ? (
                  <Loader2 size={13} className="animate-spin text-accent" />
                ) : isError ? (
                  <XCircle size={13} className="text-red-500" />
                ) : isDone ? (
                  <CheckCircle2 size={13} className="text-green-600 dark:text-green-400" />
                ) : s.state === 'run' ? (
                  <CheckCircle2 size={13} className="text-gray-400 dark:text-gray-500" />
                ) : (
                  <CheckCircle2 size={13} className="text-gray-400" />
                )}
              </span>
              <span className={
                isError ? 'text-red-500' : isDone ? 'text-green-700 dark:text-green-300'
                : 'text-gray-700 dark:text-gray-300'
              }>
                {s.step}
                {(s.detail || s.error) && (
                  <span className="block text-[11px] text-gray-500 dark:text-gray-400 font-mono mt-0.5 whitespace-pre-wrap break-words">
                    {s.error ?? s.detail}
                  </span>
                )}
              </span>
            </li>
          )
        })}
        </ul>
      </div>

      {!running && outcome && (
        <div className={`mt-2 pt-2 border-t border-border-light dark:border-border-dark
                         flex items-center gap-1.5 text-xs font-semibold
                         ${outcome === 'ok' ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
          {outcome === 'ok'
            ? <><CheckCircle2 size={13} /> Test passed</>
            : <><XCircle size={13} /> Test failed</>}
        </div>
      )}
    </div>
  )
}


