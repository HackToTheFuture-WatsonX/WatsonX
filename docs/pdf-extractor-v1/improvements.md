# PDF Extractor V1 — Improvements

## V1-Specific Issues

### IMP-V1-01: OAuth2 Developer Token Expires Every 60 Minutes
**Current:** `box.access_token` in `config.json` is a short-lived token that must be manually regenerated every hour.

**Problem:** Token expiry causes all Box operations to fail silently until the user notices the status bar error. During a long extraction session, the token may expire mid-run.

**Recommendation:** Migrate V1 to use the JWT Service Account approach already implemented in `pdf_text_extractor.py`'s `get_box_client()`. This requires placing a `box_jwt_config.json` file in the V1 folder and updating `config.json` to point to it. The `get_box_client()` in `pdf_extractor_ui.py` would need to be removed in favour of the shared engine's version.

**Effort:** Low.

---

### IMP-V1-02: No Box Upload After Extraction
**Current:** V1 exports Word/Excel/JSON files to the local app folder only. Nothing is uploaded back to Box.

**Problem:** Team members cannot access the extracted outputs unless they have access to the machine running V1.

**Recommendation:** Add `output_folder_id` to V1's `config.json` and call `_box_upload_to_dated_path()` (already implemented in the web app's `app.py`) after each successful extraction. The shared engine would need a new `upload_exports()` helper, or V1 can call the Box SDK directly for upload.

**Effort:** Medium.

---

### IMP-V1-03: No Archive Step
**Current:** V1 does not move processed PDFs to an archive folder after extraction. The source PDF remains in the Box source folder.

**Problem:** On the next scan, already-processed files are reset to Pending and could be re-extracted unnecessarily.

**Recommendation:** Add `archive_folder_id` to V1's `config.json` (field exists in the config but is unused in the V1 extraction pipeline). After a successful extraction, move the source PDF using `client.file(fid).move(dest_folder)`.

**Effort:** Low — the logic already exists in the web app's extraction pipeline.

---

### IMP-V1-04: ICA-Only AI (No Fallback Chain)
**Current:** V1's AI Assistant is wired exclusively to ICA 1.0 using session-cookie auth.

**Problem:** When ICA cookies expire, the AI goes entirely silent with no fallback.

**Recommendation:** Adopt the multi-tier AI fallback chain from the Web App (watsonx.ai → Orchestrate → ICA → Watson Assistant → local help). Even adding a single watsonx.ai fallback would significantly improve reliability.

**Effort:** Medium — requires adding watsonx credentials to V1's config and implementing the fallback routing.

---

## Shared Improvements (also apply to V1)

See [Shared Specifications](../shared/specifications.md) and the system-wide improvements that apply to all apps:

- **IMP-02:** Centralize `config.json` schema with a canonical JSON Schema file
- **IMP-03:** Replace `tracking_db.json` with SQLite for safe concurrent access
- **IMP-06:** Add `validate_config()` at startup for clear missing-field errors
- **OBS-01:** Move duplicated `build_extract_folder()` and `write_extraction_log()` into the shared engine
- **OBS-04:** Add unit tests for parser logic

---

## Feature Suggestions (V1)

### FEAT-V1-01: Re-Extract Button
A "Re-extract" button on the file table row would let users reprocess a Completed file without manually editing `tracking_db.json`.

### FEAT-V1-02: Progress Per-File Status
The current progress bar is indeterminate (just animates). A label showing "Processing 2 of 5: report-name.pdf" would improve user confidence during long extraction runs.
