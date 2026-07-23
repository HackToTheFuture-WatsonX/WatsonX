# Backup and Restore

V3 keeps every piece of state in one place. Backups are simple; restores are simpler.

---

## What to Back Up

All of it lives at `%APPDATA%\PDF Extractor V3\`:

| Path | Contents | Frequency |
|---|---|---|
| `pdf_extractor_v3.db` | Config, tracking, JWT credentials, activity log | Daily (or on-demand before major changes) |
| `pdf_extractor_v3.db-wal` | WAL journal (any un-checkpointed writes) | Same time as the .db |
| `pdf_extractor_v3.db-shm` | Shared-memory index for WAL | Same time as the .db |
| `Local Folder\Extracted\` | Word / Excel / JSON outputs | Weekly (rarely regenerated) |
| `Local Folder\Archive\` | Source PDFs after successful extraction | Optional — usually kept only as long as needed for audit |

The `.db-wal` and `.db-shm` sidecars are not strictly required — the `.db` file alone can be opened and read even without them — but including all three captures any writes that haven't yet been checkpointed. Backing up mid-run risks capturing a partially-flushed WAL; prefer backing up when V3 is closed.

**Not backed up:**
- `%TEMP%\pdf-extractor-v3-*.log` — regenerated every launch.
- `%APPDATA%\PDF Extractor V3\ica.log` — recreated on next ICA request.
- `.v3_port` — recreated on next launch.

---

## Simple Backup

Close V3 first (ensures WAL is checkpointed). Then:

```bat
robocopy "%APPDATA%\PDF Extractor V3" "D:\Backups\PDFExtractorV3-%date:~-4%%date:~4,2%%date:~7,2%" *.db *.db-wal *.db-shm
```

or a plain copy:

```bat
xcopy "%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db*" "D:\Backups\" /Y
```

Result: one folder per snapshot with the three DB files.

---

## Hot Backup (V3 running)

Not recommended for user backups, but supported for on-demand snapshots. SQLite's built-in backup API is atomic:

```bat
sqlite3 "%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db" ".backup ""D:\Backups\snapshot.db"""
```

`sqlite3.exe` ships with the OS on Windows 11 or can be installed from sqlite.org. The `.backup` command locks nothing and includes any in-flight WAL content.

Result: a single consistent `.db` file that can be dropped into `%APPDATA%\PDF Extractor V3\` on any machine.

---

## Full Restore

1. Close V3.
2. Delete or rename the current three files at `%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db*`.
3. Copy your backup files into `%APPDATA%\PDF Extractor V3\`.
4. Launch V3. Every setting, tracking row, JWT, and activity-log row is back.

---

## Partial Restore

Because everything is in tables, you can restore *just* one section by opening the backup DB and copying rows out.

Example — restore only the Box config:

```bat
:: 1. Open the backup DB with sqlite3.
sqlite3 D:\Backups\snapshot.db

sqlite> SELECT value FROM config WHERE section = 'box';
{"folder_id":"12345","archive_folder_id":"67890","output_folder_id":"11111"}

sqlite> .quit

:: 2. In V3's Settings page, paste the values into the Box section.
```

Or via a script — `db.py` has `config_get_all()` / `config_replace_all()`.

---

## Restore Just the Extracted Outputs

If the tracking DB is fine but you deleted the exports:

- The tracking table still has `status = Completed` and `ref_number` set, but the files are gone.
- Re-running Extract does NOT re-process a Completed row — you must manually flip the row back to Pending.
- Then re-run Extract to regenerate.

```sql
UPDATE tracking_files
   SET status = 'Pending', last_extracted = NULL, ref_number = NULL
 WHERE status = 'Completed';
```

Warning: this reprocesses everything. Confirm you have the source PDFs (in `Archive/`) before doing this — Extract needs the source.

Better approach: retain both source PDFs (Archive) and exports (Extracted); they're what makes V3 fully recoverable.

---

## Migrating to a New Machine

1. Install V3 on the new machine (portable or installer).
2. Launch V3 once, then close it (creates the `%APPDATA%\PDF Extractor V3\` directory).
3. Copy the three DB files from the old machine's `%APPDATA%\PDF Extractor V3\` into the new machine's same folder.
4. Optionally copy `Local Folder\` — needed if you want the export history and archived source PDFs. Not needed for future runs to work.
5. Launch V3. All settings, credentials, tracking, and history come with you.

Because `%APPDATA%` is per-user, this is not a global machine migration but a user-profile migration.

---

## Retention & Cleanup

V3 does not delete anything automatically. Options:

- **Trim the activity log** — safe to delete old rows from `extraction_logs` (older than N months). Preserve the recent months for the Logs page.
  ```sql
  DELETE FROM extraction_logs WHERE occurred_at < '2025-01-01';
  ```
- **Trim exports** — safe to delete old year-hierarchies under `Local Folder/Extracted/` if downstream teams no longer need them.
- **Trim archived source PDFs** — safe once the exports are archived to Box.

See [Data-Retention.md](Data-Retention.md).

---

## Testing Your Backup

Every quarter:

1. Copy `%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db` to a scratch directory (`C:\Temp\v3-test\`).
2. Launch V3 from that scratch directory using the `--data-dir` override:
   ```bat
   backend.exe --port 9999 --data-dir "C:\Temp\v3-test"
   ```
   (You'd need Electron to point at this too — easier to just rename `%APPDATA%\PDF Extractor V3\` temporarily and place the backup as the active dir.)
3. Confirm Settings, Sync/Extract history, and Logs render correctly.

A backup that hasn't been tested isn't a backup.

---

## Related

- [Database-Schema.md](Database-Schema.md) — what's in the .db
- [Data-Retention.md](Data-Retention.md) — retention policies
- [Deployment-Guide.md](Deployment-Guide.md) — migration walkthrough
