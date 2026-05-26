"""Restriction-fetching helpers for pages and folders (Phase 1.1).

Shared between the standalone probe (scripts/access_metadata_probe.py) and the
puller integration in Step 2.

Confluence Cloud exposes direct (non-inherited) restrictions on a page or
folder via the v1 endpoint:

    GET /wiki/rest/api/content/{id}/restriction/byOperation

Inherited restrictions are NOT returned by that endpoint — to detect inherited
restrictions we walk the ancestor chain ourselves and call this endpoint on
each ancestor. The ancestor cache lives on the caller (puller or probe) so
the same ancestor isn't re-fetched 34 times.

ADR-0006 stated V1 wouldn't call this endpoint at all. Phase 1.1 reverses that
specific stance — the endpoint IS called, but the result is still descriptive
(used to drive `visibility_signal`); enforcement still lives at the MCP read
path. See ADR-0007 (Step 1.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class RestrictionResult:
    """Normalized restriction info for one operation (read|update)."""

    has_restrictions: bool
    user_ids: list[str] = field(default_factory=list)
    group_ids: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityRestrictions:
    """Direct restrictions on a single entity (page or folder)."""

    entity_id: str
    entity_type: str  # "page" | "folder" | "unknown"
    entity_title: str = ""
    read: RestrictionResult = field(default_factory=lambda: RestrictionResult(False))
    update: RestrictionResult = field(default_factory=lambda: RestrictionResult(False))
    error: str | None = None


def v1_rest_base_from_v2(v2_base: str) -> str:
    """Derive the v1 REST base from the puller's v2 api_base.

    Examples
    --------
    >>> v1_rest_base_from_v2("https://api.atlassian.com/ex/confluence/abc/wiki/api/v2")
    'https://api.atlassian.com/ex/confluence/abc/wiki/rest/api'
    >>> v1_rest_base_from_v2("https://su-jsm.atlassian.net/wiki/api/v2")
    'https://su-jsm.atlassian.net/wiki/rest/api'
    """
    base = v2_base.rstrip("/")
    if base.endswith("/wiki/api/v2"):
        return base[: -len("/wiki/api/v2")] + "/wiki/rest/api"
    # Fallback: split on /wiki/ and rebuild
    host = base.split("/wiki/")[0]
    return host + "/wiki/rest/api"


def _normalize_restriction_bucket(operation_obj: dict[str, Any]) -> RestrictionResult:
    """Pull users + groups out of one `read` or `update` bucket.

    The v1 byOperation response shape (observed 2026-05-19):

        {
          "operation": "read",
          "restrictions": {
            "user":  {"results": [{"accountId": "...", ...}], "size": N, ...},
            "group": {"results": [{"id": "...", "name": "...", ...}], "size": M, ...}
          }
        }

    `size > 0` on either user or group → `has_restrictions = True`.
    """
    if not isinstance(operation_obj, dict):
        return RestrictionResult(has_restrictions=False, raw={})

    restrictions = operation_obj.get("restrictions") or {}
    user_obj = restrictions.get("user") or {}
    group_obj = restrictions.get("group") or {}

    user_results = user_obj.get("results") or []
    group_results = group_obj.get("results") or []

    # Prefer the API's explicit `size` field; fall back to len(results).
    user_size = user_obj.get("size")
    if not isinstance(user_size, int):
        user_size = len(user_results)
    group_size = group_obj.get("size")
    if not isinstance(group_size, int):
        group_size = len(group_results)

    user_ids = [str(u.get("accountId")) for u in user_results if u.get("accountId")]
    group_ids = [str(g.get("id")) for g in group_results if g.get("id")]

    return RestrictionResult(
        has_restrictions=bool(user_size or group_size),
        user_ids=user_ids,
        group_ids=group_ids,
        # Always store raw — empty `{}` is fine, but consistent shape across
        # entries means re-parse later doesn't need to special-case missing.
        raw=operation_obj,
    )


def parse_by_operation_response(payload: dict[str, Any]) -> tuple[RestrictionResult, RestrictionResult]:
    """Split a /restriction/byOperation response into (read, update) buckets.

    The shape is:
        {"read": {operation, restrictions: {...}},
         "update": {operation, restrictions: {...}}}

    Either bucket may be absent on entities the API hasn't materialized; we
    return RestrictionResult(False) in that case.
    """
    read = _normalize_restriction_bucket(payload.get("read") or {})
    update = _normalize_restriction_bucket(payload.get("update") or {})
    return read, update


def fetch_direct_restrictions(
    puller: Any,
    entity_id: str,
    entity_type: str = "unknown",
    entity_title: str = "",
) -> EntityRestrictions:
    """Fetch the direct (non-inherited) restrictions on one entity.

    `puller` provides the authenticated httpx client + rate-limited `_get`
    method. We use it instead of a bare client so the probe shares the
    puller's 429 backoff + 5 req/sec ceiling.

    On error (403, 404, network) we record the error and return a result
    where both buckets have `has_restrictions=False`. The classifier should
    treat any `error` as `unknown`, not as "clean".
    """
    v1_base = v1_rest_base_from_v2(puller.api_base)
    url = f"{v1_base}/content/{entity_id}/restriction/byOperation"
    try:
        payload = puller._get(url)
    except httpx.HTTPStatusError as e:
        return EntityRestrictions(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_title=entity_title,
            error=f"HTTP {e.response.status_code} on byOperation",
        )
    except httpx.HTTPError as e:
        return EntityRestrictions(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_title=entity_title,
            error=f"network error on byOperation: {e}",
        )

    read, update = parse_by_operation_response(payload)
    return EntityRestrictions(
        entity_id=entity_id,
        entity_type=entity_type,
        entity_title=entity_title,
        read=read,
        update=update,
    )
