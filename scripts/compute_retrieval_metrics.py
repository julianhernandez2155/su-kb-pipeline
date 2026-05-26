"""Step 7b — retrieval-quality metrics over a saved agentic eval run.

Reads one or more `eval-runs/*.json` files produced by `run_agentic_eval.py`
and emits hit@1/3/5/10 + MRR@10 against each query's `expected_pages`.

Design choice — read from trace, not from a search replay:
  The metric measures **what the model actually saw** when it ran. The trace
  summary records the ordered top-k search hits (k defaults to 5 in the tool
  surface). Positions in this metric are the model's view; an expected page
  that's beyond the model's top-k is unseen — that IS the retrieval failure.

Query buckets:
  - **search-grounded**: `expected_pages` non-empty AND the trace contains at
    least one `search` call. These count toward hit@k / MRR@10 aggregates.
    The metric uses the FIRST search call (most representative of "given the
    user's question, how well does search rank the right pages on attempt 1").
  - **search-less**: `expected_pages` non-empty but the agent navigated via
    `read_index` + `list_hubs` + `read_page` only. Excluded from retrieval
    metrics (there's no retrieval to score); reported separately.
  - **negative**: `expected_pages` is empty (query intentionally outside the
    corpus). Excluded from hit@k / MRR. Tracked separately: did the final
    answer cite any raw page (a hallucination-proxy signal)?

Only **raw**-layer hits count against `expected_pages` (which are raw page
IDs). Wiki-hub slugs appearing in search results are surfaced for navigation
but don't satisfy the retrieval gate.

Usage:
    python scripts/compute_retrieval_metrics.py eval-runs/eval-agentic-v3-step7b-*.json
    python scripts/compute_retrieval_metrics.py path.json --json   # emit JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# One entry of a search summary: `id(layer,score)`. id can be all-digits
# (raw page) or kebab-slug (wiki hub).
_HIT_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9_\-]*)\(([a-z]+),([0-9.]+)\)")


def parse_search_summary(summary: str) -> list[tuple[str, str, float]]:
    """Parse `query='...' → N hits: id1(layer,score), id2(layer,score)` into an ordered list.

    Returns [] for empty-query / zero-hit / malformed summaries.
    """
    if "hits:" not in summary:
        return []
    body = summary.split("hits:", 1)[1]
    return [(m.group(1), m.group(2), float(m.group(3))) for m in _HIT_RE.finditer(body)]


def first_search_call(trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first `search` tool call in a trace, or None."""
    for t in trace:
        if t.get("tool") == "search":
            return t
    return None


def query_metrics(
    expected_raw: set[str], ranking: list[tuple[str, str, float]]
) -> dict[str, Any]:
    """Compute hit@k and reciprocal rank for one ranking against expected raw page IDs.

    Position is 1-indexed against the full ranking (wiki slugs included),
    so a raw-expected page at absolute pos 2 with a wiki hub at pos 1 yields
    hit@1 = 0, hit@3 = 1, rr = 1/2. Wiki layer hits are intentionally
    excluded from `expected_raw` matching.
    """
    # (position, page_id) pairs for raw-layer hits only, position 1-indexed.
    raw_ranks = [
        (pos, pid)
        for pos, (pid, layer, _score) in enumerate(ranking[:10], start=1)
        if layer == "raw"
    ]

    def hit_at(k: int) -> int:
        return int(any(pid in expected_raw for pos, pid in raw_ranks if pos <= k))

    rr = 0.0
    first_expected_rank: int | None = None
    for pos, pid in raw_ranks:
        if pid in expected_raw:
            rr = 1.0 / pos
            first_expected_rank = pos
            break

    return {
        "hit@1": hit_at(1),
        "hit@3": hit_at(3),
        "hit@5": hit_at(5),
        "hit@10": hit_at(10),
        "reciprocal_rank": rr,
        "ranking_len": len(ranking),
        "first_expected_rank": first_expected_rank,
    }


def _replay_search(query: str, tools: Any, top_k: int = 10) -> list[tuple[str, str, float]]:
    """Call the current AgenticTools._search() and return the ranked top_k as tuples.

    Used by `--replay-search` to recompute metrics against the *current* search
    algorithm without re-running the agentic loop through the API.
    """
    result = tools._search(query, top_k=top_k)
    hits = json.loads(result.text)
    return [(h["id"], h["layer"], float(h["score"])) for h in hits]


