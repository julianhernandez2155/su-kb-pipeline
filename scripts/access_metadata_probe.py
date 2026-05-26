"""Phase 1.1 — read-only access classification probe.

See docs/phase-1.1-plan-2026-05-19.md for the full plan. This script is
standalone (not part of the puller) so the human can validate API response
shapes before any frontmatter rewrites or pipeline integration happen.

Usage (first run — read-only, no frontmatter writes):

    python scripts/access_metadata_probe.py --space ITSAI

That writes three files under output/_access/:
    access-manifest.jsonl   (one JSON per page; gitignored)
    spaces.json             (per-space audience cache; gitignored)
    access-summary.md       (committed; sanitized — counts + folder sources only)

To rewrite the three access-owned frontmatter fields on existing pages once
the manifest looks right, re-run with:

    python scripts/access_metadata_probe.py --space ITSAI --update-frontmatter

To explore without writing anything at all:

    python scripts/access_metadata_probe.py --space ITSAI --dry-run

Field ownership and the visibility-priority logic are defined in the plan.
This script is the canonical writer of the three access-owned frontmatter
fields (visibility_signal, restriction_check, restriction_source_ids) until
Step 2 folds the logic into the puller.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- sys.path bootstrap so the script runs without `pip install -e .` -------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import httpx  # noqa: E402  (after sys.path insert)
import yaml  # noqa: E402

from sukb.config import SyncConfig  # noqa: E402
from sukb.ingest.access import (  # noqa: E402
    AncestorRestrictionCache,
    PageClassification,
    classification_to_manifest_entry,
    classify_visibility,
    now_iso,
    restriction_to_jsonable,
    rewrite_access_fields,
    space_to_jsonable,
)
from sukb.ingest.frontmatter import (  # noqa: E402
    ACCESS_OWNED_FIELDS,
    VISIBILITY_SIGNAL_VALUES as VISIBILITY_VALUES,
    find_existing_page_file,
    read_existing_frontmatter,
    serialize,
)
from sukb.ingest.puller import ConfluencePuller, load_credentials  # noqa: E402
from sukb.ingest.restrictions import (  # noqa: E402
    EntityRestrictions,
    fetch_direct_restrictions,
)
from sukb.ingest.spaces import (  # noqa: E402
    SpaceAudience,
    fetch_space_audience,
)


# --- I/O helpers (atomic temp-then-rename) ----------------------------------


def _now_iso() -> str:
    return now_iso()


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    # On Windows replace() is atomic across the same volume; we accept that.
    tmp.replace(path)


# --- current-account lookup --------------------------------------------------


def fetch_current_account_id(puller: ConfluencePuller) -> str:
    """Return the accountId of the authenticated principal (sync user).

    Tries the v1 user/current endpoint (REST). On any failure, returns "".
    Recorded in each manifest entry as `checked_with_account_id` so a future
    re-classification can detect when the auth principal has changed.
    """
    from sukb.ingest.restrictions import v1_rest_base_from_v2

    url = v1_rest_base_from_v2(puller.api_base) + "/user/current"
    try:
        data = puller._get(url)
    except httpx.HTTPError:
        return ""
    return str(data.get("accountId") or "")


# --- ancestor cache ----------------------------------------------------------


# --- per-page walk -----------------------------------------------------------


def classify_page(
    puller: ConfluencePuller,
    page: dict[str, Any],
    space: SpaceAudience | None,
    ancestor_cache: AncestorRestrictionCache,
    checked_with_account_id: str,
    page_title_cache: dict[str, str],
) -> PageClassification:
    """Build one PageClassification record for a single page.

    Walks ancestors via the puller's existing endpoint, then resolves each
    ancestor's title via the puller's `_fetch_node_title` cache and its
    direct restrictions via the per-probe ancestor cache.
    """
    pid = str(page.get("id"))
    title = page.get("title") or ""
    record = PageClassification(
        page_id=pid,
        title=title,
        space_key=space.key if space else "",
        checked_at=_now_iso(),
        checked_with_account_id=checked_with_account_id,
        space=space,
    )

    # 1. Direct restrictions on the page itself.
    record.direct = fetch_direct_restrictions(
        puller, pid, entity_type="page", entity_title=title
    )

    # 2. Ancestor chain — pages or folders. The puller's existing
    #    /pages/{id}/ancestors call returns id+type minimally; titles often
    #    require follow-up. We resolve titles for the summary, and call
    #    restrictions per novel ancestor.
    try:
        ancestor_nodes = puller.get_page_ancestors(pid)
    except httpx.HTTPError as e:
        record.errors.append(f"ancestor walk failed: {e}")
        record.ancestors = []
        sig, layers, sources = classify_visibility(record.direct, None, space)
        record.visibility_signal = sig
        record.restriction_check = layers
        record.restriction_source_ids = sources
        return record

    ancestor_results: list[EntityRestrictions] = []
    for node in ancestor_nodes:
        aid = str(node.get("id") or "")
        if not aid:
            continue
        atype = (node.get("type") or "").lower() or "unknown"
        atitle = node.get("title") or page_title_cache.get(aid) or ""
        if not atitle:
            atitle = puller._fetch_node_title(aid, atype) or ""
        ancestor_results.append(ancestor_cache.get(aid, atype, atitle))

    record.ancestors = ancestor_results

    sig, layers, sources = classify_visibility(record.direct, ancestor_results, space)
    record.visibility_signal = sig
    record.restriction_check = layers
    record.restriction_source_ids = sources
    return record


# --- manifest, summary, spaces.json writers ---------------------------------


def write_manifest(path: Path, records: list[PageClassification]) -> None:
    lines = [
        json.dumps(classification_to_manifest_entry(r), ensure_ascii=False)
        for r in records
    ]
    _atomic_write(path, "\n".join(lines) + "\n" if lines else "")


def write_spaces_cache(path: Path, spaces: dict[str, SpaceAudience]) -> None:
    payload = {key: space_to_jsonable(s, include_raw=True) for key, s in spaces.items()}
    _atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_summary(
    path: Path,
    records: list[PageClassification],
    spaces: dict[str, SpaceAudience],
    space_keys: list[str],
) -> None:
    """Build the sanitized human-readable rollup.

    See the plan's §"Sanitization rules for access-summary.md" for what's
    allowed: aggregate counts + names of restriction *sources* (folders),
    never names of restricted *destinations* (pages), and never account/
    group IDs.
    """
    sig_counts = Counter(r.visibility_signal for r in records)
    # Preserve insertion order (direct,ancestors,space) — sorting would
    # group identical sets that differ only in ordering, but the order is
    # already stable, so sorting just obscures the natural sequence.
    layer_counts = Counter(",".join(r.restriction_check) or "(none)" for r in records)
    source_to_titles: dict[str, str] = {}
    source_to_count: Counter[str] = Counter()
    for r in records:
        for sid in r.restriction_source_ids:
            source_to_count[sid] += 1
            # Look up a title for this source from this record's ancestors
            # (or direct if the source matches the page itself). We don't
            # surface page titles for `restricted_direct` cases — Phase 1.1
            # only names folder sources. Per plan, page-level direct
            # restrictions are aggregated but unnamed.
            if sid == r.page_id:
                continue  # skip — would leak a restricted page title
            for a in r.ancestors:
                if str(a.entity_id) == sid and a.entity_title:
                    source_to_titles.setdefault(sid, a.entity_title)
                    break

    lines: list[str] = []
    lines.append("# Access Classification Summary")
    lines.append("")
    lines.append(f"_Generated: {_now_iso()}_")
    lines.append("")
    lines.append("Auto-generated by `scripts/access_metadata_probe.py`. Do not edit.")
    lines.append("")
    lines.append(f"Spaces classified: {', '.join(space_keys) or '(none)'}")
    lines.append(f"Pages classified: {len(records)}")
    lines.append("")
    lines.append("## Visibility breakdown")
    lines.append("")
    lines.append("| visibility_signal | count |")
    lines.append("|---|---:|")
    for sig in VISIBILITY_VALUES:
        lines.append(f"| {sig} | {sig_counts.get(sig, 0)} |")
    lines.append("")
    lines.append("## Layers checked")
    lines.append("")
    lines.append("| restriction_check | count |")
    lines.append("|---|---:|")
    for layers, count in sorted(layer_counts.items()):
        lines.append(f"| {layers} | {count} |")
    lines.append("")
    lines.append("## Per-space audience")
    lines.append("")
    lines.append("| space_key | default_audience | error |")
    lines.append("|---|---|---|")
    for key, s in sorted(spaces.items()):
        err = s.error or ""
        lines.append(f"| {key} | {s.default_audience} | {err} |")
    lines.append("")
    lines.append("## Restriction sources (folders that gate access)")
    lines.append("")
    lines.append("Each row is a folder/page node whose direct restrictions caused descendant pages to be excluded. Only nodes already named elsewhere in the corpus appear here — restricted *destination* page titles are NOT surfaced.")
    lines.append("")
    lines.append("| source_id | source_title | pages_gated |")
    lines.append("|---|---|---:|")
    for sid, count in source_to_count.most_common():
        title = source_to_titles.get(sid, "(unnamed)")
        lines.append(f"| {sid} | {title} | {count} |")
    if not source_to_count:
        lines.append("| _(none)_ | | |")
    lines.append("")

    # Errors (counts only — never the page titles tied to the errors)
    error_records = [r for r in records if r.errors or r.visibility_signal == "unknown"]
    lines.append("## Errors / unknowns")
    lines.append("")
    lines.append(f"Pages classified as `unknown`: {sig_counts.get('unknown', 0)}")
    lines.append(f"Pages with manifest-level errors: {len(error_records)}")
    lines.append("")

    _atomic_write(path, "\n".join(lines))


# --- frontmatter rewrite -----------------------------------------------------


# rewrite_access_fields lives in sukb.ingest.access (shared with puller).


# --- main --------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--space",
        action="append",
        default=[],
        required=True,
        help="Space key to classify. May be repeated for multi-space.",
    )
    p.add_argument(
        "--page-id",
        action="append",
        default=[],
        help="Optional: classify only these page IDs instead of the full space.",
    )
    p.add_argument(
        "--out",
        default="output/_access/access-manifest.jsonl",
        help="Manifest output path.",
    )
    p.add_argument(
        "--spaces-cache",
        default="output/_access/spaces.json",
        help="Per-space audience cache path.",
    )
    p.add_argument(
        "--summary",
        default="output/_access/access-summary.md",
        help="Human-readable rollup path.",
    )
    p.add_argument(
        "--config",
        default="sync_config.yaml",
        help="Path to sync_config.yaml.",
    )
    p.add_argument(
        "--env",
        default=".env",
        help="Path to .env file (ATLASSIAN_EMAIL + ATLASSIAN_TOKEN).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify + print; write nothing (no manifest, no summary, no frontmatter).",
    )
    p.add_argument(
        "--update-frontmatter",
        action="store_true",
        help="Rewrite the three access-owned fields on existing page markdown.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Resolve paths relative to project root (so the script works from any cwd).
    config_path = (PROJECT_ROOT / args.config).resolve()
    env_path = (PROJECT_ROOT / args.env).resolve()
    manifest_path = (PROJECT_ROOT / args.out).resolve()
    spaces_cache_path = (PROJECT_ROOT / args.spaces_cache).resolve()
    summary_path = (PROJECT_ROOT / args.summary).resolve()

    if not config_path.exists():
        print(f"sync_config.yaml not found at {config_path}", file=sys.stderr)
        return 2

    config = SyncConfig.load(config_path)

    email, token = load_credentials(env_path if env_path.exists() else None)
    if not email or not token:
        print("ATLASSIAN_EMAIL / ATLASSIAN_TOKEN missing from env", file=sys.stderr)
        return 2

    puller = ConfluencePuller(config=config, email=email, token=token)
    # Force gateway resolution upfront so we know the v1 base is correct.
    _ = puller.api_base

    # 1. Resolve current account once.
    checked_with_account_id = fetch_current_account_id(puller)
    print(f"[probe] checked_with_account_id={checked_with_account_id or '(unknown)'}")

    spaces: dict[str, SpaceAudience] = {}
    all_records: list[PageClassification] = []
    ancestor_cache = AncestorRestrictionCache(puller)

    for space_key in args.space:
        try:
            space_data = puller.get_space(space_key)
        except Exception as e:
            print(f"[probe] failed to resolve space {space_key}: {e}", file=sys.stderr)
            spaces[space_key] = SpaceAudience(
                key=space_key,
                checked_at=_now_iso(),
                default_audience="skipped",
                error=f"space lookup failed: {e}",
            )
            continue

        space_id = str(space_data.get("id"))
        space_name = space_data.get("name") or space_key
        homepage_id = str(space_data.get("homepageId") or "")

        audience = fetch_space_audience(
            puller=puller,
            space_key=space_key,
            space_id=space_id,
            space_name=space_name,
            homepage_id=homepage_id,
            broadly_accessible_spaces=list(config.broadly_accessible_spaces),
        )
        spaces[space_key] = audience
        print(f"[probe] {space_key}: default_audience={audience.default_audience}"
              + (f"  (error: {audience.error})" if audience.error else ""))

        # Build the title cache for ancestor lookups
        if args.page_id:
            # Limited run: fetch only specified pages, no full listing.
            pages_to_classify: list[dict[str, Any]] = []
            for pid in args.page_id:
                try:
                    data, _labels = puller.get_page_full(pid)
                    pages_to_classify.append(data)
                except Exception as e:
                    print(f"[probe] page {pid} fetch failed: {e}", file=sys.stderr)
        else:
            pages_to_classify = list(puller.list_pages(space_id))

        page_title_cache = {str(p.get("id")): (p.get("title") or "") for p in pages_to_classify}

        for i, page in enumerate(pages_to_classify, start=1):
            pid = str(page.get("id"))
            title = page.get("title") or ""
            record = classify_page(
                puller=puller,
                page=page,
                space=audience,
                ancestor_cache=ancestor_cache,
                checked_with_account_id=checked_with_account_id,
                page_title_cache=page_title_cache,
            )
            all_records.append(record)
            srcs = ",".join(record.restriction_source_ids) or "-"
            print(
                f"[probe] {i:>3}/{len(pages_to_classify)} {pid} {title[:60]!r:62}"
                f"  -> {record.visibility_signal:30} sources={srcs}"
            )

    # 2. Dry-run: print summary; no writes at all.
    if args.dry_run:
        print("\n[probe] dry-run: skipping all writes.")
        sig_counts = Counter(r.visibility_signal for r in all_records)
        for sig in VISIBILITY_VALUES:
            print(f"  {sig:30}: {sig_counts.get(sig, 0)}")
        return 0

    # 3. Write manifest, spaces cache, summary atomically.
    write_manifest(manifest_path, all_records)
    write_spaces_cache(spaces_cache_path, spaces)
    write_summary(summary_path, all_records, spaces, args.space)
    print(f"\n[probe] wrote {manifest_path.relative_to(PROJECT_ROOT)}")
    print(f"[probe] wrote {spaces_cache_path.relative_to(PROJECT_ROOT)}")
    print(f"[probe] wrote {summary_path.relative_to(PROJECT_ROOT)}")

    # 4. Optional frontmatter rewrites.
    if args.update_frontmatter:
        changed = 0
        unchanged = 0
        errors: list[tuple[str, str]] = []
        for r in all_records:
            ok, err = rewrite_access_fields(config.raw_path, r)
            if err is not None:
                errors.append((r.page_id, err))
            elif ok:
                changed += 1
            else:
                unchanged += 1
        print(f"\n[probe] frontmatter: {changed} changed, {unchanged} unchanged, {len(errors)} errors")
        for pid, err in errors:
            print(f"  ! {pid}: {err}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
