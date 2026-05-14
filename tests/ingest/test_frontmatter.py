"""Frontmatter spec §4.4 — required fields, sanitization, content hash."""

from __future__ import annotations

from sukb.ingest.frontmatter import (
    PageMeta,
    build_frontmatter,
    canonical_filename,
    content_hash,
    maintenance_signal,
    sanitize_filename_title,
    serialize,
    validate,
)


def test_sanitize_filename_replaces_windows_illegal_chars():
    assert sanitize_filename_title("Foo: bar / baz") == "Foo_ bar - baz"
    assert sanitize_filename_title('Q&A: "AI tools"?') == "Q&A_ 'AI tools'"
    # em-dash + en-dash preserved
    assert "—" in sanitize_filename_title("Long — title")
    assert "–" in sanitize_filename_title("Section – name")


def test_canonical_filename_format():
    assert canonical_filename("488210484", "Claude FAQ") == "488210484 - Claude FAQ.md"


def test_content_hash_stable():
    a = content_hash("hello world\n")
    b = content_hash("hello world\n")
    c = content_hash("hello world!\n")
    assert a == b
    assert a != c
    assert a.startswith("sha256:")


def test_maintenance_signal_buckets():
    assert maintenance_signal(0) == "fresh"
    assert maintenance_signal(89) == "fresh"
    assert maintenance_signal(90) == "aging"
    assert maintenance_signal(200) == "aging"
    assert maintenance_signal(365) == "stale"
    assert maintenance_signal(9999) == "stale"


def test_frontmatter_required_fields_validate():
    meta = PageMeta(
        page_id="488210484",
        title="Claude FAQ",
        source_url="https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/488210484/Claude+FAQ",
        space_key="ITSAI",
        space_name="Artificial Intelligence (AI)",
        space_type="knowledge_base",
        space_category="knowledge-bases",
        last_modified="2026-05-04T14:23:11Z",
        version=14,
    )
    fm = build_frontmatter(meta, body_markdown="# hello\n")
    assert validate(fm) == []
    text = serialize(fm)
    assert text.startswith("---\n")
    assert "page_id: '488210484'" in text or 'page_id: "488210484"' in text


def test_frontmatter_validation_flags_missing_last_modified():
    meta = PageMeta(
        page_id="1", title="x", source_url="https://x",
        space_key="ITSAI", space_name="AI", space_type="global", space_category="knowledge-bases",
        # last_modified deliberately omitted
    )
    fm = build_frontmatter(meta, body_markdown="body")
    errors = validate(fm)
    assert "last_modified" in errors


def test_frontmatter_classifier_fields_null_in_v1():
    meta = PageMeta(
        page_id="1", title="x", source_url="https://x",
        space_key="ITSAI", space_name="AI", space_type="global", space_category="knowledge-bases",
    )
    fm = build_frontmatter(meta, body_markdown="body")
    assert fm["audience"] is None
    assert fm["doc_type"] is None
    assert fm["tools"] == []
    assert fm["topics"] == []
