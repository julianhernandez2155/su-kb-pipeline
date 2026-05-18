---
status: accepted
date: 2026-05-14
supersedes:
---

# 0005. `src/` layout and `sukb` package rename

## Context

Before publishing the prototype to GitHub for Shahaan to collaborate on, the project's naming and structure had accumulated four conceptually distinct layers under one flat package name (`kb_ingest`):

1. **Confluence → markdown conversion** — puller, converter, macros, ADF, frontmatter, wikilinks, attachments, state, dead-letter
2. **Output corpus structure** — the on-disk artifact in `output/`
3. **Chat / RAG interface** — `kb_ingest.api.query`, `kb_ingest.api.sessions`
4. **Web app** — FastAPI server + Tailwind UI

The package name `kb_ingest` implied "just ingestion" but actually contained all four. The repo folder name `confluence-to-md-v2` implied "just conversion" but the project does much more. Distribution name (for `pip install`) didn't exist — there was no `pyproject.toml`.

This created three concrete problems for the GitHub publish:

- **Shahaan's onboarding signal-to-noise.** A package named `kb_ingest` containing a chat layer is misleading. A folder named `confluence-to-md-v2` containing a FastAPI server is misleading.
- **No installable distribution.** Scripts and tests required `sys.path` manipulation. `pip install -e .` wasn't possible. Onboarding required hand-wired path setup.
- **Layer boundaries weren't visible in the code.** Everything imported from a flat `kb_ingest/` namespace, so the four-layer mental model existed only in documentation, not in the directory tree.

## Decision

**Heavy restructure** before the first GitHub push:

1. **Folder rename:** `confluence-to-md-v2/` → `su-kb-pipeline/` (matches the product, not just the conversion tool).
2. **`src/` layout** for the Python package, per modern Python packaging conventions.
3. **Import package rename:** `kb_ingest` → `sukb` (short, matches project name, no underscore noise).
4. **Layer subpackages** under `src/sukb/` make the four layers structural, not just documentary:
   - `src/sukb/ingest/` — Layer 1 (puller, converter, macros, adf, frontmatter, attachments, wikilinks, state, dead_letter)
   - `src/sukb/chat/` — Layer 3 (query, sessions) — *moved from* `kb_ingest/api/`
   - `src/sukb/web/` — Layer 4 (server) — *moved from* `kb_ingest/api/`
   - `src/sukb/config.py` — shared utility used by all three layers
5. **Distribution name (`pyproject.toml`):** `su-kb-pipeline` (matches repo name; import package stays `sukb`). This is the standard pattern: distribution name is the public/PyPI name, import name is the short developer-facing name.
6. **Tests split** to mirror src/ structure: `tests/ingest/`, `tests/chat/`. Pytest discovers both via the `[tool.pytest.ini_options]` section in `pyproject.toml`.
7. **`pip install -e .` becomes the canonical setup path.** Scripts drop their `sys.path` hacks; conftest.py keeps a fallback that adds `src/` to sys.path so tests work even without the editable install.

## Consequences

**Positive:**

- Project name, repo name, package name, and on-disk folder all align around `su-kb-pipeline` / `sukb`. Shahaan's onboarding signal is unambiguous.
- The four-layer mental model is now visible in the directory tree, not just the README. Anyone (or anyone's agent) browsing `src/sukb/` sees `ingest/`, `chat/`, `web/` and understands the architecture immediately.
- Standard Python packaging — `pip install -e .` works, no `sys.path` manipulation needed in normal use. CI/CD path forward (when needed) is conventional.
- The `chat/` and `web/` separation makes the agentic-MCP plan ([ADR-0004](0004-agentic-tool-surface-mcp-architecture.md)) easier to execute: the chat layer can be imported into a future MCP server without dragging in the FastAPI web layer.

**Negative / trade-offs accepted:**

- Heavy migration in one pass — 14 file moves + ~20 import rewrites across src, tests, and scripts. Mitigated by phasing the work (Phase A: migration + test checkpoint, Phase B: docs polish, Phase C: publish) so pytest stayed green before any docs were touched.
- Existing references (in plans, prior commits, Codex's review notes) still say `kb_ingest`. Acceptable cost; those are historical.
- The folder rename hit Windows file locks (OneDrive + VSCode + Google Cloud Code extension) during execution. Had to defer the rename to the end of the publish flow. Logged for future ops: this kind of restructure inside OneDrive needs `code --disable-extension`-class workflow disruption to fully release handles.

## Alternatives considered

- **Light restructure: keep flat `kb_ingest/`, just rename folder + add `pyproject.toml`.** Lower-risk but doesn't make the four layers visible structurally. Rejected: the user explicitly asked for the layers to be reflected in the code, and the heavy restructure was the moment to do it (before any external collaborators see the old structure).
- **Even more aggressive: split into multiple installable packages (`sukb-ingest`, `sukb-chat`, `sukb-web`).** Future-considered for when this turns into a production library, but premature for v1.5. Rejected.
- **Keep package name `kb_ingest`, just add layer subpackages.** Half-measure that leaves the misleading top-level name in place. Rejected.
- **Distribution name = `sukb` (same as import name).** Standard practice is to have distribution name match the repo and product name, with import name being a short developer alias. Rejected per Codex's pre-publish review.

## References

- Plan that executed this migration: `~/.claude/plans/can-you-prep-my-shimmering-lemur.md`
- Final commit landing the restructure: `faf2b9e` (2026-05-14)
- Verification gate: 110/110 tests passed after migration before any docs work began
