"""Per-page access classification (Phase 1.1 Step 2, ADR-0007).

Brings together direct + ancestor + space restriction checks into a single
classification record. Both the standalone probe and the puller import the
same `classify_visibility`, `AncestorRestrictionCache`, and JSON serializers
so the two surfaces never drift apart.

Conservatism rules (tightened 2026-05-20 per review):
  - direct or ancestor errors → `unknown`
  - space.default_audience == `restricted_space` → `space_restricted`
  - space.default_audience == `unknown` (positive-ID failed AND not in the
    operator-declared allowlist) → `space_restricted`. The MCP filter
    treats `space_restricted` as restricted; pages in unidentified-audience
    spaces are not queryable.
  - direct restrictions present → `restricted_direct`
  - any ancestor has direct restrictions → `restricted_inherited`
  - everything clean → `no_read_restrictions_seen`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

import yaml

from .frontmatter import (
    ACCESS_OWNED_FIELDS,
    find_existing_page_file,
    serialize,
)
from .restrictions import EntityRestrictions, fetch_direct_restrictions
from .spaces import SpaceAudience


@dataclass
class PageClassification:
    """In-memory record for one page; serialized to the access manifest."""

    page_id: str
    title: str
    space_key: str
    visibility_signal: str = "unknown"
    restriction_check: list[str] = field(default_factory=list)
    restriction_source_ids: list[str] = field(default_factory=list)
    checked_at: str = ""
    checked_with_account_id: str = ""
    direct: EntityRestrictions | None = None
    ancestors: list[EntityRestrictions] = field(default_factory=list)
    space: SpaceAudience | None = None
    errors: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_visibility(
    direct: EntityRestrictions | None,
    ancestors: list[EntityRestrictions] | None,
    space: SpaceAudience | None,
) -> tuple[str, list[str], list[str]]:
    """Apply the priority classifier (ADR-0007 §"Classifier").

    Returns ``(visibility_signal, restriction_check_layers, restriction_source_ids)``.

    `restriction_check_layers` reflects which layers actually completed
    successfully. The page classifier is conservative: an `unknown` space
    audience (positive-ID failed, no allowlist override) is treated as
    `space_restricted` so the MCP filter excludes the page.
    """
    layers: list[str] = []
    sources: list[str] = []

    direct_checked = direct is not None and not direct.error
    ancestors_checked = ancestors is not None and all(a.error is None for a in ancestors)
    space_checked = (
        space is not None
        and space.default_audience != "skipped"
        and space.error is None
    )

    if direct_checked:
        layers.append("direct")
    if ancestors_checked:
        layers.append("ancestors")
    if space_checked:
        layers.append("space")

    if direct is None or direct.error or ancestors is None or any(a.error for a in ancestors):
        return "unknown", layers, sources

    if space is not None and space.default_audience == "restricted_space":
        sources.append(f"space:{space.key}")
        return "space_restricted", layers, sources

    # Tightened 2026-05-20: an `unknown` space audience (positive-ID failed,
    # no allowlist override) is treated as restricted at the page level. A
    # `skipped` space audience (endpoint 403/network error) is NOT treated
    # this way — operator hasn't refused us, the endpoint just isn't
    # accessible, and direct + ancestors are still load-bearing.
    if space is not None and space.default_audience == "unknown":
        sources.append(f"space:{space.key}")
        return "space_restricted", layers, sources

    if direct.read.has_restrictions:
        sources.append(str(direct.entity_id))
        return "restricted_direct", layers, sources

    inherited = [a for a in ancestors if a.read.has_restrictions]
    if inherited:
        sources.extend(str(a.entity_id) for a in inherited)
        return "restricted_inherited", layers, sources

    return "no_read_restrictions_seen", layers, sources


class AncestorRestrictionCache:
    """Per-ancestor restriction lookups, scoped to one orchestrator run.

    A 34-page corpus with a shared 'AI Workspace' ancestor should make one
    restriction call for that ancestor, not 34. The puller passes the same
    instance to every per-page classification call within one sync.
    """

    def __init__(self, puller: Any):
        self.puller = puller
        self._cache: dict[str, EntityRestrictions] = {}

    def get(self, entity_id: str, entity_type: str, entity_title: str) -> EntityRestrictions:
        if entity_id in self._cache:
            cached = self._cache[entity_id]
            if entity_title and not cached.entity_title:
                cached.entity_title = entity_title
            return cached
        result = fetch_direct_restrictions(self.puller, entity_id, entity_type, entity_title)
        self._cache[entity_id] = result
        return result


def restriction_to_jsonable(r: EntityRestrictions | None) -> dict[str, Any]:
    """Render an EntityRestrictions as the dict shape used in the manifest.

    Always includes `raw` per operation bucket — `{}` is fine, the point is
    shape consistency so a re-parse pass doesn't need branches.
    """
    if r is None:
        return {}
    return {
        "entity_id": r.entity_id,
        "entity_type": r.entity_type,
        "entity_title": r.entity_title,
        "read": {
            "has_restrictions": r.read.has_restrictions,
            "user_ids": list(r.read.user_ids),
            "group_ids": list(r.read.group_ids),
            "raw": r.read.raw,
        },
        "update": {
            "has_restrictions": r.update.has_restrictions,
            "user_ids": list(r.update.user_ids),
            "group_ids": list(r.update.group_ids),
            "raw": r.update.raw,
        },
        "error": r.error,
    }


def space_to_jsonable(s: SpaceAudience | None, *, include_raw: bool = True) -> dict[str, Any] | None:
    """Render a SpaceAudience.

    `include_raw=True` for the spaces.json cache (full paginated picture).
    `include_raw=False` for per-page manifest entries — full raw lives in
    spaces.json, keyed by space_key; manifest entries link by key.
    """
    if s is None:
        return None
    return {
        "key": s.key,
        "name": s.name,
        "homepage_id": s.homepage_id,
        "checked_at": s.checked_at,
        "default_audience": s.default_audience,
        "raw": s.raw if include_raw else {},
        "error": s.error,
    }


def classification_to_manifest_entry(r: PageClassification) -> dict[str, Any]:
    """Serialize one PageClassification as a manifest JSON entry."""
    return {
        "page_id": r.page_id,
        "title": r.title,
        "space_key": r.space_key,
        "visibility_signal": r.visibility_signal,
        "restriction_check": list(r.restriction_check),
        "restriction_source_ids": list(r.restriction_source_ids),
        "checked_at": r.checked_at,
        "checked_with_account_id": r.checked_with_account_id,
        "direct_restrictions": restriction_to_jsonable(r.direct),
        "ancestor_restrictions": [restriction_to_jsonable(a) for a in r.ancestors],
        "space": space_to_jsonable(r.space, include_raw=False),
        "errors": list(r.errors),
    }


def rewrite_access_fields(
    raw_root: Path,
    record: PageClassification,
) -> tuple[bool, str | None]:
    """Overwrite only ACCESS_OWNED_FIELDS on the page's markdown frontmatter.

    Used by:
      - The probe, for one-shot rewrites on existing pages.
      - The puller, when version-matched short-circuit skips body fetch but
        access classification still needs to refresh in-place.

    Returns ``(changed, error)``. ``changed=False`` with ``error=None`` means
    the values already matched AND were positioned next to each other (the
    file was already in canonical layout). ``error is not None`` means the
    file couldn't be located or parsed.

    Strict scope: only the three fields in ACCESS_OWNED_FIELDS are touched.
    Other puller-owned fields (`restricted_to` from the v2 schema, e.g.)
    are left untouched here — the next full sync writes the v3 schema.
    """
    page_path = find_existing_page_file(raw_root, record.page_id)
    if page_path is None:
        return False, f"no markdown file for page_id={record.page_id}"
    try:
        text = page_path.read_text(encoding="utf-8")
    except OSError as e:
        return False, f"read failed: {e}"
    if not text.startswith("---\n"):
        return False, "no frontmatter block"
    end = text.find("\n---\n", 4)
    if end == -1:
        return False, "unterminated frontmatter block"
    yaml_text = text[4:end + 1]
    rest = text[end + 5:]
    try:
        parsed = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as e:
        return False, f"yaml parse failed: {e}"
    if not isinstance(parsed, dict):
        return False, "frontmatter is not a mapping"

    new_values = {
        "visibility_signal": record.visibility_signal,
        "restriction_check": list(record.restriction_check),
        "restriction_source_ids": list(record.restriction_source_ids),
    }
    values_match = all(parsed.get(k) == v for k, v in new_values.items())
    keys = list(parsed.keys())
    canonical_layout = (
        "restriction_check" in keys
        and "restriction_source_ids" in keys
        and keys.index("restriction_source_ids") == keys.index("restriction_check") + 1
    )
    if values_match and canonical_layout:
        return False, None

    rebuilt: dict[str, Any] = {}
    inserted_sources = False
    for key, value in parsed.items():
        if key in new_values:
            rebuilt[key] = new_values[key]
            if key == "restriction_check":
                rebuilt["restriction_source_ids"] = new_values["restriction_source_ids"]
                inserted_sources = True
        elif key == "restriction_source_ids" and inserted_sources:
            continue  # already inserted next to restriction_check
        else:
            rebuilt[key] = value
    for k, v in new_values.items():
        if k not in rebuilt:
            rebuilt[k] = v

    new_text = serialize(rebuilt) + rest
    try:
        tmp = page_path.with_suffix(page_path.suffix + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(page_path)
    except OSError as e:
        return False, f"write failed: {e}"
    return True, None
