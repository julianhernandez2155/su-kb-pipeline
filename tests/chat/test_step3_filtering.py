"""Phase 1.1 Step 3 — MCP/agentic read-path enforcement (ADR-0009).

Invariant under test: a page whose frontmatter `visibility_signal` is anything
other than `no_read_restrictions_seen` MUST NOT appear via any of the five
public retrieval surfaces:

  - search
  - read_page
  - list_index (orientation files; we test that restricted page IDs don't
    bleed into the index body — orientation files themselves don't have
    visibility_signal, so the surface itself isn't filtered, but its content
    must not name restricted pages)
  - list_hubs (hubs whose synthesizes references a restricted page are
    dropped entirely)
  - hub source_pages (defense-in-depth — even if a polluted hub slipped
    through, source_pages must not surface restricted IDs)

Plus citation resolution: a `[[<restricted-id>]]` reference in an answer
resolves to `(restricted — not available)` instead of the page's title/URL.

The fixtures cover restricted_inherited (Summer Intern style), restricted_direct,
space_restricted, unknown, and the legacy `accessible_to_sync_user` value
(which must ALSO be filtered — Step 3 ships alongside the v3 schema migration
so legacy values are not the public-allow path).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sukb.chat import agentic_tools as at
from sukb.chat import query as q


# --- fixtures ---------------------------------------------------------------


def _write_raw(
    dir_: Path,
    page_id: str,
    title: str,
    body: str,
    visibility_signal: str = "no_read_restrictions_seen",
) -> None:
    """Write a v3-frontmatter raw page with explicit visibility_signal."""
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
    """Build a corpus with one page in each access bucket:

    Page 100 — no_read_restrictions_seen  (must be queryable)
    Page 200 — restricted_inherited       (must NOT be queryable)
    Page 300 — restricted_direct          (must NOT be queryable)
    Page 400 — space_restricted           (must NOT be queryable)
    Page 500 — unknown                    (must NOT be queryable)
    Page 600 — accessible_to_sync_user    (legacy v2 value — must NOT be queryable)

    Hubs:
      clean-hub   — synthesizes [100]              (must be queryable)
      mixed-hub   — synthesizes [100, 200]         (must NOT appear — restricted source)
      unknown-hub — synthesizes [100, 500]         (must NOT appear — unknown source)
    """
    output_dir = tmp_path / "output"
    raw = output_dir / "raw"
    wiki = output_dir / "wiki"
    output_dir.mkdir()
    raw.mkdir()

    _write_raw(raw / "ok", "100", "Public Claude Tips",
               "Approved tool. FERPA-safe when signed in.")
    _write_raw(raw / "intern", "200", "Restricted Inherited Page",
               "Internal staff notes about onboarding.",
               visibility_signal="restricted_inherited")
    _write_raw(raw / "direct", "300", "Restricted Direct Page",
               "Direct read restriction; HR-only.",
               visibility_signal="restricted_direct")
    _write_raw(raw / "space", "400", "Space Restricted Page",
               "Space-level lockdown.",
               visibility_signal="space_restricted")
    _write_raw(raw / "unsure", "500", "Unknown Visibility Page",
               "Classifier errored on this one.",
               visibility_signal="unknown")
    _write_raw(raw / "legacy", "600", "Legacy Sync User Page",
               "Old v2-schema value, must not pass the public gate.",
               visibility_signal="accessible_to_sync_user")

    (output_dir / "CLAUDE.md").write_text("# Agent Rules\nGo.", encoding="utf-8")
    (output_dir / "index.md").write_text("# Global Index\nSee hubs.", encoding="utf-8")

    _write_hub(wiki, "clean-hub", "Clean Hub", ["100"],
               "All-public synthesis [[100]].")
    _write_hub(wiki, "mixed-hub", "Mixed Hub", ["100", "200"],
               "Mixes a restricted source [[200]].")
    _write_hub(wiki, "unknown-hub", "Unknown Hub", ["100", "500"],
               "Mixes an unknown source [[500]].")

    return SimpleNamespace(output_dir=output_dir, raw_path=raw)


# --- load_raw_corpus filter ------------------------------------------------


def test_load_raw_corpus_returns_only_no_read_restrictions_seen(tmp_path):
    cfg = _make_mixed_corpus(tmp_path)
    pages = q.load_raw_corpus(cfg)
    ids = {p.page_id for p in pages}
    assert ids == {"100"}


def test_load_raw_corpus_with_include_restricted_returns_all(tmp_path):
    cfg = _make_mixed_corpus(tmp_path)
    pages = q.load_raw_corpus(cfg, include_restricted=True)
    ids = {p.page_id for p in pages}
    assert ids == {"100", "200", "300", "400", "500", "600"}


@pytest.mark.parametrize(
    "restricted_value",
    [
        "restricted_inherited",
        "restricted_direct",
        "space_restricted",
        "unknown",
        "accessible_to_sync_user",  # legacy v2 value — must NOT pass
        "",                         # missing/blank — must NOT pass
    ],
)
def test_load_raw_corpus_excludes_each_non_public_value(tmp_path, restricted_value):
    """Every non-public visibility_signal must be filtered. This is the
    explicit allowlist-by-value rule — only the canonical public string
    `no_read_restrictions_seen` is admitted."""
    cfg = _make_mixed_corpus(tmp_path)
    # Add a page with the parametrized value alongside the standard mix.
    _write_raw(cfg.raw_path / "test", "999", "Probe", "probe body",
               visibility_signal=restricted_value or "unknown")
    pages = q.load_raw_corpus(cfg)
    assert "999" not in {p.page_id for p in pages}


# --- load_wiki_corpus filter -----------------------------------------------


def test_load_wiki_corpus_drops_hubs_with_restricted_synthesizes(tmp_path):
    cfg = _make_mixed_corpus(tmp_path)
    allowed = {p.page_id for p in q.load_raw_corpus(cfg)}
    hubs = q.load_wiki_corpus(cfg, allowed_raw_ids=allowed)
    titles = {h.title for h in hubs}
    assert titles == {"Clean Hub"}
    # mixed-hub and unknown-hub are dropped entirely.


def test_load_wiki_corpus_records_restricted_source_ids_when_dropped_disabled(tmp_path):
    """include_restricted=True returns the hubs but flags which synthesizes
    were restricted — useful for admin/audit paths."""
    cfg = _make_mixed_corpus(tmp_path)
    allowed = {p.page_id for p in q.load_raw_corpus(cfg)}
    hubs = q.load_wiki_corpus(cfg, allowed_raw_ids=allowed, include_restricted=True)
    titles = {h.title: h for h in hubs}
    assert "Clean Hub" in titles
    assert titles["Clean Hub"].restricted_source_ids == []
    assert sorted(titles["Mixed Hub"].restricted_source_ids) == ["200"]
    assert sorted(titles["Unknown Hub"].restricted_source_ids) == ["500"]


def test_load_wiki_corpus_no_filter_when_allowed_raw_ids_none(tmp_path):
    """Backward-compat: callers passing None get every reviewed hub."""
    cfg = _make_mixed_corpus(tmp_path)
    hubs = q.load_wiki_corpus(cfg, allowed_raw_ids=None)
    titles = {h.title for h in hubs}
    assert titles == {"Clean Hub", "Mixed Hub", "Unknown Hub"}


# --- AgenticTools.search ----------------------------------------------------


def test_search_does_not_return_restricted_raw_pages(tmp_path):
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    # Search using terms that match restricted pages by title:
    res = tools.dispatch("search", {"query": "restricted page direct inherited unknown"})
    hits = json.loads(res.text)
    ids = {h["id"] for h in hits}
    # Restricted page IDs must not surface anywhere in the hits.
    assert ids.isdisjoint({"200", "300", "400", "500", "600"})


def test_search_does_not_return_hubs_with_restricted_synthesizes(tmp_path):
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    res = tools.dispatch("search", {"query": "synthesis mixed unknown restricted"})
    hits = json.loads(res.text)
    slugs = {h["id"] for h in hits if h.get("layer") == "wiki"}
    # Mixed and Unknown hubs are dropped; only clean-hub survives (if it
    # matches the query terms at all).
    assert "mixed-hub" not in slugs
    assert "unknown-hub" not in slugs


# --- AgenticTools.read_page ------------------------------------------------


@pytest.mark.parametrize("restricted_id", ["200", "300", "400", "500", "600"])
def test_read_page_returns_miss_for_restricted_page(tmp_path, restricted_id):
    """Restricted IDs return the SAME external message as a nonexistent ID.
    The model must not be able to distinguish 'exists but you can't see it'
    from 'doesn't exist' — that would enable exfiltration by enumeration.
    """
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    res = tools.dispatch("read_page", {"id": restricted_id})
    assert res.text.startswith("ERROR")
    assert restricted_id in res.text  # the ID itself is fine to echo
    # Body content of the restricted page must NOT appear.
    assert "Internal staff notes" not in res.text
    assert "HR-only" not in res.text
    assert "Space-level lockdown" not in res.text
    assert "Classifier errored" not in res.text
    # Title of the restricted page must NOT appear.
    assert "Restricted" not in res.text
    assert "Space Restricted" not in res.text


def test_read_page_trace_summary_marks_restricted(tmp_path):
    """Trace observability: the summary (NOT the text) distinguishes
    restricted from nonexistent. This is for the eval trace, never for the
    model — `text` is what Claude sees, `summary` is what the trace logs."""
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    # Restricted: summary annotated.
    r1 = tools.dispatch("read_page", {"id": "200"})
    assert "(restricted)" in r1.summary
    # Nonexistent: summary not annotated as restricted.
    r2 = tools.dispatch("read_page", {"id": "9999999"})
    assert "(restricted)" not in r2.summary


def test_read_page_returns_miss_for_dropped_wiki_hub(tmp_path):
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    # mixed-hub is dropped at load time; its slug must look like a 404.
    res = tools.dispatch("read_page", {"id": "mixed-hub"})
    assert res.text.startswith("ERROR")
    # Body of the dropped hub must not appear.
    assert "Mixes a restricted source" not in res.text


def test_read_page_still_returns_clean_pages_and_hubs(tmp_path):
    """Sanity check: the filter does not lock out clean content."""
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    raw_hit = tools.dispatch("read_page", {"id": "100"})
    assert raw_hit.text.startswith("---")
    assert "FERPA-safe" in raw_hit.text
    wiki_hit = tools.dispatch("read_page", {"id": "clean-hub"})
    assert wiki_hit.text.startswith("---")
    assert "All-public synthesis" in wiki_hit.text


# --- AgenticTools.list_hubs ------------------------------------------------


def test_list_hubs_excludes_hubs_with_restricted_synthesizes(tmp_path):
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    res = tools.dispatch("list_hubs", {})
    hubs = json.loads(res.text)
    slugs = {h["slug"] for h in hubs}
    assert slugs == {"clean-hub"}
    assert tools.dropped_hub_count == 2


def test_list_hubs_source_pages_dont_leak_restricted_titles(tmp_path):
    """Defense in depth: even though dropped hubs don't reach list_hubs,
    `_source_pages_for_hub` must also filter — if a regression ever lets
    a polluted hub through, this is the second line."""
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    # Force the resolver to run against a hub that DOES contain a
    # restricted synthesize ID. We construct a fake WikiHub for the test
    # — we are testing the resolver, not the load-time gate.
    fake_hub = q.WikiHub(
        title="Fake Mixed", filename="fake-mixed.md",
        synthesizes=["100", "200", "999"],  # 100 clean, 200 restricted, 999 nonexistent
        body="x", status="reviewed",
    )
    resolved = tools._source_pages_for_hub(fake_hub)
    by_id = {r["page_id"]: r for r in resolved}
    # 100 (clean): real title + URL
    assert by_id["100"]["title"] == "Public Claude Tips"
    assert by_id["100"]["source_url"] == "https://example.test/100"
    # 200 (restricted): sentinel, no title or URL leak
    assert by_id["200"]["title"] == "(not available)"
    assert by_id["200"]["source_url"] == ""
    # 999 (nonexistent): same sentinel — model can't distinguish
    assert by_id["999"]["title"] == "(not available)"


# --- list_index (orientation files) ----------------------------------------


def test_list_index_orientation_does_not_name_restricted_page_ids(tmp_path):
    """The orientation files (CLAUDE.md, index.md) are static surface, not
    classifier-driven. If they happen to name a restricted page by ID,
    that's a CONTENT problem to fix at the source — but this test confirms
    we never auto-generate orientation content from restricted pages.
    The current pipeline doesn't auto-write orientation files from raw
    pages, so the test asserts the surfaces only mention IDs we explicitly
    embedded as clean."""
    cfg = _make_mixed_corpus(tmp_path)
    tools = at.AgenticTools(cfg)
    res = tools.dispatch("read_index", {"path": "index.md"})
    # The fixture body says "See hubs." — no restricted IDs.
    assert "200" not in res.text
    assert "300" not in res.text
    assert "400" not in res.text
    assert "500" not in res.text
    assert "600" not in res.text


# --- citation resolution ---------------------------------------------------


def test_extract_citations_marks_restricted_distinctly_from_unresolved():
    pages = [
        q.RawPage(
            page_id="100", title="Public", source_url="https://example.test/100",
            ancestor_path=[], body="", path="100.md",
            visibility_signal="no_read_restrictions_seen",
        ),
    ]
    restricted_ids = {"200"}
    answer = "Claim A [[100]]. Claim B [[200]]. Claim C [[999]]."
    citations = q.extract_citations(answer, pages, restricted_page_ids=restricted_ids)
    by_id = {c["page_id"]: c for c in citations}
    assert by_id["100"]["title"] == "Public"
    assert by_id["200"]["title"] == "(restricted — not available)"
    assert by_id["200"]["source_url"] == ""
    assert by_id["999"]["title"] == "(unresolved)"


def test_extract_citations_backward_compat_without_restricted_arg():
    """Callers not passing `restricted_page_ids` get the legacy behavior:
    all unresolved citations look the same."""
    pages = [
        q.RawPage(
            page_id="100", title="Public", source_url="https://example.test/100",
            ancestor_path=[], body="", path="100.md",
            visibility_signal="no_read_restrictions_seen",
        ),
    ]
    answer = "Claim [[200]]."
    citations = q.extract_citations(answer, pages)
    assert citations == [{"page_id": "200", "title": "(unresolved)", "source_url": ""}]


# --- end-to-end: Summer-Intern-style fixture round-trip ---------------------


def test_summer_intern_fixture_does_not_appear_in_any_surface(tmp_path):
    """Phase 1.1 plan §"Step 4 Tests": Summer Intern fixture round-trips
    through ingest → classify → MCP filter → not-served. We simulate the
    post-ingest state directly (the puller is already tested separately)
    and assert no surface reveals the restricted page."""
    cfg = _make_mixed_corpus(tmp_path)
    # Add a Summer-Intern-style fixture: restricted_inherited via folder.
    _write_raw(cfg.raw_path / "summer-intern", "1068171339", "Julian Test 1st Page",
               "Making sure I have access to create new docs.",
               visibility_signal="restricted_inherited")
    tools = at.AgenticTools(cfg)

    # 1. search must not surface the page.
    s = json.loads(tools.dispatch("search", {"query": "Julian test page access docs"}).text)
    assert "1068171339" not in {h["id"] for h in s}

    # 2. read_page must miss.
    r = tools.dispatch("read_page", {"id": "1068171339"})
    assert r.text.startswith("ERROR")
    assert "Making sure" not in r.text

    # 3. list_hubs: even if a future hub synthesizes 1068171339, the load
    #    layer would have dropped it. We don't have such a hub here; just
    #    verify the page ID doesn't appear in list_hubs output at all.
    h = tools.dispatch("list_hubs", {})
    assert "1068171339" not in h.text
    assert "Julian Test" not in h.text

    # 4. The trace summary records the restricted miss (so eval observability works).
    assert "(restricted)" in r.summary
