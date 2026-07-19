# PDF Extractor V3 — Process & User Flows

## Overview

This document traces the major journeys through V3 — from first launch to a completed extraction — and the critical backend paths that power them.

---

## 1. Application Startup Flow

The sequence from double-clicking the `.exe` to a fully interactive window.

```mermaid
sequenceDiagram
    participant User
    participant Electron as Electron main.js
    participant FS as File System
    participant Backend as backend.exe (Python)
    participant UI as React Renderer

    User->>Electron: Double-click .exe
    Electron->>Electron: findFreePort(8765)\nskip 5000/8080/47321
    Electron->>FS: Write .v3_port file
    Electron->>FS: ensureUserConfig()\ncopy config.json template if missing
    Electron->>UI: loadURL(LOADING_HTML)\nShow splash screen immediately
    Electron->>Backend: spawn backend.exe\n--port N --data-dir %APPDATA%/PDF Extractor V3
    Backend->>Backend: argparse → set_data_dir()\nimport routers, wire SocketIO + FastAPI
    Backend->>Backend: uvicorn.run(app, port=N)
    loop Poll every 500ms (max 30s)
        Electron->>Backend: GET /api/health
        Backend-->>Electron: 200 {"status":"ok"}
    end
    Electron->>UI: loadFile(renderer/index.html)
    UI->>Backend: executeJavaScript window.__V3_API_PORT__ = N
    UI->>UI: React app boots\nRoutes to Home page
    User->>UI: App is ready
```

---

## 2. First-Time Setup Flow

How a new user configures the application after first launch.

```mermaid
flowchart TD
    A["First launch\nconfig.json created as template"] --> B["User navigates to Settings"]
    B --> C["GET /api/settings\nreturns masked template config"]
    C --> D["User fills in PDF password"]
    D --> E["User fills in Box folder IDs"]
    E --> F["User uploads box_jwt_config.json\nvia JWT Upload button"]
    F --> G["POST /api/settings/jwt\nvalidate + save JSON"]
    G --> H["User clicks Test Box Connection"]
    H --> I["GET /api/settings/test/box/stream\nSSE: Reading config → Auth → User → Folder"]
    I --> J{Test passed?}
    J -- No --> K["Fix Box credentials\nor JWT file"]
    K --> E
    J -- Yes --> L["User clicks Sign in to IBM Consulting Advantage"]
    L --> M["window.electronAPI.icaLogin()\nopen ICA browser window"]
    M --> N["User signs in with IBMid/SSO"]
    N --> O["User sends a test message in ICA chat"]
    O --> P["Electron captures cookie + team_id + chat_id\nauto-closes window"]
    P --> Q["POST /api/settings\nsave ICA credentials"]
    Q --> R["User clicks Test ICA Connection"]
    R --> S["GET /api/settings/test/ica/stream\nSSE: Credentials → POST prompt → Poll reply"]
    S --> T{Test passed?}
    T -- No --> U["Reopen ICA login window\ncapture fresh credentials"]
    T -- Yes --> V["Setup complete\nUser proceeds to Sync"]
```

---

## 3. Full Processing Workflow

The end-to-end journey from new PDFs arriving in Box to extracted outputs ready to view.

```mermaid
flowchart TD
    A["New PDFs arrive\nin IBM Box source folder"] --> B["User clicks Sync from Box"]
    B --> C["POST /api/sync/run → background thread"]
    C --> D["JWTAuth → Box Client\nList folder items"]
    D --> E["Download each new .pdf\nto Local Folder"]
    E --> F["Move original to\nBox archive folder"]
    F --> G["sync:done emitted\nScan triggered automatically"]
    G --> H["scanner.py walk Local Folder\nRegister new PDFs as Pending"]
    H --> I["scan:done emitted\nUI shows Pending count"]
    I --> J["User clicks Run Extraction"]
    J --> K["POST /api/extract/run → background thread"]
    K --> L["For each Pending PDF"]
    L --> M["Decrypt with pdf_password\nopen_and_decrypt_pdf()"]
    M --> N["Extract text by page\nbuild_structured_json()"]
    N --> O["Export Word + Excel + JSON\nto dated folder hierarchy"]
    O --> P["Upload all 3 files to Box\noutput_folder_id"]
    P --> Q["Archive source PDF locally"]
    Q --> R["Update tracking_db\nstatus = Completed"]
    R --> S["Write extraction log\nLog History/"]
    S --> T["extract:result emitted per file"]
    T --> L
    L -- "all done" --> U["extract:done emitted"]
    U --> V["User views outputs\non View page or Chat"]
```

---

## 4. Live Sync Log Stream

How real-time sync log messages flow from Box SDK through the backend to the UI.

```mermaid
sequenceDiagram
    participant UI as React Sync Page
    participant SIO as socket.io-client
    participant Server as Backend SocketIO
    participant Sync as sync.py worker thread

    UI->>Server: POST /api/sync/run
    Server-->>UI: {"status":"started"}
    UI->>SIO: subscribe("sync:log")
    UI->>SIO: subscribe("sync:done")

    Sync->>Server: _emit_log("Connecting to Box…")
    Server->>SIO: emit("sync:log", {message})
    SIO-->>UI: update log panel

    Sync->>Server: _emit_log("Downloading: report.pdf")
    Server->>SIO: emit("sync:log", {message})
    SIO-->>UI: append to log

    Sync->>Server: _emit_log("✅ Saved: report.pdf")
    Sync->>Server: _emit_log("📦 Archived on Box")
    Server->>SIO: emit("sync:log" ×2)
    SIO-->>UI: append lines

    Sync->>Server: emit("sync:done", {downloaded:1, skipped:0, errors:[]})
    Server->>SIO: emit("sync:done")
    SIO-->>UI: show summary toast
```

