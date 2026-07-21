# Deployment Guide

How to distribute, install, upgrade, and uninstall PDF Extractor V3.

---

## Distribution Model

V3 ships as two artefacts, both produced by `electron/npm run dist`:

| Artefact | Best for | Install location |
|---|---|---|
| `PDF-Extractor-V3-Setup-3.0.0.exe` | Regular deployments; team-wide rollout | `C:\Users\<you>\AppData\Local\Programs\PDF Extractor V3\` |
| `PDF-Extractor-V3-Portable-3.0.0.exe` | Ad-hoc use, USB carry, single-machine trials | Anywhere; self-extracts to `%TEMP%\<random>` at runtime |

Both are 100 % self-contained. No prerequisites on the target machine.

---

## Installer Mode (NSIS)

### Install

1. Download `PDF-Extractor-V3-Setup-3.0.0.exe`.
2. Double-click; accept SmartScreen warning (installer is unsigned — see [FAQ.md](FAQ.md#is-v3-signed)).
3. Click **Next** through the wizard:
   - **Choose install location** — default is fine.
   - **Choose shortcuts** — Desktop and Start Menu are both checked by default.
   - **Install** — takes ~10 seconds.
4. Optionally check **Run PDF Extractor V3** at the end.

Registry entries: standard NSIS uninstall entry under `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\`.

### Uninstall

Windows **Settings** → **Apps** → **Installed apps** → **PDF Extractor V3** → **Uninstall**.

The uninstaller removes the application files but does **not** touch:

- `%APPDATA%\PDF Extractor V3\` — user data, config, credentials.
- Any files under `Local Folder/`.
- The `%TEMP%\pdf-extractor-v3-*.log` files.

If you want a completely clean state, manually delete `%APPDATA%\PDF Extractor V3\` after uninstalling.

---

## Portable Mode

### Run

Double-click the exe. Windows unpacks the bundled Chromium + Node.js + Python to a fresh `%TEMP%\<random>` directory, then launches.

- **First run**: ~5–10 seconds to unpack.
- **Subsequent runs**: same — the temp directory is reused unless cleaned up.

The portable exe can be:

- Copied to a USB drive and run on any Windows machine (data still lives at `%APPDATA%\PDF Extractor V3\` on the host).
- Placed on a network share (slow launch due to unpacking over the network).
- Renamed freely — the filename doesn't matter.

### Cleanup

The `%TEMP%` extraction is cleaned up on exit. If left over (e.g. crash), it's harmless — Windows Disk Cleanup handles it.

---

## Upgrade

### Installer users

Run the new installer on top of the old one. It will:

- Stop the current instance (fail if it's still running; close V3 first).
- Overwrite the application files.
- Preserve `%APPDATA%\PDF Extractor V3\` — all user data stays intact.
- Update the shortcut icons if changed.

### Portable users

Delete the old exe. Copy the new exe in its place. All data at `%APPDATA%\PDF Extractor V3\` remains untouched.

### Schema migrations

Currently the SQLite schema uses `CREATE TABLE IF NOT EXISTS` everywhere — new columns can be added defensively without breaking older code. A hard migration (rename or drop) requires a version marker in a `meta` table and a startup migration function; when this is needed, [Release-Notes.md](Release-Notes.md) will call it out prominently.

---

## Multi-Machine Rollout

For a small team (< 20 machines), the recommended pattern:

1. Build once on a designated build machine (see [CI-CD.md](CI-CD.md)).
2. Distribute `PDF-Extractor-V3-Setup-3.0.0.exe` via SharePoint / Teams / whatever your org uses.
3. Each user installs on their machine and completes the setup flow ([Quickstart.md](Quickstart.md#3-configure-credentials--settings)).
4. Provide the shared PDF password and Box folder IDs through a secure channel.
5. Users complete their own ICA sign-in (personal IBMid — do not share).

For larger deployments (50+ machines), consider:

- Silent-install support via NSIS `/S` flag — mode is `oneClick: false` currently, so silent install isn't wired. Adding it is a small `nsis-tool.js` change if needed.
- SCCM / Intune deployment package around the NSIS exe.

---

## Smoke-Test Checklist

After installing a new release, verify:

- [ ] App launches; splash → main window in < 15 s.
- [ ] `%TEMP%\pdf-extractor-v3-backend.log` shows `Registered routes:` including `/api/scan/upload`.
- [ ] Settings page → **Test Box** → SSE stream ends with "Box connection is working."
- [ ] Settings page → **Test ICA** → SSE stream ends with "ICA connection is working." (Skip if ICA not used.)
- [ ] Sync page → **Sync Now** → completes with the expected count.
- [ ] Scan page → Diagnostics panel opens; **Upload Files** picks a test PDF; upload progresses to "Uploaded".
- [ ] Extract page → **Run Extraction** → at least one file completes.
- [ ] Logs page → new rows visible with correct Info/Warning/Error badges.
- [ ] Chat → `look up <name>` → returns known extracted report.

---

## Rollback

Both modes preserve user data across upgrade/downgrade — swap the exe back to the previous version's binary. If the DB was upgraded through a migration, restore the pre-migration DB from your backup (see [Backup-and-Restore.md](Backup-and-Restore.md)).

---

## Custom Data Directory

Advanced use case — run against a data directory that isn't `%APPDATA%\PDF Extractor V3\`. Not currently exposed as a UI option, but the backend supports it:

```bat
backend.exe --port 8765 --data-dir "D:\SharedData\PDF Extractor V3"
```

To wire this through Electron end-to-end, patch `electron/main.js:spawnBackend` to pass a custom `--data-dir`. Useful for shared drives or per-project data isolation. Not a supported user configuration in 3.0.0.

---

## Antivirus Considerations

Unsigned exes with bundled Python interpreters can trip:

- **Windows SmartScreen** — one-click "Run anyway" the first time; won't re-prompt on the same machine.
- **Corporate AV** — some heuristics flag PyInstaller-frozen binaries as suspicious. Whitelist the vendor / SHA-256 of the release.
- **False positives** — occasional; contact the AV vendor with a submission if it recurs. Long-term fix is signing the exe (see [Roadmap.md](Roadmap.md)).

---

## Related

- [CI-CD.md](CI-CD.md) — how the artefacts are produced
- [Environment-Setup.md](Environment-Setup.md) — dev vs packaged runtime
- [Quickstart.md](Quickstart.md) — first-run configuration
- [Backup-and-Restore.md](Backup-and-Restore.md) — machine migration
