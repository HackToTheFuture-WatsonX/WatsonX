/**
 * main.js — Electron main process for PDF Extractor V3.
 *
 * Startup sequence:
 *  1. Find a free port starting at 8765 (skip known-used: 5000, 8080, 47321)
 *  2. Write chosen port to .v3_port
 *  3. Spawn Python backend: python backend/main.py --port <port>
 *  4. Poll GET /api/health every 500 ms (max 30 s)
 *  5. On health OK → create BrowserWindow, load renderer/index.html
 *  6. Inject window.__V3_API_PORT__ into renderer
 *  7. On app quit → kill Python, delete .v3_port
 */

const { app, BrowserWindow, ipcMain, dialog, Menu, session } = require('electron')
const path  = require('path')
const net   = require('net')
const http  = require('http')
const fs    = require('fs')
const os    = require('os')
const { spawn } = require('child_process')

// ── File-based logging ─────────────────────────────────────────────────────────
// A packaged Windows GUI app detaches from the console, so console.log is
// invisible. Write a startup log to a predictable location so failures can be
// diagnosed. We use the OS temp dir because userData may not be resolvable yet.
const LOG_FILE = path.join(os.tmpdir(), 'pdf-extractor-v3-startup.log')

// Separate log file for the SPAWNED backend process. Because a packaged
// Windows GUI app has no console, piping backend stdout into process.stdout is
// a no-op — every request line, every scanner INFO, every Python traceback
// disappeared into the void. Redirecting to this file makes them recoverable.
const BACKEND_LOG_FILE = path.join(os.tmpdir(), 'pdf-extractor-v3-backend.log')

