"""Unit tests for sukb.chat.query — corpus loading, citation parsing,
prompt assembly, and the answer_query happy path with a stub client.

No live Anthropic calls — `answer_query` accepts an injectable `client`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sukb.chat import query as q


def _write_page(dir_: Path, page_id: str, title: str, body: str, source_url: str = "") -> Path:
    """Write a frontmatter-prefixed Markdown page to disk and return the path."""
    dir_.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace("/", "_")
    path = dir_ / f"{page_id} - {safe_title}.md"
    src = source_url or f"https://example.test/{page_id}"
    path.write_text(
        f"---\n"
        f"page_id: '{page_id}'\n"
        f"title: {title}\n"
        f"source_url: {src}\n"
        f"ancestor_path: [Root, Sub]\n"
        f"---\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return path


def _make_config(tmp_path: Path) -> SimpleNamespace:
    """Lightweight stand-in for SyncConfig — only exposes the fields query.py reads."""
    output_dir = tmp_path / "output"
    raw_path = output_dir / "raw"
    return SimpleNamespace(output_dir=output_dir, raw_path=raw_path)


# --- corpus loading ---------------------------------------------------------


def test_load_raw_corpus_skips_meta_and_non_page_files(tmp_path):
    cfg = _make_config(tmp_path)
    _write_page(cfg.raw_path / "AI", "488210484", "Claude FAQ", "Claude retains chats for 2 years.")
    _write_page(cfg.raw_path / "AI", "522289260", "Copilot FAQ", "Copilot is approved for university data.")

    # Noise that should NOT be loaded:
    meta = cfg.raw_path / ".meta"
    meta.mkdir(parents=True)
    (meta / "sync-state.json").write_text("{}", encoding="utf-8")
    (cfg.raw_path / "AI" / "README.md").write_text("not a page", encoding="utf-8")  # no page-id prefix

    pages = q.load_raw_corpus(cfg)
    ids = {p.page_id for p in pages}
    assert ids == {"488210484", "522289260"}
    claude = next(p for p in pages if p.page_id == "488210484")
    assert claude.title == "Claude FAQ"
    assert "retains chats for 2 years" in claude.body
    assert claude.source_url.startswith("https://example.test/")


def test_load_raw_corpus_returns_empty_when_raw_missing(tmp_path):
    cfg = _make_config(tmp_path)  # raw_path doesn't exist
    assert q.load_raw_corpus(cfg) == []


def test_load_raw_corpus_excludes_test_pages_by_default(tmp_path):
    cfg = _make_config(tmp_path)
    # Real pages
    _write_page(cfg.raw_path / "AI" / "Claude", "488210484", "Claude FAQ", "real")
    # Test fixture: top-level page with (Test) in the title
    _write_page(cfg.raw_path / "AI", "948797482", "(Test) Resume Brain", "fixture")
    # Test fixture: child page under a (Test) folder
    _write_page(cfg.raw_path / "AI" / "(Test) Resume Brain", "965672963", "Workflow", "fixture")
    # Test fixture: intern Summer Intern 2026 page
    _write_page(cfg.raw_path / "AI" / "Summer Intern 2026", "1068171339", "Julian Test Page", "fixture")

    default = q.load_raw_corpus(cfg)
    assert {p.page_id for p in default} == {"488210484"}

    # Opt-in escape hatch keeps everything
    everything = q.load_raw_corpus(cfg, include_test_pages=True)
    assert {p.page_id for p in everything} == {"488210484", "948797482", "965672963", "1068171339"}


def test_load_raw_corpus_respects_max_pages(tmp_path):
    cfg = _make_config(tmp_path)
    for i, pid in enumerate(["100", "200", "300", "400"]):
        _write_page(cfg.raw_path, pid, f"Page {pid}", "body")
    pages = q.load_raw_corpus(cfg, max_pages=2)
    assert len(pages) == 2


def test_load_wiki_corpus_excludes_drafts(tmp_path):
    cfg = _make_config(tmp_path)
    wiki = cfg.output_dir / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "approved-tools.md").write_text(
        "---\ntitle: Approved Tools\ntype: hub\nstatus: reviewed\nsynthesizes: ['1','2','3']\n---\n"
        "Body content.\n",
        encoding="utf-8",
    )
    (wiki / "draft-hub.md").write_text(
        "---\ntitle: Draft\ntype: hub\nstatus: draft\nsynthesizes: ['1','2','3']\n---\n"
        "Body.\n",
        encoding="utf-8",
    )
    hubs = q.load_wiki_corpus(cfg)
    assert len(hubs) == 1
    assert hubs[0].title == "Approved Tools"
    assert hubs[0].synthesizes == ["1", "2", "3"]


def test_load_wiki_corpus_returns_empty_when_dir_missing(tmp_path):
    cfg = _make_config(tmp_path)
    assert q.load_wiki_corpus(cfg) == []


# --- citation parsing -------------------------------------------------------


def test_extract_citations_resolves_known_pages(tmp_path):
    pages = [
        q.RawPage("488210484", "Claude FAQ", "http://x/488", [], "body", "p1.md"),
        q.RawPage("522289260", "Copilot FAQ", "http://x/522", [], "body", "p2.md"),
    ]
    answer = (
        "Claude retains chats for 2 years [[488210484]]. "
        "Copilot is approved [[522289260]]. Repeat ref [[488210484 - Claude FAQ]]."
    )
    cits = q.extract_citations(answer, pages)
    # Deduped to two unique page_ids, in first-mention order
    assert [c["page_id"] for c in cits] == ["488210484", "522289260"]
    assert cits[0]["title"] == "Claude FAQ"
    assert cits[1]["source_url"] == "http://x/522"


def test_extract_citations_marks_unresolved_pages():
    pages = [q.RawPage("488210484", "Claude FAQ", "http://x", [], "body", "p.md")]
    answer = "Some claim [[999999999]] that has no source."
    cits = q.extract_citations(answer, pages)
    assert cits == [{"page_id": "999999999", "title": "(unresolved)", "source_url": ""}]


def test_extract_citations_empty_answer():
    assert q.extract_citations("", []) == []
    assert q.extract_citations("no citations here", []) == []


# --- prompt assembly --------------------------------------------------------


def test_serialize_corpus_includes_raw_and_wiki_blocks():
    raw = [q.RawPage("100", "T", "http://x", [], "raw body", "p.md")]
    wiki = [q.WikiHub("Hub", "hub.md", ["100", "200", "300"], "wiki body")]
    text = q.serialize_corpus(raw, wiki)
    assert "=== RAW PAGES ===" in text
    assert "page_id: 100" in text
    assert "=== WIKI HUBS ===" in text
    assert "title: Hub" in text
    assert "synthesizes: [100, 200, 300]" in text


def test_serialize_corpus_omits_wiki_block_when_empty():
    text = q.serialize_corpus([q.RawPage("100", "T", "http://x", [], "body", "p.md")], [])
    assert "=== RAW PAGES ===" in text
    assert "=== WIKI HUBS ===" not in text


def test_build_messages_payload_sets_cache_control():
    raw = [q.RawPage("100", "T", "http://x", [], "body", "p.md")]
    payload = q.build_messages_payload("question?", raw, [])
    assert payload["model"] == q.MODEL
    assert payload["messages"] == [{"role": "user", "content": "question?"}]
    # System is two blocks: instructions, then cached corpus
    assert len(payload["system"]) == 2
    assert payload["system"][0]["text"].startswith("You are the Syracuse University")
    assert payload["system"][1]["cache_control"] == {"type": "ephemeral"}


# --- cost estimation --------------------------------------------------------


def test_estimate_cost_usd_combines_all_token_buckets():
    usage = {
        "input_tokens": 100,
        "output_tokens": 200,
        "cache_creation_input_tokens": 1000,
        "cache_read_input_tokens": 10000,
    }
    cost = q.estimate_cost_usd(usage)
    expected = (100 * 3 + 200 * 15 + 1000 * 3.75 + 10000 * 0.30) / 1_000_000
    assert cost == pytest.approx(expected, rel=1e-6)


def test_estimate_cost_usd_handles_empty_usage():
    assert q.estimate_cost_usd({}) == 0.0


# --- end-to-end with a stub client -----------------------------------------


class _StubMessages:
    """Mimics Anthropic SDK shape just enough for query.py to consume."""
    def __init__(self, text: str, usage: dict):
        self._text = text
        self._usage = usage
        self.last_payload: dict | None = None

    def create(self, **payload):
        self.last_payload = payload
        return SimpleNamespace(
            content=[SimpleNamespace(text=self._text)],
            usage=SimpleNamespace(**self._usage),
        )


class _StubClient:
    def __init__(self, text: str, usage: dict):
        self.messages = _StubMessages(text, usage)


def test_answer_query_end_to_end(tmp_path):
    cfg = _make_config(tmp_path)
    _write_page(cfg.raw_path / "AI", "488210484", "Claude FAQ", "Claude retains chats for 2 years.")
    _write_page(cfg.raw_path / "AI", "522289260", "Copilot FAQ", "Copilot info.")

    stub = _StubClient(
        text="Claude retains chats for 2 years [[488210484]].\n\nSources: 488210484",
        usage={
            "input_tokens": 50,
            "output_tokens": 100,
            "cache_creation_input_tokens": 5000,
            "cache_read_input_tokens": 0,
        },
    )
    result = q.answer_query("How long does Claude retain chats?", config=cfg, mode="raw", client=stub)

    assert result.raw_pages_loaded == 2
    assert result.wiki_pages_loaded == 0
    assert result.mode == "raw"
    assert "488210484" in result.context_used["raw_pages"]
    assert result.citations == [
        {"page_id": "488210484", "title": "Claude FAQ", "source_url": "https://example.test/488210484"}
    ]
    assert result.cost_usd > 0
    # System prompt should be built with two blocks, last one cached.
    assert stub.messages.last_payload is not None
    assert stub.messages.last_payload["system"][1]["cache_control"] == {"type": "ephemeral"}


def test_answer_query_falls_back_to_raw_when_wiki_missing(tmp_path):
    cfg = _make_config(tmp_path)
    _write_page(cfg.raw_path, "100", "P", "body")
    stub = _StubClient(
        text="Answer [[100]].",
        usage={"input_tokens": 1, "output_tokens": 1},
    )
    result = q.answer_query("q?", config=cfg, mode="raw+wiki", client=stub)
    # Wiki dir doesn't exist → effective_mode should be raw
    assert result.mode == "raw"
    assert result.wiki_pages_loaded == 0


def test_answer_query_rejects_empty_question(tmp_path):
    cfg = _make_config(tmp_path)
    cfg.raw_path.mkdir(parents=True)
    with pytest.raises(ValueError):
        q.answer_query("   ", config=cfg, client=_StubClient("x", {}))
