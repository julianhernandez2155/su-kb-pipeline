"""Frontmatter spec §4.4 — required fields, sanitization, content hash.

Schema v2 (Phase 1, 2026-05-19) tests cover:
- new factual fields (word_count, char_count, token_estimate, attachment_count,
  tags_original, visibility_*)
- threshold helpers (count_words, token_estimate_from_chars)
- classifier-key preservation across re-sync (read_existing_frontmatter +
  merge_preserved_keys)
"""

from __future__ import annotations

from pathlib import Path

import yaml

from sukb.ingest.frontmatter import (
    CLASSIFIER_OWNED_KEYS,
    FRONTMATTER_SCHEMA_VERSION,
    PageMeta,
    build_frontmatter,
    canonical_filename,
    content_hash,
    count_words,
    find_existing_page_file,
    maintenance_signal,
    merge_preserved_keys,
    read_existing_frontmatter,
    sanitize_filename_title,
    serialize,
    token_estimate_from_chars,
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


# --- schema v2 (Phase 1, 2026-05-19) ----------------------------------------


def test_count_words_basic():
    assert count_words("") == 0
    assert count_words("hello") == 1
    assert count_words("hello world") == 2
    assert count_words("hello   world\n\nfoo bar") == 4
    assert count_words("   ") == 0


def test_token_estimate_from_chars_ceiling():
    assert token_estimate_from_chars(0) == 0
    assert token_estimate_from_chars(-5) == 0
    # 7 / 3.5 = 2 exactly → 2
    assert token_estimate_from_chars(7) == 2
    # 8 / 3.5 = 2.285... → ceil → 3
    assert token_estimate_from_chars(8) == 3
    # 35 / 3.5 = 10 → 10
    assert token_estimate_from_chars(35) == 10


def test_frontmatter_observed_fields_populated():
    meta = PageMeta(
        page_id="1", title="x", source_url="https://x",
        space_key="ITSAI", space_name="AI", space_type="global", space_category="knowledge-bases",
        labels=["claude", "faq"],
        attachment_count=3,
    )
    body = "hello world foo bar"  # 4 words, 19 chars
    fm = build_frontmatter(meta, body_markdown=body)
    assert fm["word_count"] == 4
    assert fm["char_count"] == 19
    assert fm["token_estimate"] == 6  # ceil(19/3.5) = 6
    assert fm["attachment_count"] == 3
    assert fm["tags_original"] == ["claude", "faq"]
    assert fm["labels"] == ["claude", "faq"]
    # Phase 1.1 Step 2 (ADR-0007) defaults from PageMeta dataclass:
    # absence of access classification = `unknown` (MCP filters it out).
    assert fm["visibility_signal"] == "unknown"
    assert fm["restriction_check"] == []
    assert fm["restriction_source_ids"] == []
    # `restricted_to` was dropped in schema v3 — must not appear.
    assert "restricted_to" not in fm


def test_frontmatter_tags_original_is_independent_copy():
    """Mutating one list must not bleed into the other."""
    meta = PageMeta(
        page_id="1", title="x", source_url="https://x",
        space_key="ITSAI", space_name="AI", space_type="global", space_category="knowledge-bases",
        labels=["a"],
    )
    fm = build_frontmatter(meta, body_markdown="body")
    fm["labels"].append("mutated")
    assert fm["tags_original"] == ["a"]


def test_frontmatter_visibility_overrides_via_meta():
    """Schema v3 (ADR-0007): list-shape restriction_check + restriction_source_ids."""
    meta = PageMeta(
        page_id="1", title="x", source_url="https://x",
        space_key="ITSAI", space_name="AI", space_type="global", space_category="knowledge-bases",
        visibility_signal="restricted_inherited",
        restriction_check=["direct", "ancestors", "space"],
        restriction_source_ids=["1069121551"],
    )
    fm = build_frontmatter(meta, body_markdown="body")
    assert fm["visibility_signal"] == "restricted_inherited"
    assert fm["restriction_check"] == ["direct", "ancestors", "space"]
    assert fm["restriction_source_ids"] == ["1069121551"]
    assert "restricted_to" not in fm


def test_classifier_keys_preserved_across_resync(tmp_path: Path):
    meta = PageMeta(
        page_id="488210484", title="Claude FAQ",
        source_url="https://answers.atlassian.syr.edu/x",
        space_key="ITSAI", space_name="AI", space_type="knowledge_base",
        space_category="knowledge-bases",
        last_modified="2026-05-04T14:23:11Z", version=14,
    )
    target = tmp_path / "488210484 - Claude FAQ.md"

    # First write — V1 defaults for classifier-owned keys
    fm1 = build_frontmatter(meta, body_markdown="body v1")
    assert fm1["audience"] is None
    target.write_text(serialize(fm1) + "\nbody v1", encoding="utf-8")

    # Simulate the classifier writing values into the file
    existing = read_existing_frontmatter(target)
    assert existing is not None
    existing["audience"] = "student"
    existing["doc_type"] = "how_to"
    existing["tools"] = ["claude"]
    existing["topics"] = ["onboarding", "setup"]
    existing["tags_normalized"] = ["claude/setup", "windows"]
    target.write_text(serialize(existing) + "\nbody v1", encoding="utf-8")

    # Re-sync: build new frontmatter with the existing as preservation source
    existing_after_classifier = read_existing_frontmatter(target)
    fm2 = build_frontmatter(
        meta, body_markdown="body v2",
        existing_frontmatter=existing_after_classifier,
    )
    assert fm2["audience"] == "student"
    assert fm2["doc_type"] == "how_to"
    assert fm2["tools"] == ["claude"]
    assert fm2["topics"] == ["onboarding", "setup"]
    assert fm2["tags_normalized"] == ["claude/setup", "windows"]
    # But puller-owned keys must reflect the new body
    assert "v2" in fm2["content_hash"] or fm2["content_hash"] != fm1["content_hash"]


def test_classifier_preservation_keys_match_documented_set():
    """Guard against drift between the constant and what is preserved."""
    assert set(CLASSIFIER_OWNED_KEYS) == {
        "audience", "doc_type", "tools", "topics", "tags_normalized",
    }


def test_merge_preserved_keys_no_existing_is_noop():
    new_fm = {"audience": None, "doc_type": None}
    result = merge_preserved_keys(new_fm, None)
    assert result["audience"] is None
    assert result["doc_type"] is None


def test_merge_preserves_future_classifier_block():
    new_fm = {"audience": None}
    existing = {"classifier": {"model": "haiku-4.5", "confidence": 0.92}}
    result = merge_preserved_keys(new_fm, existing)
    assert result["classifier"]["model"] == "haiku-4.5"
    assert result["classifier"]["confidence"] == 0.92


def test_read_existing_frontmatter_handles_missing_file(tmp_path: Path):
    assert read_existing_frontmatter(tmp_path / "nonexistent.md") is None


def test_read_existing_frontmatter_handles_no_frontmatter(tmp_path: Path):
    p = tmp_path / "no-fm.md"
    p.write_text("just body, no frontmatter\n", encoding="utf-8")
    assert read_existing_frontmatter(p) is None


def test_read_existing_frontmatter_handles_malformed_yaml(tmp_path: Path):
    p = tmp_path / "bad-yaml.md"
    p.write_text("---\nkey: : : value\n---\nbody\n", encoding="utf-8")
    assert read_existing_frontmatter(p) is None


def test_read_existing_frontmatter_roundtrip(tmp_path: Path):
    p = tmp_path / "ok.md"
    p.write_text(
        "---\n"
        "page_id: '123'\n"
        "title: hello\n"
        "audience: student\n"
        "---\n"
        "body content\n",
        encoding="utf-8",
    )
    fm = read_existing_frontmatter(p)
    assert fm is not None
    assert fm["page_id"] == "123"
    assert fm["audience"] == "student"


# --- find_existing_page_file (rename-aware classifier preservation) ---------


def test_find_existing_page_file_basic(tmp_path: Path):
    target = tmp_path / "100 - foo.md"
    target.write_text("---\n---\n", encoding="utf-8")
    found = find_existing_page_file(tmp_path, "100")
    assert found == target


def test_find_existing_page_file_finds_after_ancestor_move(tmp_path: Path):
    """Page used to live at A/B/100 - x.md, now under D/100 - x.md."""
    space_root = tmp_path / "space"
    new_dir = space_root / "D"
    new_dir.mkdir(parents=True)
    moved = new_dir / "100 - new-loc.md"
    moved.write_text("body", encoding="utf-8")
    found = find_existing_page_file(space_root, "100")
    assert found == moved


def test_find_existing_page_file_finds_after_title_change(tmp_path: Path):
    """Page renamed: old filename was '100 - old.md', now '100 - new.md'."""
    (tmp_path / "100 - new title.md").write_text("body", encoding="utf-8")
    found = find_existing_page_file(tmp_path, "100")
    assert found is not None
    assert found.name == "100 - new title.md"


def test_find_existing_page_file_missing(tmp_path: Path):
    (tmp_path / "100 - x.md").write_text("body", encoding="utf-8")
    assert find_existing_page_file(tmp_path, "999") is None


def test_find_existing_page_file_handles_absent_dir(tmp_path: Path):
    assert find_existing_page_file(tmp_path / "does-not-exist", "100") is None


def test_classifier_preservation_survives_rename(tmp_path: Path):
    """Integration: read+merge flow preserves classifier fields when title
    changed and the new canonical path differs from the old one. This is the
    Phase 1 G2 'rename-aware preservation' fix.
    """
    space_root = tmp_path / "ITSAI"
    old_dir = space_root / "Old Ancestor"
    old_dir.mkdir(parents=True)
    old_path = old_dir / "100 - Old Title.md"

    # Pretend a prior sync wrote this file with classifier fields populated.
    initial_fm = {
        "page_id": "100",
        "title": "Old Title",
        "audience": "student",
        "doc_type": "how_to",
        "tools": ["claude"],
        "topics": ["onboarding"],
        "tags_normalized": ["claude/setup"],
    }
    old_path.write_text(serialize(initial_fm) + "\nold body\n", encoding="utf-8")

    # The page got renamed + moved in Confluence. Puller would build a new
    # target path under a different ancestor; the old file is the orphan.
    found = find_existing_page_file(space_root, "100")
    assert found == old_path

    existing_fm = read_existing_frontmatter(found)
    assert existing_fm is not None
    assert existing_fm["audience"] == "student"

    # Build the new frontmatter for the renamed page; classifier fields
    # should be carried across.
    meta = PageMeta(
        page_id="100", title="New Title",
        source_url="https://x", space_key="ITSAI",
        space_name="AI", space_type="knowledge_base",
        space_category="knowledge-bases",
        last_modified="2026-05-04T14:23:11Z", version=15,
    )
    fm = build_frontmatter(meta, body_markdown="new body", existing_frontmatter=existing_fm)
    assert fm["title"] == "New Title"  # puller-owned: updated
    assert fm["audience"] == "student"  # classifier-owned: preserved
    assert fm["doc_type"] == "how_to"
    assert fm["tools"] == ["claude"]
    assert fm["topics"] == ["onboarding"]
    assert fm["tags_normalized"] == ["claude/setup"]


def test_frontmatter_schema_version_constant_exposed():
    """Phase 1.1 Step 2 (ADR-0007) bumps to schema v3.

    The constant is the contract surface — bumps trigger state-driven
    backfill via `SyncState.should_skip_by_version`.
    """
    assert FRONTMATTER_SCHEMA_VERSION == 3


def test_serialized_yaml_field_ordering():
    """New fields are placed near related existing fields (codex G1 guidance).

    This is a guard rail — a regression here would reshuffle every page on
    the next ingest and make diffs unreadable.
    """
    meta = PageMeta(
        page_id="1", title="x", source_url="https://x",
        space_key="ITSAI", space_name="AI", space_type="global",
        space_category="knowledge-bases",
        last_modified="2026-05-04T14:23:11Z", version=14,
        labels=["foo"],
    )
    fm = build_frontmatter(meta, body_markdown="body")
    text = serialize(fm)
    # Field ordering checks (substring positions)
    assert text.index("source_url") < text.index("visibility_signal")
    assert text.index("visibility_signal") < text.index("space_key")
    assert text.index("labels") < text.index("tags_original")
    assert text.index("tags_original") < text.index("audience")
    assert text.index("maintenance_signal") < text.index("word_count")
    assert text.index("word_count") < text.index("char_count")
    assert text.index("char_count") < text.index("token_estimate")
    assert text.index("token_estimate") < text.index("attachment_count")
