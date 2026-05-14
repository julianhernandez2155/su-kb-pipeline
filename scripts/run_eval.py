"""Run the v1.5 eval set against /api/query and save each turn as a session.

Usage:
    python scripts/run_eval.py --mode raw [--server http://127.0.0.1:8765]

Reads `docs/eval-queries.yaml`, fires each query
against the running server, persists each result as a chat session (so it
shows up in the Query-tab sidebar), and writes a JSON artifact you can
hand-grade against. Use mode=raw for baseline, mode=raw+wiki for Step 6.

This is a one-shot ops script — not part of the importable package.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import urllib.error
import urllib.request

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # repo root
EVAL_YAML = PROJECT_ROOT / "docs" / "eval-queries.yaml"


def _post(url: str, body: dict, timeout: int = 120) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} → HTTP {e.code}: {msg}") from None


def _slugify(text: str, max_len: int = 40) -> str:
    """For session names: q01-can-i-upload-ferpa-protected-..."""
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:max_len]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["raw", "raw+wiki"], default="raw")
    ap.add_argument("--server", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default=str(PROJECT_ROOT / "eval-runs"))
    ap.add_argument("--prefix", default="eval-baseline", help="session name prefix")
    args = ap.parse_args()

    if not EVAL_YAML.exists():
        print(f"ERROR: {EVAL_YAML} not found", file=sys.stderr)
        return 2

    with EVAL_YAML.open("r", encoding="utf-8") as fh:
        eval_set = yaml.safe_load(fh)
    queries = eval_set["queries"]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_stamp = time.strftime("%Y%m%dT%H%M%S")
    run_path = out_dir / f"{args.prefix}-{args.mode.replace('+','-')}-{run_stamp}.json"

    results = []
    total_cost = 0.0
    for i, q in enumerate(queries, 1):
        qid = q["id"]
        question = q["question"]
        expected = [str(p) for p in q.get("expected_pages", [])]
        sys.stdout.write(f"[{i}/{len(queries)}] {qid}: {question[:60]}...")
        sys.stdout.flush()
        t0 = time.perf_counter()
        try:
            r = _post(f"{args.server}/api/query", {"question": question, "mode": args.mode})
        except Exception as e:
            print(f"  FAILED: {e}")
            continue
        elapsed = time.perf_counter() - t0
        total_cost += r.get("cost_usd", 0)

        cited = [c["page_id"] for c in r.get("citations", [])]
        hit = [p for p in expected if p in cited]
        miss = [p for p in expected if p not in cited]
        extra = [p for p in cited if p not in expected]

        # Save as a session so it lands in the UI sidebar
        session_name = f"{args.prefix}-{qid}-{_slugify(question)}"
        turns = [
            {"role": "user", "text": question, "mode": args.mode, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")},
            {
                "role": "assistant",
                "text": r.get("answer", ""),
                "mode": r.get("mode", args.mode),
                "citations": r.get("citations", []),
                "context_used": r.get("context_used", {}),
                "cost_usd": r.get("cost_usd", 0),
                "latency_ms": r.get("latency_ms", 0),
                "raw_pages_loaded": r.get("raw_pages_loaded", 0),
                "wiki_pages_loaded": r.get("wiki_pages_loaded", 0),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        ]
        try:
            sess = _post(f"{args.server}/api/query/sessions", {"turns": turns, "name": session_name})
            session_id = sess.get("session_id")
        except Exception as e:
            print(f"  (session save failed: {e})")
            session_id = None

        results.append({
            "id": qid,
            "type": q.get("type"),
            "question": question,
            "expected_pages": expected,
            "expected_to_benefit_from_wiki": bool(q.get("expected_to_benefit_from_wiki")),
            "answer": r.get("answer", ""),
            "citations": r.get("citations", []),
            "cited_page_ids": cited,
            "hit_expected": hit,
            "missed_expected": miss,
            "extra_pages": extra,
            "cost_usd": r.get("cost_usd", 0),
            "latency_ms": r.get("latency_ms", 0),
            "session_id": session_id,
        })
        print(f"  cited={cited} hit={len(hit)}/{len(expected)} ${r.get('cost_usd',0):.4f} {elapsed:.1f}s")

    run_payload = {
        "run_stamp": run_stamp,
        "mode": args.mode,
        "total_queries": len(queries),
        "completed": len(results),
        "total_cost_usd": round(total_cost, 6),
        "results": results,
    }
    run_path.write_text(json.dumps(run_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {run_path}")
    print(f"total cost: ${total_cost:.4f} over {len(results)} queries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
