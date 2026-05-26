# docs/archive/

Historical planning and design docs that preceded the decisions now captured in [ADRs](../decisions/) and [session logs](../log/). Nothing here is a live reference — read the supersedor instead.

This folder exists for two reasons:

1. **Decision provenance.** When an ADR cites "we did a probe and observed X," the probe write-up may live here. Future readers asking "why did we choose schema v3?" can trace from ADR → archived plan → observed evidence.
2. **Flat-folder hygiene.** `docs/` was hitting the [folder-architecture-mistakes](../../../../CC%20Knowledge%20Base/wiki/patterns/folder-architecture-mistakes.md) #6 threshold (>10 files at one level). Moving the historical docs here keeps `docs/` scannable.

## Contents

| Archived doc | What it was | Live successor |
|---|---|---|
| [phase-1-design-2026-05-19.md](phase-1-design-2026-05-19.md) | G1/G2 design freeze + Codex review trail for Phase 1 metadata schema v2 | [ADR-0005](../decisions/0005-src-layout-and-sukb-package-rename.md), [ADR-0006](../decisions/0006-visibility-metadata-is-descriptive.md), [docs/log/2026-05-14.md](../log/2026-05-14.md) |
| [phase-1.1-plan-2026-05-19.md](phase-1.1-plan-2026-05-19.md) | Phase 1.1 implementation plan (3 steps + ADR timing) | [ADR-0007](../decisions/0007-access-classification-v1.md), [ADR-0008](../decisions/0008-space-classifier-tightening.md), [ADR-0009](../decisions/0009-mcp-read-path-filter.md), [docs/log/2026-05-19.md](../log/2026-05-19.md), [docs/log/2026-05-20.md](../log/2026-05-20.md) |
| [access-metadata-plan-2026-05-19.md](access-metadata-plan-2026-05-19.md) | API-shape probe deep-dive (`/restriction/byOperation` response shapes, Summer Intern finding) | [ADR-0007 §"Observed evidence"](../decisions/0007-access-classification-v1.md), [output/_access/access-summary.md](../../output/_access/access-summary.md) |
| [aaron-meeting-2026-05-18-followups.md](aaron-meeting-2026-05-18-followups.md) | Tracking doc for F-01 → F-15 follow-ups from Aaron's 2026-05-18 meeting | Shipped items: ADRs 0006–0010. Deferred items: [STATUS.md §"Out of scope"](../STATUS.md) and [ADR-0010 §"Future-readiness notes"](../decisions/0010-trust-zones-admin-vs-mcp.md). |
| [wiki-proposals-2026-05-13.md](wiki-proposals-2026-05-13.md) | Karpathy-style hub proposal pass (8 candidates, 2 approved, 6 rejected) | [output/wiki/index.md](../../output/wiki/) — the 2 shipped hubs |
| [phase-1-pr-draft.md](phase-1-pr-draft.md) | Working-tree PR body draft written before PR #1 actually opened | [PR #1](https://github.com/julianhernandez2155/su-kb-pipeline/pull/1) — the live PR with the comprehensive body |

## Operator rules

- **Don't update files in this folder.** They're frozen at the date in their filename. If a fact needs updating, it lives in the live successor (ADR / STATUS / log), not here.
- **Don't delete files here without a reason in a commit message.** The cost of keeping them is low; the cost of losing decision-provenance is high.
- **Cite from here only when an ADR explicitly references this folder.** Otherwise, link to the ADR.
