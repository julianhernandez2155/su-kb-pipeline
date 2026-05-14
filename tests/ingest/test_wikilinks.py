"""Wikilink resolution — in-corpus + out-of-corpus degraded form (spec §4.6)."""

from __future__ import annotations

from sukb.ingest.wikilinks import PUBLIC_HOST, CorpusIndex, DefaultLinkResolver


def test_in_corpus_link_returns_page_id_wikilink(resolver):
    out = resolver.resolve_page_link("Claude FAQ", "ITSAI", None)
    assert out == "[[488210484 - Claude FAQ]]"


def test_in_corpus_link_by_id(resolver):
    out = resolver.resolve_page_link(None, None, "836698117")
    assert out == "[[836698117 - Copilot FAQ]]"


def test_out_of_corpus_emits_search_url_with_space_key():
    # Empty corpus → every link is out-of-corpus
    resolver = DefaultLinkResolver(corpus=CorpusIndex(), current_space_key="ITSAI", current_page_id="1")
    out = resolver.resolve_page_link("Data Classification Definitions", "InfoSec", None)
    # Spec §4.6: degraded form is `[title](source_url)` — not `[title](#anchor)`
    assert out.startswith("[Data Classification Definitions](")
    assert PUBLIC_HOST in out
    assert "text=Data+Classification+Definitions" in out
    assert "spaceKey=InfoSec" in out
    # No placeholder anchor
    assert "#unresolved" not in out


def test_out_of_corpus_falls_back_to_current_space_key_when_none_given():
    resolver = DefaultLinkResolver(corpus=CorpusIndex(), current_space_key="ITSAI", current_page_id="1")
    out = resolver.resolve_page_link("Some Page", None, None)
    assert "spaceKey=ITSAI" in out


def test_out_of_corpus_no_title_emits_safe_fallback():
    resolver = DefaultLinkResolver(corpus=CorpusIndex(), current_space_key="ITSAI", current_page_id="1")
    out = resolver.resolve_page_link(None, None, None)
    assert PUBLIC_HOST in out
    assert "#unresolved" not in out


def test_attachment_resolver_returns_relative_path(resolver):
    assert resolver.resolve_attachment("999", "diagram.png") == "attachments/999/diagram.png"
