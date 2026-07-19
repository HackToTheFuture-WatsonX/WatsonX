/**
 * preload.js — Electron preload script for PDF Extractor V3.
 * Exposes a minimal context bridge so the renderer can query the chosen API port
 * and drive the browser-assisted ICA login flow.
 */
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  getApiPort: () => ipcRenderer.invoke('get-api-port'),

  /**
   * Open a browser-assisted ICA login window. The user signs in normally
   * (IBMid / SSO); the main process captures the session cookie and the
   * team/chat identifiers from the authenticated ICA API traffic.
   *
   * Resolves to:
   *   { status: 'ok', captured: { full_cookie, team_id, team_name, chat_id, base_url } }
   *   { status: 'cancelled' }              — user closed the window before capture
   *   { status: 'error', error: string }   — something went wrong
   */
  icaLogin: () => ipcRenderer.invoke('ica-login'),

  /** True when running inside Electron (vs. a plain browser during dev). */
  isElectron: true,
})
