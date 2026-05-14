"""Confluence v2 API client + pull-space orchestrator (spec §4.1).

Drives the full ingestion flow for one space:
  list pages → for each: check sync state → convert → download attachments → write.

Yields progress events so the FastAPI layer can SSE-stream them to the UI.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx

from .adf import page_uses_adf
from .attachments import download_attachments, verify_attachment_references
from ..config import SyncConfig
from .converter import convert_page
from .dead_letter import write_failure
from .frontmatter import PageMeta, build_frontmatter, canonical_filename, content_hash, sanitize_filename_title, serialize, validate
from .state import SyncState
from .wikilinks import CorpusIndex, DefaultLinkResolver


# Source-URL pattern — every page links back to the authoritative Confluence
# location on the public-facing host (spec §1, item 5).
PUBLIC_HOST = "https://answers.atlassian.syr.edu"


@dataclass
class PullEvent:
    kind: str  # "started" | "discovered" | "page_skipped" | "page_converted" | "page_failed" | "completed"
    space_key: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class PullSummary:
    space_key: str
    pages_total: int = 0
    pages_converted: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    pages_warned: int = 0
    duration_s: float = 0.0


class ConfluencePuller:
    def __init__(
        self,
        config: SyncConfig,
        email: str,
        token: str,
    ) -> None:
        self.config = config
        self.email = email
        self.token = token
        self.client = httpx.Client(
            auth=(email, token),
            timeout=30.0,
            headers={"Accept": "application/json"},
        )
        self._last_call_at: str | None = None
        # Ancestor lookups: same folder/page appears as ancestor on many child
        # pages. Cache aggressively so a 34-page pull doesn't make 34× redundant
        # ancestor-detail calls.
        self._ancestor_title_cache: dict[str, str] = {}
        # Spec §4.1 recommends the Atlassian gateway URL over the custom domain
        # — *and* it's mandatory for attachment downloads, which return 401
        # against `su-jsm.atlassian.net/wiki/download/...` but 302-redirect
        # cleanly through the gateway to Media Services with a JWT. Resolved
        # lazily on first API call via /_edge/tenant_info.
        self._api_base: str = config.api_base
        self._gateway_resolved: bool = False

    # --- low-level API helpers ------------------------------------------------

    @property
    def api_base(self) -> str:
        if not self._gateway_resolved:
            self._resolve_gateway_base()
        return self._api_base

    def _resolve_gateway_base(self) -> None:
        """Swap the configured custom-domain api_base for the Atlassian gateway
        URL (`api.atlassian.com/ex/confluence/<cloud-id>/...`). Per spec §4.1
        + verified empirically: attachment downloads only work via the gateway.
        Falls back to the configured api_base on resolution failure.
        """
        if self._api_base.startswith("https://api.atlassian.com/"):
            self._gateway_resolved = True
            return
        host = self._api_base.split("/wiki/")[0]
        try:
            resp = self.client.get(f"{host}/_edge/tenant_info", timeout=10.0)
            resp.raise_for_status()
            cloud_id = resp.json().get("cloudId")
            if cloud_id:
                self._api_base = f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2"
        except (httpx.HTTPError, ValueError):
            # Tolerated — fall back to the configured base. Downloads will fail
            # but the rest of the pipeline can still produce markdown.
            pass
        self._gateway_resolved = True

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        delay = 1.0
        for attempt in range(6):
            resp = self.client.get(url, params=params)
            self._last_call_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", delay))
                time.sleep(retry_after)
                delay = min(delay * 2, 30.0)
                continue
            if resp.status_code >= 500:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue
            resp.raise_for_status()
            # Rate limit ourselves to config.rate_limit_per_sec
            time.sleep(1.0 / max(self.config.rate_limit_per_sec, 0.1))
            return resp.json()
        resp.raise_for_status()
        return {}

    @property
    def last_call_at(self) -> str | None:
        return self._last_call_at

    def auth_status(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "token_loaded": bool(self.token),
            "last_call_ts": self._last_call_at,
        }

    # --- inventory helpers ----------------------------------------------------

    def list_spaces(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 250}
            if cursor:
                params["cursor"] = cursor
            data = self._get(f"{self.api_base}/spaces", params=params)
            out.extend(data.get("results", []))
            cursor = _cursor_from_next(data)
            if not cursor:
                break
        return out

    def get_space(self, space_key: str) -> dict[str, Any]:
        data = self._get(f"{self.api_base}/spaces", params={"keys": space_key})
        results = data.get("results", [])
        if not results:
            raise ValueError(f"No space found with key {space_key!r}")
        return results[0]

    def list_pages(self, space_id: str) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"body-format": "storage", "limit": 250}
            if cursor:
                params["cursor"] = cursor
            data = self._get(f"{self.api_base}/spaces/{space_id}/pages", params=params)
            for page in data.get("results", []):
                yield page
            cursor = _cursor_from_next(data)
            if not cursor:
                break

    def get_page_ancestors(self, page_id: str) -> list[dict[str, Any]]:
        data = self._get(f"{self.api_base}/pages/{page_id}/ancestors")
        return data.get("results", [])

    def _fetch_node_title(self, node_id: str, hinted_kind: str | None = None) -> str:
        """Fetch the title of an ancestor node, trying pages then folders.

        v2 /pages/{id}/ancestors returns minimal fields (often just id +
        sometimes type). When a Confluence space is organised using folder
        content-type nodes (not parent pages), those ancestors aren't in our
        pages corpus and have no title in the ancestors response — so we look
        them up individually here. Results cached on the puller instance.
        """
        if node_id in self._ancestor_title_cache:
            return self._ancestor_title_cache[node_id]

        # Try the hinted endpoint first, then the other. The v2 API returns 404
        # for the wrong type, so we just fall through.
        order = ["folders", "pages"] if hinted_kind == "folder" else ["pages", "folders"]
        title = ""
        for kind in order:
            try:
                data = self._get(f"{self.api_base}/{kind}/{node_id}")
            except httpx.HTTPError:
                continue
            t = data.get("title")
            if t:
                title = t
                break

        self._ancestor_title_cache[node_id] = title
        return title

    def _resolve_ancestor_path(
        self,
        page: dict[str, Any],
        title_cache: dict[str, str],
    ) -> list[str]:
        parent_id = str(page.get("parentId") or "") or None
        if not parent_id:
            return []
        try:
            ancestors = self.get_page_ancestors(str(page.get("id")))
        except httpx.HTTPError:
            return []
        titles: list[str] = []
        for a in ancestors:
            aid = str(a.get("id"))
            if not aid:
                continue
            # Prefer the title the ancestors endpoint gave us; then the
            # pages-in-this-space title cache; then fetch the node directly
            # (handles folder-type ancestors that aren't pages).
            title = a.get("title") or title_cache.get(aid)
            if not title:
                title = self._fetch_node_title(aid, a.get("type"))
            if title:
                titles.append(title)
        return titles

    def get_page_labels(self, page_id: str) -> list[str]:
        try:
            data = self._get(f"{self.api_base}/pages/{page_id}/labels")
        except httpx.HTTPStatusError:
            return []
        return [lbl.get("name") for lbl in data.get("results", []) if lbl.get("name")]

    def get_page_versions(self, page_id: str) -> list[dict[str, Any]]:
        try:
            data = self._get(f"{self.api_base}/pages/{page_id}/versions")
        except httpx.HTTPStatusError:
            return []
        return data.get("results", [])

    def get_page_direct_children(self, page_id: str) -> list[dict[str, str]]:
        try:
            data = self._get(f"{self.api_base}/pages/{page_id}/children")
        except httpx.HTTPStatusError:
            return []
        return [
            {"id": str(c.get("id")), "title": c.get("title", "")}
            for c in data.get("results", [])
        ]

    # --- main orchestrator ----------------------------------------------------

    def pull_space(self, space_key: str) -> Iterator[PullEvent]:
        start = time.monotonic()
        summary = PullSummary(space_key=space_key)

        yield PullEvent("started", space_key, {"ts": _now_iso()})

        # 1. Resolve space.
        try:
            space = self.get_space(space_key)
        except Exception as e:
            yield PullEvent("failed_to_resolve_space", space_key, {"error": str(e)})
            return

        space_id = str(space.get("id"))
        space_name = space.get("name") or space_key
        space_type = space.get("type") or "global"
        category = self.config.category_for(space_key)

        space_root = self.config.raw_path / category / _safe_dir(space_name)
        space_root.mkdir(parents=True, exist_ok=True)
        attachments_root = space_root / "attachments"
        meta_root = space_root / ".meta"
        meta_root.mkdir(parents=True, exist_ok=True)
        state = SyncState.load(meta_root / ".sync-state.json")
        dead_letter_root = self.config.output_dir / "conversion-failures"

        # 2. First pass — list pages, build corpus index for wikilink resolution.
        all_pages = list(self.list_pages(space_id))
        corpus = CorpusIndex()
        for p in all_pages:
            pid = str(p.get("id"))
            title = p.get("title", "")
            source_url = _build_source_url(space_key, pid, title)
            corpus.register(pid, title, space_key, source_url)

        yield PullEvent("discovered", space_key, {
            "space_id": space_id,
            "space_name": space_name,
            "page_count": len(all_pages),
        })

        # Cache: page_id → title (for ancestor resolution)
        title_cache: dict[str, str] = {pid: t[0] for pid, t in corpus.pages_by_id.items()}

        # 3. Per-page processing
        for page in all_pages:
            pid = str(page.get("id"))
            title = page.get("title", "")
            version_no = int((page.get("version") or {}).get("number") or 1)
            body_storage = ((page.get("body") or {}).get("storage") or {}).get("value", "")
            last_modified = (page.get("version") or {}).get("createdAt", "")
            source_url = _build_source_url(space_key, pid, title)

            summary.pages_total += 1

            try:
                # Conversion (no skip yet — we need the hash to decide).
                resolver = DefaultLinkResolver(
                    corpus=corpus,
                    current_space_key=space_key,
                    current_page_id=pid,
                )
                children = self.get_page_direct_children(pid) if "ac:name=\"children\"" in body_storage else []
                conv = convert_page(
                    storage_xml=body_storage,
                    page_id=pid,
                    space_key=space_key,
                    link_resolver=resolver,
                    children_for_page=children,
                )

                # Skip if version + hash unchanged
                body_hash = content_hash(conv.markdown)
                if state.should_skip(pid, version_no, body_hash):
                    summary.pages_skipped += 1
                    yield PullEvent("page_skipped", space_key, {
                        "page_id": pid, "title": title, "reason": "version+hash unchanged",
                    })
                    state.record(pid, version_no, body_hash, _now_iso(), "skipped")
                    state.save()
                    continue

                # Strictness boundary — content non-empty source but empty body = hard fail
                if body_storage.strip() and not conv.markdown.strip():
                    raise ValueError("Body converted to empty when source body was non-empty")

                # Resolve ancestors → folder path
                ancestor_path = self._resolve_ancestor_path(
                    page=page,
                    title_cache=title_cache,
                )

                # Build full output folder
                target_dir = space_root
                for ancestor_title in ancestor_path:
                    target_dir = target_dir / _safe_dir(ancestor_title)
                target_dir.mkdir(parents=True, exist_ok=True)

                # Attachments — download + verify on disk
                manifest = None
                if _has_attachment_refs(body_storage):
                    try:
                        manifest = download_attachments(
                            client=self.client,
                            api_base=self.api_base,
                            page_id=pid,
                            out_root=attachments_root,
                        )
                    except Exception as att_err:
                        conv.warnings.append(f"attachment download partial-failure: {att_err}")

                # Spec §4.3 acceptance: every emitted attachment reference must
                # exist on disk. Surface gaps as warnings on the page so they
                # show up in the per-page log (and frontmatter) — operational
                # visibility, not silent corruption.
                missing_refs = verify_attachment_references(conv.markdown, attachments_root)
                conv.warnings.extend(missing_refs)

                # Build frontmatter
                labels = self.get_page_labels(pid)
                versions = self.get_page_versions(pid)
                contributors = sorted({v.get("authorId") or v.get("authorAccountId") or "" for v in versions if v})
                contributors = [c for c in contributors if c]

                meta = PageMeta(
                    page_id=pid,
                    title=title,
                    source_url=source_url,
                    space_key=space_key,
                    space_name=space_name,
                    space_type=space_type,
                    space_category=category,
                    ancestor_path=ancestor_path,
                    last_modified=last_modified,
                    version=version_no,
                    contributors=contributors,
                    labels=labels,
                    aliases=[],
                )

                status_for_fm = "warning" if conv.warnings else "ok"
                fm = build_frontmatter(
                    meta=meta,
                    body_markdown=conv.markdown,
                    last_sync_status=status_for_fm,
                    warnings=conv.warnings,
                )
                missing = validate(fm)
                if missing:
                    raise ValueError(f"Missing required frontmatter fields: {missing}")

                # Write file
                filename = canonical_filename(pid, title)
                target_path = target_dir / filename
                target_path.write_text(serialize(fm) + "\n" + conv.markdown, encoding="utf-8")

                # Record state
                state.record(pid, version_no, content_hash(conv.markdown), _now_iso(), status_for_fm)
                # Save incrementally — a crash mid-pull preserves progress on
                # the pages already on disk so the next run skips them via
                # content_hash rather than re-converting + re-classifying.
                state.save()

                if conv.warnings:
                    summary.pages_warned += 1
                summary.pages_converted += 1

                yield PullEvent("page_converted", space_key, {
                    "page_id": pid,
                    "title": title,
                    "status": status_for_fm,
                    "macros_unconverted": sum(1 for w in conv.warnings if "unconverted macro" in w),
                    "warnings_count": len(conv.warnings),
                    "used_adf": conv.used_adf,
                    "output_path": str(target_path),
                    "ancestor_path": ancestor_path,
                    "labels": labels,
                    "attachment_count": len(manifest.files) if manifest else 0,
                })

            except Exception as e:
                summary.pages_failed += 1
                dl_path = write_failure(
                    dead_letter_root=dead_letter_root,
                    space_key=space_key,
                    page_id=pid,
                    title=title,
                    storage_xml=body_storage,
                    error=e,
                    warnings=[],
                    extra={"source_url": source_url, "version": version_no},
                )
                state.record(pid, version_no, "", _now_iso(), "failed")
                state.save()
                yield PullEvent("page_failed", space_key, {
                    "page_id": pid,
                    "title": title,
                    "error": str(e),
                    "dead_letter_path": str(dl_path),
                })

        # 4. Persist state + manifest
        state.save()
        _write_space_manifest(meta_root, space_key, space_id, space_name, space_type, len(all_pages), summary)

        summary.duration_s = round(time.monotonic() - start, 3)
        yield PullEvent("completed", space_key, {
            "summary": {
                "pages_total": summary.pages_total,
                "pages_converted": summary.pages_converted,
                "pages_skipped": summary.pages_skipped,
                "pages_warned": summary.pages_warned,
                "pages_failed": summary.pages_failed,
                "duration_s": summary.duration_s,
                "space_root": str(space_root),
            }
        })


# --- helpers ------------------------------------------------------------------


def _cursor_from_next(data: dict[str, Any]) -> str | None:
    nxt = (data.get("_links") or {}).get("next")
    if not nxt:
        return None
    m = re.search(r"cursor=([^&]+)", nxt)
    return m.group(1) if m else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_dir(name: str) -> str:
    return sanitize_filename_title(name)


def _build_source_url(space_key: str, page_id: str, title: str) -> str:
    slug = re.sub(r"\s+", "+", title.strip())
    return f"{PUBLIC_HOST}/wiki/spaces/{space_key}/pages/{page_id}/{slug}"


def _has_attachment_refs(body: str) -> bool:
    return ("ri:attachment" in body) or ("ac:image" in body)


def _write_space_manifest(
    meta_root: Path,
    space_key: str,
    space_id: str,
    space_name: str,
    space_type: str,
    page_count: int,
    summary: PullSummary,
) -> None:
    import json

    payload = {
        "space_key": space_key,
        "space_id": space_id,
        "space_name": space_name,
        "space_type": space_type,
        "page_count": page_count,
        "last_sync": _now_iso(),
        "last_summary": {
            "pages_total": summary.pages_total,
            "pages_converted": summary.pages_converted,
            "pages_skipped": summary.pages_skipped,
            "pages_failed": summary.pages_failed,
        },
    }
    (meta_root / "space-manifest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    # Append to sync-log.jsonl
    log_line = json.dumps({
        "ts": _now_iso(),
        "op": "sync_complete",
        "space": space_key,
        "pages_total": summary.pages_total,
        "pages_changed": summary.pages_converted,
        "pages_failed": summary.pages_failed,
    })
    with (meta_root / "sync-log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(log_line + "\n")


def load_credentials(env_path: Path | None = None) -> tuple[str, str]:
    """Load ATLASSIAN_EMAIL + ATLASSIAN_TOKEN from .env or process env."""
    if env_path and env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            # Manual parse if python-dotenv isn't installed
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    email = os.environ.get("ATLASSIAN_EMAIL", "")
    token = os.environ.get("ATLASSIAN_TOKEN", "")
    return email, token
