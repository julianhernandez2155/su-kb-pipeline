"""Unit tests for puller module-level helper functions.

Phase 1 G2 (2026-05-19) — covers:
- `_extract_storage_body`: distinguishes API anomaly (missing keys → raise)
  from legitimately empty page (value: "" → return "").
- `_attempt_orphan_cleanup`: deletes a renamed page's prior path; returns a
  warning string on failure so the caller can escalate page status to
  "warning" and rewrite frontmatter honestly (Codex G2 round-2 catch).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sukb.ingest.puller import _attempt_orphan_cleanup, _extract_storage_body


def test_extract_storage_body_happy_path():
    response = {"body": {"storage": {"value": "<p>hello</p>"}}}
    assert _extract_storage_body(response) == "<p>hello</p>"


def test_extract_storage_body_legitimately_empty_value():
    """Empty string is allowed — some Confluence pages legitimately have no body."""
    response = {"body": {"storage": {"value": ""}}}
    assert _extract_storage_body(response) == ""


def test_extract_storage_body_raises_on_missing_body():
    with pytest.raises(ValueError, match="body.storage"):
        _extract_storage_body({})


def test_extract_storage_body_raises_on_non_dict_body():
    with pytest.raises(ValueError, match="body.storage"):
        _extract_storage_body({"body": "not a dict"})


def test_extract_storage_body_raises_on_missing_storage_key():
    with pytest.raises(ValueError, match="body.storage"):
        _extract_storage_body({"body": {}})


def test_extract_storage_body_raises_on_non_dict_storage():
    with pytest.raises(ValueError, match="body.storage.value"):
        _extract_storage_body({"body": {"storage": "string-not-dict"}})


def test_extract_storage_body_raises_on_missing_value_key():
    with pytest.raises(ValueError, match="body.storage.value"):
        _extract_storage_body({"body": {"storage": {}}})


def test_extract_storage_body_coerces_non_string_value_to_empty():
    """If `value` is null (shouldn't happen, but be safe), return "" rather
    than blowing up downstream conversion with a non-string body.
    """
    response = {"body": {"storage": {"value": None}}}
    assert _extract_storage_body(response) == ""


# --- _attempt_orphan_cleanup ------------------------------------------------


def test_attempt_orphan_cleanup_noop_when_existing_is_none(tmp_path: Path):
    target = tmp_path / "new.md"
    target.write_text("body", encoding="utf-8")
    assert _attempt_orphan_cleanup(None, target) is None


def test_attempt_orphan_cleanup_noop_when_paths_equal(tmp_path: Path):
    """Same file on both sides (page not renamed) → no deletion attempted."""
    same = tmp_path / "same.md"
    same.write_text("body", encoding="utf-8")
    assert _attempt_orphan_cleanup(same, same) is None
    # File must still exist after a no-op call
    assert same.exists()


def test_attempt_orphan_cleanup_deletes_orphan(tmp_path: Path):
    orphan = tmp_path / "old.md"
    target = tmp_path / "new.md"
    orphan.write_text("old body", encoding="utf-8")
    target.write_text("new body", encoding="utf-8")
    assert _attempt_orphan_cleanup(orphan, target) is None
    assert not orphan.exists()
    assert target.exists()


def test_attempt_orphan_cleanup_returns_warning_on_oserror(tmp_path: Path):
    """When unlink raises (file lock, permission), return a warning string so
    the caller can escalate status + rewrite frontmatter."""
    target = tmp_path / "new.md"
    target.write_text("new body", encoding="utf-8")
    # Use a directory as the orphan path — `Path.unlink()` on a directory
    # raises OSError (IsADirectoryError on Linux, PermissionError on Windows).
    fake_orphan_dir = tmp_path / "old-dir"
    fake_orphan_dir.mkdir()
    warning = _attempt_orphan_cleanup(fake_orphan_dir, target)
    assert warning is not None
    assert "orphan cleanup failed" in warning
    # The directory should still exist (unlink didn't succeed)
    assert fake_orphan_dir.exists()
