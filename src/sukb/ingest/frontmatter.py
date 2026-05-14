"""Frontmatter build + serialize per spec §4.4.

Classifier-derived fields (audience, doc_type, tools, topics) emit null/[] in
v1 — wire in v1.1.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml


# Windows-illegal char map per spec §4.2
_SANITIZE_MAP = {
    ":": "_",
    "/": "-",
    "\\": "-",
    "?": "",
    "*": "",
    '"': "'",
    "<": "(",
    ">": ")",
    "|": "-",
}


def sanitize_filename_title(title: str) -> str:
    out = title or "untitled"
    for ch, repl in _SANITIZE_MAP.items():
        out = out.replace(ch, repl)
    out = re.sub(r"\s+", " ", out).strip().strip(".")
    return out or "untitled"


def canonical_filename(page_id: str, title: str) -> str:
    return f"{page_id} - {sanitize_filename_title(title)}.md"


def content_hash(body_markdown: str) -> str:
    h = hashlib.sha256(body_markdown.encode("utf-8")).hexdigest()
    return f"sha256:{h}"


def maintenance_signal(days_since_modified: int) -> str:
    if days_since_modified < 90:
        return "fresh"
    if days_since_modified < 365:
        return "aging"
    return "stale"


@dataclass
class PageMeta:
    """All data needed to build frontmatter for one page."""

    page_id: str
    title: str
    source_url: str
    space_key: str
    space_name: str
    space_type: str  # 'global' | 'knowledge_base'
    space_category: str
    ancestor_path: list[str] = field(default_factory=list)
    last_modified: str = ""  # ISO 8601 UTC
    version: int = 1
    contributors: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


def build_frontmatter(
    meta: PageMeta,
    body_markdown: str,
    synced_at: str | None = None,
    last_sync_status: str = "ok",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    synced = synced_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if meta.last_modified:
        try:
            dt = datetime.fromisoformat(meta.last_modified.replace("Z", "+00:00"))
            now = datetime.fromisoformat(synced.replace("Z", "+00:00"))
            days_since = (now - dt).days
        except ValueError:
            days_since = 0
    else:
        days_since = 0

    return {
        "page_id": str(meta.page_id),
        "title": meta.title,
        "aliases": meta.aliases,
        "source_url": meta.source_url,
        "space_key": meta.space_key,
        "space_name": meta.space_name,
        "space_type": meta.space_type,
        "space_category": meta.space_category,
        "ancestor_path": meta.ancestor_path,
        "last_modified": meta.last_modified,
        "version": meta.version,
        "contributors": meta.contributors,
        "contributors_count": len(meta.contributors),
        "content_hash": content_hash(body_markdown),
        "synced_at": synced,
        "last_sync_status": last_sync_status,
        "labels": meta.labels,
        # Classifier-derived — v1.1 will fill these
        "audience": None,
        "doc_type": None,
        "tools": [],
        "topics": [],
        # Maintenance signals
        "days_since_modified": days_since,
        "maintenance_signal": maintenance_signal(days_since),
        # Build-time diagnostic — not a permanent field; useful at v1 for UI surfacing
        "conversion_warnings": warnings or [],
    }


def serialize(fm: dict[str, Any]) -> str:
    """Emit the YAML frontmatter block (with --- delimiters + trailing newline)."""
    body = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{body}---\n"


# Identity / provenance fields that must be non-empty. Classifier-derived
# fields (audience, doc_type, tools, topics) are intentionally not required —
# v1 emits them as null/[] until v1.1 wires Haiku.
REQUIRED_FIELDS = (
    "page_id",
    "title",
    "source_url",
    "space_key",
    "space_name",
    "space_type",
    "space_category",
    # Sync-state load-bearing — without these, downstream content_hash skip
    # logic and maintenance-signal filtering break silently.
    "last_modified",
    "version",
    "content_hash",
    "synced_at",
    "last_sync_status",
)


def validate(fm: dict[str, Any]) -> list[str]:
    """Return a list of missing-required-field errors. Empty = valid.

    A field is "missing" if it's None, an empty string, or absent. `0` is
    accepted (e.g., version 0 would be a legit value if it ever appeared).
    """
    return [
        f for f in REQUIRED_FIELDS
        if f not in fm or fm[f] is None or fm[f] == ""
    ]
