"""Karpathy-style wiki-hub proposal pass over the v1 raw corpus (Step 4).

Loads all reviewed raw pages, sends the full corpus to Claude in one shot with
an explicit set of constraints (3+ page synthesis, no 1:1 rewrites, citation
depth focus), and saves the model's YAML proposals + rationale to a markdown
artifact under docs/.

Reuses sukb.chat.query for corpus loading + serialization so the format
matches what the live query endpoint sends.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sukb.chat import query as q  # noqa: E402
from sukb.config import SyncConfig  # noqa: E402

ENV_PATH = PROJECT_ROOT / ".env"

PROPOSAL_INSTRUCTIONS = """\
You are proposing wiki-hub articles for the Syracuse University AI Knowledge Base.

CONTEXT FROM THE V1.5 BASELINE EVAL (2026-05-13)
The raw corpus (29 ITSAI pages) already answers 14 of 15 representative student/staff queries
correctly and completely. Only 1 query (q03 "What AI tools at SU are approved for use with
university data?") scored partial — it cited only the master Approved-Tools page and missed
per-tool FAQ depth. Other "synthesis" queries (q04 tool comparison, q11 MCP) already worked
in raw-only mode by pulling adjacent pages on the fly.

Implication: the wiki layer's purpose at SU is NOT to rescue broken raw answers. It is to
improve (a) citation depth on cross-cutting questions, (b) canonical synthesis for
demoable/authoritative answers, and (c) stability of answers that today rely on
the model happening to find the right adjacent pages.

CONSTRAINTS (from wiki-operating-model.md)
1. Every hub must synthesize at least 3 raw pages. NO 1:1 rewrites of any single raw page.
2. A hub exists ONLY if it captures a view that no single raw page owns.
3. Each hub must cite raw page IDs as `[[<page-id>]]` for every claim.
4. Prefer FEWER, SHARPER hubs over many diluted ones. Quality > coverage.
5. Be honest about candidates that don't pass the bar — list them in "rejected_candidates".

OUTPUT FORMAT
Return a single YAML block with two top-level keys: `candidates` and `rejected_candidates`.

```yaml
candidates:
  - title: "Short, descriptive title"
    why_it_exists: "One sentence on the cross-cutting view this hub captures that no single raw page owns."
    addresses_eval_queries: ["q03", "q14"]   # which eval-set queries (q01..q15) this hub would canonicalize
    synthesizes:                              # raw page_ids — minimum 3
      - "488210484"
      - "488144948"
      - "..."
    example_queries:                          # 2-3 realistic SU questions this hub answers
      - "Can I use Claude with FERPA data?"
      - "..."
    draft_sketch: |
      2-3 sentences describing the hub's structure: opening framing, key section breakdown,
      a notable comparison or matrix if relevant. Not the full draft.
    leverage: "high" | "medium" | "low"      # your judgment of expected lift vs. raw-only
    leverage_rationale: "One sentence on why."

rejected_candidates:
  - title: "..."
    why_rejected: "1:1 with the X raw page" OR "synthesizes <3 pages" OR "duplicates an
                   already-strong raw page" OR "interesting but tangential to corpus mission"
```

Important:
- Don't pad the candidate list. If only 2 hubs clear the bar, propose 2.
- For each candidate, the `addresses_eval_queries` field must reference real query IDs from
  the eval set (q01-q15). If a hub doesn't address any specific eval query, that's a signal
  it may not be worth building yet.
- The `leverage` field should reflect: would this hub change a baseline-✅ answer? Or a
  baseline-⚠️ answer? Hubs that only improve already-✅ answers are lower leverage.
- After the YAML, write 2-3 sentences of meta-commentary: which 1-3 candidates should Step 5
  build first, and why.
"""

USER_KICKER = """\
Read every page in the corpus carefully. Then propose wiki-hub candidates per the rules above,
plus a `rejected_candidates` list, and your top-3 build recommendation.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-opus-4-7",
                    help="claude-opus-4-7 (default; better synthesis) or claude-sonnet-4-6 (cheaper)")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "sync_config.yaml"))
    ap.add_argument("--out", default=str(
        PROJECT_ROOT / "docs" /
        f"wiki-proposals-{time.strftime('%Y-%m-%d')}.md"))
    args = ap.parse_args()

    # Load .env so ANTHROPIC_API_KEY is available
    if ENV_PATH.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_PATH)
        except ImportError:
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY missing from environment / .env", file=sys.stderr)
        return 1

    config = SyncConfig.load(args.config)
    raw = q.load_raw_corpus(config)
    print(f"Loaded {len(raw)} raw pages from {config.raw_path}")
    if len(raw) < 3:
        print("ERROR: corpus too small to propose hubs", file=sys.stderr)
        return 1

    corpus_block = q.serialize_corpus(raw, [])

    from anthropic import Anthropic
    client = Anthropic()

    print(f"Calling {args.model}…")
    t0 = time.perf_counter()
    response = client.messages.create(
        model=args.model,
        max_tokens=8000,
        system=[
            {"type": "text", "text": PROPOSAL_INSTRUCTIONS},
            {"type": "text", "text": corpus_block,
             "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": USER_KICKER}],
    )
    elapsed = time.perf_counter() - t0

    body = response.content[0].text
    usage = response.usage
    pricing_per_mtok = {
        "claude-opus-4-7": {"input": 15, "output": 75, "cache_write": 18.75, "cache_read": 1.5},
        "claude-sonnet-4-6": {"input": 3, "output": 15, "cache_write": 3.75, "cache_read": 0.3},
    }.get(args.model, {"input": 3, "output": 15, "cache_write": 3.75, "cache_read": 0.3})

    cost = (
        getattr(usage, "input_tokens", 0) * pricing_per_mtok["input"]
        + getattr(usage, "output_tokens", 0) * pricing_per_mtok["output"]
        + getattr(usage, "cache_creation_input_tokens", 0) * pricing_per_mtok["cache_write"]
        + getattr(usage, "cache_read_input_tokens", 0) * pricing_per_mtok["cache_read"]
    ) / 1_000_000

    md = (
        f"---\n"
        f"title: Wiki-Hub Proposals — Step 4 Karpathy Pass\n"
        f"status: draft (LLM-generated; needs human curation before Step 5)\n"
        f"date: {time.strftime('%Y-%m-%d')}\n"
        f"project: kb-ingestion-internship\n"
        f"phase: Step 4 of next-phase-plan.md\n"
        f"model: {args.model}\n"
        f"corpus: {len(raw)} ITSAI pages (test fixtures excluded)\n"
        f"baseline_context: eval-baseline-2026-05-13.md (14 ✅ / 1 ⚠️ / 0 ❌)\n"
        f"prompt: see prototypes/confluence-to-md-v2/scripts/run_proposals.py\n"
        f"cost_usd: {round(cost, 4)}\n"
        f"latency_s: {round(elapsed, 1)}\n"
        f"---\n\n"
        f"# Wiki-Hub Proposals — Step 4\n\n"
        f"Proposal pass from {args.model} over the full 29-page raw corpus. The model was given\n"
        f"the v1.5 baseline context (raw-only is already strong; wiki's job is canonical\n"
        f"synthesis and citation depth, not rescue) and the wiki-operating-model rules.\n\n"
        f"Step 5 picks 1-3 of these to actually build as `output/wiki/*.md` hubs. The model's\n"
        f"top-pick recommendation appears in the meta-commentary at the bottom.\n\n"
        f"---\n\n"
        f"{body}\n"
        f"\n---\n\n"
        f"## Run metadata\n\n"
        f"- Model: `{args.model}`\n"
        f"- Cost: **${cost:.4f}** "
        f"(input={getattr(usage,'input_tokens',0)}, "
        f"output={getattr(usage,'output_tokens',0)}, "
        f"cache_write={getattr(usage,'cache_creation_input_tokens',0)}, "
        f"cache_read={getattr(usage,'cache_read_input_tokens',0)})\n"
        f"- Latency: {elapsed:.1f}s\n"
        f"- Reproducer: `python scripts/run_proposals.py --model {args.model}`\n"
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")

    print(f"\nwrote {out_path}")
    print(f"cost: ${cost:.4f} · latency: {elapsed:.1f}s")
    print(f"usage: input={getattr(usage,'input_tokens',0)} "
          f"output={getattr(usage,'output_tokens',0)} "
          f"cache_write={getattr(usage,'cache_creation_input_tokens',0)} "
          f"cache_read={getattr(usage,'cache_read_input_tokens',0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
