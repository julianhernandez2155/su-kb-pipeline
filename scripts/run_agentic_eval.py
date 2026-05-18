"""Step 7 — Agentic tool-use eval.

Runs the 15-query eval set through Claude's tool-use loop using the four
MCP-shape tools defined in `sukb.chat.agentic_tools`. This is the
production-shape test: instead of stuffing the whole 50k-token corpus
into one prompt (Step 6's ceiling), the model navigates with
`read_index → list_hubs → search → read_page` the way it would through
a real MCP server.

The trace (every tool call with its input + output summary) is the key
new artifact. Final answer, citations, cost, and latency are also captured.

Usage:
    python scripts/run_agentic_eval.py [--server http://127.0.0.1:8765] \\
                                       [--out eval-runs] \\
                                       [--prefix eval-agentic] \\
                                       [--sleep 5] \\
                                       [--max-iters 10]

The script calls the Anthropic API directly (not /api/query). It uses
the server only for saving sessions so they show up in the Query-tab
sidebar. Set --no-save-sessions to skip that.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_YAML = PROJECT_ROOT / "docs" / "eval-queries.yaml"

# Load .env so ANTHROPIC_API_KEY is available when running outside the server.
load_dotenv(PROJECT_ROOT / ".env")

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sukb.chat.agentic_tools import AgenticTools  # noqa: E402
from sukb.chat.query import (  # noqa: E402
    CITATION_RE,
    MODEL,
    estimate_cost_usd,
)
from sukb.config import SyncConfig  # noqa: E402

MAX_TOKENS_OUT = 4096
SYSTEM_PROMPT = """\
You are the Syracuse University AI Knowledge Base assistant. Answer questions \
about Syracuse's AI tools, policies, and procedures using ONLY content you \
retrieve via the provided tools.

CORPUS SHAPE
- 29 raw pages from Syracuse's "Artificial Intelligence (AI)" Confluence space.
  Topics: Claude, Copilot, Gemini, mentorAI (Clementine), NotebookLM,
  approved-tools policy, data classification, MCP and connectors, Claude
  Code setup, example use cases.
- 2 reviewed wiki hubs that synthesize cross-cutting questions across 3+ raw
  pages each (data policy comparison, Claude product surface map).
- Orientation files (CLAUDE.md, indexes) describe the layout and routing rules.

NAVIGATION PATTERN
1. Start by reading an orientation file (`read_index`) — `index.md` or the
   space-level `raw/.../index.md` — unless you already know which page covers
   the question.
2. For cross-cutting questions (policy comparisons, "what's enabled at SU",
   tool selection), call `list_hubs` and prefer a hub if one matches.
3. Use `search` to find pages by keyword when the indexes don't already point
   at the right page.
4. Always `read_page` before citing. A search snippet is not enough to ground a
   citation.

CITATION RULES
1. Every factual claim MUST cite its source page using `[[<page-id>]]` for raw
   pages (digits) or `[[<slug>]]` for wiki hubs, inline at the end of the
   sentence. Example: "Claude retains chats for 2 years [[488210484]]."
   These wiki-style ids are the backend/admin trace citation.
2. Don't cite a page you haven't read with `read_page` in this turn.
3. User-facing citations must link to the original Confluence pages. End every
   answer with a "Sources:" section where each raw page is listed as a Markdown
   link to its `source_url`, followed by the trace id. Example:
   "- [Claude FAQ](https://answers.atlassian.syr.edu/...) [[488210484]]".
4. If you cite a wiki hub such as `[[approved-ai-tools-for-university-data]]`,
   also list the hub's `source_pages` as Confluence links in "Sources:" so the
   user can open the original Confluence pages behind the synthesis.
5. If the corpus doesn't answer the question, say so explicitly — do not
   invent content.

