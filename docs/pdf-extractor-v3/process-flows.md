# PDF Extractor V3 — Process & User Flows

This document traces the major journeys through V3 — from first launch to a completed extraction run — along with the critical backend event sequences.

---

## 1. Application Startup

From double-clicking the `.exe` to a fully interactive window.

```mermaid
sequenceDiagram
    participant User
    participant Electron as Electron main.js
    participant FS as File System
    participant Backend as backend.exe (Python)
    participant UI as React Renderer

    User->>Electron: Double-click .exe
    Electron->>Electron: findFreePort(8765)\nskip 5000 / 8080 / 47321
    Electron->>FS: Write .v3_port file
    Electron->>UI: loadURL(LOADING_HTML)\nShow splash screen immediately
    Electron->>Backend: spawn backend.exe\n--port N --data-dir %APPDATA%/PDF Extractor V3
    Backend->>Backend: argparse → set_data_dir()
    Backend->>Backend: db.init_db()\nCreate tables if not exist (WAL mode)
    Backend->>Backend: Import routers → wire FastAPI + SocketIO
    Backend->>Backend: uvicorn.run(app, port=N)
    loop Poll every 500ms (max 30s)
        Electron->>Backend: GET /api/health
        Backend-->>Electron: 200 {"status":"ok","version":"3.0.0"}
    end
    Electron->>UI: loadFile(renderer/index.html)
    Electron->>UI: executeJavaScript window.__V3_API_PORT__ = N
    UI->>UI: React app boots → routes to Home page
    User->>UI: App is ready
```

---

## 2. First-Time Setup

How a new user configures the application after first launch.

```mermaid
flowchart TD
    A["First launch\nDatabase created with empty tables"] --> B["User opens Settings page"]
    B --> C["GET /api/settings\nReturns masked default template"]
    C --> D["User enters PDF password"]
    D --> E["User fills in Box folder IDs\n(Source, Archive, Output)"]
    E --> F["User pastes Box JWT JSON\ninto the JWT text area"]
    F --> G["Click Upload JWT"]
    G --> H["POST /api/settings/jwt\nValidate JSON → db.jwt_config_set()"]
    H --> I["User clicks Test Box Connection"]
    I --> J["GET /api/settings/test/box/stream\nSSE: Read config → Auth → User → Folder"]
    J --> K{Test passed?}
    K -- No --> L["Fix Box credentials or JWT\nRe-upload JWT if needed"]
    L --> E
    K -- Yes --> M["User clicks Sign in to ICA"]
    M --> N["window.electronAPI.icaLogin()\nOpen Electron browser window"]
    N --> O["User signs in with IBMid/SSO"]
    O --> P["User opens a chat and\nSENDS ONE MESSAGE"]
    P --> Q["Electron captures\ncookie + team_id + chat_id (trusted)"]
    Q --> R["POST /api/settings\nSave ICA credentials to DB"]
    R --> S["User clicks Test ICA Connection"]
    S --> T["GET /api/settings/test/ica/stream\nSSE: Credentials → POST prompt → Poll reply"]
    T --> U{Test passed?}
    U -- No --> V["Re-open ICA login\nCapture fresh credentials"]
    V --> M
    U -- Yes --> W["Setup complete\nProceed to Sync"]
```

---

## 3. Full Processing Workflow

End-to-end from new PDFs on Box to extracted outputs ready to view.

```mermaid
flowchart TD
    A["New PDFs arrive in Box source folder"] --> B["User clicks Sync from Box"]
    B --> C["POST /api/sync/run → background thread"]
    C --> D["JWT from db.jwt_config_get()\nBox Client authenticated"]
    D --> E["Download each new .pdf\nto Local Folder"]
    E --> F["Move original to Box archive folder"]
    F --> G["Emit sync:done\nAuto-trigger run_scan()"]
    G --> H["Walk Local Folder\nRegister new PDFs as Pending\nin tracking_files table"]
    H --> I["Emit scan:done\nUI shows Pending count"]
    I --> J["User clicks Run Extraction"]
    J --> K["POST /api/extract/run → background thread"]
    K --> L["For each Pending PDF\nfrom tracking_files"]
    L --> M["Decrypt with pdf_password\nfrom config table"]
    M --> N["extract_text_by_page()\nbuild_structured_json()"]
    N --> O["Export Word + Excel + JSON\ninto dated folder"]
    O --> P["Upload 3 files to Box\noutput_folder_id"]
    P --> Q["Archive source PDF locally"]
    Q --> R["Update tracking_files\nstatus = Completed"]
    R --> S["db.log_add()\nWrite log to extraction_logs table"]
    S --> T["Emit extract:result"]
    T --> L
    L -- "all done" --> U["Emit extract:done\n{completed, failed, total}"]
    U --> V["User views outputs on View page\nor queries Chat"]
```

---

## 4. Live Sync Log Stream

How real-time sync log messages flow from Box SDK through the backend to the UI.

```mermaid
sequenceDiagram
    participant UI as React Sync Page
    participant SIO as socket.io-client
    participant Server as Backend SocketIO
    participant Worker as sync.py thread

    UI->>Server: POST /api/sync/run
    Server-->>UI: {"status":"started"}
    UI->>SIO: subscribe("sync:log")
    UI->>SIO: subscribe("sync:done")

    Worker->>Server: _emit_log("Connecting to Box…")
    Server->>SIO: emit("sync:log", {message})
    SIO-->>UI: Append to log panel

    Worker->>Server: _emit_log("Downloading: report.pdf")
    Server->>SIO: emit("sync:log")
    SIO-->>UI: Append line

    Worker->>Server: _emit_log("✅ Saved: report.pdf")
    Worker->>Server: _emit_log("📦 Archived on Box: report.pdf")
    Server->>SIO: emit("sync:log" ×2)
    SIO-->>UI: Append lines

    Worker->>Server: emit("sync:done", {downloaded:1, skipped:0, errors:[]})
    Server->>SIO: emit("sync:done")
    SIO-->>UI: Show completion summary toast
```

