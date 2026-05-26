"""Per-space .sync-state.json — drives skip-on-rerun + resumability (spec §5).

Keyed by page_id → {version, content_hash, synced_at, last_sync_status,
frontmatter_schema_version}. The schema version is what enables Phase 1's
backfill safety: when the puller's frontmatter schema bumps, prior state
entries record a stale `frontmatter_schema_version`, so `should_skip_by_version`
forces a re-ingest until every page has been rewritten under the current
schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .frontmatter import FRONTMATTER_SCHEMA_VERSION


@dataclass
class PageState:
    version: int
    content_hash: str
    synced_at: str
    last_sync_status: str  # ok | warning | failed | skipped
    # Frontmatter schema version that was current at the time of the last
    # successful sync. 0 means "legacy / unknown" — pre-Phase-1 state entries
    # carry this default and force a backfill re-ingest.
    frontmatter_schema_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "content_hash": self.content_hash,
            "synced_at": self.synced_at,
            "last_sync_status": self.last_sync_status,
            "frontmatter_schema_version": self.frontmatter_schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PageState:
        return cls(
            version=int(d.get("version", 0)),
            content_hash=str(d.get("content_hash", "")),
            synced_at=str(d.get("synced_at", "")),
            last_sync_status=str(d.get("last_sync_status", "")),
            frontmatter_schema_version=int(d.get("frontmatter_schema_version", 0)),
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
        """Return True only when a prior sync wrote this exact page (same
        version, same body hash) under the CURRENT frontmatter schema, AND
        the prior sync was successful.

        The schema check matters even here, where we already have a freshly
        converted body. Without it, a legacy state entry (Confluence version
        and content_hash unchanged since the last v1 sync) would let the
        belt-and-suspenders skip path bypass schema backfill: the file on
        disk would stay at v1 frontmatter while `state.record(...)` overwrote
        the state's schema_version to current. Codex G2 catch.

        The status check (matching `should_skip_by_version`) is belt-and-
        suspenders for the failed-record case: failed syncs typically record
        an empty `content_hash`, so the hash check above would already reject
        them, but a hypothetical failed record with a real hash should still
        force re-sync. Keeps the two skip helpers semantically parallel.
        """
        prior = self.pages.get(page_id)
        if not prior:
            return False
        if prior.version != version:
            return False
        if prior.content_hash != content_hash:
            return False
        if prior.frontmatter_schema_version != FRONTMATTER_SCHEMA_VERSION:
            return False
        return prior.last_sync_status in ("ok", "warning", "skipped")

    def should_skip_by_version(self, page_id: str, version: int) -> bool:
        """Return True if prior sync at this exact version succeeded AND was
        written under the current frontmatter schema.

        Enables metadata-first sync: skip body fetch + convert when Confluence
        reports an unchanged version. Safe because version bumps deterministically
        on body edits, so a matching version implies a matching body (and thus
        a matching content_hash by transitivity through our deterministic
        converter).

        The schema-version gate is the backfill safety check: when the puller's
        frontmatter schema bumps, any page whose state was recorded under an
        older schema must be re-ingested even though its Confluence version is
        unchanged. Otherwise the file on disk would never receive the new
        fields. Failed prior syncs always retry regardless of schema version.
        """
        prior = self.pages.get(page_id)
        if not prior:
            return False
        if prior.version != version:
            return False
        if prior.frontmatter_schema_version != FRONTMATTER_SCHEMA_VERSION:
            return False
        return prior.last_sync_status in ("ok", "warning", "skipped")

    def record(
        self,
        page_id: str,
        version: int,
        content_hash: str,
        synced_at: str,
        status: str,
        frontmatter_schema_version: int = FRONTMATTER_SCHEMA_VERSION,
    ) -> None:
        self.pages[page_id] = PageState(
            version=version,
            content_hash=content_hash,
            synced_at=synced_at,
            last_sync_status=status,
            frontmatter_schema_version=frontmatter_schema_version,
        )
