"""Per-space .sync-state.json roundtrip + skip logic."""

from __future__ import annotations

import json
from pathlib import Path

from sukb.ingest.frontmatter import FRONTMATTER_SCHEMA_VERSION
from sukb.ingest.state import SyncState


def test_state_roundtrip(tmp_path: Path):
    p = tmp_path / "sync-state.json"
    state = SyncState.load(p)
    assert state.pages == {}
    state.record("123", version=2, content_hash="sha256:abc", synced_at="2026-05-13T10:00:00Z", status="ok")
    state.save()

    state2 = SyncState.load(p)
    assert "123" in state2.pages
    assert state2.pages["123"].version == 2
    assert state2.pages["123"].content_hash == "sha256:abc"


def test_should_skip_logic(tmp_path: Path):
    p = tmp_path / "sync-state.json"
    state = SyncState.load(p)
    state.record("123", 2, "sha256:abc", "t", "ok")
    # Same version + hash → skip
    assert state.should_skip("123", 2, "sha256:abc") is True
    # Version bumped → don't skip
    assert state.should_skip("123", 3, "sha256:abc") is False
    # Hash changed → don't skip
    assert state.should_skip("123", 2, "sha256:def") is False
    # Unknown page → don't skip
    assert state.should_skip("999", 1, "x") is False


def test_should_skip_by_version_match_succeeds(tmp_path: Path):
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "ok")
    assert state.should_skip_by_version("123", 5) is True


def test_should_skip_by_version_warning_status_still_skips(tmp_path: Path):
    """A page that synced with conversion warnings is still a valid skip target."""
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "warning")
    assert state.should_skip_by_version("123", 5) is True


def test_should_skip_by_version_skipped_status_still_skips(tmp_path: Path):
    """Previously-skipped pages must remain skippable on subsequent runs."""
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "skipped")
    assert state.should_skip_by_version("123", 5) is True


def test_should_skip_by_version_failed_status_forces_retry(tmp_path: Path):
    """Failed prior syncs must always re-fetch, even if version matches."""
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "", "t", "failed")
    assert state.should_skip_by_version("123", 5) is False


def test_should_skip_by_version_bump_forces_resync(tmp_path: Path):
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "ok")
    assert state.should_skip_by_version("123", 6) is False


def test_should_skip_by_version_unknown_page(tmp_path: Path):
    state = SyncState.load(tmp_path / "s.json")
    assert state.should_skip_by_version("999", 1) is False


# --- Phase 1 G2: schema-version gate forces backfill ------------------------


def test_record_defaults_to_current_schema_version(tmp_path: Path):
    """A fresh record() (no explicit schema kwarg) writes the current
    schema version, so a same-process re-sync skips correctly."""
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "ok")
    assert state.pages["123"].frontmatter_schema_version == FRONTMATTER_SCHEMA_VERSION
    assert state.should_skip_by_version("123", 5) is True


def test_schema_version_mismatch_forces_backfill(tmp_path: Path):
    """The blocker fix: a page recorded under an OLDER schema MUST re-ingest
    even though its Confluence version is unchanged. Otherwise the new
    frontmatter fields never get populated on disk.
    """
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "ok", frontmatter_schema_version=0)
    assert state.should_skip_by_version("123", 5) is False
    # Even bumping to schema 1 (intermediate, hypothetical) must still force
    # re-sync — only an exact match with the current version allows skip.
    state.record("123", 5, "sha256:abc", "t", "ok", frontmatter_schema_version=1)
    assert state.should_skip_by_version("123", 5) is False


def test_legacy_state_json_loads_with_schema_v0(tmp_path: Path):
    """Existing state files (written before Phase 1) lack the
    frontmatter_schema_version field. Loading them must default to 0 so the
    first re-sync after the upgrade triggers a backfill.
    """
    p = tmp_path / "s.json"
    p.write_text(
        json.dumps({
            "pages": {
                "123": {
                    "version": 5,
                    "content_hash": "sha256:abc",
                    "synced_at": "2026-05-13T10:00:00Z",
                    "last_sync_status": "ok",
                    # frontmatter_schema_version intentionally absent
                }
            }
        }),
        encoding="utf-8",
    )
    state = SyncState.load(p)
    assert state.pages["123"].frontmatter_schema_version == 0
    # Backfill: same Confluence version, but stale schema → no skip
    assert state.should_skip_by_version("123", 5) is False


def test_state_json_roundtrip_persists_schema_version(tmp_path: Path):
    p = tmp_path / "s.json"
    state = SyncState.load(p)
    state.record("123", 5, "sha256:abc", "t", "ok")
    state.save()

    state2 = SyncState.load(p)
    assert state2.pages["123"].frontmatter_schema_version == FRONTMATTER_SCHEMA_VERSION


def test_state_save_writes_schema_version_to_disk(tmp_path: Path):
    """Belt-and-suspenders: explicit JSON check that the field hits disk."""
    p = tmp_path / "s.json"
    state = SyncState.load(p)
    state.record("123", 5, "sha256:abc", "t", "ok")
    state.save()
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["pages"]["123"]["frontmatter_schema_version"] == FRONTMATTER_SCHEMA_VERSION


# --- Phase 1 G2 round 2: schema gate now applies to should_skip too ---------


def test_should_skip_schema_mismatch_forces_rewrite_even_with_matching_hash(tmp_path: Path):
    """Codex G2 round-2 blocker fix: even when Confluence version AND content
    hash match a prior sync, a legacy schema_version entry MUST NOT skip the
    write. Otherwise the belt-and-suspenders hash skip bypasses backfill —
    the file on disk would stay at v1 frontmatter while `record()` quietly
    upgraded the state's schema_version to current, masking the migration.
    """
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "ok", frontmatter_schema_version=0)
    # Same version, same hash, but legacy schema → must not skip.
    assert state.should_skip("123", 5, "sha256:abc") is False


def test_should_skip_passes_when_everything_matches_at_current_schema(tmp_path: Path):
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "ok")  # default schema = CURRENT
    assert state.should_skip("123", 5, "sha256:abc") is True


def test_should_skip_refuses_failed_status_even_with_matching_hash(tmp_path: Path):
    """Parallelism with should_skip_by_version: a hypothetical failed record
    that somehow carries a real content_hash must still force a re-sync.
    Belt-and-suspenders — failed records normally have empty hashes anyway.
    """
    state = SyncState.load(tmp_path / "s.json")
    state.record("123", 5, "sha256:abc", "t", "failed")
    assert state.should_skip("123", 5, "sha256:abc") is False