---

## 5. Extraction Progress Stream

Per-file progress events during extraction.

```mermaid
sequenceDiagram
    participant UI as React Extract Page
    participant SIO as socket.io-client
    participant Server as Backend SocketIO
    participant Worker as extractor.py thread

    UI->>Server: POST /api/extract/run
    Server-->>UI: {"status":"started"}
    UI->>SIO: subscribe("extract:progress")
    UI->>SIO: subscribe("extract:result")
    UI->>SIO: subscribe("extract:done")

    loop For each pending file
        Worker->>Server: emit("extract:progress", {current, total, percent, name})
        Server->>SIO: forward event
        SIO-->>UI: Update progress bar

        Worker->>Worker: Decrypt → Parse → Export → Upload → Archive
        Worker->>Worker: db.log_add() — write log to DB

        Worker->>Server: emit("extract:result", {status:"ok", fname, ref, word, excel, json, upload})
        Server->>SIO: forward event
        SIO-->>UI: Append row to results table
    end

    Worker->>Server: emit("extract:done", {completed, failed, total})
    Server->>SIO: forward event
    SIO-->>UI: Show completion toast
```

---

## 6. Settings SSE Connection Test

How the streaming "Test Box" or "Test ICA" button shows live step-by-step progress.

```mermaid
sequenceDiagram
    participant UI as Settings Page
    participant ES as EventSource
    participant API as GET /api/settings/test/box/stream
    participant Gen as test_box_stream() generator

    UI->>ES: new EventSource("/api/settings/test/box/stream")
    ES->>API: HTTP GET (keep-alive)
    API->>Gen: iterate generator

    Gen-->>API: yield {step:"Reading configuration…", state:"run"}
    API-->>ES: data: {step, state:"run"}\n\n
    ES-->>UI: Show spinner row

    Gen-->>API: yield {step:"Authenticating with Box…", state:"run"}
    ES-->>UI: Show next spinner row

    Gen-->>API: yield {step:"Authenticated ✓", state:"ok"}
    ES-->>UI: Green checkmark

    Gen-->>API: yield {step:"Box connection is working.", state:"done", detail:"..."}
    ES-->>UI: Show success summary
    UI->>ES: close()
```

---

## 7. Chat Report Lookup

How a "look up John Smith" message is processed.

```mermaid
sequenceDiagram
    participant User
    participant UI as Chat Page
    participant API as POST /api/chat/send
    participant Router as route_chat_message()
    participant Skill as skill_lookup_report()
    participant FS as JSON File Extracts/

    User->>UI: "look up John Smith"
    UI->>API: POST {message, history:[...]}
    API->>Router: route_chat_message()
    Router->>Router: _sanitize_history()\nremove any hallucinated turns
    Router->>Router: Match LOOKUP_PATTERNS regex
    Router->>Skill: skill_lookup_report("john smith")
    Skill->>FS: rglob("*.json") over JSON File Extracts/
    loop Each JSON file
        Skill->>Skill: _name_matches("john smith", subject_name)
        Skill->>Skill: Keep newest match per case_reference
    end
    Skill-->>Router: Formatted report block (plain text)
    Router-->>API: reply string
    API-->>UI: {"reply": "Subject: John Smith | Ref: RN-001 ..."}
    UI-->>User: Display in assistant chat bubble
```

---

## 8. ICA Browser Login

Credential capture via the embedded Electron browser window.

```mermaid
sequenceDiagram
    participant User
    participant Settings as Settings Page
    participant IPC as Electron ipcMain
    participant Win as ICA BrowserWindow
    participant WR as webRequest hook
    participant ICA as IBM Consulting Advantage

    User->>Settings: Click "Sign in to ICA"
    Settings->>IPC: window.electronAPI.icaLogin()
    IPC->>Win: new BrowserWindow(partition: persist:ica-login)
    Win->>ICA: loadURL(https://ibm.com/curatorai/…)
    ICA-->>Win: Login page rendered
    User->>Win: Sign in with IBMid / w3id SSO
    User->>Win: Open a chat thread and send a message
    Win->>ICA: POST /chats/{chat_id}/entries
    WR->>WR: onSendHeaders captures:\ncookie + teamid + teamname\nchat_id (trusted — from /entries POST)
    WR->>IPC: chatIdIsTrusted = true\nmaybeComplete() → finish({status:'ok', captured})
    IPC->>Win: win.close() (50ms delay)
    IPC-->>Settings: {status:'ok', captured:{full_cookie, team_id, chat_id, …}}
    Settings->>Settings: POST /api/settings\n(save captured credentials to DB)
    Settings-->>User: "ICA credentials captured & saved ✓"
```

---

## 9. Application Shutdown

Clean teardown when the user closes the window.

```mermaid
flowchart TD
    A["User closes Electron window"] --> B["app: window-all-closed"]
    B --> C["app.quit() called (non-macOS)"]
    C --> D["app: will-quit event"]
    D --> E["pythonProcess.kill()\nTerminate backend.exe"]
    E --> F["Delete .v3_port file\nfrom userData directory"]
    F --> G["Electron process exits cleanly"]
```
