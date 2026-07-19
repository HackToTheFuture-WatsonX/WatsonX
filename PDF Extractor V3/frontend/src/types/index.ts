// Shared TypeScript interfaces for PDF Extractor V3

export interface TrackedFile {
  key:            string
  name:           string
  status:         'Pending' | 'Completed'
  last_extracted: string | null
  ref_number:     string | null
  local_path:     string
}

export interface ScanResult {
  files:     TrackedFile[]
  total:     number
  pending:   number
  completed: number
}

export interface ExtractResult {
  status:  'ok' | 'error'
  fname:   string
  ref?:    string
  word?:   string
  excel?:  string
  json?:   string
  upload?: string
  error?:  string
}

export interface ViewFile {
  name:  string
  path:  string
  mtime: string
}

export interface ViewGroup {
  ref:   string
  files: ViewFile[]
}

export interface ViewSection {
  label:  string
  type:   string
  ext:    string
  count:  number
  groups: ViewGroup[]
}

export interface InsightsStats {
  total:     number
  completed: number
  pending:   number
}

export interface ChartBucket {
  period:    string
  completed: number
  pending:   number
}

export interface InsightsData {
  stats:  InsightsStats
  chart:  ChartBucket[]
  period: string
}

export interface ChatMessage {
  role:    'user' | 'assistant' | 'system'
  content: string
}

export interface LinksPayload {
  header: string
  items:  ExtractResult[]
}

// ── Settings / configuration ────────────────────────────────────────────────
export interface AppConfig {
  pdf_password: string
  box: {
    folder_id:         string
    archive_folder_id: string
    output_folder_id:  string
    jwt_config_file:   string
  }
  local: {
    local_folder:     string
    extracted_folder: string
    archive_folder:   string
  }
  sync: {
    auto_sync_enabled:          boolean
    auto_sync_interval_minutes: number
  }
  ica: {
    full_cookie:  string
    team_id:      string
    team_name:    string
    assistant_id: string
    chat_id:      string
    base_url:     string
  }
  settings: {
    search_subfolders:          boolean
    file_extension:             string
    overwrite_existing_exports: boolean
    log_activity:               boolean
    chat_enabled:               boolean
  }
}

// ── Electron bridge (preload contextBridge) ─────────────────────────────────
export interface IcaCaptured {
  full_cookie: string
  team_id:     string
  team_name:   string
  chat_id:     string
  base_url:    string
}

export type IcaLoginResult =
  | { status: 'ok'; captured: IcaCaptured }
  | { status: 'cancelled' }
  | { status: 'error'; error: string }

export interface ElectronAPI {
  getApiPort: () => Promise<number>
  icaLogin:   () => Promise<IcaLoginResult>
  isElectron: boolean
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
    __V3_API_PORT__?: number
  }
}

export interface SettingsStatus {
  box: {
    configured:   boolean
    jwt_uploaded: boolean
    folder_id:    boolean
  }
  ica: {
    configured:  boolean
    full_cookie: boolean
    team_id:     boolean
    chat_id:     boolean
  }
  pdf_password: boolean
  ready:        boolean
}

