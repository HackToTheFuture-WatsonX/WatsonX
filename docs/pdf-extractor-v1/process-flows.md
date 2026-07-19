# PDF Extractor V1 — Process Flows

## User Journey: First-Time Setup

```mermaid
flowchart TD
    A[Install Python 3.10+] --> B[cd PDF Extractor\npip install -r requirements.txt]
    B --> C[Go to app.box.com/developers/console]
    C --> D[Create Custom App → OAuth 2.0]
    D --> E[Generate Developer Token\nvalid for 60 minutes]
    E --> F[Fill in config.json:\nclient_id, client_secret,\naccess_token, folder_id]
    F --> G[Optional: configure ICA credentials\nusing ICA Cookie Parser tool]
    G --> H[Double-click Launch.vbs\nor run python pdf_extractor_ui.py]
    H --> I[App opens — Home screen]
```

---

## User Journey: Daily Extraction Workflow

```mermaid
flowchart TD
    A[Open app → Home screen] --> B[Click Check Box Folder card]
    B --> C[Click Scan Box Folder button]
    C --> D{Scan succeeds?}
    D -- No: token expired --> E[Update access_token in config.json\nScan again]
    D -- Yes --> F[Review Pending file table]
    F --> G{Any Pending files?}
    G -- No --> H[Nothing to do — check again later]
    G -- Yes --> I[Click Extract Files card]
    I --> J[Click Start Extraction]
    J --> K[Wait — progress bar animates]
    K --> L[Review result cards\n✅ Completed / ❌ Failed]
    L --> M[Optional: open Insights\ncheck chart]
    M --> N[Optional: open AI Assistant\nask about a report]
```

---

## Backend Process: Extraction Pipeline

```mermaid
flowchart TD
    START([Start Extraction]) --> CHECK{Already running?}
    CHECK -- Yes --> SKIP([Ignore — show busy message])
    CHECK -- No --> FLAG[Set _running = True\nDisable Start button\nStart progress bar]

    FLAG --> LOAD[Load config.json\nLoad tracking_db.json]
    LOAD --> AUTH[Connect to Box OAuth2]
    AUTH --> LOOP{For each\nPending PDF}

    LOOP --> DL[Download PDF bytes\nfrom Box into memory]
    DL --> DECRYPT{Encrypted?}
    DECRYPT -- Yes --> PASS[Authenticate with pdf_password]
    PASS --> OK{Password\ncorrect?}
    OK -- No --> FAIL[Log error\nAdd ❌ card\nKeep Pending]
    OK -- Yes --> PARSE[Extract text per page\nParse via shared engine]
    DECRYPT -- No --> PARSE

    PARSE --> EXPORT[Export .docx / .xlsx / .json\nto dated local folders]
    EXPORT --> MARK[Mark Completed\nUpdate tracking_db.json]
    MARK --> LOG[Write .log to Log History/]
    LOG --> CARD[Add ✅ result card to UI]
    CARD --> LOOP

    LOOP -- "All done" --> DONE[Stop progress bar\nRe-enable Start button\nSet _running = False]
    FAIL --> LOOP
```

---

## Process: Box Token Refresh

The OAuth2 Developer Token expires every **60 minutes**. Here is the refresh flow:

```mermaid
flowchart TD
    A[Scan or Extract fails\nStatus bar shows token-expired warning]
    A --> B[Open browser:\nhttps://app.box.com/developers/console]
    B --> C[Select your app → Configuration tab]
    C --> D[Click Generate Developer Token]
    D --> E[Copy the new token]
    E --> F[Open PDF Extractor/config.json]
    F --> G[Replace box.access_token value]
    G --> H[Save config.json]
    H --> I[Retry Scan or Extraction]
```

---

## Process: ICA Credential Refresh

ICA session cookies expire periodically. When the AI stops responding:

```mermaid
flowchart TD
    A[AI returns error or empty reply]
    A --> B[Open ICA Cookie Parser:\nICA Cookie Parser/ica_cookie_parser.html]
    B --> C[Open ICA in browser\nSend any test message]
    C --> D[Open DevTools → Network tab]
    D --> E[Click the entries POST request\nHeaders tab → copy all headers]
    E --> F[Paste into Cookie Parser\nClick Parse & Generate Config]
    F --> G[Copy the ica block]
    G --> H[Paste into PDF Extractor/config.json\nReplace the ica section]
    H --> I[Save config.json\nRestart the AI Assistant chat]
```

---

## Process: Dated Output Folder Creation

Every export is written into a consistent dated path:

```mermaid
flowchart LR
    ROOT["Word Extracts/\n(or CSV / JSON)"]
    YEAR["2026/"]
    MONTH["Jul_2026_Extracts/"]
    WEEK["Week_28/"]
    DAY["2026-07-10/"]
    REF["RN-123456_789_10/"]
    FILE["RN-123456_789_10.docx"]

    ROOT --> YEAR --> MONTH --> WEEK --> DAY --> REF --> FILE
```

Folders are created automatically with `Path.mkdir(parents=True, exist_ok=True)`.
