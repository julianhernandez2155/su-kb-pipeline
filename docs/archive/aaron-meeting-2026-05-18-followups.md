# Aaron Meeting Follow-ups — 2026-05-18

_Source: Group Meeting 2026-05-18, 13:04–14:03 (Aaron Starr, Shahaan Khan, Julian Hernandez, Robert Dube). Transcript: `C:\Users\julia\Downloads\Group Meeting.docx`._

## Context for the reviewer (codex)

This doc captures every architectural / product change that came out of yesterday's stakeholder review with Aaron Starr (ITS, primary contact). It is **scoped to Julian's lane — folder & file architecture** (the `output/`, `src/sukb/ingest/`, `src/sukb/chat/` surface). Shahaan owns the FastMCP server side; items there are out of scope unless our folder schema has to support them.

The goal is for codex to read this against the actual codebase (`src/sukb/`, `output/`, `docs/`) and decide:

1. Which items are real work vs. already-handled vs. premature.
2. Where each surviving item lands on the priority ladder.
3. Whether any item should become an ADR (we have an ADR convention — see [decisions/README.md](decisions/README.md)).

Items use stable IDs (`F-NN`) so review notes can reference them.

## Status legend

| Status | Meaning |
|---|---|
| `open` | Not started, not analyzed yet |
| `triage` | Needs codex review before we commit |
| `in-progress` | Active work |
| `done` | Shipped |
| `dropped` | Decided against |

## Summary table

