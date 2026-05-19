"""Frontmatter build + serialize per spec §4.4.

Phase 1 (2026-05-19) — schema v2: observed-facts/classifier-output separation.

Field ownership:
  Puller-owned (always overwritten on sync):
    identity (page_id, title, source_url, space_*, ancestor_path),
    version + last_modified + contributors + content_hash + synced_at,
    labels + tags_original,
    word_count + char_count + token_estimate + attachment_count,
    days_since_modified + maintenance_signal (legacy pipeline-derived; keep for
        backward compat — reports should compute staleness from last_modified
        dynamically),
    visibility_signal + restriction_check + restricted_to (V1: descriptive
        best-effort metadata, NOT enforcement — see ADR-0006).

  Classifier-owned (read from target_path before write; preserved if present):
    audience, doc_type, tools, topics,
    tags_normalized (future — not yet written by anything),
    classifier (future block).
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# Frontmatter schema version — bump when the set of puller-owned fields changes
# in a way that requires re-ingesting existing pages. Used by SyncState's
# `should_skip_by_version` to force backfill when prior syncs predate the
# current schema. Phase 1 (2026-05-19) adds word_count, char_count,
# token_estimate, attachment_count, tags_original, visibility_signal,
# restriction_check, restricted_to → bumped to 2.
FRONTMATTER_SCHEMA_VERSION = 2


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


def count_words(body_markdown: str) -> int:
    return len([w for w in body_markdown.split() if w])


def token_estimate_from_chars(char_count: int) -> int:
    if char_count <= 0:
        return 0
    return math.ceil(char_count / 3.5)


# Classifier-owned keys read from existing frontmatter and preserved across
# re-syncs. Puller writes defaults only when the target file doesn't exist or
# the key is absent in the existing frontmatter.
CLASSIFIER_OWNED_KEYS: tuple[str, ...] = (
    "audience",
    "doc_type",
    "tools",
    "topics",
    "tags_normalized",
)


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
    attachment_count: int = 0
    visibility_signal: str = "accessible_to_sync_user"
    restriction_check: str = "not_checked"
    restricted_to: list[Any] = field(default_factory=list)


def find_existing_page_file(space_root: Path, page_id: str) -> Path | None:
    """Locate an existing `<page-id> - *.md` file under space_root.

    Survives Confluence renames and ancestor-path moves: the filename prefix
    is the page id (ADR-0001), so finding a page by id works regardless of
    title or location in the tree. Returns the first match; orphan files
    should be cleaned up by the caller after a successful write.
    """
    if not space_root.exists():
        return None
    matches = list(space_root.rglob(f"{page_id} - *.md"))
    return matches[0] if matches else None


def read_existing_frontmatter(target_path: Path) -> dict[str, Any] | None:
    """Parse the YAML frontmatter block from an existing markdown file.

    Returns the parsed dict, or None if the file is absent, has no frontmatter,
    or the frontmatter block is malformed. Used by the puller to preserve
    classifier-owned keys across re-syncs.
    """
    if not target_path.exists():
        return None
    try:
        text = target_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    yaml_text = text[4:end + 1]
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def merge_preserved_keys(
    new_fm: dict[str, Any],
    existing_fm: dict[str, Any] | None,
) -> dict[str, Any]:
    """Preserve classifier-owned keys from existing frontmatter into new_fm.

    Always preserves any classifier-owned key present in `existing_fm`,
    regardless of value (a classifier may legitimately emit null or []). New
    pages (existing_fm is None) keep the puller defaults.
    """
    if not existing_fm:
        return new_fm
    for key in CLASSIFIER_OWNED_KEYS:
        if key in existing_fm:
            new_fm[key] = existing_fm[key]
    if "classifier" in existing_fm:
        new_fm["classifier"] = existing_fm["classifier"]
    return new_fm


def build_frontmatter(
    meta: PageMeta,
    body_markdown: str,
    synced_at: str | None = None,
    last_sync_status: str = "ok",
    warnings: list[str] | None = None,
    existing_frontmatter: dict[str, Any] | None = None,
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

    char_count = len(body_markdown)
    word_count = count_words(body_markdown)
    token_estimate = token_estimate_from_chars(char_count)

    new_fm: dict[str, Any] = {
        "page_id": str(meta.page_id),
        "title": meta.title,
        "aliases": meta.aliases,
        "source_url": meta.source_url,
        # Visibility (V1 best-effort, see ADR-0006) — placed near source/provenance
        "visibility_signal": meta.visibility_signal,
        "restriction_check": meta.restriction_check,
        "restricted_to": meta.restricted_to,
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
        # Tags — `labels` kept for backward compat, `tags_original` is the
        # clearer name going forward. Both mirror the Confluence labels
        # endpoint at sync time.
        "labels": meta.labels,
        "tags_original": list(meta.labels),
        # Classifier-derived — default empty/null; overwritten by
        # merge_preserved_keys() below if existing_frontmatter has values.
        "audience": None,
        "doc_type": None,
        "tools": [],
        "topics": [],
        # Maintenance signals (legacy: maintenance_signal pipeline-derived; new
        # reports should compute staleness from last_modified directly)
        "days_since_modified": days_since,
        "maintenance_signal": maintenance_signal(days_since),
        # Size diagnostics — facts about the converted body, used by reports
        # to compute size buckets dynamically (thresholds not baked here).
        "word_count": word_count,
        "char_count": char_count,
        "token_estimate": token_estimate,
        "attachment_count": meta.attachment_count,
        # Build-time diagnostic — not a permanent field; useful at v1 for UI surfacing
        "conversion_warnings": warnings or [],
    }

    return merge_preserved_keys(new_fm, existing_frontmatter)


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