---

## 5. Extraction Progress Stream

Per-file progress events during extraction.

```mermaid
sequenceDiagram
    participant UI as React Extract Page
    participant SIO as socket.io-client
    participant Server as Backend SocketIO
    participant Ext as extractor.py thread

    UI->>Server: POST /api/extract/run
    Server-->>UI: {"status":"started"}
    UI->>SIO: subscribe("extract:progress")
    UI->>SIO: subscribe("extract:result")
    UI->>SIO: subscribe("extract:done")

    loop For each pending file
        Ext->>Server: emit("extract:progress", {current, total, percent, name})
        Server->>SIO: emit("extract:progress")
        SIO-->>UI: update progress bar

        Ext->>Server: emit("extract:result", {status:"ok", fname, ref, word, excel, json, upload})
        Server->>SIO: emit("extract:result")
        SIO-->>UI: append to results table
    end

    Ext->>Server: emit("extract:done", {completed, failed, total})
    Server->>SIO: emit("extract:done")
    SIO-->>UI: show completion toast
```

---

## 6. Chat: Report Lookup Flow

How a "look up John Smith" message is processed end-to-end.

```mermaid
sequenceDiagram
    participant User
    participant UI as Chat Page
    participant API as POST /api/chat/send
    participant Router as route_chat_message()
    participant Skill as skill_lookup_report()
    participant FS as JSON File Extracts/

    User->>UI: "look up John Smith"
    UI->>API: POST {message: "look up John Smith", history: [...]}
    API->>Router: route_chat_message()
    Router->>Router: _sanitize_history()\nremove hallucinated turns
    Router->>Router: Match LOOKUP_PATTERNS regex
    Router->>Skill: skill_lookup_report("john smith")
    Skill->>FS: rglob("*.json") over JSON File Extracts/
    loop Each JSON file
        Skill->>Skill: _name_matches("john smith", subject_name)
        Skill->>Skill: Keep newest match per case_reference
    end
    Skill-->>Router: Formatted report block (text)
    Router-->>API: reply string
    API-->>UI: {"reply": "Subject: John Smith | Ref: BC-2024-001 ..."}
    UI-->>User: Display in chat bubble
```

---

## 7. Settings SSE Connection Test Flow

How the "Test Box" button shows live step-by-step progress.

```mermaid
sequenceDiagram
    participant UI as Settings Page
    participant ES as EventSource (browser)
    participant API as GET /api/settings/test/box/stream
    participant Gen as test_box_stream()

    UI->>ES: new EventSource("/api/settings/test/box/stream")
    ES->>API: HTTP GET (SSE)
    API->>Gen: iterate generator

    Gen-->>API: yield {step:"Reading configuration…", state:"run"}
    API-->>ES: data: {"step":"Reading configuration…","state":"run"}\n\n
    ES-->>UI: show step row with spinner

    Gen-->>API: yield {step:"Authenticating with Box…", state:"run"}
    API-->>ES: SSE event
    ES-->>UI: show next step

    Gen-->>API: yield {step:"Authenticated ✓", state:"ok"}
    ES-->>UI: green checkmark

    Gen-->>API: yield {step:"Box connection is working.", state:"done", detail:"..."}
    ES-->>UI: show success summary
    UI->>ES: close()
```

---

## 8. ICA Browser Login Flow

Credential capture via the embedded Electron browser window.

```mermaid
sequenceDiagram
    participant User
    participant Settings as Settings Page
    participant IPC as Electron ipcMain
    participant Win as ICA BrowserWindow
    participant WR as webRequest hook
    participant ICA as IBM Consulting Advantage

    User->>Settings: Click "Sign in to IBM Consulting Advantage"
    Settings->>IPC: window.electronAPI.icaLogin()
    IPC->>Win: new BrowserWindow(partition: persist:ica-login)
    Win->>ICA: loadURL(https://ibm.com/curatorai/…)
    ICA-->>Win: Login page
    User->>Win: Sign in with IBMid / w3id SSO
    ICA-->>Win: Authenticated UI

    User->>Win: Type and send a message in ICA chat
    Win->>ICA: POST /chats/{chat_id}/entries
    WR->>WR: onSendHeaders captures:\ncookie + teamid + teamname + chat_id (trusted)
    WR->>IPC: maybeComplete() → finish({status:'ok', captured})
    IPC->>Win: win.close()
    IPC-->>Settings: {status:'ok', captured:{full_cookie, team_id, chat_id, …}}
    Settings->>Settings: POST /api/settings (save credentials)
    Settings-->>User: "ICA credentials saved ✓"
```

---

## 9. Application Shutdown Flow

Clean teardown when the user closes the window.

```mermaid
flowchart TD
    A["User closes Electron window"] --> B["app: window-all-closed"]
    B --> C["app.quit() on non-macOS"]
    C --> D["app: will-quit"]
    D --> E["pythonProcess.kill()\nTerminate backend.exe"]
    E --> F["Delete .v3_port file\nfrom userData"]
    F --> G["Electron process exits"]
```
