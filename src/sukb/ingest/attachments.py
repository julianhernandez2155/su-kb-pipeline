"""Attachment download + reference rewriting (spec §4.2, §4.3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass
class AttachmentManifest:
    page_id: str
    page_dir: Path
    files: list[str]


def download_attachments(
    client: httpx.Client,
    api_base: str,
    page_id: str,
    out_root: Path,
) -> AttachmentManifest:
    """Fetch all attachments for a page; persist under attachments/<page-id>/.

    Lazy-creates the page directory only when a file actually lands on disk —
    pages that mention `ri:attachment` in their storage XML but have no real
    attachments (e.g., embedded ADF that strings-matched the heuristic) do
    not leave empty folders behind.

    Returns the manifest so wikilink rewriting can verify files exist on disk
    (acceptance criterion: "AND the files exist on disk").
    """
    page_dir = out_root / page_id
    files: list[str] = []

    def ensure_dir() -> None:
        if not page_dir.exists():
            page_dir.mkdir(parents=True, exist_ok=True)

    cursor: str | None = None
    while True:
        params = {"limit": 250}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(f"{api_base}/pages/{page_id}/attachments", params=params)
        resp.raise_for_status()
        data = resp.json()
        for att in data.get("results", []):
            filename = att.get("title") or att.get("fileId")
            if not filename:
                continue
            download_link = (att.get("_links") or {}).get("download") or att.get("downloadLink")
            if not download_link:
                # v2 API uses a webuiLink pattern; fall back to /attachments/<id>/download
                attachment_id = att.get("id")
                if not attachment_id:
                    continue
                download_link = f"/wiki/download/attachments/{page_id}/{filename}"
            # Resolve relative URL against the wiki root.
            # api_base ends with `/wiki/api/v2`; downloadLink looks like
            # `/download/attachments/<page>/<file>?...`. We want
            # `<gateway>/wiki/download/attachments/...`, so strip just
            # `/api/v2` from api_base to land on `<gateway>/wiki`.
            if download_link.startswith("http"):
                file_url = download_link
            else:
                wiki_root = api_base.rsplit("/api/v2", 1)[0]
                file_url = wiki_root + download_link
            try:
                fresp = client.get(file_url, follow_redirects=True)
                fresp.raise_for_status()
                ensure_dir()
                target = page_dir / filename
                target.write_bytes(fresp.content)
                files.append(filename)
            except httpx.HTTPError:
                # Tolerated — attachment failures are warnings, not page failures.
                continue

        cursor = _next_cursor(data)
        if not cursor:
            break

    return AttachmentManifest(page_id=page_id, page_dir=page_dir, files=files)


# Confluence filenames legitimately contain spaces ("Screenshot 2026-03-10.png")
# and parentheses ("image (1).png"). Split by emit context to keep the
# character classes accurate:
#   - Obsidian wikilink embed:  ![[attachments/<id>/<name>]]   or  ...|width]]
#   - Markdown link:            [label](attachments/<id>/<name>)
_WIKILINK_ATTACHMENT_RE = re.compile(
    r"!?\[\[attachments/(?P<page>\d+)/(?P<file>[^\]|]+?)(?=[\]|])"
)
_MDLINK_ATTACHMENT_RE = re.compile(
    r"\]\(attachments/(?P<page>\d+)/(?P<file>[^)]+)\)"
)


def verify_attachment_references(
    markdown: str,
    attachments_root: Path,
) -> list[str]:
    """Walk converted Markdown for attachment references and verify each file
    exists on disk under `attachments_root/<page-id>/<filename>`.

    Returns a list of human-readable warning strings (empty = all good).
    Spec acceptance criterion: "All <ac:image> / <ri:attachment> references
    resolve to local attachments/<page-id>/<filename> paths AND the files
    exist on disk."
    """
    missing: list[str] = []
    seen: set[tuple[str, str]] = set()
    for regex in (_WIKILINK_ATTACHMENT_RE, _MDLINK_ATTACHMENT_RE):
        for m in regex.finditer(markdown):
            page_id = m.group("page")
            filename = m.group("file").strip()
            key = (page_id, filename)
            if key in seen:
                continue
            seen.add(key)
            if not (attachments_root / page_id / filename).exists():
                missing.append(f"missing attachment on disk: attachments/{page_id}/{filename}")
    return missing


def _next_cursor(data: dict) -> str | None:
    links = data.get("_links") or {}
    nxt = links.get("next")
    if not nxt:
        return None
    # Format: "/wiki/api/v2/...?cursor=XYZ&limit=..."
    import re

    m = re.search(r"cursor=([^&]+)", nxt)
    return m.group(1) if m else None
