"""Dead-letter routing per spec §4.3 + §6.

Conversion failures land in output/conversion-failures/<space>/<page-id>.json
with raw storage XML + traceback + warnings. Never silently dropped.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_failure(
    dead_letter_root: Path,
    space_key: str,
    page_id: str,
    title: str,
    storage_xml: str,
    error: BaseException,
    warnings: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    target_dir = dead_letter_root / space_key
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{page_id}.json"

    payload = {
        "page_id": page_id,
        "title": title,
        "space_key": space_key,
        "error": str(error),
        "error_type": type(error).__name__,
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        "warnings": warnings or [],
        "logged_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "storage_xml": storage_xml,
        **(extra or {}),
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def list_failures(dead_letter_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not dead_letter_root.exists():
        return out
    for f in dead_letter_root.rglob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "page_id": data.get("page_id"),
            "title": data.get("title"),
            "space_key": data.get("space_key"),
            "error": data.get("error"),
            "error_type": data.get("error_type"),
            "logged_at": data.get("logged_at"),
            "path": str(f),
        })
    return sorted(out, key=lambda r: r.get("logged_at", ""), reverse=True)


def load_failure(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def clear_failure(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
