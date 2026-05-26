"""Space-level permission helper (Phase 1.1, tightened 2026-05-20).

Discovers whether a space is broadly accessible to the SU community vs
restricted to a narrow allowlist. Shared between the probe and the puller.

Classifier (tightened per 2026-05-20 review):

1. Positive identification — look for a `role:ANONYMOUS` principal with
   `read/space` operation. In Atlassian Cloud, ANONYMOUS marks a space as
   "anyone the site lets in can read." SU's tenant blocks anonymous at the
   site level, so in practice this means "any authenticated SU user."
   Empirically present on ITSAI; expected to be the standard SU pattern
   for knowledge-base spaces.
2. Config allowlist fallback — `broadly_accessible_spaces` in sync_config.yaml
   lets the operator mark a space as `su_community` even if the positive-ID
   signal is missing. Use sparingly; document the rationale per space.
3. Otherwise — `unknown`. The page-level classifier then treats pages in
   `unknown`-audience spaces as `space_restricted` (filtered by the MCP).

If the endpoint 403s or errors, the space is `skipped` — page-level
classification still works from direct + ancestor checks alone. `skipped`
is treated separately from `unknown`: the operator hasn't refused us, the
endpoint just isn't accessible, and the conservative-by-default page
classifier may still pass pages if direct + ancestors are clean.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx


# default_audience vocabulary (per docs/archive/phase-1.1-plan-2026-05-19.md §"Space cache"):
#   su_community     — endpoint responded, space is open to general SU audience
#   restricted_space — endpoint responded, space is locked to a narrow allowlist
#   anonymous        — endpoint responded, space is world-readable (unlikely at SU)
#   unknown          — endpoint responded with a shape we don't recognize
#   skipped          — endpoint was deliberately not attempted (e.g., 403)
DEFAULT_AUDIENCE_VALUES = (
    "su_community",
    "restricted_space",
    "anonymous",
    "unknown",
    "skipped",
)


@dataclass
class SpaceAudience:
    """Per-space audience snapshot persisted in spaces.json."""

    key: str
    name: str = ""
    homepage_id: str = ""
    checked_at: str = ""
    default_audience: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def has_anonymous_read_space(permissions_payload: dict[str, Any]) -> bool:
    """True iff the permissions list contains a `role:ANONYMOUS` principal
    with `read/space` operation.

    Confluence Cloud uses this to mark a space as readable by anyone the
    site itself lets in. On SU's tenant (which blocks anonymous at the site
    level), this is the positive signal for "any authenticated SU user can
    read this space."
    """
    results = permissions_payload.get("results")
    if not isinstance(results, list):
        return False
    for r in results:
        principal = r.get("principal") or {}
        op = r.get("operation") or {}
        if (
            principal.get("type") == "role"
            and str(principal.get("id", "")).upper() == "ANONYMOUS"
            and op.get("key") == "read"
            and op.get("targetType") == "space"
        ):
            return True
    return False


def classify_space_audience(
    permissions_payload: dict[str, Any],
    *,
    space_key: str = "",
    broadly_accessible_spaces: list[str] | None = None,
) -> str:
    """Given a (possibly paginated-aggregated) permissions payload, classify
    the space's default audience.

    Priority order:
      1. Allowlist override — operator-declared `su_community`.
      2. Positive-ID — `role:ANONYMOUS` read/space marker.
      3. Otherwise — `unknown` (page classifier will treat as space_restricted).

    Returns one of DEFAULT_AUDIENCE_VALUES (other than "skipped", which is
    "didn't attempt" — set by the caller, not by the classifier).
    """
    allowlist = broadly_accessible_spaces or []
    if space_key and space_key in allowlist:
        return "su_community"

    results = permissions_payload.get("results")
    if not isinstance(results, list):
        return "unknown"
    if not results:
        return "unknown"

    if has_anonymous_read_space(permissions_payload):
        return "su_community"

    return "unknown"


def fetch_space_audience(
    puller: Any,
    space_key: str,
    space_id: str,
    space_name: str = "",
    homepage_id: str = "",
    broadly_accessible_spaces: list[str] | None = None,
) -> SpaceAudience:
    """Attempt one space-permissions call; on 403/error, mark `skipped`.

    Endpoint: GET /spaces/{space-id}/permissions (v2). The sync token may
    lack scope — that's a known limitation, not a failure. The probe's
    summary surfaces skipped spaces in plain text.
    """
    base = puller.api_base  # v2 base, gateway-resolved
    url = f"{base}/spaces/{space_id}/permissions"

    # Permissions are paginated. Follow `_links.next` so the cached raw
    # reflects the full audience picture (not just the first page) — even
    # though Phase 1.1's classifier doesn't distinguish narrow allowlists
    # within the results, the full data is what re-classification later
    # will read from spaces.json.
    all_results: list[dict[str, Any]] = []
    next_url: str | None = url
    last_payload: dict[str, Any] = {}
    pages_fetched = 0
    try:
        while next_url and pages_fetched < 20:  # hard cap to avoid runaway pagination
            payload = puller._get(next_url)
            last_payload = payload
            page_results = payload.get("results") or []
            if isinstance(page_results, list):
                all_results.extend(page_results)
            pages_fetched += 1
            next_link = (payload.get("_links") or {}).get("next") or ""
            if not next_link:
                next_url = None
            else:
                # `_links.next` is a relative path like
                # `/wiki/api/v2/spaces/{id}/permissions?cursor=...`.
                # Rebuild against the host portion of the v2 base.
                host = base.split("/wiki/")[0]
                if next_link.startswith("http"):
                    next_url = next_link
                elif next_link.startswith("/"):
                    next_url = f"{host}{next_link}"
                else:
                    next_url = f"{host}/{next_link}"
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        return SpaceAudience(
            key=space_key,
            name=space_name,
            homepage_id=str(homepage_id) if homepage_id else "",
            checked_at=_now_iso(),
            default_audience="skipped",
            error=f"HTTP {status} on /spaces/{{id}}/permissions",
        )
    except httpx.HTTPError as e:
        return SpaceAudience(
            key=space_key,
            name=space_name,
            homepage_id=str(homepage_id) if homepage_id else "",
            checked_at=_now_iso(),
            default_audience="skipped",
            error=f"network error on /spaces/{{id}}/permissions: {e}",
        )

    aggregated = {
        "results": all_results,
        "_meta": {
            "pages_fetched": pages_fetched,
            "total_results": len(all_results),
            "last_links": last_payload.get("_links", {}),
        },
    }
    audience = classify_space_audience(
        aggregated,
        space_key=space_key,
        broadly_accessible_spaces=broadly_accessible_spaces,
    )
    return SpaceAudience(
        key=space_key,
        name=space_name,
        homepage_id=str(homepage_id) if homepage_id else "",
        checked_at=_now_iso(),
        default_audience=audience,
        raw=aggregated,
    )
