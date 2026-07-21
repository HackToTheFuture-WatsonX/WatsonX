# Quickstart

Get from zero to first extracted report in about ten minutes.

---

## Prerequisites

- Windows 10 or 11 (x64).
- Box service-account JWT JSON (obtain from `app.box.com/developers/console` → your app → **Configuration** → **App Settings** → **Generate a Public/Private Keypair**).
- Box folder IDs for **source**, **archive**, and **output** folders.
- PDF password (the shared password used by the vendor to encrypt reports).
- An IBM ID with access to IBM Consulting Advantage (optional; the app runs without ICA but Bee's answers will be limited to local skills).

---

## 1. Install

Pick one:

- **Installer** — double-click `PDF-Extractor-V3-Setup-3.0.0.exe`. Choose install location; check both **Desktop shortcut** and **Start Menu shortcut**.
- **Portable** — copy `PDF-Extractor-V3-Portable-3.0.0.exe` anywhere (USB drive, network share, `C:\Tools\`). Double-click to run. No install step; nothing gets written to `C:\Program Files`.

Either mode stores its data at:

```
%APPDATA%\PDF Extractor V3\
    pdf_extractor_v3.db
    ica.log
    Local Folder\
```

---

## 2. First Launch

Double-click the exe. A dark splash appears reading "Starting backend service…". Within ~5–10 seconds the app swaps to the main window.

If it hangs longer than 30 seconds:
- Check `%TEMP%\pdf-extractor-v3-backend.log` for Python errors.
- Check `%TEMP%\pdf-extractor-v3-startup.log` for Electron startup issues.
- See [Troubleshooting.md](Troubleshooting.md#backend-never-becomes-healthy).

---

## 3. Configure Credentials — Settings

Click **Settings** in the left sidebar.

### 3.1 PDF Password

Paste the shared PDF password. It will render as `••••••••` after save.

### 3.2 Box

- **Source folder ID** — where new vendor PDFs land.
- **Archive folder ID** — where source PDFs move after download.
- **Output folder ID** — (optional) where V3 uploads the Word/Excel/JSON exports.
- **JWT config** — click **Upload JWT** and paste (or drop) the service-account JSON.

Click **Test Box**. The stream will show:

```
Reading configuration…
Authenticating with Box using JWT service account…
Authenticated with Box ✓
Fetching current Box user…
Signed in as <service-account-login> ✓
Opening configured folder (id <folder_id>)…
Folder "<name>" reachable ✓
Box connection is working.
```

### 3.3 ICA (optional but recommended for Chat)

Click **Sign in to ICA**. A dedicated browser window opens the IBM Consulting Advantage sign-in page. Complete IBMid / SSO exactly as you would in a normal browser. Once you send a first message on any chat, V3 auto-captures:

- `full_cookie` — the complete Cookie header (including HttpOnly auth token)
- `team_id`, `team_name`
- `chat_id` — the *trusted* chat ID (one that has actually accepted a prompt)

Click **Test ICA** — you should get `ICA connection is working. Reply: <bee's response to "Hi Bee">`.

Click **Initialize ICA System Prompt** — this sends `backend/prompt/bee_prompt.md` as the first prompt on the chosen chat_id. When it succeeds, the Settings status shows **Primed**.

### 3.4 Local Folders (default is fine)

The defaults resolve to `%APPDATA%\PDF Extractor V3\Local Folder\`. Only change these if you need to route data to a different drive.

Click **Save**.

---

## 4. Your First Run

### 4.1 Sync

- **Sync** page → **Sync Now**.
- Watch the live log as PDFs download from Box and are moved to your archive folder on Box.

### 4.2 Scan

- Auto-triggered after Sync. Or **Scan** page → **Scan Now**.
- The tracking table populates with each file as **Pending**.

### 4.3 Extract

- **Extract** page → **Run Extraction**.
- The counter climbs as each file passes through decrypt → parse → export → (Box upload) → archive.

### 4.4 View the results

- **View** page — browse by reference number. Each row has Word/Excel/JSON buttons that open the file in the OS default handler.

---

## 5. Try Bee

Click the floating chat bubble (bottom-right corner of any page).

```
> look up Jose Manalo
> logs this week
> file status
> generate report for Jose Manalo
```

If ICA is primed, Bee also handles freeform natural-language questions grounded in the Bee persona.

---

## Where Things Live

| Artefact | Path |
|---|---|
| App executable | Portable exe location, or `C:\Users\<you>\AppData\Local\Programs\PDF Extractor V3\` (installer) |
| Config + tracking + JWT + logs | `%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db` |
| Local PDFs + exports | `%APPDATA%\PDF Extractor V3\Local Folder\` |
| ICA debug log | `%APPDATA%\PDF Extractor V3\ica.log` |
| Backend process log | `%TEMP%\pdf-extractor-v3-backend.log` |
| Electron startup log | `%TEMP%\pdf-extractor-v3-startup.log` |

See [Deployment-Guide.md](Deployment-Guide.md) for install/uninstall detail and [Backup-and-Restore.md](Backup-and-Restore.md) for backup guidance.

---

## Next Steps

- **[User-Guide.md](User-Guide.md)** — full page-by-page tour.
- **[FAQ.md](FAQ.md)** — common gotchas.
- **[Troubleshooting.md](Troubleshooting.md)** — what to do when something breaks.