QUESTION SHAPE — calibrate effort to the question type:

  (a) NARROW LOOKUP questions ("how long does Claude retain chats", "where do I
      sign up", "how do I install X") — the answer lives in one or two pages.
      Target 2–3 tool calls total (orient + read). Don't over-navigate.

  (b) LIST / DISCOVERY / CATALOG questions ("what example uses are available",
      "what pages cover X", "which tools/connectors/options exist", "show me
      all examples of Y") — completeness beats tool-count minimization. If the
      index or a search result identifies multiple relevant pages, READ EACH
      relevant page before summarizing or citing it. Cap at a reasonable ~8
      pages if the set is larger.

  (c) CROSS-CUTTING / SYNTHESIS questions ("how should I decide between X and
      Y", "compare X vs Y on policy", "what's the SU posture on Z") — prefer
      the relevant wiki hub via `list_hubs → read_page(slug)`. One canonical
      hub beats stitching across raw pages.

DO NOT MENTION OTHER PAGES IN PROSE WITHOUT READING THEM. If you reference a
page by title or page_id, either:
  (i)  call `read_page` for it and cite `[[<page-id>]]` inline + add it to the
       Sources section, OR
  (ii) explicitly frame your mention as "the index also lists these page IDs
       (not yet summarized): [list]" so the reader knows it's an index excerpt,
       not a summary.

EFFICIENCY (subordinate to QUESTION SHAPE above):
- Don't call tools just to confirm what an index already told you.
- Don't redundantly read the same page twice in one turn.
"""


# --- HTTP helper for session save -------------------------------------------


def _post(url: str, body: dict, timeout: int = 60) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"POST {url} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')}"
        ) from None


def _slugify(text: str, max_len: int = 40) -> str:
    out: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:max_len]


def _ascii_safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")


def _session_citations(
    cited_raw: list[str],
    cited_wiki: list[str],
    tools: AgenticTools,
) -> list[dict[str, Any]]:
    """Return user-facing Confluence citations for saved UI sessions.

    Raw page citations map directly to Confluence source_url. Wiki hub citations
    expand to the raw pages the hub synthesizes, because users need the original
    Confluence page links, not only the local wiki slug.
    """
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()

    for pid in cited_raw:
        page = tools._by_page_id.get(pid)
        if page and page.page_id not in seen:
            citations.append(page.to_citation())
            seen.add(page.page_id)

    for slug in cited_wiki:
        hub = tools._by_slug.get(slug)
        if not hub:
            continue
        for src in tools._source_pages_for_hub(hub):
            pid = src.get("page_id", "")
            if pid and pid not in seen:
                citations.append(src)
                seen.add(pid)

    return citations


# --- agentic loop ------------------------------------------------------------


def run_one_query(
    client: Any,
    tools: AgenticTools,
    question: str,
    max_iters: int = 10,
) -> dict[str, Any]:
    """Run a single query through the tool-use loop.

    Returns a dict with: answer, trace, citations, cost_usd, latency_ms,
    iterations, tool_call_count, total_usage, search_calls, miss_calls.
    """
    tool_defs = tools.tool_definitions
    # Cache the system prompt + tool definitions across the multi-turn loop AND
    # across queries within a process. Anthropic caches up to and including the
    # last block with cache_control set.
    system_blocks = [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]

    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    trace: list[dict[str, Any]] = []
    total_usage: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    final_answer = ""
    iters = 0
    t0 = time.perf_counter()
    stop_reason = "unknown"
    search_calls = 0
    miss_calls = 0

    while iters < max_iters:
        iters += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_OUT,
            system=system_blocks,
            tools=tool_defs,
            messages=messages,
        )
        usage = response.usage
        for k in total_usage:
            total_usage[k] += int(getattr(usage, k, 0) or 0)

        stop_reason = getattr(response, "stop_reason", "unknown")
        content_blocks = response.content or []

        if stop_reason != "tool_use":
            for blk in content_blocks:
                text = getattr(blk, "text", None)
                if text:
                    final_answer += text
            break

        # tool_use — append the assistant's full content (text + tool_use blocks)
        # back into messages, then dispatch each tool and append tool_result blocks.
        messages.append({"role": "assistant", "content": [_block_to_dict(b) for b in content_blocks]})

        tool_results: list[dict[str, Any]] = []
        for blk in content_blocks:
            if getattr(blk, "type", None) != "tool_use":
                continue
            name = blk.name
            inp = blk.input or {}
            tool_use_id = blk.id
            result = tools.dispatch(name, inp)
            trace.append({
                "iter": iters,
                "tool": name,
                "input": inp,
                "summary": result.summary,
                "output_chars": len(result.text),
            })
            if name == "search":
                search_calls += 1
            if result.summary.startswith("miss:"):
                miss_calls += 1
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result.text,
            })
        messages.append({"role": "user", "content": tool_results})

    latency_ms = int((time.perf_counter() - t0) * 1000)
    cost = estimate_cost_usd(total_usage)

    return {
        "answer": final_answer,
        "trace": trace,
        "iterations": iters,
        "tool_call_count": len(trace),
        "search_calls": search_calls,
        "miss_calls": miss_calls,
        "stop_reason": stop_reason,
        "usage": total_usage,
        "cost_usd": cost,
        "latency_ms": latency_ms,
    }


def _block_to_dict(block: Any) -> dict[str, Any]:
    """Convert an Anthropic SDK content block back to the JSON shape the API expects."""
    t = getattr(block, "type", None)
    if t == "text":
        return {"type": "text", "text": getattr(block, "text", "")}
    if t == "tool_use":
        return {
            "type": "tool_use",
            "id": getattr(block, "id", ""),
            "name": getattr(block, "name", ""),
            "input": getattr(block, "input", {}),
        }
    if t == "thinking":
        return {"type": "thinking", "thinking": getattr(block, "thinking", "")}
    # Fallback: serialize via model_dump if available
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return {"type": t or "unknown"}


# --- main --------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8765",
                    help="server URL for session save (used only if --save-sessions)")
    ap.add_argument("--out", default=str(PROJECT_ROOT / "eval-runs"))
    ap.add_argument("--prefix", default="eval-agentic")
    ap.add_argument("--sleep", type=float, default=5.0,
                    help="seconds between queries to stay under input-token rate limit")
    ap.add_argument("--max-iters", type=int, default=10,
                    help="max tool-use iterations per query (safety cap)")
    ap.add_argument("--no-save-sessions", action="store_true",
                    help="skip POSTing each result to /api/query/sessions")
    ap.add_argument("--ids", default="",
                    help="comma-separated list of query ids to run (e.g. 'q06,q10,q15'); "
                         "default empty = run all queries in the eval set")
    args = ap.parse_args()

    if not EVAL_YAML.exists():
        print(f"ERROR: {EVAL_YAML} not found", file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        return 2

    from anthropic import Anthropic  # local import so the module can still be tested without SDK

    config = SyncConfig.load(PROJECT_ROOT / "sync_config.yaml")
    tools = AgenticTools(config)
    print(
        f"corpus: {len(tools.raw_pages)} raw, {len(tools.wiki_hubs)} wiki, "
        f"{len(tools.orientation)} orientation"
    )

    client = Anthropic()

    with EVAL_YAML.open("r", encoding="utf-8") as fh:
        eval_set = yaml.safe_load(fh)
    queries = eval_set["queries"]

    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        queries = [q for q in queries if q["id"] in wanted]
        missing = wanted - {q["id"] for q in queries}
        if missing:
            print(f"WARN: unknown ids skipped: {sorted(missing)}", file=sys.stderr)
        if not queries:
            print(f"ERROR: no queries matched --ids={args.ids!r}", file=sys.stderr)
            return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_stamp = time.strftime("%Y%m%dT%H%M%S")
    run_path = out_dir / f"{args.prefix}-agentic-{run_stamp}.json"

    results: list[dict[str, Any]] = []
    total_cost = 0.0
    for i, q in enumerate(queries, 1):
        qid = q["id"]
        question = q["question"]
        expected = [str(p) for p in q.get("expected_pages", [])]
        sys.stdout.write(f"[{i}/{len(queries)}] {qid}: {question[:55]}... ")
        sys.stdout.flush()

        if i > 1 and args.sleep > 0:
            time.sleep(args.sleep)

        try:
            r = run_one_query(client, tools, question, max_iters=args.max_iters)
        except Exception as e:
            print(f"FAILED: {_ascii_safe(str(e))}")
            continue

        total_cost += r["cost_usd"]

        # Citation extraction: same regex as Step 6. Citations to raw pages are
        # digit-only; citations to wiki hubs use the slug. We only resolve raw.
        cited_raw = [m.group(1) for m in CITATION_RE.finditer(r["answer"])]
        # Dedup preserving order
        seen: list[str] = []
        for pid in cited_raw:
            if pid not in seen:
                seen.append(pid)
        cited_raw = seen
        # Also detect wiki-slug citations: [[approved-ai-tools-for-university-data]]
        slug_re = re.compile(r"\[\[([a-z][a-z0-9\-]+)\]\]")
        cited_wiki = []
        for m in slug_re.finditer(r["answer"]):
            slug = m.group(1)
            if slug in tools._by_slug and slug not in cited_wiki:
                cited_wiki.append(slug)
        citations = _session_citations(cited_raw, cited_wiki, tools)

        hit = [p for p in expected if p in cited_raw]
        miss = [p for p in expected if p not in cited_raw]
        extra = [p for p in cited_raw if p not in expected]

        elapsed_s = r["latency_ms"] / 1000.0
        print(
            f"iters={r['iterations']} tools={r['tool_call_count']} "
            f"cited={cited_raw} hit={len(hit)}/{len(expected)} "
            f"${r['cost_usd']:.4f} {elapsed_s:.1f}s"
        )

        # Save as a session for the UI sidebar
        session_id: str | None = None
        if not args.no_save_sessions:
            session_name = f"{args.prefix}-{qid}-{_slugify(question)}"
            turns = [
                {
                    "role": "user",
                    "text": question,
                    "mode": "agentic",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                {
                    "role": "assistant",
                    "text": r["answer"],
                    "mode": "agentic",
                    "citations": citations,
                    "context_used": {
                        "raw_pages_cited": cited_raw,
                        "wiki_hubs_cited": cited_wiki,
                    },
                    "tool_calls": r["trace"],
                    "iterations": r["iterations"],
                    "tool_call_count": r["tool_call_count"],
                    "cost_usd": r["cost_usd"],
                    "latency_ms": r["latency_ms"],
                    "usage": r["usage"],
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            ]
            try:
                sess = _post(
                    f"{args.server}/api/query/sessions",
                    {"turns": turns, "name": session_name},
                )
                session_id = sess.get("session_id")
            except Exception as e:
                print(f"  (session save failed: {_ascii_safe(str(e))})")

        results.append({
            "id": qid,
            "type": q.get("type"),
            "question": question,
            "expected_pages": expected,
            "expected_to_benefit_from_wiki": bool(q.get("expected_to_benefit_from_wiki")),
            "answer": r["answer"],
            "cited_raw": cited_raw,
            "cited_wiki": cited_wiki,
            "citations": citations,
            "hit_expected": hit,
            "missed_expected": miss,
            "extra_pages": extra,
            "trace": r["trace"],
            "iterations": r["iterations"],
            "tool_call_count": r["tool_call_count"],
            "search_calls": r["search_calls"],
            "miss_calls": r["miss_calls"],
            "stop_reason": r["stop_reason"],
            "usage": r["usage"],
            "cost_usd": r["cost_usd"],
            "latency_ms": r["latency_ms"],
            "session_id": session_id,
        })

    avg_tool_calls = (
        sum(r["tool_call_count"] for r in results) / len(results) if results else 0
    )
    run_payload = {
        "run_stamp": run_stamp,
        "mode": "agentic",
        "model": MODEL,
        "total_queries": len(queries),
        "completed": len(results),
        "total_cost_usd": round(total_cost, 6),
        "avg_tool_calls_per_query": round(avg_tool_calls, 2),
        "corpus": {
            "raw_pages": len(tools.raw_pages),
            "wiki_hubs": len(tools.wiki_hubs),
            "orientation_files": len(tools.orientation),
        },
        "results": results,
    }
    run_path.write_text(
        json.dumps(run_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {run_path}")
    print(
        f"total cost: ${total_cost:.4f}  avg tool calls/query: {avg_tool_calls:.1f}  "
        f"completed: {len(results)}/{len(queries)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
