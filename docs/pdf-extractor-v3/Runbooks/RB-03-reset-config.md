# RB-03 — Reset a Machine to Factory Config

## When to run

- The `pdf_extractor_v3.db` is suspected to be corrupted (rare — SQLite is extremely robust).
- Preparing to hand a machine to a new operator with no residual state.
- Debugging: you want to prove a bug is not caused by lingering config.

## Preconditions

- You have exported / backed up anything you want to keep first — this operation is **destructive**.
- V3 is closed.

## Steps

1. **Back up first** (mandatory unless you're deliberately discarding everything):
   ```bat
   xcopy "%APPDATA%\PDF Extractor V3" "%APPDATA%\PDF Extractor V3.bak" /E /I /Y
   ```

2. **Close V3** completely — right-click the tray icon (if present) and Quit, then confirm via Task Manager that no `backend.exe` or `PDF Extractor V3.exe` is running.

3. **Delete the DB files**:
   ```bat
   del "%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db"
   del "%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db-wal" 2>nul
   del "%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db-shm" 2>nul
   ```

4. **Optionally** clear the ICA log:
   ```bat
   del "%APPDATA%\PDF Extractor V3\ica.log"
   ```

5. **Optionally** clear Local Folder contents:
   - Only if you also want to discard synced PDFs and their exports.
   - Skip this if you want the *config* reset but the historical data preserved:
     ```bat
     rmdir /S /Q "%APPDATA%\PDF Extractor V3\Local Folder"
     ```

6. **Launch V3**.
   - The splash appears.
   - The first startup creates a fresh empty `pdf_extractor_v3.db` with the schema.
   - Every page will render, but Sync / Extract / Chat will refuse to do work until credentials are entered.

7. **Reconfigure** per [Quickstart.md](../Quickstart.md#3-configure-credentials--settings):
   - PDF password.
   - Box folder IDs.
   - Upload JWT.
   - Sign in to ICA (see [RB-02](RB-02-refresh-ica-cookies.md)).
   - Initialize ICA system prompt.

## Verify

- Settings page reads all-empty at first launch.
- All connection tests pass after reconfiguration.
- A test Sync/Scan/Extract cycle completes end-to-end.

## Rollback

If you deleted before saving critical data:

1. Close V3.
2. Copy the backup back:
   ```bat
   xcopy "%APPDATA%\PDF Extractor V3.bak" "%APPDATA%\PDF Extractor V3" /E /I /Y
   ```
3. Launch V3 — original state restored.

## Related

- [Backup-and-Restore.md](../Backup-and-Restore.md) — proper backup practice
- [RB-02](RB-02-refresh-ica-cookies.md) — ICA sign-in after reset
- [Deployment-Guide.md](../Deployment-Guide.md#migrating-to-a-new-machine) — moving state instead of resetting
