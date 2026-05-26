"""Phase 1.1 Step 3 follow-up — streaming chat paths must enforce ADR-0009.

The non-streaming `answer_query` path passes `allowed_raw_ids` into
`load_wiki_corpus` and `restricted_page_ids` into `extract_citations`.
The streaming paths in `sukb.web.server` had drifted from that contract
(Codex review, 2026-05-21):

  - `_run_chat_stream` called `load_wiki_corpus(config)` with no
    allowlist → a restricted-synthesizing hub could enter the streaming
    raw+wiki prompt. Security-meaningful.
  - `_run_chat_stream` and `_run_agentic_stream` called
    `extract_citations(full_answer, raw_pages)` without
    `restricted_page_ids` → restricted citations degraded to
    `(unresolved)` instead of `(restricted — not available)`. Operator
    signal weakness, not a content leak.

This file pins both invariants on the streaming surface.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sukb.chat import query as q
from sukb.web import server as web_server


# --- fixtures (parallel to tests/chat/test_step3_filtering.py) -------------


def _write_raw(
    dir_: Path,
    page_id: str,
    title: str,
    body: str,
    visibility_signal: str = "no_read_restrictions_seen",
) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{page_id} - {title}.md").write_text(
        f"---\n"
        f"page_id: '{page_id}'\n"
        f"title: {title}\n"
        f"source_url: https://example.test/{page_id}\n"
        f"ancestor_path: [Root]\n"
        f"visibility_signal: {visibility_signal}\n"
        f"---\n{body}\n",
        encoding="utf-8",
    )


def _write_hub(wiki_dir: Path, slug: str, title: str, synthesizes: list[str], body: str) -> None:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    syn = ", ".join(f"'{s}'" for s in synthesizes)
    (wiki_dir / f"{slug}.md").write_text(
        f"---\ntitle: {title}\ntype: hub\nstatus: reviewed\nsynthesizes: [{syn}]\n---\n{body}\n",
        encoding="utf-8",
    )


def _make_mixed_corpus(tmp_path: Path) -> SimpleNamespace:
    """One clean page (100), one restricted page (200), one clean hub,
    one restricted-synthesizing hub."""
    output_dir = tmp_path / "output"
    raw = output_dir / "raw"
    wiki = output_dir / "wiki"
    output_dir.mkdir()
    raw.mkdir()
    _write_raw(raw / "ok", "100", "Public Claude Tips",
               "Approved tool. FERPA-safe when signed in.")
    _write_raw(raw / "intern", "200", "Restricted Inherited Page",
               "TIGER_CANARY_INTERNAL_NOTES — staff only.",
               visibility_signal="restricted_inherited")
    (output_dir / "CLAUDE.md").write_text("# Agent Rules\nGo.", encoding="utf-8")
    (output_dir / "index.md").write_text("# Global Index\nSee hubs.", encoding="utf-8")
    _write_hub(wiki, "clean-hub", "Clean Hub", ["100"],
               "All-public synthesis [[100]].")
    _write_hub(wiki, "mixed-hub", "Mixed Hub", ["100", "200"],
               "TIGER_CANARY_HUB_BODY — paraphrases restricted [[200]].")
    return SimpleNamespace(output_dir=output_dir, raw_path=raw)


# --- fake Anthropic SDK surface --------------------------------------------


class _FakeDelta:
    def __init__(self, text: str) -> None:
        self.type = "text_delta"
        self.text = text


class _FakeEvent:
    def __init__(self, text: str) -> None:
        self.type = "content_block_delta"
        self.delta = _FakeDelta(text)


class _FakeStream:
    """Captures the payload and replays a fixed sequence of text_delta events.

    Mirrors the slice of the Anthropic streaming surface that
    `_run_chat_stream` actually touches: iteration of events with
    `.type == content_block_delta` plus `.delta.text`, and a final
    `.get_final_message()` for usage extraction.
    """

    def __init__(self, payload: dict[str, Any], answer_chunks: list[str]) -> None:
        self.payload = payload
        self._chunks = answer_chunks
        self._final = SimpleNamespace(usage={"input_tokens": 1, "output_tokens": 1})

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def __iter__(self):
        for chunk in self._chunks:
            yield _FakeEvent(chunk)

    def get_final_message(self):
        return self._final


class _FakeMessages:
    def __init__(self, captured: dict[str, Any], answer_chunks: list[str]) -> None:
        self._captured = captured
        self._chunks = answer_chunks

    def stream(self, **payload):
        self._captured["payload"] = payload
        return _FakeStream(payload, self._chunks)


class _FakeAnthropic:
    def __init__(self, answer_chunks: list[str]) -> None:
        self.captured: dict[str, Any] = {}
        self.messages = _FakeMessages(self.captured, answer_chunks)


# --- helpers ---------------------------------------------------------------


def _drive_chat_stream(monkeypatch, config, mode: str, answer: str):
    """Run `_run_chat_stream` with the Anthropic client mocked. Returns
    (events, captured_payload). `events` is a list of (name, data) tuples
    captured from the emit callback."""
    fake = _FakeAnthropic(answer_chunks=[answer])
    monkeypatch.setattr(web_server.query_mod, "_default_client", lambda: fake)
    events: list[tuple[str, dict[str, Any]]] = []
    def emit(name: str, data: dict[str, Any]) -> None:
        events.append((name, data))
    web_server._run_chat_stream("question?", mode, config, emit)
    return events, fake.captured.get("payload", {})


def _system_text(payload: dict[str, Any]) -> str:
    """Concatenate every system text block's text."""
    blocks = payload.get("system", [])
    return "\n".join(b.get("text", "") for b in blocks if isinstance(b, dict))


