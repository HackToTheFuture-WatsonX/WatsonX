# Feature Request Process

How ideas become tracked work, then shipped features.

---

## Where to File

- **GitHub issue** on the project repo, using the `feature-request` label.
- **Slack** DM to the maintainer for a synchronous discussion first (helpful for anything vague or exploratory).
- **Email** with `[V3-feature]` in the subject if GitHub isn't available.

Do not file feature requests via bug reports or Chat with Bee — those channels are for different things.

---

## Anatomy of a Good Feature Request

Include, at minimum:

1. **The user problem** — What are you trying to accomplish that V3 makes hard today? (Not "add X"; instead "I need to do Y and X would help").
2. **The workflow it belongs to** — Which of the eight pages (Home / Sync / Scan / Extract / View / Insights / Logs / Settings) or global surfaces (Chat, notifications) is affected?
3. **Frequency and impact** — How often does this come up? Who else feels it?
4. **Workarounds you've tried** — Reveals shape of the actual gap.
5. **Success signal** — How will you know the feature works?

Bonus:
- Screenshots or annotated mockups.
- Sample data (redacted) showing the input/output shape.
- Existing behaviour excerpt from the Logs page.

---

## Triage

Requests are triaged into one of:

| Verdict | Meaning |
|---|---|
| **Accepted** | Added to [Roadmap.md](Roadmap.md) with a target release |
| **Deferred** | Valid but not prioritised; sits in the backlog |
| **Duplicate** | Existing tracked item — link provided |
| **Out of scope** | Doesn't fit V3's charter (see [Feature-Scope.md](Feature-Scope.md#out-of-scope-deliberate)); rationale provided |
| **Needs info** | Reporter asked for more context |

Target triage response time: **one business week**.

---

## Design Discussion

For anything larger than a trivial UI tweak, the maintainer opens a short design thread on the issue:

- What's the smallest useful shape of the feature?
- Does it need an ADR? (See [ADR/](ADR/) — required when it crosses a module boundary, adds a dependency, or changes on-disk format.)
- What's the rough effort?
- What breaks?

Not every feature needs an ADR — only those that affect architecture. UI-only work doesn't.

---

## Prioritisation

Ordered roughly by:

1. **Fixes to shipped behaviour** — actual bugs, always highest.
2. **Compliance / security requirements** — legal or regulatory forcing functions.
3. **Broad user-value features** — features hitting the primary persona ([P1](User-Personas.md#p1--hr-operations-analyst-primary)).
4. **Ergonomic wins** — features hitting power users ([P4](User-Personas.md#p4--power-user--analyst-with-curiosity-occasional)).
5. **Nice-to-haves** — cosmetic, edge cases.

No formal weighted-scoring rubric — the maintainer's judgement call, informed by user feedback volume and roadmap alignment.

---

## From Roadmap to Ship

Once on the roadmap, a feature goes through:

1. **Design confirmation** — ADR authored if required.
2. **Implementation** — usually one PR against `main` (or a feature branch for anything > 200 LoC).
3. **Manual verification** — smoke test per [Deployment-Guide.md](Deployment-Guide.md#smoke-test-checklist).
4. **Docs update** — the relevant pages under `docs/pdf-extractor-v3/` are updated in the same PR.
5. **Release** — bundled into the next release ([RB-01](Runbooks/RB-01-rebuild-and-release.md)).
6. **Announcement** — an entry in [Release-Notes.md](Release-Notes.md).

Small features can go from filed to shipped in a week. Larger ones take a release cycle (typically 2–4 weeks).

---

## Feedback After Shipping

The requester is notified when the feature ships. If it doesn't solve the original problem:

1. Reopen the original issue with what's still missing.
2. Attach fresh context (a screenshot, a Logs export, whatever's relevant).
3. The maintainer decides between a follow-up patch or a new feature ticket.

---

## What Not to Request

Consistent with [Feature-Scope.md](Feature-Scope.md#out-of-scope-deliberate):

- Multi-user server mode.
- Non-Windows binaries (macOS/Linux are on the roadmap; not on the ask list).
- Editable exports (V3 is read-only extraction).
- Non-Box source integrations.
- Push notifications.
- OCR for scanned PDFs.

If your need is one of these, the answer is "not planned" — but it's worth filing the request anyway so the pattern is visible to future planning.

---

## Related

- [Roadmap.md](Roadmap.md) — the tracked-forward list
- [Feature-Scope.md](Feature-Scope.md) — what's in / out
- [Bug-Report-Process.md](Bug-Report-Process.md) — for bugs, not features
- [ADR/](ADR/) — for architectural decisions
