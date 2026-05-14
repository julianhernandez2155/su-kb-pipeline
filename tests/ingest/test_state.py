"""Per-space .sync-state.json roundtrip + skip logic."""

from __future__ import annotations

from pathlib import Path

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
