# PDF Extractor V2 — Process Flows

## User Journey: First-Time Setup

```mermaid
flowchart TD
    A[Install Python 3.10+] --> B[cd PDF Extractor V2\npip install -r requirements.txt]
    B --> C[Go to app.box.com/developers/console]
    C --> D[Create Custom App → OAuth 2.0]
    D --> E[Generate Developer Token\nvalid for 60 minutes]
    E --> F[Fill in config.json:\nclient_id, client_secret, access_token\nfolder_id, output_folder_id]
    F --> G[Optional: set sync.auto_sync_enabled = true]
    G --> H[Optional: configure ICA credentials]
    H --> I[Double-click Launch.vbs\nor python pdf_extractor_ui_v2.py]
    I --> J[App opens — if auto_sync_enabled,\nfirst sync fires after 10 seconds]
```

---

## User Journey: Daily Workflow (Manual Sync)

```mermaid
flowchart TD
    A[Open app] --> B[Go to Sync Box to Local]
    B --> C[Click Sync Now]
    C --> D{Sync OK?}
    D -- No: token expired --> E[Update access_token in config.json\nSync again]
    D -- Yes --> F[PDFs downloaded to Local Folder/\nScan runs automatically]
    F --> G[Go to Extract Files]
    G --> H[Click Start Extraction]
    H --> I[Wait — exports written locally\nUploaded to Box\nSource PDFs archived]
    I --> J[Review result summary]
    J --> K[Optional: View Extracted Files\nto open or verify outputs]
    K --> L[Optional: AI Assistant\nlook up a report]
```

---

## User Journey: Auto-Sync Daily Workflow

```mermaid
flowchart TD
    A[Open app] --> B{auto_sync_enabled?}
    B -- Yes --> C[App waits 10 seconds\nthen auto-syncs]
    C --> D[PDFs downloaded\nAuto-scan runs]
    D --> E[Pending file list is ready]
    B -- No --> E2[Manual: Sync Box to Local\nthen Scan Local Folder]
    E & E2 --> F[Click Extract Files\nStart Extraction]
    F --> G[Outputs written and uploaded\nSource PDFs archived]
```

---

## Backend Process: Sync Box to Local

```mermaid
flowchart TD
    START([Sync triggered]) --> AUTH[Connect to Box OAuth2]
    AUTH --> OK{Auth OK?}
    OK -- No --> ERR[Show error in status bar\nReschedule if auto-sync]
    OK -- Yes --> LIST[List PDFs in source folder_id]
    LIST --> LOOP{For each PDF}
    LOOP --> DL[Download to Local Folder/<filename>]
    DL --> EXISTS{File already\nexists locally?}
    EXISTS -- Yes + same size --> SKIP[Skip download]
    EXISTS -- No --> WRITE[Write to disk]
    SKIP & WRITE --> LOOP
    LOOP -- "Done" --> SCAN_AUTO[Auto-trigger Scan Local Folder]
    SCAN_AUTO --> UPDATE[Register new PDFs as Pending]
    UPDATE --> RESCHEDULE[Reschedule next auto-sync\nif auto_sync_enabled]
```

---

## Backend Process: Extraction Pipeline (V2)

```mermaid
flowchart TD
    START([Start Extraction]) --> LOCK{Already running?}
    LOCK -- Yes --> SKIP([Return busy])
    LOCK -- No --> FLAG[Set running flag\nDisable Start button]

    FLAG --> LOAD[Load config.json + tracking_db.json]
    LOAD --> LOOP{For each Pending PDF\nin Local Folder/}

    LOOP --> READ[Read PDF from local disk]
    READ --> DECRYPT{Encrypted?}
    DECRYPT -- Yes --> PASS[Authenticate with pdf_password]
    PASS --> OK{Password OK?}
    OK -- No --> FAIL[Log error, keep Pending]
    OK -- Yes --> PARSE[Parse via shared engine]
    DECRYPT -- No --> PARSE

    PARSE --> EXPORT[Export to Local Folder/Extracted/\n.docx + .xlsx + .json + dated path]

    EXPORT --> UPLOAD{output_folder_id\nconfigured?}
    UPLOAD -- Yes --> BOXUP[Upload 3 files to Box\noutput_folder_id / dated path]
    UPLOAD -- No --> SKIP_UP[Skip upload]

    BOXUP & SKIP_UP --> ARCHIVE{archive_folder_id\nconfigured?}
    ARCHIVE -- Yes --> MOVE[Move source PDF to\nBox archive_folder_id]
    ARCHIVE -- No --> SKIP_ARCH[Skip archive]

    MOVE & SKIP_ARCH --> MARK[Mark Completed in tracking_db]
    MARK --> LOG[Write .log to Log History/]
    LOG --> LOOP

    LOOP -- "All done" --> DONE[Show summary\nRe-enable Start button]
    FAIL --> LOOP
```

---

## Process: Box Token Refresh (V2)

Same as V1. Applies before Sync and before Extract (if extracting from Box directly):

```mermaid
flowchart TD
    A[Sync or Extract fails with 401 error]
    A --> B[Open browser: app.box.com/developers/console]
    B --> C[Select your app → Configuration tab]
    C --> D[Generate Developer Token]
    D --> E[Copy token]
    E --> F[Open PDF Extractor V2/config.json]
    F --> G[Replace box.access_token]
    G --> H[Save → Retry Sync or Extract]
```
