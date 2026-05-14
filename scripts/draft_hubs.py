"""Draft the two Step-5 wiki hubs from the Step-4 proposal pass.

For each hub spec, sends the full raw corpus + spec to Opus 4.7 and asks it
to write a draft hub article that follows wiki-operating-model.md (frontmatter
+ `[[<page-id>]]` citations on every claim, no claims without source).

Writes each draft to `output/wiki/<slug>.md` with `status: draft`. A human
must verify each citation resolves and then promote to `status: reviewed`.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sukb.chat import query as q  # noqa: E402
from sukb.config import SyncConfig  # noqa: E402

ENV_PATH = PROJECT_ROOT / ".env"


@dataclass
class HubSpec:
    slug: str
    title: str
    why_it_exists: str
    addresses_eval_queries: list[str]
    synthesizes: list[str]
    example_queries: list[str]
    draft_sketch: str
    tags: list[str] = field(default_factory=list)


HUBS: dict[str, HubSpec] = {
    "approved-tools": HubSpec(
        slug="approved-ai-tools-for-university-data",
        title="Approved AI Tools at Syracuse: Data Policy & Capability Comparison",
        why_it_exists=(
            "No single page compares the approved tools side-by-side on data handling "
            "(retention, training, ownership, allowed data classifications). The master "
            "list is link-only and each per-tool FAQ only covers one tool in isolation."
        ),
        addresses_eval_queries=["q03", "q04"],
        synthesizes=[
            "488144948",  # Approved Tools for Use with University Data
            "488210484",  # Claude FAQ
            "522289260",  # Copilot FAQ
            "498597967",  # Gemini FAQ
            "483525103",  # AI @ SU
            "544538648",  # Gemini @ SU
            "534642749",  # Claude Enterprise @ SU
            "544505857",  # mentorAI @ SU
        ],
        example_queries=[
            "Which approved AI tools can I use with FERPA or other Confidential university data?",
            "How long does Claude vs Copilot vs Gemini retain my chats, and do any of them train on my data?",
            "Who owns the outputs I generate in Claude, Copilot, or Gemini?",
        ],
        draft_sketch=(
            "Open with canonical approved-tools list and the universal NetID rule (all data "
            "classifications permitted when logged in). Core: side-by-side comparison matrix "
            "across Claude, Copilot, Gemini, mentorAI covering data ownership, training-on-user-"
            "data, retention period, incognito/temporary mode behavior, admin/IT access posture, "
            "and special caveats. Close with 'which tool for which job' guidance, plus access URLs."
        ),
        tags=["hub", "ai-policy", "approved-tools", "data-classification"],
    ),
    "product-surface": HubSpec(
        slug="claude-at-syracuse-product-surface-map",
        title="Claude at Syracuse: Product Surface Map",
        why_it_exists=(
            "Claude at SU spans many distinct surfaces — Chat, Code, API, Cowork, M365 "
            "connector, custom connector requests, local MCP, Filesystem — and no single "
            "page maps which surface is enabled, which costs money, which is disabled, "
            "and how they relate."
        ),
        addresses_eval_queries=["q11"],
        synthesizes=[
            "534642749",  # Claude Enterprise @ SU
            "522158118",  # Understanding Claude Products: Chat, Code, API
            "540934169",  # Purchase Claude Code and Claude API Access
            "836698117",  # Claude Cowork — Overview and Security Considerations
            "544210961",  # Connect Claude to M365
            "841875458",  # Requesting a Claude Connector
            "837517313",  # Claude Local MCP — Power BI
            "988774401",  # Working with SharePoint Files in Claude
            "986841103",  # Claude Code Setup
        ],
        example_queries=[
            "What's the difference between Claude Chat, Claude Code, Cowork, and MCP — and which can I actually use at SU?",
            "How do I connect Claude to SharePoint, Power BI, or another tool?",
            "Why is Claude Cowork disabled and what should I use instead?",
        ],
        draft_sketch=(
            "Open with a 'what's enabled / what costs extra / what's disabled' status table covering "
            "every Claude surface at SU. Middle: surfaces grouped by purpose — conversational (Chat), "
            "agentic (Code, Cowork-disabled), integrations (M365 connector enabled, Atlassian enabled, "
            "custom via request, local MCP, Filesystem). Each row links to its raw page. Close with "
            "decision guidance: 'I want to connect Claude to X — which path do I take?'"
        ),
        tags=["hub", "claude", "product-map", "mcp", "connectors"],
    ),
}

DRAFTING_INSTRUCTIONS = """\
You are drafting a wiki-hub article for the Syracuse University AI Knowledge Base. The
hub sits above a 29-page raw Markdown corpus mirroring SU's Confluence "AI" space. Every
factual claim in the hub MUST cite the source raw page using the `[[<page-id>]]` format
inline at the end of the sentence.

CONSTRAINTS (from wiki-operating-model.md)
1. Use ONLY information present in the raw corpus. Do not invent facts.
2. Every claim cites at least one raw `[[<page-id>]]`. If a claim has no support in the
   corpus, drop it.
