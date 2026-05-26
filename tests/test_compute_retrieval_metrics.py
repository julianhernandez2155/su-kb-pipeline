"""Tests for scripts/compute_retrieval_metrics.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from compute_retrieval_metrics import (  # noqa: E402
    _replay_search,
    analyze_run,
    first_search_call,
    parse_search_summary,
    query_metrics,
)


class _FakeSearchTools:
    """Stub matching the AgenticTools._search() shape for replay-mode tests."""

    def __init__(self, ranking_by_query: dict[str, list[dict]]):
        self._by_query = ranking_by_query

    def _search(self, query: str, top_k: int = 10):
        hits = self._by_query.get(query, [])[:top_k]
        return type("Result", (), {"text": json.dumps(hits), "summary": ""})()


class TestParseSearchSummary:
    def test_mixed_layers(self):
        s = (
            "query='Claude Code install Windows' → 5 hits: "
            "claude-at-syracuse-product-surface-map(wiki,113.85), "
            "986841103(raw,79.0), 488210484(raw,75.0), 540934169(raw,46.5)"
        )
        out = parse_search_summary(s)
        assert len(out) == 4
        assert out[0] == ("claude-at-syracuse-product-surface-map", "wiki", 113.85)
        assert out[1] == ("986841103", "raw", 79.0)
        assert out[3] == ("540934169", "raw", 46.5)

    def test_zero_hits(self):
        assert parse_search_summary("query='asdfqwerty' → 0 hits") == []

    def test_no_summary_arrow(self):
        assert parse_search_summary("some unrelated string") == []

    def test_empty(self):
        assert parse_search_summary("") == []


class TestQueryMetrics:
    def test_top1_raw_hit(self):
        ranking = [("page-a", "raw", 10.0), ("page-b", "raw", 5.0)]
        m = query_metrics({"page-a"}, ranking)
        assert m["hit@1"] == 1
        assert m["hit@3"] == 1
        assert m["hit@5"] == 1
        assert m["hit@10"] == 1
        assert m["reciprocal_rank"] == 1.0
        assert m["first_expected_rank"] == 1

    def test_top3_raw_hit(self):
        # wiki at position 1 doesn't count; raw expected at position 3
        ranking = [
            ("hub", "wiki", 100.0),
            ("zzz", "raw", 50.0),
            ("target", "raw", 30.0),
        ]
        m = query_metrics({"target"}, ranking)
        assert m["hit@1"] == 0
        assert m["hit@3"] == 1
        assert m["hit@10"] == 1
        assert m["reciprocal_rank"] == pytest.approx(1 / 3)
        assert m["first_expected_rank"] == 3

    def test_top5_only_not_top3(self):
        ranking = [
            ("a", "raw", 10.0),
            ("b", "raw", 9.0),
            ("c", "raw", 8.0),
            ("d", "raw", 7.0),
            ("target", "raw", 6.0),
        ]
        m = query_metrics({"target"}, ranking)
        assert m["hit@1"] == 0
        assert m["hit@3"] == 0
        assert m["hit@5"] == 1
        assert m["hit@10"] == 1
        assert m["reciprocal_rank"] == pytest.approx(0.2)
        assert m["first_expected_rank"] == 5

    def test_no_hit_in_top10(self):
        ranking = [("aaa", "raw", 10.0)] * 10
        m = query_metrics({"target"}, ranking)
        assert m["hit@1"] == 0
        assert m["hit@3"] == 0
        assert m["hit@10"] == 0
        assert m["reciprocal_rank"] == 0.0
        assert m["first_expected_rank"] is None

    def test_wiki_at_top_does_not_satisfy_raw_expected(self):
        # wiki slug at position 1 + raw expected at position 2
        ranking = [("hub-slug", "wiki", 100.0), ("target", "raw", 50.0)]
        m = query_metrics({"target"}, ranking)
        assert m["hit@1"] == 0  # target is at absolute pos 2, not 1
        assert m["hit@3"] == 1
        assert m["reciprocal_rank"] == 0.5
        assert m["first_expected_rank"] == 2

    def test_multiple_expected_first_wins(self):
        # Two expected pages; first-encountered wins reciprocal-rank
        ranking = [
            ("other", "raw", 10.0),
            ("expected-b", "raw", 9.0),  # pos 2
            ("expected-a", "raw", 8.0),  # pos 3
        ]
        m = query_metrics({"expected-a", "expected-b"}, ranking)
        assert m["hit@1"] == 0
        assert m["hit@3"] == 1
        assert m["reciprocal_rank"] == 0.5
        assert m["first_expected_rank"] == 2

    def test_rank_11_does_not_count(self):
        # Hit at position 11 is outside top-10 window
        ranking = [("filler", "raw", 1.0)] * 10 + [("target", "raw", 0.5)]
        m = query_metrics({"target"}, ranking)
        assert m["hit@10"] == 0
        assert m["reciprocal_rank"] == 0.0
        assert m["first_expected_rank"] is None


class TestFirstSearchCall:
    def test_returns_first_search_in_order(self):
        trace = [
            {"iter": 1, "tool": "list_hubs", "input": {}, "summary": "..."},
            {"iter": 2, "tool": "search", "input": {"query": "x"}, "summary": "..."},
            {"iter": 3, "tool": "search", "input": {"query": "y"}, "summary": "..."},
        ]
        out = first_search_call(trace)
        assert out is not None
        assert out["input"]["query"] == "x"

    def test_returns_none_when_no_search(self):
        trace = [
            {"iter": 1, "tool": "list_hubs", "input": {}, "summary": "..."},
            {"iter": 2, "tool": "read_page", "input": {"id": "111"}, "summary": "..."},
        ]
        assert first_search_call(trace) is None

    def test_empty_trace(self):
        assert first_search_call([]) is None


class TestAnalyzeRun:
    def test_buckets_and_aggregates(self, tmp_path: Path):
        run = {
            "run_stamp": "test",
            "results": [
                # search-grounded hit at pos 1
                {
                    "id": "qA",
                    "question": "A?",
                    "expected_pages": ["111"],
                    "cited_raw": ["111"],
                    "cited_wiki": [],
                    "answer": "Answer A [[111]]",
                    "trace": [
                        {
                            "iter": 1,
                            "tool": "search",
                            "input": {"query": "A"},
                            "summary": "query='A' → 2 hits: 111(raw,10.0), 222(raw,5.0)",
                        },
                        {
                            "iter": 2,
                            "tool": "read_page",
                            "input": {"id": "111"},
                            "summary": "raw 111 'X' (100 chars)",
                        },
                    ],
                    "tool_call_count": 2,
                },
                # search-grounded miss (expected page not in top-5)
                {
                    "id": "qB",
                    "question": "B?",
                    "expected_pages": ["999"],
                    "cited_raw": [],
                    "cited_wiki": [],
                    "answer": "Answer B",
                    "trace": [
                        {
                            "iter": 1,
                            "tool": "search",
                            "input": {"query": "B"},
                            "summary": "query='B' → 2 hits: 333(raw,10.0), 444(raw,5.0)",
                        },
                    ],
                    "tool_call_count": 1,
                },
                # search-less (used read_index → read_page directly)
                {
                    "id": "qC",
                    "question": "C?",
                    "expected_pages": ["555"],
                    "cited_raw": ["555"],
                    "cited_wiki": [],
                    "answer": "Answer C [[555]]",
                    "trace": [
                        {
                            "iter": 1,
                            "tool": "read_index",
                            "input": {"path": "x"},
                            "summary": "x (10 chars)",
                        },
                        {
                            "iter": 2,
                            "tool": "read_page",
                            "input": {"id": "555"},
                            "summary": "raw 555 'X' (10 chars)",
                        },
                    ],
                    "tool_call_count": 2,
                },
                # negative (correct refusal — no raw citations)
                {
                    "id": "qD",
                    "question": "D?",
                    "expected_pages": [],
                    "cited_raw": [],
                    "cited_wiki": [],
                    "answer": "The corpus does not cover D.",
                    "trace": [],
                    "tool_call_count": 0,
                },
                # negative (hallucination — has a raw citation)
                {
                    "id": "qE",
                    "question": "E?",
                    "expected_pages": [],
                    "cited_raw": ["888"],
                    "cited_wiki": [],
                    "answer": "E is covered [[888]]",
                    "trace": [],
                    "tool_call_count": 0,
                },
            ],
        }
        p = tmp_path / "run.json"
        p.write_text(json.dumps(run))
        out = analyze_run(p)
        agg = out["aggregates"]
        assert agg["n_queries"] == 5
        assert agg["n_search_grounded"] == 2
        assert agg["n_search_less"] == 1
        assert agg["n_negatives"] == 2
        # hit@3: 1 hit (qA) + 0 miss (qB) → 0.5
        assert agg["hit@3"] == 0.5
        # MRR: (1.0 + 0.0) / 2 = 0.5
        assert agg["MRR@10"] == 0.5
        # Negatives separation: qD (good) vs qE (bad)
        negs = {n["id"]: n for n in out["negatives"]}
        assert negs["qD"]["n_raw_citations"] == 0
        assert negs["qE"]["n_raw_citations"] == 1

    def test_empty_results(self, tmp_path: Path):
        p = tmp_path / "empty.json"
        p.write_text(json.dumps({"results": []}))
        out = analyze_run(p)
        agg = out["aggregates"]
        assert agg["n_queries"] == 0
        assert agg["n_search_grounded"] == 0
        # No division-by-zero
        assert agg["hit@3"] == 0
        assert agg["MRR@10"] == 0


class TestReplaySearch:
    def test_replay_search_returns_ordered_tuples(self):
        tools = _FakeSearchTools({
            "find me": [
                {"id": "p1", "layer": "raw", "score": 9.5},
                {"id": "hub-a", "layer": "wiki", "score": 8.0},
            ],
        })
        out = _replay_search("find me", tools, top_k=10)
        assert out == [("p1", "raw", 9.5), ("hub-a", "wiki", 8.0)]

    def test_replay_overrides_trace_ranking(self, tmp_path: Path):
        """If --replay-search is wired in via replay_tools, the metric uses the
        replay ranking, not the trace summary. Demonstrates that a new search
        algorithm can change the metric without re-running the agent."""
        # Saved trace shows expected page missing from top-5
        run = {
            "results": [
                {
                    "id": "qA",
                    "question": "A?",
                    "expected_pages": ["target"],
                    "cited_raw": [],
                    "cited_wiki": [],
                    "answer": "",
                    "trace": [
                        {
                            "iter": 1,
                            "tool": "search",
                            "input": {"query": "find target"},
                            "summary": "query='find target' → 2 hits: x(raw,1.0), y(raw,0.5)",
                        }
                    ],
                    "tool_call_count": 1,
                }
            ]
        }
        p = tmp_path / "r.json"
        p.write_text(json.dumps(run))
        # Trace-mode: target not found
        a_trace = analyze_run(p)
        assert a_trace["aggregates"]["hit@3"] == 0.0
        assert a_trace["aggregates"]["MRR@10"] == 0.0
        # Replay-mode with a new algorithm that puts target at rank 1
        new_tools = _FakeSearchTools({
            "find target": [
                {"id": "target", "layer": "raw", "score": 99.0},
                {"id": "x", "layer": "raw", "score": 1.0},
            ],
        })
        a_replay = analyze_run(p, replay_tools=new_tools)
        assert a_replay["aggregates"]["hit@3"] == 1.0
        assert a_replay["aggregates"]["MRR@10"] == 1.0
        # Source tag distinguishes the two modes
        assert a_replay["search_grounded"][0]["ranking_source"] == "replay"
        assert a_trace["search_grounded"][0]["ranking_source"] == "trace"