| ID | Title | Aaron-asked? | Priority (proposed) | Status |
|---|---|---|---|---|
| F-01 | Visibility / restriction metadata + `raw/public/` split | ✅ explicit (Julian called out by name) | P0 | triage |
| F-02 | Version-aware incremental sync (skip unchanged) | ✅ explicit | P0 | triage |
| F-03 | Edit-cadence time-series report | ✅ explicit ("we can give that a shot") | P1 (unblocks cron decision) | triage |
| F-04 | Page-size edge cases (oversize stub + tiny fallback) | ✅ explicit | P1 | triage |
| F-05 | Tag taxonomy + `tags_original` / `tags_normalized` split | ✅ explicit (long discussion) | P1 | triage |
| F-06 | Staleness tracking + weekly digest | ✅ explicit (Shahaan promised; Aaron liked) | P2 | triage |
| F-07 | Hierarchical index (scales 34 pages → 30 spaces × thousands) | implied (scale signal) | P1 | triage |
| F-08 | Cross-space hub `scope` field | implied (Maxwell+AI example) | P2 | triage |
| F-09 | Department handoff template | implied (Aaron: "hand to other people") | P2 | triage |
| F-10 | Source-citation lint with page-id resolution | implied (Aaron clicks through to verify) | P2 | triage |
| F-11 | OAuth 2.0 abstraction in puller | implied (service account constraint) | P2 | triage |
| F-12 | Read-only enforcement on `raw/` (test) | implied (MCP is read-only; mirror it) | P3 | triage |
| F-13 | Classifier-model eval harness (Haiku vs Sonnet vs Opus) | ✅ explicit (Aaron's question) | P2 (Shahaan-led, Julian-supported) | triage |
| F-14 | Low-confidence review queue surface | implied (Shahaan's 0.7 threshold) | P3 | triage |
| F-15 | Usage / audit-report from source-id citations | implied (audit-log positioning) | P3 | triage |
| D-01 | Send Aaron: VM/service-account/ownership checklist | ✅ explicit | P0 (this week) | open |
| D-02 | Send Aaron: PowerPoints | ✅ explicit | P0 (this week) | open |
| D-03 | Send Aaron: GitHub repo links | ✅ explicit | P0 (this week) | open |

---

## F-01 — Visibility / restriction metadata + `raw/public/` split

**Source.** Aaron, ~27:00: _"on Julian side, I think one thing to look at is also the page restrictions… we need to kind of have the AI not talk to that based on who you are."_ Followed by agreement (Aaron + Shahaan + Julian) that V1 ingests **public-only**, with a two-tier future: (1) public MCP owned by ITS, (2) private admin MCPs per department.

**Why it matters.** Even though V1 is public-only, the schema needs to encode visibility from day one — otherwise we re-ingest everything when the admin tier comes online, and we have no audit trail for "why didn't we surface page X?"

**Proposed change.**
- Add frontmatter fields to every page in `output/raw/`:
  - `visibility: public | restricted | unknown`
  - `restricted_to: [<group-id or user-id>...]` (empty list when public)
  - `audience: student | admin | mixed` (initial value from heuristic; Haiku can refine)
- Puller change ([src/sukb/ingest/](../src/sukb/ingest/)): when `permissions.read` is non-empty from the Confluence API, write a stub to `output/quarantine/<page-id>.md` containing only `{id, title, url, last_updated, reason: "restricted at source"}` — body is never fetched.
- Filesystem split: `output/raw/public/` (everything MCP can see) vs. `output/raw/internal/` (future admin tier, empty for now). Loader (`sukb.chat.query.load_wiki_corpus` and similar) reads only `public/`.

**Open questions for codex.**
- Does Confluence's REST response include enough permission detail to classify reliably, or do we need a separate `/permissions` call per page? (Check `learnings/confluence_at_syracuse.md` first.)
- Should `quarantine/` be inside `output/` or outside? Argument either way.
- Is the `audience` field worth populating now, or defer until classifier work in F-05/F-13?

---

## F-02 — Version-aware incremental sync (skip unchanged)

**Source.** Aaron, ~30:00: _"if the version hasn't changed, then forget about it. Don't waste our money trying to do anything."_

**Why it matters.** Biggest cost lever at scale. We already pull `version` in metadata (Aaron noticed); we just don't act on it. Saves the Haiku classification spend Shahaan is currently incurring on every sync.

**Proposed change.**
- Persist per-space sync state in `output/_state/<space>.json`: `{page_id: {last_synced_version, last_classified_version, last_synced_at, content_hash}}`.
- Sync loop:
  1. Fetch metadata only (cheap call).
  2. Compare `version` to `last_synced_version`.
  3. If unchanged → skip body fetch, skip re-classify, skip markdown rewrite.
  4. If `version` bumped but `content_hash` of body matches → re-write metadata only, skip classify.
  5. If both changed → full re-ingest + re-classify.
- This composes with the existing content-hash skip (per [STATUS.md](STATUS.md) — "re-runs are 1.5s no-ops via content-hash skip"). Codex should check whether the existing hash-skip already covers part of this and we only need the version-gate on classification.

**Open questions for codex.**
- Does the existing hash-skip already short-circuit body fetch, or only the markdown write? If it already skips fetch, F-02 collapses to "add a classification-version gate."
- Confluence webhook option (Aaron mentioned): defer? Probably yes — cron is cheaper and we're not latency-bound.

---

## F-03 — Edit-cadence time-series report

**Source.** Aaron asked directly, ~42:00: Shahaan offered _"do you want us to run a time series on it and just tell you like over the last like year how many updates happened month over month."_ Aaron: _"Yeah, we can give that a shot."_

**Why it matters.** Aaron is leaning weekly or monthly cron, not daily. He won't commit until he sees the data. This is the unblocker for the sync-cadence decision.

**Proposed change.**
- New `scripts/analyze_edit_cadence.py`: queries Confluence `content/{id}/history` (or the `version` endpoint) across all 30 spaces we can read, last 12 months.
- Output: `research/kb-ingestion-project/sync-cadence-analysis-2026-05-19.md` with edits/month per space, p50/p95 staleness, recommendation (weekly vs monthly), spaces with anomalously high churn.
- Output the same table as JSON in `output/_reports/edit-cadence-<date>.json` for re-use by Shahaan's cron tooling.

**Open questions for codex.**
- Single script or split into "fetch raw history" + "render report"? Probably split — fetch is slow + idempotent, render is fast + iterative.
- API rate limits at 30-space × N-page × history scale — does the existing puller's rate-limit handling generalize?

---

## F-04 — Page-size edge cases (oversize stub + tiny fallback)

**Source.** Aaron, ~33:30: _"what happens if the page is ginormous? […] What happens if a page is like nothing or it just says like placeholder or has just one image?"_ Resolution in the call:
- Hard size limit picked from top-10 largest pages per space (manually evaluated).
- Title-only fallback ("the AI could say, hey, I can't read the page, but this seems maybe up your alley").

**Why it matters.** Currently we load full bodies indiscriminately. At scale this blows the agent's context window and wastes inference. Tiny/empty pages waste a tool-call.

**Proposed change.**
- At ingest, compute and store in frontmatter: `word_count`, `char_count`, `token_estimate` (use tiktoken or a cheap heuristic — codex pick), `attachment_count`, `size_class: tiny | normal | large | oversize`.
- For `oversize` (over the per-space cap): body is **not** written into the page markdown. Instead, write a stub: title + ancestors + first-N-words summary + URL + size warning. Stub still gets a page-id filename so links don't break.
- For `tiny`: keep the body (it's small) but tag `size_class: tiny` so the agent can degrade gracefully ("page exists but has no content — try the URL").
- The space-level [index.md](../output/raw/knowledge-bases/Artificial%20Intelligence%20%28AI%29/index.md) surfaces `size_class` so the agent can decide between `get_page` vs `title_only` retrieval.

**Open questions for codex.**
- Where does the per-space "top-10 → cap" logic live — a one-time script, or in the puller (re-evaluated each sync)?
- Should `oversize` stubs live in `raw/` alongside normal pages, or in a separate `raw/oversize/`? Separation cleaner; co-location preserves the hierarchy mirror.

---

## F-05 — Tag taxonomy + `tags_original` / `tags_normalized` split

**Source.** Long discussion at ~36:00–40:00. Aaron: _"I'm a big believer in structure… I like the idea of an AI reading the tag… we strip away almost everyone's ability to add tags themselves."_ Aaron confirmed _"not really, not for confluence"_ when asked if ITS has a tag gold standard. Shahaan proposed comparing existing-tags vs AI-generated tags side-by-side; Aaron agreed.

**Why it matters.** Confluence-author tags are inconsistent and free-form — Shahaan's classifier is already compensating, but without a canonical taxonomy we can't QC the classifier or stabilize the user-facing filter set.

**Proposed change.**
- Create `taxonomies/its-tags.md` — canonical tag list. V1 seed: pull every existing Confluence label across the 30 spaces, dedupe, manually curate.
- Frontmatter dual-track: `tags_original: [...]` (from author, never overwritten) and `tags_normalized: [...]` (from classifier, regenerated on body change per F-02).
- Reserved system tags the agent can filter on: `_meta/oversize`, `_meta/stale-2y`, `_meta/abandoned-5y`, `_meta/empty`, `_meta/review-pending`. These are written by pipeline logic, never by humans or the classifier.
- New `scripts/tag_audit_report.py` — compares author tags vs classifier tags, emits delta. Output to `research/kb-ingestion-project/tag-audit-<date>.md`.
- Tags feed cross-space synthesis hubs (Maxwell+AI example) — see F-08.

**Open questions for codex.**
- Should the taxonomy be flat or hierarchical (`policy/access`, `policy/usage`)? Aaron didn't specify; Shahaan's classifier emits `type` (how-to / FAQ / concept / policy) + free-form tags — those should probably stay separate fields.
- Does `taxonomies/` belong at the repo root or under `output/`? It's data about the corpus, not corpus content — repo root probably.

---

## F-06 — Staleness tracking + weekly digest

**Source.** Shahaan, ~22:00: _"you have about 20 pages that are stale, that are over 2 years old, and if they're over five years, do you want us to just get rid of them?"_ Aaron: _"Yeah."_

**Why it matters.** Aaron likes this as a differentiator vs the Atlassian Rovo connector. The weekly digest is the surface; the folder schema has to support it.

**Proposed change.**
- Frontmatter additions (computed at ingest): `last_updated_at` (already present — confirm), `staleness_days`, `staleness_class: fresh | aging | stale-2y | abandoned-5y`.
- Lint rule on `output/wiki/` hubs: a hub at `status: evergreen` whose cited sources are ≥50% `stale-2y` auto-demotes to `reviewed` and the lint emits a warning. Codifies the "hubs should be backed by living sources" rule from [wiki-operating-model.md](wiki-operating-model.md).
- `scripts/weekly_staleness_report.py` — markdown digest by space + owner. Folder side supports it; cron + email delivery is Shahaan's MCP server side.

**Open questions for codex.**
- Are the thresholds (2y / 5y) right, or should they come from F-03's edit-cadence data? Probably the latter once we have it.
- Should the digest also flag *low-confidence-classified* pages (F-14)? Combining surfaces might be cleaner.

---

## F-07 — Hierarchical index (scales 34 pages → 30 spaces × thousands)

**Source.** Implied — Aaron asked how this scales. Currently:
- `output/index.md` (top-level)
- `output/raw/knowledge-bases/<space>/index.md`
- `output/wiki/index.md`

At 30 spaces × thousands of pages, a single top-level index will not fit in one tool-call context window. We hit this before we hit any retrieval-quality problem.

**Why it matters.** The architecture's whole pitch is "the corpus carries the map." If the map doesn't fit, the pitch breaks at scale.

**Proposed change.**
- Three index tiers:
  1. `output/index.md` — lists *spaces only*. Tiny, always loadable.
  2. `output/raw/<space>/index.md` — lists ancestor tree + hubs *for that space*. Bounded per space.
  3. `output/wiki/index.md` — *cross-space hubs only*. Per-space hubs move to `output/wiki/<space>/index.md`.
- Agent navigation pattern: read top-level → pick space(s) → read per-space index → fetch hubs or pages.
- Codex should compare against current [output/CLAUDE.md](../output/CLAUDE.md) agent-rules and see whether the agent prompt needs updating for the new tier.

**Open questions for codex.**
- Should the per-space index include `size_class` and `staleness_class` columns (F-04, F-06)? Probably yes — they enable agentic skip decisions without a `get_page`.
- Is there a max-size budget for any single index file we should enforce in lint?

---

## F-08 — Cross-space hub `scope` field

**Source.** Implied. Julian's Maxwell+AI example to Aaron — a hub that spans the Maxwell School space and the AI space. Hub frontmatter currently has no scope field.

**Proposed change.**
- Frontmatter on every hub in `output/wiki/`: `scope: space:<name>` or `scope: cross-space:[<space-a>, <space-b>, ...]`.
- File layout follows scope: single-space hubs at `output/wiki/<space>/<hub>.md`, cross-space at `output/wiki/cross-space/<hub>.md`.
- Lint rule: a hub's citations (`[[<page-id>]]`) must all resolve to pages whose space is in the hub's `scope`.

**Open questions for codex.**
- Is `scope: cross-space:[...]` already implicit in our current hubs? If so this is a frontmatter formalization, not new functionality.

---

## F-09 — Department handoff template

**Source.** Aaron, ~30:00: _"we like to build products that we can hand to other people and they can manage."_ The vision is admin-tier MCPs per department.

**Proposed change.**
- Carve out `templates/department-kb-skeleton/` containing empty `raw/`, `wiki/`, a templated `CLAUDE.md`, a templated `index.md`, and a `setup.md` with the 5-step "to onboard your space, do X."
- This is portable — not part of the public corpus build.

**Open questions for codex.**
- Is this premature given V1 is public-only? Counter-argument: doing it now is cheap, and Aaron explicitly flagged the handoff model as core.

---

## F-10 — Source-citation lint with page-id resolution

**Source.** Implied. Aaron's quality bar: he clicks through to verify. If a hub cites `[[123]]` and `123` was deleted upstream, the hub silently lies.

**Proposed change.**
- Extend the existing citation lint (per [output/CLAUDE.md](../output/CLAUDE.md) "every claim cites `[[<page-id>]]`") to also verify each cited page-id resolves to a real `output/raw/.../<id> - *.md` file. Missing-target citations fail the lint.
- Wire into the existing test suite at [tests/](../tests/) so CI catches it.

---

## F-11 — OAuth 2.0 abstraction in puller

**Source.** Aaron, ~43:00: _"they're unlikely to give us like a random user… it's basically gonna have to go down to an OAuth, most likely the OAuth 2.0 authentication."_

**Proposed change.**
- Abstract the auth layer behind a `sukb.auth.Provider` interface (PAT now, OAuth 2.0 later).
- Config-driven swap, not a code rewrite.

**Open questions for codex.**
- How tightly is the current puller coupled to PAT? Might be a one-line change to swap headers, or a deeper refactor.

---

## F-12 — Read-only enforcement on `raw/` (test)

**Source.** Implied. Aaron approved Shahaan's MCP being read-only. Mirror constraint in repo: nothing in `src/sukb/` except `ingest/` should open files in `raw/` for write.

**Proposed change.**
- Add a unit test that walks the `src/sukb/` tree and fails if any non-`ingest/` module opens `output/raw/*` with a write mode.
- Or simpler: a lightweight runtime guard / `pathlib` wrapper.

---

## F-13 — Classifier-model eval harness (Haiku vs Sonnet vs Opus)

**Source.** Aaron, ~45:00: _"how would we test the Haiku response better, or how does Sonnet respond and how does Opus respond?"_ Aaron flagged University-prefers-Claude (no ChatGPT/Nano).

**Why this is here (it's mostly Shahaan's lane).** The harness needs a stable test set + side-by-side tag-output diff, which lives in `eval-runs/` on Julian's side. Julian provides the eval scaffolding; Shahaan runs the comparison.

**Proposed change.**
- Reuse the existing `eval-runs/` structure (per [STATUS.md](STATUS.md)).
- Output: `research/kb-ingestion-project/classifier-model-comparison-<date>.md` with 10–20 pages × 3 models × 2–3 runs (variance check).
- Compare on: tag overlap, confidence calibration, cost, time.

---

## F-14 — Low-confidence review queue surface

**Source.** Shahaan, ~51:00: _"if the confidence is less than 0.7… it gets flagged for human review."_

**Proposed change.**
- Frontmatter: `classifier_confidence: <0.0-1.0>`, `review_pending: bool` (true when confidence < threshold).
- A `_review_queue.md` auto-generated index of all `review_pending: true` pages. Surfaces in the weekly digest (F-06).
- The classifier skips re-tagging on next sync if `review_pending: true` and version hasn't changed — wait for human input.

---

## F-15 — Usage / audit-report from source-id citations

**Source.** Aaron, ~56:00: audit was framed as a competitive differentiator vs Rovo. _"we can audit what people query is going to be really big."_

**Proposed change.**
- Folder side: ensure every agent response logs the page-ids it cited in a parseable format. (Shahaan's MCP logs queries; this is the join key.)
- `scripts/usage_report.py` — answers "which pages got cited last 30 days," "which pages never get cited," "which hubs are dead weight."

---

## Deliverables Aaron asked us to send him (close-of-meeting, 58:00–58:50)

### D-01 — VM / service-account / ownership checklist
One-page doc, what we need from ITS:
- VM specs (2 vCPU, 4 GB RAM, 100 GB disk per Shahaan)
- Atlassian OAuth 2.0 service account
- Hosting decision (VM vs. RDS vs. Azure)
- Ownership decision (ITS owns public tier — Aaron will discuss with Ryan/Andrew)

Location: `SU_AI_Intern/deliverables/2026-05-19-aaron-checklist.md`. Link from STATUS.md.

### D-02 — PowerPoints
Julian's deck + Shahaan's deck. Send via Teams.

### D-03 — GitHub repos
Julian's repo URL + Shahaan's repo URL. Send via Teams.

---

## Suggested next-session ordering (proposed; codex can re-rank)

1. **D-01 / D-02 / D-03** — send today/tomorrow so VM + service-account requests get in motion.
2. **F-03** — edit-cadence report. Aaron explicitly asked, blocks his sync-cadence decision.
3. **F-01 + F-02 + F-04** — schema migration (visibility, version, size). Do together — they all touch the same frontmatter + puller code.
4. **F-05** — tag taxonomy seed + audit. Feeds both folder structure and Shahaan's classifier eval (F-13).
5. **F-07** — hierarchical index restructure. Before any scale-up to a second space.
6. Everything else.

## Codex review prompts (suggested)

When reviewing this doc against the codebase, codex could focus on:

1. **Already-done detection.** Anything in F-01..F-15 that's already implemented? STATUS.md mentions content-hash skip — does that subsume F-02?
2. **Wrong-lane items.** Anything here that's actually MCP-server work, not folder-architecture work?
3. **Priority re-rank.** With actual code visibility, which P-tier is wrong?
4. **ADR candidates.** Which items are big enough to warrant a new ADR vs. just a code change? F-01 (visibility model), F-05 (taxonomy), F-07 (hierarchical index) feel ADR-shaped.
5. **Missing items.** Anything Aaron said that I missed in the transcript pass?
