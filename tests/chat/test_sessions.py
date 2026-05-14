"""Unit tests for sukb.chat.sessions — chat persistence for the Query tab."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from sukb.chat import sessions as sm


def _cfg(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(output_dir=tmp_path / "output")


def _sample_turns(question: str = "How long does Claude retain chats?") -> list[dict]:
    return [
        {"role": "user", "text": question, "mode": "raw", "timestamp": "2026-05-13T19:00:00Z"},
        {
            "role": "assistant",
            "text": "Claude retains chats for 2 years [[488210484]].",
            "mode": "raw",
            "citations": [{"page_id": "488210484", "title": "Claude FAQ", "source_url": "http://x"}],
            "context_used": {"raw_pages": ["488210484"], "wiki_pages": []},
            "cost_usd": 0.0134,
            "latency_ms": 4427,
            "raw_pages_loaded": 29,
            "wiki_pages_loaded": 0,
            "timestamp": "2026-05-13T19:00:05Z",
        },
    ]


# --- save / load roundtrip --------------------------------------------------


def test_save_session_creates_file_with_metadata(tmp_path):
    cfg = _cfg(tmp_path)
    result = sm.save_session(cfg, _sample_turns())

    assert result["session_id"]
    assert result["name"] == "How long does Claude retain chats?"
    assert result["turn_count"] == 1  # one user turn
    assert result["total_cost_usd"] == pytest.approx(0.0134)
    # File should be on disk under output/query-sessions/<id>.json
    expected = sm.sessions_dir(cfg) / f"{result['session_id']}.json"
    assert expected.exists()


def test_save_session_uses_explicit_name(tmp_path):
    cfg = _cfg(tmp_path)
    result = sm.save_session(cfg, _sample_turns(), name="q02 baseline raw")
    assert result["name"] == "q02 baseline raw"


def test_save_session_truncates_long_auto_name(tmp_path):
    cfg = _cfg(tmp_path)
    long_q = "x" * 200
    result = sm.save_session(cfg, [{"role": "user", "text": long_q}])
    assert len(result["name"]) == 80


def test_save_session_rejects_empty_turns(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(ValueError):
        sm.save_session(cfg, [])


def test_load_session_returns_full_payload(tmp_path):
    cfg = _cfg(tmp_path)
    saved = sm.save_session(cfg, _sample_turns())
    loaded = sm.load_session(cfg, saved["session_id"])
    assert loaded["session_id"] == saved["session_id"]
    assert loaded["turns"] == saved["turns"]
    assert loaded["name"] == saved["name"]


def test_load_session_raises_on_missing(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(FileNotFoundError):
        sm.load_session(cfg, "20260513T190000-deadbe")


# --- listing ----------------------------------------------------------------


def test_list_sessions_empty(tmp_path):
    assert sm.list_sessions(_cfg(tmp_path)) == []


def test_list_sessions_newest_first(tmp_path):
    cfg = _cfg(tmp_path)
    first = sm.save_session(cfg, _sample_turns("first?"))
    # Sleep just past one second so the timestamp prefix in the ID differs.
    time.sleep(1.05)
    second = sm.save_session(cfg, _sample_turns("second?"))
    listed = sm.list_sessions(cfg)
    assert [s["session_id"] for s in listed] == [second["session_id"], first["session_id"]]
    # Metadata-only — no turn bodies in the list view.
    assert "turns" not in listed[0]
    assert listed[0]["name"] == "second?"


def test_list_sessions_skips_corrupted_files(tmp_path):
    cfg = _cfg(tmp_path)
    sm.save_session(cfg, _sample_turns())
    bad = sm.sessions_dir(cfg) / "garbage.json"
    bad.write_text("not json {{{", encoding="utf-8")
    listed = sm.list_sessions(cfg)
    assert len(listed) == 1  # corrupted file was skipped, not crashed on


# --- delete -----------------------------------------------------------------


def test_delete_session_removes_file(tmp_path):
    cfg = _cfg(tmp_path)
    saved = sm.save_session(cfg, _sample_turns())
    assert sm.delete_session(cfg, saved["session_id"]) is True
    assert not (sm.sessions_dir(cfg) / f"{saved['session_id']}.json").exists()
    assert sm.list_sessions(cfg) == []


def test_delete_session_missing_returns_false(tmp_path):
    cfg = _cfg(tmp_path)
    assert sm.delete_session(cfg, "20260513T000000-deadbe") is False


# --- rename -----------------------------------------------------------------


def test_rename_session_updates_name_only(tmp_path):
    cfg = _cfg(tmp_path)
    saved = sm.save_session(cfg, _sample_turns())
    renamed = sm.rename_session(cfg, saved["session_id"], "q01 baseline raw mode")
    assert renamed["name"] == "q01 baseline raw mode"
    assert renamed["turns"] == saved["turns"]
    assert renamed["session_id"] == saved["session_id"]


def test_rename_session_rejects_empty(tmp_path):
    cfg = _cfg(tmp_path)
    saved = sm.save_session(cfg, _sample_turns())
    with pytest.raises(ValueError):
        sm.rename_session(cfg, saved["session_id"], "   ")


# --- path traversal guard --------------------------------------------------


@pytest.mark.parametrize("bad_id", ["../etc/passwd", "..\\windows\\system32", "id with spaces", "id/with/slash", ""])
def test_safe_id_rejects_traversal_and_garbage(tmp_path, bad_id):
    cfg = _cfg(tmp_path)
    with pytest.raises(ValueError):
        sm.load_session(cfg, bad_id)
    with pytest.raises(ValueError):
        sm.delete_session(cfg, bad_id)