function logLine(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`
  try { fs.appendFileSync(LOG_FILE, line) } catch { /**/ }
  try { process.stdout.write(line) } catch { /**/ }
}
try { fs.writeFileSync(LOG_FILE, '') } catch { /**/ }
logLine(`=== PDF Extractor V3 launch === isPackaged pending, argv=${process.argv.join(' ')}`)

process.on('uncaughtException', (err) => {
  logLine(`UNCAUGHT EXCEPTION: ${err && err.stack ? err.stack : err}`)
  try { dialog.showErrorBox('PDF Extractor V3 — Fatal Error', String(err && err.stack ? err.stack : err)) } catch { /**/ }
})
process.on('unhandledRejection', (reason) => {
  logLine(`UNHANDLED REJECTION: ${reason}`)
})


const PREFERRED_PORT = 8765
const SKIP_PORTS     = new Set([5000, 8080, 47321])
const HEALTH_TIMEOUT = 30_000   // 30 seconds
const HEALTH_POLL_MS = 500

let pythonProcess = null
let mainWindow    = null
let chosenPort    = PREFERRED_PORT
let backendStderr = ''   // captured for error reporting
let backendExited = null // { code } once the backend process exits

// ── Port finder ───────────────────────────────────────────────────────────────
function findFreePort(preferred, maxAttempts = 20) {
  return new Promise((resolve, reject) => {
    let candidate = preferred
    let attempts  = 0

    function tryPort() {
      if (attempts >= maxAttempts) {
        reject(new Error(`No free port found near ${preferred}`))
        return
      }
      if (SKIP_PORTS.has(candidate)) {
        candidate++; attempts++; tryPort(); return
      }
      const server = net.createServer()
      server.once('error', () => { candidate++; attempts++; tryPort() })
      server.once('listening', () => {
        const port = server.address().port
        server.close(() => resolve(port))
      })
      server.listen(candidate, '127.0.0.1')
    }
    tryPort()
  })
}

// ── Health poll ───────────────────────────────────────────────────────────────
function waitForHealth(port) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + HEALTH_TIMEOUT
    function poll() {
      if (Date.now() > deadline) { reject(new Error('Backend health timeout')); return }
      http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        if (res.statusCode === 200) resolve()
        else setTimeout(poll, HEALTH_POLL_MS)
      }).on('error', () => setTimeout(poll, HEALTH_POLL_MS))
    }
    poll()
  })
}

// ── Spawn Python backend ──────────────────────────────────────────────────────
function spawnBackend(port) {
  let cmd, args, cwd

  if (app.isPackaged) {
    // Production: use the bundled backend.exe (PyInstaller one-folder build)
    // Electron-builder places extraResources at process.resourcesPath
    const backendDir = path.join(process.resourcesPath, 'backend')
    const exe        = path.join(backendDir, 'backend.exe')
    const userData   = app.getPath('userData')
    cmd  = exe
    args = ['--port', String(port), '--data-dir', userData]
    cwd  = backendDir
  } else {
    // Development: run python main.py directly
    const backendDir = path.join(__dirname, '..', 'backend')
    const python     = process.platform === 'win32' ? 'python' : 'python3'
    cmd  = python
    args = [path.join(backendDir, 'main.py'), '--port', String(port)]
    cwd  = backendDir
  }

  pythonProcess = spawn(cmd, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    env:   { ...process.env, PYTHONUNBUFFERED: '1' },
    // Required on Windows for .exe — don't wrap in shell
    shell: false,
  })

  // Truncate + open the backend log fresh for this launch. Append after that
  // so the exit code lands in the same file.
  try {
    fs.writeFileSync(
      BACKEND_LOG_FILE,
      `=== backend launch @ ${new Date().toISOString()} ===\n` +
      `cmd: ${cmd} ${args.join(' ')}\n` +
      `cwd: ${cwd}\n\n`,
    )
  } catch (e) { logLine(`Could not truncate backend log: ${e && e.message}`) }
  const backendLogStream = fs.createWriteStream(BACKEND_LOG_FILE, { flags: 'a' })

  pythonProcess.stdout.on('data', (d) => {
    try { backendLogStream.write(`[out] ${d}`) } catch { /**/ }
    try { process.stdout.write(`[backend] ${d}`) } catch { /**/ }
  })
  pythonProcess.stderr.on('data', (d) => {
    const text = d.toString()
    backendStderr = (backendStderr + text).slice(-4000)  // keep last 4 KB
    try { backendLogStream.write(`[err] ${text}`) } catch { /**/ }
    try { process.stderr.write(`[backend] ${text}`) } catch { /**/ }
  })
  pythonProcess.on('exit', (code) => {
    backendExited = { code }
    const line = `\n=== backend exited with code ${code} @ ${new Date().toISOString()} ===\n`
    try { backendLogStream.end(line) } catch { /**/ }
    console.log(`[backend] exited with code ${code}`)
  })

}

// ── Loading splash (shown immediately while the backend warms up) ─────────────
const LOADING_HTML =
  'data:text/html;charset=utf-8,' + encodeURIComponent(`
<!doctype html><html><head><meta charset="utf-8"><title>PDF Extractor V3</title>
<style>
  html,body{margin:0;height:100%;font-family:'Segoe UI',system-ui,sans-serif;
    background:#0F1117;color:#E5E7EB;display:flex;align-items:center;
    justify-content:center;flex-direction:column;gap:22px}
  .spinner{width:46px;height:46px;border-radius:50%;
    border:4px solid rgba(108,99,255,.25);border-top-color:#6C63FF;
    animation:spin 1s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  .title{font-size:18px;font-weight:600;letter-spacing:.3px}
  .sub{font-size:13px;color:#9CA3AF}
</style></head>
<body>
  <div class="spinner"></div>
  <div class="title">PDF Extractor V3</div>
  <div class="sub">Starting backend service…</div>
</body></html>`)

// ── Create window ─────────────────────────────────────────────────────────────
// Create the window and show it IMMEDIATELY with a loading splash so the user
// gets instant feedback instead of a long white screen during backend cold-start.
function createWindow() {
  mainWindow = new BrowserWindow({
    width:  1280,
    height: 800,
    minWidth: 1000,
    minHeight: 640,
    title:  'PDF Extractor V3',
    backgroundColor: '#0F1117',
    autoHideMenuBar: false,
    show:   true,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
    },
  })
  mainWindow.loadURL(LOADING_HTML)
  mainWindow.on('closed', () => { mainWindow = null })
}

// Swap the splash for the real renderer once the backend is healthy.
function loadRenderer(port) {
  if (!mainWindow || mainWindow.isDestroyed()) return
  // Vite builds the renderer to electron/renderer (see frontend/vite.config.ts
  // → build.outDir: '../electron/renderer'), for BOTH dev and packaged builds.
  // There is no frontend/dist directory, so always load from electron/renderer.
  const rendererPath = path.join(__dirname, 'renderer', 'index.html')


  mainWindow.webContents.once('did-finish-load', () => {
    mainWindow.webContents.executeJavaScript(
      `window.__V3_API_PORT__ = ${port};`
    )
    if (!app.isPackaged) mainWindow.webContents.openDevTools({ mode: 'detach' })
  })

  mainWindow.loadFile(rendererPath)
}


// ── App lifecycle ─────────────────────────────────────────────────────────────
// ── First-launch: copy config template to userData if missing ─────────────────
function ensureUserConfig() {
  if (!app.isPackaged) return
  const userData   = app.getPath('userData')
  const destConfig = path.join(userData, 'config.json')
  const srcConfig  = path.join(process.resourcesPath, 'backend', 'config.json')

  if (!fs.existsSync(destConfig) && fs.existsSync(srcConfig)) {
    fs.mkdirSync(userData, { recursive: true })
    fs.copyFileSync(srcConfig, destConfig)
    console.log(`[V3] Config template copied to ${destConfig}`)
  }
  // JWT config is stored in the SQLite database — upload it via Settings page.
}

app.whenReady().then(async () => {
  try {
    // Fully remove the native application menu (File/Edit/View/…). Combined with
    // autoHideMenuBar on the window, this ensures the menu never appears — not
    // even when the user presses Alt.
    Menu.setApplicationMenu(null)
    logLine(`whenReady: isPackaged=${app.isPackaged} resourcesPath=${process.resourcesPath} __dirname=${__dirname}`)
    ensureUserConfig()

    logLine('ensureUserConfig done')

    chosenPort = await findFreePort(PREFERRED_PORT)
    logLine(`findFreePort -> ${chosenPort}`)

    // Write port file
    const portFile = path.join(app.getPath('userData'), '.v3_port')
    fs.writeFileSync(portFile, String(chosenPort), 'utf8')

    // Show the window + splash immediately so the user gets instant feedback.
    createWindow()
    logLine('createWindow called (splash)')

    spawnBackend(chosenPort)
    logLine('spawnBackend called')
    await waitForHealth(chosenPort)
    logLine('waitForHealth resolved (backend healthy)')

    // Backend is up — swap the splash for the real React app.
    loadRenderer(chosenPort)
    logLine('loadRenderer called')
  } catch (err) {

    logLine(`STARTUP CATCH: ${err && err.stack ? err.stack : err} | backendExited=${JSON.stringify(backendExited)} | stderr=${backendStderr}`)

    const detail = backendExited
      ? `Backend process exited (code ${backendExited.code}).\n\n${backendStderr}`
      : `${err.message}\n\n${backendStderr}`
    console.error('[V3] Startup failed:', err, backendStderr)
    dialog.showErrorBox('PDF Extractor V3 — Startup Failed', detail || String(err))
    app.quit()
  }

})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('will-quit', () => {
  if (pythonProcess && !pythonProcess.killed) {
    pythonProcess.kill()
    console.log('[V3] Backend process terminated.')
  }
  try {
    const portFile = path.join(app.getPath('userData'), '.v3_port')
    if (fs.existsSync(portFile)) fs.unlinkSync(portFile)
  } catch { /**/ }
})

// ── IPC: renderer can ask for the port ───────────────────────────────────────
ipcMain.handle('get-api-port', () => chosenPort)
ipcMain.handle('get-backend-log-path', () => BACKEND_LOG_FILE)

// ── Browser-assisted ICA login ────────────────────────────────────────────────
// Opens a dedicated login window pointed at IBM Consulting Advantage (ICA).
// The user signs in normally (IBMid / SSO). While the window is open we watch
// the authenticated ICA API traffic to auto-capture:
//   • full_cookie  — the complete Cookie header sent to servicesessentials.ibm.com
//   • team_id / team_name — from the `teamid` / `teamname` request headers
//   • chat_id      — parsed from the /chats/<id>/entries API path
//   • base_url     — the curatorai chat service root
// Once we have a cookie + team_id + chat_id we resolve automatically. The user
// can also simply close the window to cancel.
const ICA_LOGIN_URL   = 'https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat'
const ICA_HOST_SUBSTR = 'servicesessentials.ibm.com'
const ICA_API_SUBSTR  = '/curatorai/services/chat/'
// The prompt-submit endpoint. A chat_id parsed from this URL is guaranteed to be
// a real, initialized thread bound to the assistant (the user actually sent a
// message), so it is the only chat_id we trust for later API POSTs.
const ICA_ENTRIES_RE  = /\/chats\/([^/?#]+)\/entries\b/
const ICA_BASE_URL    = 'https://servicesessentials.ibm.com/curatorai/services/chat/new-chat'

// Persistent partition so a returning user stays logged in between attempts.
const ICA_PARTITION   = 'persist:ica-login'

let icaLoginWindow = null

// Wipe the ICA login window's persisted session data (cookies, cache, storage).
// The partition is `persist:` so Electron writes it to disk; without an explicit
// clear it would linger between sign-ins. Call this AFTER the needed credential
// fields have been captured and returned to the renderer. We resolve the session
// from the partition NAME (not win.webContents) because the window is already
// destroyed by the time this runs.
function clearIcaLoginSession() {
  try {
    const ses = session.fromPartition(ICA_PARTITION)
    ses.clearStorageData()
      .then(() => logLine('ICA login session storage cleared on window close'))
      .catch((e) => logLine(`ICA clearStorageData error: ${e && e.message ? e.message : e}`))
    ses.clearCache().catch(() => { /**/ })
  } catch (e) {
    logLine(`clearIcaLoginSession error: ${e && e.message ? e.message : e}`)
  }
}

// Read the FULL cookie string directly from the ICA partition's cookie jar.
//
// Why: session.webRequest.onSendHeaders frequently OMITS the Cookie header —
// Chromium's network stack attaches cookies from its jar without exposing them
// to the observer, and HttpOnly cookies (ak_bmsc, bm_sv, _abck, and crucially
// the ica_core_auth_proxy auth token) are never visible there. Reading the jar
// via cookies.get() returns every cookie regardless of HttpOnly, so we can
// rebuild the complete `name=value; name2=value2; …` header the API expects.
//
// MUST be called BEFORE clearIcaLoginSession() wipes the jar.
async function readIcaCookieString() {
  try {
    const ses = session.fromPartition(ICA_PARTITION)
    // Query the ICA host explicitly so we get exactly the cookies the browser
    // would send to the API (path/domain/secure filtering handled by Electron).
    const cookies = await ses.cookies.get({ url: 'https://servicesessentials.ibm.com/' })
    if (!Array.isArray(cookies) || cookies.length === 0) return ''
    // Dedupe by name (keep last), preserving insertion order.
    const seen = new Map()
    for (const c of cookies) {
      if (c && c.name) seen.set(c.name, c.value == null ? '' : c.value)
    }
    return Array.from(seen.entries()).map(([n, v]) => `${n}=${v}`).join('; ')
  } catch (e) {
    logLine(`readIcaCookieString error: ${e && e.message ? e.message : e}`)
    return ''
  }
}


function _extractChatId(urlStr) {

  // Matches …/chats/<id>/entries or …/chats/<id>
  const m = /\/chats\/([^/?#]+)/.exec(urlStr || '')
  return m ? decodeURIComponent(m[1]) : ''
}

function icaBrowserLogin() {
  return new Promise((resolve) => {
    // Guard against a second concurrent login window.
    if (icaLoginWindow && !icaLoginWindow.isDestroyed()) {
      try { icaLoginWindow.focus() } catch { /**/ }
      resolve({ status: 'error', error: 'A login window is already open.' })
      return
    }

    const captured = {
      full_cookie: '',
      team_id:     '',
      team_name:   '',
      chat_id:     '',
      base_url:    ICA_BASE_URL,
    }
    let settled = false
    // Once we observe a chat_id on a real /entries request, it is authoritative.
    // Placeholder chat_ids seen on the new-chat landing page (metadata/config
    // calls) must never overwrite it — they point at an uninitialized thread the
    // assistant never answers, which is what caused "(ICA did not respond in time)".
    let chatIdIsTrusted = false

    const win = new BrowserWindow({
      width:  980,
      height: 760,
      title:  'Sign in to IBM Consulting Advantage',
      backgroundColor: '#0F1117',
      autoHideMenuBar: true,
      parent: mainWindow && !mainWindow.isDestroyed() ? mainWindow : undefined,
      modal:  false,
      webPreferences: {
        partition:        ICA_PARTITION,
        contextIsolation: true,
        nodeIntegration:  false,
      },
    })
    icaLoginWindow = win

    const ses = win.webContents.session

    function finish(result) {
      if (settled) return
      settled = true
      try { ses.webRequest.onSendHeaders(null) } catch { /**/ }
      if (win && !win.isDestroyed()) {
        // Close on next tick so the in-flight request finishes cleanly.
        setTimeout(() => { try { win.close() } catch { /**/ } }, 50)
      }
      resolve(result)
    }

    async function maybeComplete() {
      // Only auto-resolve once we have a TRUSTED chat_id (from an /entries POST).
      // Resolving on a placeholder new-chat id is exactly what produced the
      // "(ICA did not respond in time)" failure downstream. If the user never
      // sends a message, the window-close handler still returns cookie+team so
      // the UI can prompt them to complete the step.
      if (captured.team_id && captured.chat_id && chatIdIsTrusted) {
        // Always prefer the COMPLETE cookie jar over whatever onSendHeaders saw
        // (which may be partial or missing HttpOnly cookies like the auth token).
        const jarCookie = await readIcaCookieString()
        if (jarCookie) captured.full_cookie = jarCookie
        if (!captured.full_cookie) return  // nothing usable yet — wait
        logLine(`ICA login captured: team_id=${captured.team_id} chat_id=${captured.chat_id} cookieLen=${captured.full_cookie.length}`)
        finish({ status: 'ok', captured })
      }
    }



    // Watch outgoing headers on authenticated ICA API calls.
    ses.webRequest.onSendHeaders(
      { urls: ['https://servicesessentials.ibm.com/*'] },
      (details) => {
        try {
          const url     = details.url || ''
          const headers = details.requestHeaders || {}
          // Case-insensitive header lookup.
          const lower = {}
          for (const k of Object.keys(headers)) lower[k.toLowerCase()] = headers[k]

          if (url.includes(ICA_API_SUBSTR)) {
            if (lower['cookie'])   captured.full_cookie = lower['cookie']
            if (lower['teamid'])   captured.team_id     = lower['teamid']
            if (lower['teamname']) captured.team_name   = lower['teamname']

            // A chat_id on a real /entries request means the user actually sent
            // a prompt → the thread is initialized and the assistant will answer.
            // Trust that id and lock it. All other API calls (metadata, config,
            // history) may carry a placeholder new-chat id — never let those
            // overwrite a trusted id, or downstream POSTs will time out.
            const entriesMatch = ICA_ENTRIES_RE.exec(url)
            if (entriesMatch) {
              captured.chat_id = decodeURIComponent(entriesMatch[1])
              chatIdIsTrusted  = true
            } else if (!chatIdIsTrusted) {
              const cid = _extractChatId(url)
              if (cid) captured.chat_id = cid
            }
            maybeComplete()
          } else if (url.includes(ICA_HOST_SUBSTR) && lower['cookie'] && !captured.full_cookie) {

            // Fall back to any authenticated cookie on the ICA host so we at
            // least have the session even before an API call is observed.
            captured.full_cookie = lower['cookie']
          }
        } catch (e) {
          logLine(`ICA onSendHeaders error: ${e}`)
        }
      }
    )

    win.on('closed', () => {
      icaLoginWindow = null
      // Read the FULL cookie jar and resolve BEFORE clearing the session — once
      // clearIcaLoginSession() runs the jar is empty. We ALWAYS refresh the
      // captured field values from the jar on close (Task D): even if the user
      // closed the window without triggering a full auto-capture, whatever the
      // browser accumulated (cookie + any team/chat headers seen) is returned so
      // the Settings fields get updated. readIcaCookieString() is async, so we
      // do the jar read → resolve → clear inside a self-invoking async function.
      ;(async () => {
        if (!settled) {
          settled = true
          // Always prefer the COMPLETE cookie jar (includes HttpOnly auth cookies
          // that onSendHeaders never exposes) over whatever the observer captured.
          const jarCookie = await readIcaCookieString()
          if (jarCookie) captured.full_cookie = jarCookie

          // If a message was never sent, chat_id is either empty or an untrusted
          // placeholder from the new-chat landing page — never let that reach the
          // config, or downstream POSTs time out with "(ICA did not respond in
          // time)". Blank it so the UI prompts the user to send a message.
          if (!chatIdIsTrusted) captured.chat_id = ''

          // ALWAYS return the captured values so the Settings fields are updated
          // on close (cookie / team_id / team_name / chat_id / base_url), even a
          // partial capture. The renderer only overwrites fields that have a
          // value, and reports what's still missing.
          if (captured.full_cookie || captured.team_id || captured.chat_id) {
            resolve({ status: 'ok', captured })
          } else {
            resolve({ status: 'cancelled' })
          }
        }
        // The credential fields have now been captured from the jar and returned.
        // Wipe this login window's persisted session so no cookies/cache/storage
        // linger on disk between sign-ins.
        clearIcaLoginSession()
      })()
    })




    win.loadURL(ICA_LOGIN_URL).catch((e) => {
      finish({ status: 'error', error: `Failed to open ICA: ${e && e.message ? e.message : e}` })
    })
  })
}

ipcMain.handle('ica-login', async () => {
  try {
    return await icaBrowserLogin()
  } catch (e) {
    logLine(`ica-login handler error: ${e && e.stack ? e.stack : e}`)
    return { status: 'error', error: String(e && e.message ? e.message : e) }
  }
})