# --- the bug Codex flagged: hub filter on streaming raw+wiki ---------------


def test_streaming_raw_plus_wiki_drops_hubs_with_restricted_synthesizes(tmp_path, monkeypatch):
    """The streaming raw+wiki path must NOT include a hub whose
    `synthesizes` references a restricted page. The canary string
    `TIGER_CANARY_HUB_BODY` lives in mixed-hub; if it shows up in the
    payload sent to Anthropic, the bug is regressed."""
    config = _make_mixed_corpus(tmp_path)
    events, payload = _drive_chat_stream(monkeypatch, config, "raw+wiki", "no [[100]].")

    ctx = dict(events)["context_loaded"]
    # Only the clean hub should be loaded.
    assert ctx["wiki_pages_loaded"] == 1
    assert ctx["mode"] == "raw+wiki"

    system_text = _system_text(payload)
    assert "All-public synthesis" in system_text  # clean-hub body is present
    assert "TIGER_CANARY_HUB_BODY" not in system_text  # mixed-hub body is absent
    # And the underlying restricted raw page must not appear either.
    assert "TIGER_CANARY_INTERNAL_NOTES" not in system_text


def test_streaming_raw_mode_excludes_restricted_pages_from_payload(tmp_path, monkeypatch):
    """Sanity: even in plain `raw` mode (no wiki), the restricted page is
    excluded by `load_raw_corpus`. Pins the existing invariant on the
    streaming surface."""
    config = _make_mixed_corpus(tmp_path)
    _, payload = _drive_chat_stream(monkeypatch, config, "raw", "no [[100]].")
    system_text = _system_text(payload)
    assert "Approved tool" in system_text
    assert "TIGER_CANARY_INTERNAL_NOTES" not in system_text


# --- citation resolution on streaming paths --------------------------------


def test_streaming_chat_citations_distinguish_restricted_from_unresolved(tmp_path, monkeypatch):
    """A streamed answer that cites [[100]] (clean), [[200]] (restricted),
    and [[999]] (nonexistent) must resolve them to: real title, the
    `(restricted — not available)` sentinel, and the `(unresolved)`
    sentinel respectively. Mirrors `answer_query` behavior — was missing
    on the streaming path."""
    config = _make_mixed_corpus(tmp_path)
    answer = "Claim A [[100]]. Claim B [[200]]. Claim C [[999]]."
    events, _ = _drive_chat_stream(monkeypatch, config, "raw+wiki", answer)
    done = dict(events)["done"]
    by_id = {c["page_id"]: c for c in done["citations"]}
    assert by_id["100"]["title"] == "Public Claude Tips"
    assert by_id["200"]["title"] == "(restricted — not available)"
    assert by_id["200"]["source_url"] == ""
    assert by_id["999"]["title"] == "(unresolved)"


# --- agentic streaming path: citation resolution ---------------------------


def test_streaming_agentic_citations_distinguish_restricted_from_unresolved(tmp_path, monkeypatch):
    """`_run_agentic_stream` must also pass `restricted_page_ids` into
    `extract_citations`. The agentic tool surface already filters content
    by ADR-0009, but the operator citation panel still needs the
    restricted-vs-unresolved distinction."""
    config = _make_mixed_corpus(tmp_path)
    answer = "Claim A [[100]]. Claim B [[200]]. Claim C [[999]]."

    # Stub `stream_one_query` so we don't need a live Anthropic SDK call.
    # The agentic stream forwards events from this generator. We only need
    # to deliver one `done` event with our fabricated answer; the citation
    # resolution happens after.
    def fake_stream_one_query(client, tools, question):
        yield {"event": "done", "data": {
            "answer": answer,
            "trace": [],
            "cost_usd": 0.0,
            "usage": {},
            "latency_ms": 0,
            "iterations": 1,
        }}

    monkeypatch.setattr(web_server.agentic_mod, "stream_one_query", fake_stream_one_query)
    monkeypatch.setattr(web_server.query_mod, "_default_client", lambda: object())

    events: list[tuple[str, dict[str, Any]]] = []
    def emit(name: str, data: dict[str, Any]) -> None:
        events.append((name, data))

    web_server._run_agentic_stream("question?", config, emit)

    done = dict(events)["done"]
    by_id = {c["page_id"]: c for c in done["citations"]}
    assert by_id["100"]["title"] == "Public Claude Tips"
    assert by_id["200"]["title"] == "(restricted — not available)"
    assert by_id["999"]["title"] == "(unresolved)"