3. Use Markdown structure: headings, bullets, tables for comparisons.
4. Frontmatter: emit the exact YAML block I supply below, verbatim, at the top of your
   output. Do NOT modify or extend the frontmatter — I'll handle status/reviewer fields.
5. Voice: descriptive, not opinionated. "The corpus says X" rather than "X is best."
6. Hub purpose: improve citation depth and canonical synthesis. Do NOT duplicate any
   single raw page — synthesize across multiple.
7. End with a "## Sources" section listing every raw `[[<page-id> - <title>]]` you cited.

OUTPUT FORMAT
Emit a single Markdown document starting with the frontmatter block I supply, followed by
the article body. No commentary before or after the document.
"""


def build_user_prompt(hub: HubSpec, corpus_block: str) -> str:
    frontmatter = (
        "---\n"
        f'title: "{hub.title}"\n'
        "type: hub\n"
        "status: draft\n"
        "synthesizes:\n"
        + "".join(f'  - "{pid}"\n' for pid in hub.synthesizes)
        + "created: " + time.strftime("%Y-%m-%d") + "\n"
        + "updated: " + time.strftime("%Y-%m-%d") + "\n"
        + "tags:\n"
        + "".join(f"  - {t}\n" for t in hub.tags)
        + "---\n"
    )
    return (
        f"Draft the following wiki hub. Use exactly this frontmatter at the top of your output:\n\n"
        f"```yaml\n{frontmatter}```\n\n"
        f"HUB SPEC\n"
        f"- title: {hub.title}\n"
        f"- why_it_exists: {hub.why_it_exists}\n"
        f"- synthesizes (these are the raw page_ids you should draw from — minimum 3, ideally all): "
        f"{', '.join(hub.synthesizes)}\n"
        f"- addresses_eval_queries: {', '.join(hub.addresses_eval_queries)}\n"
        f"- example_queries this hub must answer well:\n"
        + "".join(f"  • {q}\n" for q in hub.example_queries)
        + f"- structural sketch: {hub.draft_sketch}\n\n"
        f"CORPUS\n"
        f"Read the raw pages below carefully. Every fact in your draft must trace to one of these.\n\n"
        f"{corpus_block}\n"
    )


def draft_hub(hub: HubSpec, config: SyncConfig, model: str) -> tuple[str, dict]:
    from anthropic import Anthropic
    client = Anthropic()

    raw = q.load_raw_corpus(config)
    corpus_block = q.serialize_corpus(raw, [])

    t0 = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=[
            {"type": "text", "text": DRAFTING_INSTRUCTIONS},
            {"type": "text", "text": corpus_block,
             "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": build_user_prompt(hub, "[corpus already supplied via cached system block]")}],
    )
    elapsed = time.perf_counter() - t0

    body = response.content[0].text
    usage = response.usage
    pricing = {
        "claude-opus-4-7": {"input": 15, "output": 75, "cache_write": 18.75, "cache_read": 1.5},
        "claude-sonnet-4-6": {"input": 3, "output": 15, "cache_write": 3.75, "cache_read": 0.3},
    }.get(model, {"input": 3, "output": 15, "cache_write": 3.75, "cache_read": 0.3})
    cost = (
        getattr(usage, "input_tokens", 0) * pricing["input"]
        + getattr(usage, "output_tokens", 0) * pricing["output"]
        + getattr(usage, "cache_creation_input_tokens", 0) * pricing["cache_write"]
        + getattr(usage, "cache_read_input_tokens", 0) * pricing["cache_read"]
    ) / 1_000_000

    return body, {
        "model": model,
        "cost_usd": round(cost, 4),
        "latency_s": round(elapsed, 1),
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", choices=list(HUBS.keys()) + ["all"], default="all")
    ap.add_argument("--model", default="claude-opus-4-7")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "sync_config.yaml"))
    args = ap.parse_args()

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
        print("ERROR: ANTHROPIC_API_KEY missing", file=sys.stderr)
        return 1

    config = SyncConfig.load(args.config)
    wiki_dir = config.output_dir / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    hub_keys = list(HUBS.keys()) if args.hub == "all" else [args.hub]
    total_cost = 0.0
    for k in hub_keys:
        hub = HUBS[k]
        print(f"\n=== drafting: {hub.title} ===")
        body, meta = draft_hub(hub, config, args.model)
        out_path = wiki_dir / f"{hub.slug}.md"
        out_path.write_text(body, encoding="utf-8")
        print(f"  wrote {out_path}")
        print(f"  cost ${meta['cost_usd']} · {meta['latency_s']}s · "
              f"in={meta['input_tokens']} out={meta['output_tokens']} "
              f"cw={meta['cache_creation_input_tokens']} cr={meta['cache_read_input_tokens']}")
        total_cost += meta["cost_usd"]

    print(f"\ntotal cost: ${total_cost:.4f} over {len(hub_keys)} hub(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
