# ADR 0003 — ICA two-POST prompt/answer flow

- **Status:** Accepted
- **Date:** 2026-03-05
- **Deciders:** V3 core team

## Context

V2's chat integration used a one-POST flow:

1. `POST /chats/<id>/entries` with `{type: "PROMPT", content: {prompt: "..."}}`.
2. Poll `GET /chats/<id>/entries` until an `ANSWER` entry appeared.

The polling loop timed out on every request with "ICA did not respond in time". After tracing the browser DevTools of a working ICA session, we found the actual flow:

1. `POST /chats/<id>/entries` with `{type: "PROMPT", ...}` → server returns `{ _id: "<promptEntryId>", ... }`. **No inference is triggered.** The chat just accumulates the prompt.
2. `POST /chats/<id>/entries` with `{type: "ANSWER", content: {answer: "", promptEntryId: "<id>"}}`. **This** is the request that triggers inference. It returns HTTP 201 with `Content-Type: text/event-stream` carrying chunks literally prefixed with `answer: `.

Additional gotchas we hit and solved along the way:
- `teamid` and `teamname` headers must be URL-encoded — raw spaces caused Akamai to reject with HTTP 501.
- `promptEntryId` must live inside `content`, not at the top level — otherwise ICA replies with a NOTIFICATION titled "No prompt entry found".
- The SSE body chunks are concatenated with `"answer: "` between them. The correct parse is a plain `raw.replace("answer: ", "").strip()`.
- HttpOnly cookies (auth token) are only available via the Electron cookie jar — `webRequest.onSendHeaders` never sees them. Must call `session.cookies.get()`.

## Decision

Implement the two-POST flow in `backend/chat.py:_ica_send_and_stream`:

```python
# Step 1: POST PROMPT, capture _id
prompt_payload = json.dumps({
    "chatId": chat_id, "type": "PROMPT",
    "content": {"prompt": prompt, "promptId": "", "promptUuid": "",
                "isIncludedInContext": True,
                "sensitiveInformation": {"hasSensitiveInformation": False}}}).encode()
# ... urlopen ... echo = json.loads(...) ; prompt_id = echo["_id"]

# Step 2: POST ANSWER trigger, read SSE stream
answer_payload = json.dumps({
    "chatId": chat_id, "type": "ANSWER",
    "content": {"answer": "", "promptEntryId": prompt_id}}).encode()
sse_headers = _ica_headers(..., accept="text/event-stream")
# ... urlopen ... raw = resp.read().decode(...)
return raw.replace("answer: ", "").strip()
```

Route every ICA-bound message through this one function. Log the full request context (with cookie fingerprint only, never the value) to `%APPDATA%\PDF Extractor V3\ica.log` so failures are diagnosable after the fact.

For login, the browser-assisted flow (`electron/main.js:icaBrowserLogin`) only trusts a `chat_id` observed on a `/entries` POST — provisional IDs seen on metadata/config URLs are discarded on window close. This prevents the two-POST flow from targeting an uninitialized thread.

## Consequences

**Positive**
- Every ICA request produces a real answer within seconds instead of timing out.
- Errors get a clear cause (Akamai 501 vs "No prompt entry found" vs cookie expiry) surfaced through the SSE stream to the Settings UI.
- The ICA log makes reproducing production failures possible without a fresh sign-in session.

**Negative**
- Non-obvious contract — any developer touching the ICA path must read this ADR first.
- If ICA's contract changes (they add auth headers, change `_id` field name, drop the `answer: ` prefix), our transport breaks.

**Neutral**
- No official API documentation for ICA exists; the contract was reverse-engineered from browser traffic. When a breaking change happens, expect a hotfix release.

## Related

- `backend/chat.py:_ica_send_and_stream`
- `electron/main.js:icaBrowserLogin`
- [System-Design.md](../System-Design.md#ica-two-post-flow)
