# RB-02 — Refresh ICA Session Cookies

## When to run

- **Test ICA** on the Settings page returns "ICA unreachable" or "HTTP 401 / 403".
- Bee returns `⚠ ICA error: HTTP 401` when the user talks to it.
- `%APPDATA%\PDF Extractor V3\ica.log` shows recent `HTTP 401` or `HTTP 403` responses from ICA.

ICA session cookies expire on a rolling window (typically 8–24 hours of inactivity). This is normal and expected — the fix is to sign in again.

## Preconditions

- You have IBMid credentials that can access IBM Consulting Advantage.
- V3 is open on the affected machine.

## Steps

1. Open **Settings**.

2. Scroll to the ICA section. Click **Sign in to IBM Consulting Advantage**.

3. The browser-assisted login window opens against `servicesessentials.ibm.com/curatorai/apps/ui/new-chat`. Complete the IBMid / SSO exactly as you would in a normal browser.

4. **Send at least one prompt in that chat window before closing it.**
   - Type any message (e.g. `Hello`) and submit.
   - This ensures V3 captures a **trusted** chat_id (one that has actually accepted a `/entries` POST).
   - Closing the window without sending a prompt causes V3 to blank the chat_id — the login window returns cookie and team info only.

5. Close the login window. V3 auto-populates the ICA fields:
   - `full_cookie` — the complete Cookie header (masked as `••••••••` after save).
   - `team_id`, `team_name`.
   - `chat_id` — the trusted ID from the /entries POST.

6. Click **Save**.

7. Click **Test ICA**. Watch the SSE stream to `ICA connection is working. Reply: …`.

8. If **Test ICA** succeeded but the Settings status still shows `Not yet primed`, click **Initialize ICA System Prompt**. Wait for `ICA system prompt initialized`.

## Verify

- Settings status shows both `ICA: configured ✓` and `ICA: primed ✓`.
- Open the floating chat; ask Bee `Hi Bee` — you should get a persona-consistent reply within a few seconds.

## Rollback

If the new cookie captured is somehow worse than the previous one (rare), you can:

- Restore a backup of `pdf_extractor_v3.db` if you have one from before the sign-in ([Backup-and-Restore.md](../Backup-and-Restore.md)).
- Or manually paste the old cookie into the Full Cookie field on the Settings page (advanced — you'd need to have saved it externally).

Better path: just re-run this runbook.

## Notes

- The ICA cookie is stored in the `config` table (section `ica`, key `full_cookie`) as plain text. Windows file permissions on `%APPDATA%` are the only barrier — see [Security-Model.md](../Security-Model.md).
- If you never send a prompt in the sign-in window (step 4), V3 records the login as "cookie + team but no chat_id" — the Settings UI will prompt you to complete the step. Downstream Bee calls will fail until a trusted chat_id is captured.
- If your organisation forces frequent SSO re-auth, this runbook will run more often. Consider bookmarking it.
