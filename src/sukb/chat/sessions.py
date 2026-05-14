"""Persist Query-tab chat sessions to disk so they survive reloads and can be
referenced from the eval writeup (Step 3+).

Storage: one JSON file per session at `output/query-sessions/<session_id>.json`.
IDs are timestamp-prefixed for natural sort (newest first when reverse-sorted).
Path traversal is blocked by `_safe_id`.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import SyncConfig

SESSIONS_DIRNAME = "query-sessions"
_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def sessions_dir(config: SyncConfig) -> Path:
    return config.output_dir / SESSIONS_DIRNAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    """Sortable, unique session id: `20260513T193215-a1b2c3`."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:6]}"


def _safe_id(session_id: str) -> str:
    if not session_id or not _ID_RE.match(session_id):
        raise ValueError(f"invalid session_id: {session_id!r}")
    return session_id


def _derive_name(turns: list[dict[str, Any]]) -> str:
    """Default name = the first user question, truncated."""
    for t in turns:
        if t.get("role") == "user":
            text = (t.get("text") or "").strip()
            if text:
                return text[:80]
    return "Untitled chat"


def save_session(
    config: SyncConfig,
    turns: list[dict[str, Any]],
    name: str | None = None,
) -> dict[str, Any]:
    if not turns:
        raise ValueError("session must contain at least one turn")
    sd = sessions_dir(config)
    sd.mkdir(parents=True, exist_ok=True)
    sid = _new_id()
    final_name = (name or "").strip() or _derive_name(turns)
    user_turns = [t for t in turns if t.get("role") == "user"]
    total_cost = sum(
        float(t.get("cost_usd") or 0)
        for t in turns
        if t.get("role") == "assistant"
    )
    payload = {
        "session_id": sid,
        "name": final_name,
        "created_at": _now_iso(),
        "turns": turns,
        "turn_count": len(user_turns),
        "total_cost_usd": round(total_cost, 6),
    }
    (sd / f"{sid}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def list_sessions(config: SyncConfig) -> list[dict[str, Any]]:
    """Return session metadata (no turn bodies) — newest first."""
    sd = sessions_dir(config)
    if not sd.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(sd.glob("*.json"), reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            {
                "session_id": data.get("session_id"),
                "name": data.get("name"),
                "created_at": data.get("created_at"),
                "turn_count": data.get("turn_count"),
                "total_cost_usd": data.get("total_cost_usd"),
            }
        )
    return out


def load_session(config: SyncConfig, session_id: str) -> dict[str, Any]:
    path = sessions_dir(config) / f"{_safe_id(session_id)}.json"
    if not path.exists():
        raise FileNotFoundError(f"session {session_id} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def delete_session(config: SyncConfig, session_id: str) -> bool:
    path = sessions_dir(config) / f"{_safe_id(session_id)}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def rename_session(config: SyncConfig, session_id: str, new_name: str) -> dict[str, Any]:
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("new_name must be non-empty")
    path = sessions_dir(config) / f"{_safe_id(session_id)}.json"
    if not path.exists():
        raise FileNotFoundError(f"session {session_id} not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["name"] = new_name[:120]
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return data
