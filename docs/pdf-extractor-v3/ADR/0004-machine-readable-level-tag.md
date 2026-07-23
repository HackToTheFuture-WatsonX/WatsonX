# ADR 0004 — `[[level=…]]` marker for activity-log rows

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** V3 core team

## Context

The Logs page classifies each `extraction_logs.content` row as **Info**, **Warning**, or **Error** for filtering and badge colouring. Originally the classifier used a keyword heuristic:

```typescript
function inferLevel(content: string): 'Info'|'Warning'|'Error' {
  const lower = content.toLowerCase()
  if (/error|fail|exception/.test(lower)) return 'Error'
  if (/warn|cancel/.test(lower))           return 'Warning'
  return 'Info'
}
```

This misclassified:

- Successful sync completion → `Sync complete — 0 downloaded, 0 skipped, 0 error(s).` The word "error" matched → Error badge.
- Any Info row containing the string "warning" in a benign context.
- Any log mentioning the word "failed" inside a diagnostic ("last known failure was recovered").

Users reported the confusion: "the sync completed but the Logs page says it errored".

Alternatives considered:

1. **Rewrite messages to avoid trigger words.** Fragile; every message becomes hostile to expression.
2. **Add a `level` column to `extraction_logs`.** Cleanest, but a schema change requiring a migration story we don't yet have.
3. **Prefix the content with a machine-readable tag.** Zero schema change, backwards compatible, strippable at render time.

## Decision

Every activity-log write goes through `backend/activity.write(ref, content, *, level="info"|"warning"|"error")`, which prepends:

```
[[level=info]]  <content>
```

Frontend classifier (`Logs.tsx`) reads the tag first:

```typescript
const LEVEL_TAG_RE = /^\[\[level=(info|warning|error)\]\]\s*/i

function parseContent(raw: string): { level: Level; body: string } {
  const m = raw.match(LEVEL_TAG_RE)
  if (m) return {
    level: (m[1] === 'error' ? 'Error' : m[1] === 'warning' ? 'Warning' : 'Info'),
    body:  raw.replace(LEVEL_TAG_RE, ''),
  }
  // Fallback for legacy rows written before this ADR was implemented.
  // Uses a smarter regex that ignores "0 error(s)" / "0 failed" phrasing.
  ...
}
```

The tag is stripped from the displayed body — users never see it.

Every existing `activity.write()` call site (`sync.py`, `scanner.py`, `settings.py`, `chat.py`, `extractor.py`) was audited and now passes an explicit `level=` argument matching the semantic:

- **info** — success, empty runs, benign skips.
- **warning** — cancellations, missing credentials, per-item failures inside an otherwise-successful batch.
- **error** — exceptions, connection tests that failed, JWT upload rejections.

## Consequences

**Positive**
- Deterministic classification — no more phrase-matching false positives.
- Zero schema change; forwards-compatible with the future `level` column if we ever add one.
- Legacy rows still render acceptably via the fallback heuristic.
- The activity log doubles as a structured audit trail.

**Negative**
- Content strings now have a small opaque prefix that isn't user-visible but is present in the DB. Anyone reading `pdf_extractor_v3.db` directly (via `sqlite3`) sees the marker.
- Every new activity write must pass an explicit level or the default `info` is used — reviewers must catch this in PRs.

**Neutral**
- Content is still just text — no structured logging library was introduced.

## Related

- `backend/activity.py`
- `frontend/src/pages/Logs.tsx:parseContent`
- [Business-Rules.md](../Business-Rules.md#br-15-per-file-log-level-semantics)
