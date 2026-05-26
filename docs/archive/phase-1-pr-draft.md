# Phase 1 PR draft

_Draft for the `phase-1-metadata-schema` → `main` PR. NOT committed; sits in working tree on main as an untracked artifact. Copy into `gh pr create --body` or the GitHub UI when ready._

---

**Title:** `Phase 1: metadata schema hardening + classifier preservation`

**Body:**

```markdown
## Summary

- Adds 8 observed-fact frontmatter fields (`word_count`, `char_count`, `token_estimate`, `attachment_count`, `tags_original`, `visibility_signal`, `restriction_check`, `restricted_to`). Derived classifications (size_class, staleness_class) deliberately deferred to dynamic reports so Aaron's thresholds don't require re-ingest to retune.
- Switches the puller to metadata-first listing with opportunistic `include-labels=true` fold-in (fallback to `/pages/{id}/labels`). Adds a frontmatter schema-version gate on **both** skip paths (`should_skip_by_version` + `should_skip`) so legacy `.sync-state.json` entries force backfill until every page is at schema v2.
- Adds rename-aware classifier preservation via `find_existing_page_file` — `audience`/`doc_type`/`tools`/`topics`/`tags_normalized` survive Confluence title and ancestor moves. Orphan files cleaned up after rename; cleanup failures escalate page status to `warning` and rewrite frontmatter honestly.
- Ships [scripts/tag_inventory.py](scripts/tag_inventory.py) (seeds F-05 taxonomy work) and [scripts/lint_wiki_citations.py](scripts/lint_wiki_citations.py) (F-10 citation lint, CI-wired via `tests/test_lint_wiki_citations.py`).
- Codifies the visibility model in [ADR-0006](docs/decisions/0006-visibility-metadata-is-descriptive.md) — visibility metadata is descriptive best-effort, not access enforcement. PAT scope IS the access boundary in V1.

Implements **F-01, F-02, F-04, F-05 (partial), F-06 (partial), F-10** from [docs/aaron-meeting-2026-05-18-followups.md](docs/aaron-meeting-2026-05-18-followups.md). Design freeze + codex review trail in [docs/phase-1-design-2026-05-19.md](docs/phase-1-design-2026-05-19.md).

Codex reviewed at G1, G2, G2-round-2, and approved with one parallelism nit (applied).

## What this PR does NOT do

- **No re-ingest.** Schema change is additive — existing files coexist fine, new fields populate on the next puller run. Scheduling re-ingest is the deployment step, not part of this PR.
- **No paid eval.** The 15-query baseline should be re-run post-ingest to confirm zero retrieval regression; defer to a separate gate.
- **No RBAC.** Visibility fields are descriptive metadata, not an enforcement boundary (see ADR-0006). Real access control waits on the OAuth 2.0 service account.

## Test plan

- [ ] `python -m pytest tests -q` — 197 passing locally on Windows + default basetemp
- [ ] `git diff --check` — exits 0 (CRLF→LF normalization on my modified files; view semantic diff with `git diff --ignore-cr-at-eol`)
- [ ] (post-merge) Run puller against the AI space (29 pages). Verify all pages rewrite under schema v2 — diff shows only frontmatter additions, no content changes.
- [ ] (post-merge) Run `python scripts/run_eval.py --mode raw --server http://127.0.0.1:8765` — confirm 14/15 baseline unchanged. Cost ~$0.10.
- [ ] (post-merge) Smoke-test `python scripts/tag_inventory.py` and `python scripts/lint_wiki_citations.py` against the live corpus.

## Files changed

- `src/sukb/ingest/frontmatter.py` — schema v2 fields, classifier preservation helpers, `find_existing_page_file`, `FRONTMATTER_SCHEMA_VERSION = 2`
- `src/sukb/ingest/puller.py` — metadata-first listing, `get_page_full` with include-labels fallback, `_extract_storage_body`, `_attempt_orphan_cleanup`, rename-aware preservation
- `src/sukb/ingest/state.py` — `frontmatter_schema_version` field on `PageState`, schema gate on both skip helpers
- `tests/ingest/test_frontmatter.py` — +19 tests (schema fields, threshold helpers, classifier preservation, rename-aware lookup, YAML ordering guard)
- `tests/ingest/test_state.py` — +9 tests (schema-version gate on both skip paths, legacy state migration, parallelism)
- `tests/ingest/test_puller_helpers.py` — new file, 12 tests (defensive body extract, orphan cleanup)
- `tests/test_lint_wiki_citations.py` — new file, 7 tests including a live-corpus regression guard
- `scripts/tag_inventory.py` — new, Phase 3
- `scripts/lint_wiki_citations.py` — new, Phase 3
- `docs/decisions/0006-visibility-metadata-is-descriptive.md` — new ADR
- `docs/decisions/README.md` — +1 line for ADR index
- `docs/phase-1-design-2026-05-19.md` — design freeze + codex review trail
- `docs/aaron-meeting-2026-05-18-followups.md` — followups doc that scoped Phase 1 (also informs Phase 2)

## Line-ending note

Files I touched have been normalized to LF to satisfy `git diff --check` under git's default `cr-at-eol` whitespace rule. Other files in the repo (untouched) remain CRLF. A `.gitattributes` policy can standardize the whole repo later — out of scope for this PR.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