def analyze_run(run_path: Path, *, replay_tools: Any | None = None) -> dict[str, Any]:
    """Read an eval JSON and bucket queries into search-grounded / search-less / negative.

    If `replay_tools` is provided, each search-grounded query's ranking is taken
    from a fresh `_search()` call against those tools (top_k=10) instead of
    parsed from the saved trace summary. This lets us measure the effect of
    a search-algorithm change without re-running the agentic loop.
    """
    with run_path.open(encoding="utf-8") as fp:
        run = json.load(fp)
    results = run.get("results", [])

    search_grounded: list[dict[str, Any]] = []
    search_less: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []

    for r in results:
        qid = r["id"]
        expected = {str(p) for p in r.get("expected_pages", [])}
        cited_raw = r.get("cited_raw", [])
        cited_wiki = r.get("cited_wiki", [])
        answer_text = r.get("answer", "")

        if not expected:
            # Negative case: corpus correctly should NOT cover this. Proxy
            # for hallucination = any raw [[page-id]] citation in the answer.
            negatives.append({
                "id": qid,
                "question": r["question"],
                "cited_raw": cited_raw,
                "cited_wiki": cited_wiki,
                "n_raw_citations": len(cited_raw),
                "answer_excerpt": answer_text[:300],
            })
            continue

        search_call = first_search_call(r.get("trace", []))
        if not search_call:
            search_less.append({
                "id": qid,
                "question": r["question"],
                "expected_pages": sorted(expected),
                "tool_call_count": r.get("tool_call_count", 0),
            })
            continue

        query_text = search_call["input"].get("query", "")
        if replay_tools is not None and query_text:
            ranking = _replay_search(query_text, replay_tools, top_k=10)
            source = "replay"
        else:
            ranking = parse_search_summary(search_call["summary"])
            source = "trace"
        m = query_metrics(expected, ranking)
        m["id"] = qid
        m["question"] = r["question"]
        m["expected_pages"] = sorted(expected)
        m["search_query"] = query_text
        m["ranked_ids_top10"] = [pid for pid, _, _ in ranking[:10]]
        m["ranking_source"] = source
        search_grounded.append(m)

    n = len(search_grounded)

    def avg(field: str) -> float:
        return sum(q[field] for q in search_grounded) / n if n else 0.0

    aggregates = {
        "n_queries": len(results),
        "n_search_grounded": n,
        "n_search_less": len(search_less),
        "n_negatives": len(negatives),
        "hit@1": round(avg("hit@1"), 4),
        "hit@3": round(avg("hit@3"), 4),
        "hit@5": round(avg("hit@5"), 4),
        "hit@10": round(avg("hit@10"), 4),
        "MRR@10": round(avg("reciprocal_rank"), 4),
    }

    return {
        "run_path": str(run_path),
        "aggregates": aggregates,
        "search_grounded": search_grounded,
        "search_less": search_less,
        "negatives": negatives,
    }


def print_report(analysis: dict[str, Any]) -> None:
    agg = analysis["aggregates"]
    print(f"=== {analysis['run_path']} ===")
    print(
        f"Queries: {agg['n_queries']} total | "
        f"search-grounded: {agg['n_search_grounded']} | "
        f"search-less: {agg['n_search_less']} | "
        f"negative: {agg['n_negatives']}"
    )
    print(
        f"hit@1: {agg['hit@1']:.3f}  hit@3: {agg['hit@3']:.3f}  "
        f"hit@5: {agg['hit@5']:.3f}  hit@10: {agg['hit@10']:.3f}  "
        f"MRR@10: {agg['MRR@10']:.3f}"
    )
    print()
    print("Per-query (search-grounded), sorted by reciprocal rank:")
    print(f"  {'id':<5} {'h@1':>3} {'h@3':>3} {'h@5':>3} {'h@10':>4} {'rr':>6}  rank  query")
    rows = sorted(analysis["search_grounded"], key=lambda r: -r["reciprocal_rank"])
    for q in rows:
        rank = q["first_expected_rank"] if q["first_expected_rank"] is not None else "—"
        print(
            f"  {q['id']:<5} {q['hit@1']:>3} {q['hit@3']:>3} {q['hit@5']:>3} {q['hit@10']:>4} "
            f"{q['reciprocal_rank']:>6.3f}  {str(rank):>4}  {q['search_query'][:60]}"
        )
    if analysis["search_less"]:
        print()
        print(f"Search-less ({len(analysis['search_less'])} queries — agent navigated without search):")
        for q in analysis["search_less"]:
            print(f"  {q['id']}: {q['question'][:80]}")
    if analysis["negatives"]:
        print()
        print(f"Negative queries ({len(analysis['negatives'])} — corpus should not cover):")
        for q in analysis["negatives"]:
            verdict = (
                "OK no-raw-citations"
                if q["n_raw_citations"] == 0
                else f"FAIL cited {q['cited_raw']}"
            )
            print(f"  {q['id']}: {verdict}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="eval-runs/*.json files")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of human report")
    ap.add_argument(
        "--replay-search",
        action="store_true",
        help="recompute rankings via a fresh AgenticTools._search() call (top_k=10) "
             "against the current search algorithm, instead of parsing the saved trace.",
    )
    ap.add_argument(
        "--sync-config",
        default=str(PROJECT_ROOT / "sync_config.yaml"),
        help="path to sync_config.yaml (only used with --replay-search)",
    )
    args = ap.parse_args()

    replay_tools = None
    if args.replay_search:
        from sukb.chat.agentic_tools import AgenticTools  # noqa: E402
        from sukb.config import SyncConfig  # noqa: E402
        cfg = SyncConfig.load(Path(args.sync_config))
        replay_tools = AgenticTools(cfg)

    if args.json:
        out = [analyze_run(Path(p), replay_tools=replay_tools) for p in args.paths]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for p in args.paths:
            print_report(analyze_run(Path(p), replay_tools=replay_tools))
    return 0


if __name__ == "__main__":
    sys.exit(main())
