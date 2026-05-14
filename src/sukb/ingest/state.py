"""Per-space .sync-state.json — drives skip-on-rerun + resumability (spec §5).

Keyed by page_id → {version, content_hash, synced_at, last_sync_status}.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PageState:
    version: int
    content_hash: str
    synced_at: str
    last_sync_status: str  # ok | warning | failed | skipped

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "content_hash": self.content_hash,
            "synced_at": self.synced_at,
            "last_sync_status": self.last_sync_status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PageState:
        return cls(
            version=int(d.get("version", 0)),
            content_hash=str(d.get("content_hash", "")),
            synced_at=str(d.get("synced_at", "")),
            last_sync_status=str(d.get("last_sync_status", "")),
        )


@dataclass
class SyncState:
    path: Path
    pages: dict[str, PageState] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> SyncState:
        if not path.exists():
            return cls(path=path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        pages = {pid: PageState.from_dict(p) for pid, p in raw.get("pages", {}).items()}
        return cls(path=path, pages=pages)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"pages": {pid: p.to_dict() for pid, p in self.pages.items()}}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def should_skip(self, page_id: str, version: int, content_hash: str) -> bool:
        prior = self.pages.get(page_id)
        if not prior:
            return False
        return prior.version == version and prior.content_hash == content_hash

    def record(self, page_id: str, version: int, content_hash: str, synced_at: str, status: str) -> None:
        self.pages[page_id] = PageState(
            version=version,
            content_hash=content_hash,
            synced_at=synced_at,
            last_sync_status=status,
        )
