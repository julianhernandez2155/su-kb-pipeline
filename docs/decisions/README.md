# Architecture Decision Records

This directory holds ADRs (Architecture Decision Records) for `su-kb-pipeline` in [MADR](https://adr.github.io/madr/) format. Each ADR captures one decision: what we chose, why, and what we accepted as trade-offs. ADRs are **immutable once accepted** — when a decision changes, write a new ADR that supersedes the old one. The old ADR's `status` field is updated to point at the new one, but its body stays as historical record.

## Index

| # | Title | Status | Date |
|---|---|---|---|
| [0001](0001-page-id-prefixed-filenames.md) | Page-ID-prefixed filenames | accepted | 2026-05-09 |
| [0002](0002-fallback-first-adf-parsing.md) | Fallback-first ADF parsing | accepted | 2026-05-10 |
| [0003](0003-rag-pipeline-mcp-architecture.md) | RAG-pipeline MCP architecture (original) | superseded by [0004](0004-agentic-tool-surface-mcp-architecture.md) | 2026-05-05 |
| [0004](0004-agentic-tool-surface-mcp-architecture.md) | Agentic tool-surface MCP architecture | accepted | 2026-05-13 |
| [0005](0005-src-layout-and-sukb-package-rename.md) | `src/` layout + `sukb` package rename | accepted | 2026-05-14 |
| [0006](0006-visibility-metadata-is-descriptive.md) | Visibility metadata is descriptive, not enforcement | accepted | 2026-05-19 |

## Adding a new ADR

Easiest path: invoke the `decision-log` skill in a Claude Code session:

- `/decide <one-line title>` — bootstrap a new ADR
- `/supersede NNNN` — create a new ADR that overrides ADR-NNNN (and updates 0NNN's status to point at the new one)

Manual path:

1. Copy an existing ADR (e.g., `0001-page-id-prefixed-filenames.md`) as a template
2. Bump the number to the next sequential 4-digit slot
3. Fill in Context / Decision / Consequences
4. Update the index table above
