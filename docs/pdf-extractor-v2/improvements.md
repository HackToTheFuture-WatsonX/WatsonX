# PDF Extractor V2 — Improvements

## V2-Specific Issues

### IMP-V2-01: OAuth2 Developer Token Still Expires Every 60 Minutes
**Current:** V2 still uses a short-lived Developer Token for all Box operations (sync, upload, archive).

**Problem:** If the token expires mid-sync or during the Box upload step of extraction, that step fails. Auto-sync will silently fail if the token has expired overnight.

**Recommendation:** Migrate V2 to JWT Service Account auth (same as the Web App). This eliminates all token refresh problems. The shared engine's `get_box_client()` already supports JWT — V2 just needs the `box_jwt_config.json` file and a config update.

**Effort:** Low.

---

### IMP-V2-02: No Conflict Resolution During Sync
**Current:** V2 checks if a file already exists locally by name only before deciding whether to skip the download.

**Problem:** If a PDF in Box is updated (new version, same name), V2 will skip it because a local copy already exists — the stale local file will be extracted instead of the updated version.

**Recommendation:** Compare file size or Box file modification time with the local copy. If they differ, overwrite the local file. The Box SDK provides `file.get(['modified_at', 'size'])` for this.

**Effort:** Low.

---

### IMP-V2-03: Auto-Sync Fires Even When App Is Idle
**Current:** Auto-sync runs on a fixed interval regardless of whether the user is actively using the app.

**Problem:** Unnecessary Box API calls when there are no new files to sync.

**Recommendation:** Add a "last sync had new files" flag. If the previous sync found zero new PDFs, increase the backoff interval (e.g. 2× up to a max of 4 hours) before trying again.

**Effort:** Medium.

---

### IMP-V2-04: ICA-Only AI (No Fallback Chain)
Same issue as V1. V2's AI Assistant is wired to ICA 1.0 only. When ICA cookies expire, the AI goes silent.

**Recommendation:** Adopt the web app's multi-tier AI fallback (watsonx.ai → Orchestrate → ICA → Watson Assistant).

**Effort:** Medium.

---

### IMP-V2-05: Box Upload Errors Are Silent
**Current:** If the Box upload step fails during extraction (e.g. network hiccup, permissions error), the extraction log records the failure but the file is still marked `Completed`.

**Problem:** A user looking at the Completed count has no indication that the Box upload failed — the outputs exist locally but not on Box.

**Recommendation:** Add a separate `upload_status` field to `tracking_db.json` entries (`Uploaded` / `Upload Failed`). Show upload status in the result card and the View Extracted Files screen.

**Effort:** Medium.

---

## Shared Improvements (also apply to V2)

- **IMP-02:** Centralize `config.json` schema
- **IMP-03:** Replace `tracking_db.json` with SQLite
- **IMP-06:** Add `validate_config()` startup validation
- **OBS-01:** Move duplicated helper functions into shared engine
- **OBS-04:** Add unit tests for parser logic

---

## Feature Suggestions (V2)

### FEAT-V2-01: Schedule Sync Window
Allow configuring a time window for auto-sync (e.g. "only sync between 08:00 and 18:00") to avoid overnight API calls outside business hours.

### FEAT-V2-02: Sync Status Notification
Show a desktop system tray notification when a sync finds new PDFs, so users don't need to keep the app in focus.

### FEAT-V2-03: Bulk Re-Extract
A "Re-extract all" button to reset all Completed files back to Pending and re-run the pipeline — useful after a parser update.
