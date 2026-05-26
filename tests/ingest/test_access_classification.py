"""Phase 1.1 Step 2 tests — direct + ancestor + space classifier (ADR-0007)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sukb.ingest.access import (
    PageClassification,
    classification_to_manifest_entry,
    classify_visibility,
    rewrite_access_fields,
)
from sukb.ingest.frontmatter import (
    ACCESS_OWNED_FIELDS,
    PageMeta,
    build_frontmatter,
    serialize,
)
from sukb.ingest.restrictions import (
    EntityRestrictions,
    RestrictionResult,
    _normalize_restriction_bucket,
    parse_by_operation_response,
    v1_rest_base_from_v2,
)
from sukb.ingest.spaces import (
    SpaceAudience,
    classify_space_audience,
    has_anonymous_read_space,
)


# --- builders ---------------------------------------------------------------


def _clean_direct(entity_id: str = "100", entity_type: str = "page") -> EntityRestrictions:
    return EntityRestrictions(
        entity_id=entity_id,
        entity_type=entity_type,
        read=RestrictionResult(False, raw={}),
        update=RestrictionResult(False, raw={}),
    )


def _restricted_direct(
    entity_id: str = "100",
    entity_type: str = "page",
    entity_title: str = "",
    user_ids: list[str] | None = None,
) -> EntityRestrictions:
    return EntityRestrictions(
        entity_id=entity_id,
        entity_type=entity_type,
        entity_title=entity_title,
        read=RestrictionResult(True, user_ids=user_ids or ["abc"], raw={}),
        update=RestrictionResult(False, raw={}),
    )


def _space(audience: str = "su_community", key: str = "ITSAI") -> SpaceAudience:
    return SpaceAudience(key=key, default_audience=audience, checked_at="t")


# --- classify_visibility ---------------------------------------------------


def test_classify_no_read_restrictions_seen():
    direct = _clean_direct()
    ancestors = [_clean_direct("p1"), _clean_direct("p2")]
    sig, layers, sources = classify_visibility(direct, ancestors, _space("su_community"))
    assert sig == "no_read_restrictions_seen"
    assert layers == ["direct", "ancestors", "space"]
    assert sources == []


def test_classify_no_restrictions_with_space_skipped():
    direct = _clean_direct()
    ancestors = [_clean_direct("p1")]
    sig, layers, sources = classify_visibility(direct, ancestors, _space("skipped"))
    assert sig == "no_read_restrictions_seen"
    assert layers == ["direct", "ancestors"]
    assert sources == []


def test_classify_restricted_direct():
    direct = _restricted_direct("100", "page")
    ancestors = [_clean_direct("p1")]
    sig, layers, sources = classify_visibility(direct, ancestors, _space("su_community"))
    assert sig == "restricted_direct"
    assert sources == ["100"]


def test_classify_restricted_inherited():
    direct = _clean_direct("100")
    ancestors = [
        _clean_direct("p1"),
        _restricted_direct("1069121551", "folder", "Summer Intern 2026"),
    ]
    sig, layers, sources = classify_visibility(direct, ancestors, _space("su_community"))
    assert sig == "restricted_inherited"
    assert sources == ["1069121551"]


def test_classify_space_restricted_wins_over_direct_clean():
    direct = _clean_direct()
    ancestors: list[EntityRestrictions] = []
    sig, layers, sources = classify_visibility(direct, ancestors, _space("restricted_space"))
    assert sig == "space_restricted"
    assert sources == ["space:ITSAI"]


def test_classify_unknown_space_audience_treated_as_space_restricted():
    """Tightened 2026-05-20: positive-ID failed AND no allowlist override.

    The MCP filter treats `space_restricted` as restricted, so pages in
    unidentified-audience spaces are not queryable. Skipped (vs unknown)
    is the safe path through direct+ancestors.
    """
    direct = _clean_direct()
    ancestors: list[EntityRestrictions] = [_clean_direct("p1")]
    sig, layers, sources = classify_visibility(direct, ancestors, _space("unknown"))
    assert sig == "space_restricted"
    assert sources == ["space:ITSAI"]


def test_classify_unknown_when_direct_errored():
    direct = EntityRestrictions(entity_id="100", entity_type="page", error="HTTP 403")
    sig, _, sources = classify_visibility(direct, [], _space("su_community"))
    assert sig == "unknown"
    assert sources == []


def test_classify_unknown_when_ancestor_errored():
    direct = _clean_direct()
    ancestors = [
        EntityRestrictions(entity_id="p1", entity_type="page", error="HTTP 403"),
    ]
    sig, layers, sources = classify_visibility(direct, ancestors, _space("su_community"))
    assert sig == "unknown"
    # `ancestors` excluded from check layers when the walk had an error
    assert "ancestors" not in layers


def test_classify_unknown_when_ancestors_is_none():
    direct = _clean_direct()
    sig, layers, _ = classify_visibility(direct, None, _space("su_community"))
    assert sig == "unknown"
    assert layers == ["direct", "space"]


# --- restrictions normalization --------------------------------------------


def test_normalize_restriction_bucket_clean():
    payload = {
        "operation": "read",
        "restrictions": {
            "user": {"results": [], "size": 0},
            "group": {"results": [], "size": 0},
        },
    }
    r = _normalize_restriction_bucket(payload)
    assert r.has_restrictions is False
    assert r.user_ids == []
    assert r.group_ids == []
    assert r.raw is payload


def test_normalize_restriction_bucket_with_users_and_groups():
    payload = {
        "operation": "read",
        "restrictions": {
            "user": {
                "results": [
                    {"accountId": "u1"},
                    {"accountId": "u2", "displayName": "x"},
                ],
                "size": 2,
            },
            "group": {"results": [{"id": "g1"}], "size": 1},
        },
    }
    r = _normalize_restriction_bucket(payload)
    assert r.has_restrictions is True
    assert r.user_ids == ["u1", "u2"]
    assert r.group_ids == ["g1"]


def test_normalize_falls_back_to_len_when_size_missing():
    payload = {
        "operation": "read",
        "restrictions": {
            "user": {"results": [{"accountId": "u1"}]},
            "group": {"results": []},
        },
    }
    r = _normalize_restriction_bucket(payload)
    assert r.has_restrictions is True  # len-derived
    assert r.user_ids == ["u1"]


def test_parse_by_operation_response_full_shape():
    payload = {
        "read": {
            "operation": "read",
            "restrictions": {"user": {"results": [{"accountId": "u1"}], "size": 1}, "group": {"results": [], "size": 0}},
        },
        "update": {
            "operation": "update",
            "restrictions": {"user": {"results": [], "size": 0}, "group": {"results": [{"id": "g1"}], "size": 1}},
        },
    }
    read, update = parse_by_operation_response(payload)
    assert read.has_restrictions is True
    assert read.user_ids == ["u1"]
    assert update.has_restrictions is True
    assert update.group_ids == ["g1"]


def test_v1_rest_base_from_v2_gateway_url():
    assert v1_rest_base_from_v2(
        "https://api.atlassian.com/ex/confluence/abc-cloud-id/wiki/api/v2"
    ) == "https://api.atlassian.com/ex/confluence/abc-cloud-id/wiki/rest/api"


def test_v1_rest_base_from_v2_custom_host():
    assert v1_rest_base_from_v2(
        "https://su-jsm.atlassian.net/wiki/api/v2"
    ) == "https://su-jsm.atlassian.net/wiki/rest/api"


# --- space classifier (tightened 2026-05-20) -------------------------------


def test_has_anonymous_read_space_present():
    payload = {
        "results": [
            {"principal": {"type": "group", "id": "abc"}, "operation": {"key": "read", "targetType": "space"}},
            {"principal": {"type": "role", "id": "ANONYMOUS"}, "operation": {"key": "read", "targetType": "space"}},
        ]
    }
    assert has_anonymous_read_space(payload) is True


def test_has_anonymous_read_space_absent():
    payload = {
        "results": [
            {"principal": {"type": "user", "id": "u1"}, "operation": {"key": "read", "targetType": "space"}},
        ]
    }
    assert has_anonymous_read_space(payload) is False


def test_has_anonymous_read_space_anonymous_but_not_read_space():
    """ANONYMOUS marker on a different operation must NOT count."""
    payload = {
        "results": [
            {"principal": {"type": "role", "id": "ANONYMOUS"}, "operation": {"key": "view", "targetType": "page"}},
        ]
    }
    assert has_anonymous_read_space(payload) is False


def test_classify_space_audience_su_community_via_positive_id():
    payload = {
        "results": [
            {"principal": {"type": "role", "id": "ANONYMOUS"}, "operation": {"key": "read", "targetType": "space"}},
        ]
    }
    assert classify_space_audience(payload) == "su_community"


def test_classify_space_audience_unknown_without_positive_id():
    """Tightened classifier: no ANONYMOUS marker and no allowlist override → unknown.

    The page-level classifier then treats pages in this space as
    `space_restricted` (MCP filters them).
    """
    payload = {
        "results": [
            {"principal": {"type": "group", "id": "abc"}, "operation": {"key": "read", "targetType": "space"}},
        ]
    }
    assert classify_space_audience(payload) == "unknown"


def test_classify_space_audience_allowlist_override():
    """Operator-declared `broadly_accessible_spaces` override positive-ID."""
    payload = {"results": [{"principal": {"type": "group", "id": "abc"}, "operation": {"key": "read", "targetType": "space"}}]}
    assert (
        classify_space_audience(payload, space_key="OPS", broadly_accessible_spaces=["OPS"])
        == "su_community"
    )


def test_classify_space_audience_unknown_when_empty_results():
    assert classify_space_audience({"results": []}) == "unknown"


def test_classify_space_audience_unknown_when_results_missing():
    assert classify_space_audience({}) == "unknown"


# --- manifest serialization ------------------------------------------------


def test_classification_to_manifest_entry_shape():
    record = PageClassification(
        page_id="100",
        title="Test",
        space_key="ITSAI",
        visibility_signal="restricted_inherited",
        restriction_check=["direct", "ancestors", "space"],
        restriction_source_ids=["1069121551"],
        checked_at="2026-05-20T12:00:00Z",
        checked_with_account_id="acct1",
        direct=_clean_direct(),
        ancestors=[_restricted_direct("1069121551", "folder", "Summer Intern 2026")],
        space=_space("su_community"),
    )
    entry = classification_to_manifest_entry(record)
    assert entry["page_id"] == "100"
    assert entry["restriction_check"] == ["direct", "ancestors", "space"]
    assert entry["restriction_source_ids"] == ["1069121551"]
    # Per-page space entry: include_raw=False — raw lives in spaces.json.
    assert entry["space"]["raw"] == {}
    assert entry["ancestor_restrictions"][0]["entity_title"] == "Summer Intern 2026"


# --- frontmatter access-owned enforcement ----------------------------------


def test_access_owned_fields_constant():
    assert ACCESS_OWNED_FIELDS == (
        "visibility_signal",
        "restriction_check",
        "restriction_source_ids",
    )


def test_build_frontmatter_overwrites_access_fields_regardless_of_existing(tmp_path: Path):
    """ADR-0007 §"Field ownership": access fields are puller-owned, NOT
    classifier-owned. An existing file's stale access values MUST be
    overwritten on re-sync — otherwise lifted-restriction pages stay
    flagged forever (and vice versa).
    """
    meta = PageMeta(
        page_id="1",
        title="x",
        source_url="https://x",
        space_key="ITSAI",
        space_name="AI",
        space_type="global",
        space_category="knowledge-bases",
        visibility_signal="no_read_restrictions_seen",
        restriction_check=["direct", "ancestors", "space"],
        restriction_source_ids=[],
    )
    existing = {
        # Stale values that would clobber the fresh classification if
        # preserved through merge_preserved_keys (must not).
        "visibility_signal": "restricted_inherited",
        "restriction_check": ["direct", "ancestors"],
        "restriction_source_ids": ["1069121551"],
        # A real classifier-owned field that SHOULD be preserved.
        "audience": "student",
    }
    fm = build_frontmatter(meta, body_markdown="body", existing_frontmatter=existing)
    assert fm["visibility_signal"] == "no_read_restrictions_seen"
    assert fm["restriction_check"] == ["direct", "ancestors", "space"]
    assert fm["restriction_source_ids"] == []
    assert fm["audience"] == "student"  # classifier-owned still preserved


# --- rewrite_access_fields (Step 2 frontmatter-only writer) ----------------


def test_rewrite_access_fields_changes_only_three_fields(tmp_path: Path):
    """Crucial Phase 1.1 invariant: the rewrite touches exactly the three
    access-owned fields and nothing else (other puller-owned + classifier-
    owned fields are preserved byte-for-byte where possible).
    """
    raw_root = tmp_path / "raw"
    (raw_root / "space").mkdir(parents=True)
    page_path = raw_root / "space" / "100 - Title.md"
    original_fm = {
        "page_id": "100",
        "title": "Title",
        "aliases": [],
        "source_url": "https://x",
        "visibility_signal": "no_read_restrictions_seen",
        "restriction_check": ["direct", "ancestors", "space"],
        "restriction_source_ids": [],
        "space_key": "ITSAI",
        "audience": "student",
        "doc_type": "how_to",
    }
    page_path.write_text(serialize(original_fm) + "\nbody", encoding="utf-8")

    record = PageClassification(
        page_id="100",
        title="Title",
        space_key="ITSAI",
        visibility_signal="restricted_inherited",
        restriction_check=["direct", "ancestors", "space"],
        restriction_source_ids=["1069121551"],
    )

    changed, err = rewrite_access_fields(raw_root, record)
    assert err is None
    assert changed is True

    text = page_path.read_text(encoding="utf-8")
    assert "visibility_signal: restricted_inherited" in text
    assert "restriction_source_ids:" in text
    assert "- '1069121551'" in text
    # Untouched fields preserved
    assert "audience: student" in text
    assert "doc_type: how_to" in text
    # Body preserved
    assert text.endswith("\nbody")


def test_rewrite_access_fields_idempotent(tmp_path: Path):
    """Re-running with the same values must be a no-op."""
    raw_root = tmp_path / "raw"
    (raw_root / "space").mkdir(parents=True)
    page_path = raw_root / "space" / "200 - X.md"
    fm = {
        "page_id": "200",
        "title": "X",
        "visibility_signal": "no_read_restrictions_seen",
        "restriction_check": ["direct", "ancestors", "space"],
        "restriction_source_ids": [],
    }
    page_path.write_text(serialize(fm) + "\nbody", encoding="utf-8")

    record = PageClassification(
        page_id="200",
        title="X",
        space_key="ITSAI",
        visibility_signal="no_read_restrictions_seen",
        restriction_check=["direct", "ancestors", "space"],
        restriction_source_ids=[],
    )
    changed, err = rewrite_access_fields(raw_root, record)
    assert err is None
    assert changed is False  # idempotent


def test_rewrite_access_fields_no_file_returns_error(tmp_path: Path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    record = PageClassification(page_id="999", title="missing", space_key="ITSAI")
    changed, err = rewrite_access_fields(raw_root, record)
    assert changed is False
    assert err is not None
    assert "no markdown file" in err
