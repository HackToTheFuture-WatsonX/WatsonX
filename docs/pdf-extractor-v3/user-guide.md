# PDF Extractor V3 — User Guide

This guide walks you through every page and action in PDF Extractor V3, from first launch to viewing your extracted reports. No technical knowledge is required.

---

## Table of Contents

1. [Before You Start](#1-before-you-start)
2. [Launching the Application](#2-launching-the-application)
3. [Settings Page — Configure Everything](#3-settings-page--configure-everything)
   - [PDF Password](#31-pdf-password)
   - [IBM Box Credentials](#32-ibm-box-credentials)
   - [Box JWT Config Upload](#33-box-jwt-config-upload)
   - [Test Box Connection](#34-test-box-connection)
   - [IBM Consulting Advantage (ICA) — Sign In](#35-ibm-consulting-advantage-ica--sign-in)
   - [Test ICA Connection](#36-test-ica-connection)
   - [Extraction & Sync Options](#37-extraction--sync-options)
   - [Save Settings](#38-save-settings)
4. [Sync Page — Download PDFs from Box](#4-sync-page--download-pdfs-from-box)
5. [Scan Page — Register PDFs for Extraction](#5-scan-page--register-pdfs-for-extraction)
6. [Extract Page — Process Reports](#6-extract-page--process-reports)
7. [View Page — Browse Extracted Files](#7-view-page--browse-extracted-files)
8. [Insights Page — Stats & Charts](#8-insights-page--stats--charts)
9. [Chat Page — Ask Detective Conan](#9-chat-page--ask-detective-conan)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Before You Start

You will need the following before configuring V3:

| What | Where to get it |
|---|---|
| **PDF password** | The password used to open background check PDFs (ask your team admin) |
| **Box source folder ID** | Log in to app.box.com → open the source folder → copy the number from the URL (e.g. `https://app.box.com/folder/123456789` → ID is `123456789`) |
| **Box archive folder ID** | Same as above, for the folder where processed originals are moved |
| **Box output folder ID** | Same as above, for the folder where extracted Word/Excel/JSON files are uploaded |
| **Box JWT config JSON** | Log in to app.box.com/developers/console → your app → Configuration → App Settings → Generate a Public/Private Keypair → download the JSON file |
| **ICA access** | An active IBM Consulting Advantage (CuratorAI) account accessible via `servicesessentials.ibm.com` |

You do **not** need Python, Node.js, or any other software installed. Everything is bundled inside the `.exe`.

---

## 2. Launching the Application

1. Double-click `PDF-Extractor-V3-Portable-3.0.0.exe` (or the installed shortcut).
2. A dark splash screen appears — **"Starting backend service…"** This is normal. The embedded Python backend is warming up. It takes about 5–15 seconds on first launch.
3. Once the backend is ready, the splash is replaced by the Home page.

> **If the splash stays for more than 30 seconds** and then shows an error dialog, see [Troubleshooting](#10-troubleshooting).

### The Home Page

The Home page shows five quick-access cards. Click any card to jump directly to that page.

| Card | What it opens |
|---|---|
| Scan Local Folder | Register PDFs for extraction |
| Sync Box to Local | Download PDFs from IBM Box |
| Extract Files | Run the extraction pipeline |
| View Extracted Files | Browse Word / Excel / JSON outputs |
| Chat with AI Assistant | Ask Detective Conan about reports |

The **sidebar** on the left is always visible and shows the same navigation links. The sun/moon icon at the top right toggles dark and light mode.

---

## 3. Settings Page — Configure Everything

On first launch, go to **Settings** (gear icon in the sidebar) before doing anything else. All credentials are stored securely in the application database — you only need to enter them once.

The status pills at the top of the page show at a glance which sections are configured:

| Pill | Meaning |
|---|---|
| ✅ **Box** | Box folder IDs + JWT uploaded and verified |
| ✅ **JWT** | Box JWT JSON uploaded to the database |
| ✅ **ICA** | ICA session cookie, team ID, and chat ID are all set |
| ✅ **PDF Password** | PDF decryption password is saved |
| ✅ **Ready** | Minimum configuration to sync and extract is complete |

---

### 3.1 PDF Password

Enter the password used to decrypt the background check PDF files. This is the same password for all reports from Corpnet Global Corp.

- Click the eye icon to reveal what you typed (if your browser supports it).
- The password is stored in the database and never shown again — the field will display `••••••••` after saving.

---

### 3.2 IBM Box Credentials

Fill in the three Box folder IDs:

| Field | What to enter |
|---|---|
| **Source Folder ID** | The Box folder where new PDF reports arrive |
| **Archive Folder ID** | The Box folder where processed originals are moved after sync |
| **Output Folder ID** | The Box folder where extracted Word / Excel / JSON files are uploaded |

To find a folder ID:
1. Open [app.box.com](https://app.box.com)
2. Navigate to the folder
3. Copy the number from the browser URL — e.g. `https://app.box.com/folder/`**`123456789`**

---

### 3.3 Box JWT Config Upload

The Box JWT config is a JSON file containing a service-account cryptographic key that lets V3 access Box without a user login.

**How to upload it:**
1. Open the JSON file you downloaded from the Box Developer Console in a text editor (Notepad, VS Code, etc.)
2. Select All → Copy
3. Paste the full JSON content into the **Box JWT Config JSON** text area on the Settings page
4. Click **Upload JWT**
5. You should see **"JWT config saved ✓"**

> **Note:** The JWT JSON is stored in the database — you do not need to keep the file anywhere after uploading it. If you need to replace it later, just paste the new content and click Upload JWT again.

---

### 3.4 Test Box Connection

After uploading the JWT and filling in the folder IDs, click **Test Box** to verify everything works.

A live step log will appear below the button showing:

```
⟳ Reading configuration…
⟳ Authenticating with Box using JWT service account…
✅ Authenticated with Box ✓
⟳ Fetching current Box user…
✅ Signed in as service-account@your-org.com ✓
⟳ Opening configured folder (id 123456789)…
✅ Folder "Reports Inbox" reachable ✓
✅ Box connection is working.
```

If any step fails, the error detail is shown inline. Common issues:

| Error | Fix |
|---|---|
| "Box JWT config file not found" | Upload the JWT JSON (Section 3.3) |
| "Box authentication failed" | The JWT JSON is invalid or expired — re-download from Box Developer Console |
| "Could not open the configured folder" | The folder ID is wrong or the service account lacks access |

---

### 3.5 IBM Consulting Advantage (ICA) — Sign In

ICA is the AI backend that powers the Chat page for general questions. Setting it up is optional — the Chat page works without ICA for all built-in commands (look up, scan, extract, file status, logs).

**The easiest way to set up ICA is the Sign In button:**

1. Click **Sign in to ICA**.
2. An IBM Consulting Advantage browser window opens.
3. Sign in with your IBMid or w3id SSO credentials.
4. Once signed in, **open any chat thread** and **send at least one message** (e.g. type "hello" and press Enter).
5. The window closes automatically — credentials are captured and saved.
6. You should see: **"Signed in — ICA credentials captured & saved ✓"**

> **Why do I need to send a message?** The application needs to observe a real chat request to capture your Chat ID. Simply logging in is not enough — you must send at least one message so the chat thread is initialised.

> **If the window closes before you send a message:** You will see "Login window closed before a message was sent." Re-click Sign in to ICA, sign in again, and send a message.

**Manual ICA setup** (alternative): If the automatic login does not work, you can paste credentials manually:
- **Team ID** — the UUID of your IBM team
- **Team Name** — your team name (URL-encoded, e.g. `My%20Team`)
- **Chat ID** — the UUID of an initialised chat thread
- **Full Cookie** — the full `Cookie:` header value from an authenticated ICA request (captured from browser DevTools → Network tab)

---

### 3.6 Test ICA Connection

After setting up ICA credentials, click **Test ICA** to verify.

The test sends a ping message to ICA and waits for a reply. This can take **up to 5 minutes** — the live step log shows a heartbeat update every 2 seconds:

```
✅ Credentials present (cookie, team ID, chat ID) ✓
⟳ Sending test prompt "ping — connection test" to ICA…
✅ Prompt accepted — waiting for a reply…
⟳ Waiting for ICA response… (6s / up to 300s)
⟳ Waiting for ICA response… (8s / up to 300s)
…
✅ Reply received from ICA ✓
✅ ICA connection is working.
```

Click **Cancel** at any time to stop the test.

If the test fails, the most common causes are:
- **Expired session cookie** — click Sign in to ICA again and re-capture credentials
- **Wrong chat ID** — the chat thread was never initialised; sign in and send one message
- **ICA service unavailable** — try again in a few minutes

---

### 3.7 Extraction & Sync Options

| Option | Default | Description |
|---|---|---|
| Search subfolders when scanning | ✅ On | Recursively scan subfolders inside Local Folder |
| Overwrite existing exports | ❌ Off | Re-export files even if a `.docx` / `.xlsx` / `.json` already exists |
| Log activity to history | ✅ On | Write an extraction log entry to the database for every processed file |
| Enable automatic Box sync | ❌ Off | Auto-sync from Box at the configured interval *(scheduler not yet active — see Improvements)* |
| File Extension | `.pdf` | File type to look for during scanning |
| Auto-Sync Interval (minutes) | `30` | How often to auto-sync when enabled |

---

### 3.8 Save Settings

Click **Save Settings** (top right) after making any changes. A green confirmation message **"Settings saved successfully"** appears briefly.

You can also use the **Clear** button next to each section to blank out just that section's fields and save immediately. **Clear All** (top right, next to Save) wipes every field at once — the Box JWT file in the database is preserved.

---

## 4. Sync Page — Download PDFs from Box

The Sync page downloads new PDFs from the Box source folder to your local machine.

**Steps:**
1. Go to **Sync** in the sidebar.
2. Click **Sync from Box**.
3. Watch the live log panel. Each line shows what is happening:
   - `Connecting to Box (source folder 123456789)…`
   - `Downloading: RN-123456_789_10.pdf`
   - `✅ Saved: RN-123456_789_10.pdf`
   - `📦 Archived on Box: RN-123456_789_10.pdf`
   - `Sync complete — 3 downloaded, 1 skipped, 0 error(s).`

4. After the sync completes, a **folder scan runs automatically** — new files are immediately registered as Pending.

**What "Skip" means:** A file is skipped if a file with the same name already exists in your Local Folder. It is not downloaded again.

**What "Archived on Box" means:** After a file is saved locally, the original on Box is moved to the Archive Folder ID you configured. This prevents re-downloading the same file on the next sync.

> **If no files appear:** Check that your Box source folder contains PDF files and that the Source Folder ID in Settings is correct.

---

## 5. Scan Page — Register PDFs for Extraction

The Scan page walks your local folder and registers every PDF as "Pending" in the tracking database.

**You normally don't need to run this manually** — it runs automatically after every sync. Use it when:
- You have dropped PDF files manually into the Local Folder
- You want to refresh the status list after making changes to the folder

**Steps:**
1. Go to **Scan** in the sidebar.
2. Click **Scan Folder**.
3. The file table updates in real time as each PDF is found.
4. When complete, you see a summary: total files, how many are Pending, how many are Completed.

**The file table shows:**

| Column | Meaning |
|---|---|
| File Name | The PDF filename |
| Status | **Pending** (not yet extracted) or **Completed** (extracted) |
| Reference | The case reference number (filled in after extraction) |
| Last Extracted | Timestamp of the most recent successful extraction |

> **Files in `Extracted/` and `Archive/` subfolders are automatically ignored** by the scanner — only the unprocessed files in the root of Local Folder are registered.

---

## 6. Extract Page — Process Reports

The Extract page runs the extraction pipeline on every Pending PDF.

**What extraction does for each file:**
1. Opens and decrypts the PDF using the PDF password
2. Reads the report text page by page
3. Parses the cover page, employment checks, reference checks, and database checks
4. Exports a formatted **Word document** (`.docx`), **Excel workbook** (`.xlsx`), and **JSON data file** (`.json`)
5. Uploads all three files to your Box output folder
6. Moves the source PDF to the local Archive folder
7. Writes a log entry to the database

**Steps:**
1. Go to **Extract** in the sidebar.
2. Check the pending file count — it should be greater than zero. If not, run a Sync or Scan first.
3. Click **Run Extraction**.
4. A progress bar appears for each file being processed:

```
Processing file 2 of 5 (40%) — RN-123456_789_10.pdf
```

5. As each file completes, a result row appears:

| Result | Meaning |
|---|---|
| ✅ **ok** | File extracted, exported, and uploaded successfully |
| ❌ **error** | Extraction failed — see the error message for details |

6. When all files are done, a summary toast appears: "Extraction complete — 5 completed, 0 failed."

> **Completed files are not re-processed.** Only Pending files are extracted. To re-process a file, you would need to reset it to Pending (currently requires a manual database edit — see Improvements for a planned UI).

> **If a file fails with "wrong password":** Update the PDF password on the Settings page and run extraction again. Failed files remain Pending.

---

## 7. View Page — Browse Extracted Files

The View page shows all extracted output files, organised by type and case reference.

**Layout:**
- Three sections: **Word Documents**, **Excel Workbooks**, **JSON Files**
- Within each section, files are grouped by **case reference** (the folder name)
- Files are sorted by modification time — newest first

**To open a file:**
1. Go to **View** in the sidebar.
2. Expand the section (Word, Excel, or JSON).
3. Find the case reference group.
4. Click the filename to open it in the default Windows application (Word, Excel, etc.).

> **Tip:** JSON files are useful for integration with other systems. Open them in VS Code or any JSON viewer for a clean view of the structured data.

> **If no files appear:** You haven't run an extraction yet, or the Extracted folder path in Settings is incorrect.

---

## 8. Insights Page — Stats & Charts

The Insights page shows a summary of processing activity.

**Stat cards (top):**
| Card | Shows |
|---|---|
| **Total** | All files registered in the tracking database |
| **Completed** | Files successfully extracted |
| **Pending** | Files registered but not yet extracted |

**Bar chart:**
The chart shows Completed vs. Pending files over time. Use the period selector to change the view:

| Period | Shows |
|---|---|
| Day | One bar per calendar day |
| Week | One bar per ISO week |
| Month | One bar per calendar month (default) |
| Year | One bar per year |

**Log history:**
Below the chart, you can view extraction logs. Click a period to see the log entries from that time, including the reference number, timestamp, output file paths, and Box upload status.

---

## 9. Chat Page — Ask Detective Conan

The Chat page lets you ask questions and give commands in plain language.

### Built-In Commands

These work without ICA configured:

| Command | What happens |
|---|---|
| `sync` | Downloads new PDFs from Box |
| `scan` | Scans the Local Folder for new PDFs |
| `extract` | Runs the extraction pipeline |
| `file status` | Shows how many files are Pending / Completed |
| `logs this week` | Shows extraction log entries from this week |
| `logs today` / `this month` / `this year` | Shows logs for the selected period |
| `look up John Smith` | Searches extracted reports for that name and shows a formatted summary |
| `find RN-123456` | Searches by case reference number |
| `generate reports` | Lists all extracted reports |
| `generate report for John Smith` | Finds the report and asks which format to open |

### Report Lookup

When you say `look up John Smith`, Detective Conan searches all extracted JSON files for that name. If found, he returns a formatted block:

```
Subject: Smith, John | Ref: RN-123456_789_10 | Delivery: 2026-07-08
Overall Status: ✅ Cleared

── Employment Verification ──
  ✅ Employment 1: Acme Corp — Cleared
    Position: Software Engineer
    Dates: Jan 2020 – Dec 2023
    Result: Verified – Clear

── Database Checks ──
  ✅ Adverse Media Check: Cleared
  ✅ Global Sanctions: Cleared
  …
```

### Opening a Report File

Say `generate report for John Smith`. Detective Conan will:
1. Find the report
2. Ask which file type you want: **Word**, **Excel**, or **JSON**
3. Open the file in the appropriate application

### General Questions (ICA Required)

If ICA is configured and your question does not match a built-in command, it is forwarded to IBM Consulting Advantage. Use this for free-form questions.

> **Important:** Detective Conan will never invent report data. If ICA tries to fabricate a report, the hallucination guard catches it and replaces the response with a safe message. Always use `look up [name]` to get real report data.

### Chat Tips
- The chat history is preserved while the app is open (Zustand store)
- Closing the app clears the history
- You can mix commands and questions in a natural conversation

---

## 10. Troubleshooting

### App shows error dialog on startup — "Backend health timeout"

The backend (`backend.exe`) failed to start within 30 seconds. Check the startup log at:
```
%TEMP%\pdf-extractor-v3-startup.log
```

Common causes:
- **Port in use** — another application is using ports 8765–8785. Restart your computer and try again.
- **Antivirus blocking** — add the app folder to your antivirus exceptions.
- **Corrupted install** — re-run the installer or re-extract the portable exe.

---

### Settings are blank after opening the app

This is normal on the very first launch — the database is empty. Fill in your credentials on the Settings page and click **Save Settings**.

---

### "Box authentication failed"

- The Box JWT JSON is invalid or the service account's key pair has been revoked.
- Re-download the JWT JSON from the Box Developer Console (app.box.com/developers/console → your app → Configuration → App Settings → Regenerate keypair) and re-upload it on the Settings page.

---

### "No reports found matching 'John Smith'"

- The report has not been extracted yet — run Extract first.
- The name in the extracted JSON does not match your search. Try searching by the case reference number instead: `look up RN-123456`.
- The JSON File Extracts folder is empty or in a different location than configured.

---

### ICA test passes but Chat gives "(ICA did not respond in time)"

Your `chat_id` is stale — it was captured from the ICA new-chat landing page before you sent a message, so the thread was never initialised.

**Fix:**
1. Go to **Settings** → click **Sign in to ICA** again.
2. Sign in, open a chat thread, and **send at least one message**.
3. The window closes automatically and captures a fresh, valid `chat_id`.
4. Click **Test ICA** to verify.

---

### Extracted files are not appearing on the View page

- Check that extraction completed without errors (Extract page → result rows).
- Verify that the `extracted_folder` path in Settings → Extraction & Sync Options resolves to an existing location.
- Check that the `Local Folder/Extracted/` directory exists and contains files (open File Explorer and navigate to `%APPDATA%\PDF Extractor V3\Local Folder\Extracted\`).

---

### A PDF fails to extract with "incorrect password"

The `pdf_password` in Settings does not match the encryption on that PDF. Update the password on the Settings page, save, and re-run extraction. Affected files remain Pending and will be retried.

---

### Where are my files?

All application data is in:
```
%APPDATA%\PDF Extractor V3\
```

Open File Explorer, click the address bar, and type `%APPDATA%\PDF Extractor V3\` to navigate there directly.

| Path | Contents |
|---|---|
| `pdf_extractor_v3.db` | Everything: config, tracking, JWT, logs |
| `ica.log` | ICA HTTP request/response debug log |
| `Local Folder\` | Synced PDFs (unprocessed) |
| `Local Folder\Extracted\` | Word / Excel / JSON export files |
| `Local Folder\Archive\` | Source PDFs after extraction |
