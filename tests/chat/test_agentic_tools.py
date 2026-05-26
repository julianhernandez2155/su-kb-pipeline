"""Unit tests for sukb.chat.agentic_tools — the 4 MCP-shape tools."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sukb.chat import agentic_tools as at


def _write_raw_page(
    dir_: Path,
    page_id: str,
    title: str,
    body: str,
    visibility_signal: str = "no_read_restrictions_seen",
) -> None:
    """Phase 1.1 Step 3 (ADR-0009): defaults visibility_signal to the public
    value so existing tests keep loading the fixture page. Tests for the
    filter pass an explicit non-public visibility_signal.
    """
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{page_id} - {title}.md").write_text(
        f"---\npage_id: '{page_id}'\ntitle: {title}\n"
        f"source_url: https://example.test/{page_id}\n"
        f"ancestor_path: [Root, Sub]\n"
        f"visibility_signal: {visibility_signal}\n---\n{body}\n",
        encoding="utf-8",
    )


def _make_corpus(tmp_path: Path) -> SimpleNamespace:
    output_dir = tmp_path / "output"
    raw = output_dir / "raw"
    wiki = output_dir / "wiki"
    output_dir.mkdir()
    raw.mkdir()
    wiki.mkdir()

    (output_dir / "CLAUDE.md").write_text("# Agent Rules\nRules body.", encoding="utf-8")
    (output_dir / "index.md").write_text("# SU KB\nGlobal map.", encoding="utf-8")
    (wiki / "index.md").write_text(
        "---\ntitle: Wiki Index\ntype: index\nstatus: reviewed\n---\nHub list body.\n",
        encoding="utf-8",
    )

    _write_raw_page(raw / "AI", "488210484", "Claude FAQ",
                    "Claude retains chats for 2 years. FERPA data is allowed when logged in with NetID.")
    _write_raw_page(raw / "AI", "522289260", "Copilot FAQ",
                    "Microsoft Copilot stores conversations in your mailbox.")
    _write_raw_page(raw / "AI", "498597967", "Gemini FAQ",
                    "Google Gemini does not train on your data under Workspace for Education.")

    (wiki / "approved-tools.md").write_text(
        "---\ntitle: Approved AI Tools\ntype: hub\nstatus: reviewed\n"
        "synthesizes: ['488210484','522289260','498597967']\n---\n"
        "## When to use this hub\nUse this hub when comparing approved AI tools "
        "for university data across Claude, Copilot, and Gemini.\n\n"
        "## Comparison\nClaude retains 2 years [[488210484]]. Copilot stores in mailbox [[522289260]].\n",
        encoding="utf-8",
    )

    return SimpleNamespace(output_dir=output_dir, raw_path=raw)


def test_tool_definitions_are_well_formed(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    defs = tools.tool_definitions
    names = [d["name"] for d in defs]
    assert names == ["read_index", "list_hubs", "search", "read_page"]
    for d in defs:
        assert "description" in d and len(d["description"]) > 20
        assert d["input_schema"]["type"] == "object"
        # required is always present (possibly empty for list_hubs)
        assert "required" in d["input_schema"]
    # read_index lists every orientation file as a valid enum path
    rid = next(d for d in defs if d["name"] == "read_index")
    enum = rid["input_schema"]["properties"]["path"]["enum"]
    assert "CLAUDE.md" in enum and "index.md" in enum and "wiki/index.md" in enum


def test_read_index_hits_and_misses(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)

    hit = tools.dispatch("read_index", {"path": "CLAUDE.md"})
    assert "Agent Rules" in hit.text
    assert "Rules body" in hit.text
    assert hit.summary.startswith("CLAUDE.md")

    miss = tools.dispatch("read_index", {"path": "wiki/nope.md"})
    assert miss.text.startswith("ERROR")
    assert miss.summary.startswith("miss:")


def test_list_hubs_returns_metadata_and_when_to_use(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)

    res = tools.dispatch("list_hubs", {})
    payload = json.loads(res.text)
    assert len(payload) == 1
    hub = payload[0]
    assert hub["slug"] == "approved-tools"
    assert hub["title"] == "Approved AI Tools"
    assert hub["status"] == "reviewed"
    assert hub["synthesizes"] == ["488210484", "522289260", "498597967"]
    assert hub["source_pages"][0] == {
        "page_id": "488210484",
        "title": "Claude FAQ",
        "source_url": "https://example.test/488210484",
    }
    assert "comparing approved AI tools" in hub["when_to_use"]


def test_search_returns_top_hits_with_title_weight(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)

    res = tools.dispatch("search", {"query": "Claude FERPA retention", "top_k": 5})
    hits = json.loads(res.text)
    # Claude FAQ should rank first — title contains "Claude" + body has FERPA + retention.
    assert hits[0]["id"] == "488210484"
    assert hits[0]["layer"] == "raw"
    # The wiki hub also matches and should appear because it cites Claude.
    layers = {h["layer"] for h in hits}
    assert "wiki" in layers or "raw" in layers  # at minimum we get one
    for h in hits:
        assert {"id", "title", "snippet", "score", "layer", "path"} <= set(h)
        if h["layer"] == "raw":
            assert h["source_url"].startswith("https://example.test/")
        if h["layer"] == "wiki":
            assert h["source_pages"][0]["source_url"].startswith("https://example.test/")
        assert h["score"] > 0


def test_search_empty_query_returns_no_hits(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    res = tools.dispatch("search", {"query": "the and of"})  # all stopwords
    assert res.text == "[]"
    assert "empty-query" in res.summary


def test_read_page_raw_and_wiki(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)

    raw_hit = tools.dispatch("read_page", {"id": "488210484"})
    assert "Claude FAQ" in raw_hit.text
    assert "page_id: 488210484" in raw_hit.text
    assert "layer: raw" in raw_hit.text
    assert "FERPA" in raw_hit.text

    wiki_hit = tools.dispatch("read_page", {"id": "approved-tools"})
    assert "Approved AI Tools" in wiki_hit.text
    assert "layer: wiki" in wiki_hit.text
    assert "synthesizes:" in wiki_hit.text
    assert "source_pages:" in wiki_hit.text
    assert "https://example.test/488210484" in wiki_hit.text


def test_read_page_misses(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)

    raw_miss = tools.dispatch("read_page", {"id": "999999"})
    assert raw_miss.text.startswith("ERROR")
    assert raw_miss.summary.startswith("miss: raw")

    wiki_miss = tools.dispatch("read_page", {"id": "no-such-hub"})
    assert wiki_miss.text.startswith("ERROR")
    assert wiki_miss.summary.startswith("miss: wiki")
    # Known slugs surfaced in the error to help the model recover
    assert "approved-tools" in wiki_miss.text


def test_dispatch_unknown_tool_returns_error(tmp_path):
    cfg = _make_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    res = tools.dispatch("does_not_exist", {})
    assert res.text.startswith("ERROR")
    assert "unknown tool" in res.summary
