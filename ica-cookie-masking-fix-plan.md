# ICA Cookie Masking Fix

## Overview

**Goal:** Remove the masking of the `full_cookie` field in the ICA settings section.

**Problem:** The `full_cookie` field is being masked (shown as `••••••••`) in the Settings page. When the user saves settings while the masked value is displayed, the literal mask string `"••••••••"` gets written to `config.json` as the cookie value. This breaks the ICA connection status check and prevents "Chat with AI" from being enabled, even though the ICA test may have passed at an earlier point with the real cookie.

**Root cause:** The `full_cookie` field is (or was at some point) included in `_SECRET_PATHS` in `backend/settings.py`, causing it to be replaced by the mask marker `"••••••••"` in the GET response. Even if removed from `_SECRET_PATHS`, the mask string may already be persisted in `config.json`.

**Approach:** Two-part fix:
1. Ensure `full_cookie` is not in `_SECRET_PATHS` (backend — already the case, confirm and keep).
2. Make the frontend `full_cookie` textarea display its value in plaintext (no masking, no CSS obscuring), and ensure the `_deep_merge` guard in the backend does not accidentally treat the real cookie as a mask if someone pastes a look-alike value.
3. Show the cookie value in a way that the user can visually confirm it is set correctly (not hidden).

---

## Sub-Tasks

### Sub-Task 1 — Confirm backend does not mask `full_cookie`

**Intent:** Verify and ensure `full_cookie` is not in `_SECRET_PATHS` in [`backend/settings.py`](PDF%20Extractor%20V3/backend/settings.py). Only `pdf_password` should be masked.

**Expected Outcomes:**
- `_SECRET_PATHS` contains only `("pdf_password",)`.
- The GET `/api/settings` response returns the real `full_cookie` value in plaintext.
- The POST `/api/settings` response also returns the real value.

**Todo List:**
1. Open [`PDF Extractor V3/backend/settings.py`](PDF%20Extractor%20V3/backend/settings.py) and confirm `_SECRET_PATHS` is `[("pdf_password",)]` with no ICA entry.
2. If `("ica", "full_cookie")` or similar is present, remove it.
3. No other changes needed in the backend.

**Relevant Context:**
- [`backend/settings.py:32-34`](PDF%20Extractor%20V3/backend/settings.py:32) — `_SECRET_PATHS`
- [`backend/settings.py:56-65`](PDF%20Extractor%20V3/backend/settings.py:56) — `_mask_config()`

**Status:** [ ] pending

---

### Sub-Task 2 — Fix any corrupted `full_cookie` in config.json

**Intent:** If config.json currently stores `"••••••••"` as the `full_cookie` value (the mask string was written back), it needs to be cleared so the user can re-enter the real cookie. The frontend should detect when the displayed value equals the mask and treat it as empty.

**Expected Outcomes:**
- If `full_cookie` in config.json equals `"••••••••"`, it is treated as unconfigured.
- The status endpoint returns `configured: false` correctly when only the mask string is stored.
- The user is prompted to re-enter the cookie.

**Todo List:**
1. In [`backend/settings.py`](PDF%20Extractor%20V3/backend/settings.py), in the `settings_status()` function, update the `ica_ok` check to also treat the `_MASK` value as falsy:
   ```python
   def _is_real(val: str) -> bool:
       return bool(val) and val != _MASK
   ica_ok = _is_real(ica.get("full_cookie")) and _is_real(ica.get("team_id")) and _is_real(ica.get("chat_id"))
   ```
2. Also apply this guard to the individual field booleans in the status response.

**Relevant Context:**
- [`backend/settings.py:112-137`](PDF%20Extractor%20V3/backend/settings.py:112) — `settings_status()`
- [`backend/settings.py:68-79`](PDF%20Extractor%20V3/backend/settings.py:68) — `_deep_merge()` already skips `_MASK` on write

**Status:** [ ] pending

---

### Sub-Task 3 — Update the frontend textarea to show cookie in plaintext

**Intent:** The `full_cookie` textarea in [`Settings.tsx`](PDF%20Extractor%20V3/frontend/src/pages/Settings.tsx) should display the real cookie value in plaintext. Remove any styling or input type that causes it to render as dots/bullets.

**Expected Outcomes:**
- The Full Cookie textarea shows the real cookie value (or is empty if not set).
- The user can visually confirm the cookie is present and correct.
- If the stored value is the mask string `"••••••••"`, the textarea shows it clearly so the user knows to re-enter the real value.

**Todo List:**
1. Open [`PDF Extractor V3/frontend/src/pages/Settings.tsx`](PDF%20Extractor%20V3/frontend/src/pages/Settings.tsx) at lines 494-506.
2. Confirm the `<textarea>` has no `type` attribute (textareas can't have `type="password"` anyway).
3. Check if any CSS class is applying `font-security` or similar bullet-masking. The existing class `font-mono` is fine.
4. Add a small helper note below the textarea: "The cookie value is shown in plaintext. If you see `••••••••`, re-paste your real cookie and save."
5. Optionally: if `cfg.ica.full_cookie === '••••••••'`, auto-clear it to empty string on load so the user sees a blank field rather than the mask.

**Relevant Context:**
- [`frontend/src/pages/Settings.tsx:494-506`](PDF%20Extractor%20V3/frontend/src/pages/Settings.tsx:494) — Full Cookie textarea
- [`frontend/src/pages/Settings.tsx:84-94`](PDF%20Extractor%20V3/frontend/src/pages/Settings.tsx:84) — `load()` function

**Status:** [ ] pending

---

### Sub-Task 4 — Auto-clear mask value on settings load

**Intent:** When the settings page loads and the stored `full_cookie` equals the mask string, automatically clear it to `""` in the local form state so the user sees an empty field and is prompted to re-paste the real value.

**Expected Outcomes:**
- On page load, if `cfg.ica.full_cookie === '••••••••'`, the field appears empty.
- The user repastes their cookie, saves, and ICA shows as configured.
- The mask value is never re-saved to config.json by accident.

**Todo List:**
1. In [`Settings.tsx`](PDF%20Extractor%20V3/frontend/src/pages/Settings.tsx) `load()` function (lines 84-94), after `setCfg(res.config)`, check if `res.config.ica.full_cookie === '••••••••'` and if so, set it to `''`:
   ```typescript
   const config = res.config
   if (config.ica?.full_cookie === '••••••••') {
     config.ica.full_cookie = ''
   }
   setCfg(config)
   ```

**Relevant Context:**
- [`frontend/src/pages/Settings.tsx:84-94`](PDF%20Extractor%20V3/frontend/src/pages/Settings.tsx:84) — `load()`

**Status:** [ ] pending
