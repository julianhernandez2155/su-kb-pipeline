"""MCP-shaped tools that the agentic eval (Step 7) exposes to Claude.

The four tools mirror what a production MCP server would publish over
Streamable HTTP + OAuth/JWT. Keeping the contracts close to the future
MCP interface means migrating Step 7's local Python functions to a hosted
MCP server is "wrap these in transport + auth" rather than "redesign
retrieval logic."

Tools:
  - read_index(path)   — orientation files (CLAUDE.md, index.md, wiki/index.md, space-level)
  - list_hubs()        — reviewed wiki hubs with `when_to_use` guidance
  - search(query, top_k) — title-weighted lexical search over raw + wiki
  - read_page(id)      — full content of a raw page (by page_id) or wiki hub (by slug)

Search is intentionally simple — token overlap with a 3x title weight, a
stopword filter, and a small wiki-layer boost. The plan notes that if
paraphrase queries miss, the next local optimization is title/heading-weighted
FTS5 or hybrid lexical search before any MCP/VM work. We start here and
record search misses in the trace.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import SyncConfig
from .query import (
    OrientationFile,
    RawPage,
    WikiHub,
    load_orientation_files,
    load_raw_corpus,
    load_wiki_corpus,
)

# --- search helpers ---------------------------------------------------------

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does",
    "for", "from", "how", "i", "in", "is", "it", "its", "me", "my", "of", "on",
    "or", "the", "this", "that", "to", "was", "were", "what", "when", "where",
    "which", "who", "why", "will", "with", "you", "your", "if", "any", "use",
    "using", "used", "have", "has", "had", "would", "should", "could", "did",
    "we", "us", "our",
}

_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens with short/stopword filter."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2]


def _snippet(body: str, query_terms: set[str], window: int = 240) -> str:
    """Return a small excerpt around the first query-term hit, else the head."""
    lower = body.lower()
    pos = -1
    for term in query_terms:
        i = lower.find(term)
        if i != -1 and (pos == -1 or i < pos):
            pos = i
    if pos == -1:
        return body[:window].strip()
    start = max(0, pos - window // 2)
    end = min(len(body), pos + window // 2)
    snip = body[start:end].strip()
    return ("…" if start > 0 else "") + snip + ("…" if end < len(body) else "")


# --- tools class ------------------------------------------------------------


@dataclass
class ToolResult:
    """Container returned from `dispatch` — the raw payload + trace info."""
    text: str
    summary: str  # short-form for the trace; full text goes to Claude


class AgenticTools:
    """Holds the corpus in memory and dispatches MCP-shape tool calls.

    Construct once per eval run. Pre-loads raw pages, wiki hubs, and orientation
    files so each tool call is a dict lookup, not a disk walk.
    """

    def __init__(self, config: SyncConfig):
        self.config = config
        self.raw_pages: list[RawPage] = load_raw_corpus(config)
        self.wiki_hubs: list[WikiHub] = load_wiki_corpus(config)
        self.orientation: list[OrientationFile] = load_orientation_files(config)
        self._by_page_id: dict[str, RawPage] = {p.page_id: p for p in self.raw_pages}
        self._by_slug: dict[str, WikiHub] = {Path(w.filename).stem: w for w in self.wiki_hubs}
        self._by_relpath: dict[str, OrientationFile] = {o.relpath: o for o in self.orientation}

    def _source_pages_for_hub(self, hub: WikiHub) -> list[dict[str, str]]:
        """Resolve a hub's synthesized raw page ids to user-facing source URLs."""
        out: list[dict[str, str]] = []
        for pid in hub.synthesizes:
            page = self._by_page_id.get(str(pid))
            if page:
                out.append({
                    "page_id": page.page_id,
                    "title": page.title,
                    "source_url": page.source_url,
                })
            else:
                out.append({"page_id": str(pid), "title": "(unresolved)", "source_url": ""})
        return out

    # ---- tool definitions (Anthropic tool-use JSON schema) ------------------

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Schemas the model sees; names + descriptions must match dispatch()."""
        index_paths = sorted(self._by_relpath.keys())
        return [
            {
                "name": "read_index",
                "description": (
                    "Read an orientation file by relative path. Orientation files describe how "
                    "the corpus is laid out and where to route different question types. Always "
                    "read at least one orientation file before answering — that's how you find "
                    "the right wiki hub or raw page. Available paths: "
                    + ", ".join(index_paths)
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path under output/, e.g. 'CLAUDE.md', 'index.md', 'wiki/index.md'.",
                            "enum": index_paths,
                        }
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "list_hubs",
                "description": (
                    "List reviewed wiki hubs with their `when_to_use` guidance. A wiki hub "
                    "synthesizes 3+ raw pages and is the canonical answer for cross-cutting "
                    "questions (policy comparisons, tool selection, etc.). If the user's "
                    "question matches a hub's `when_to_use`, read the hub via read_page(slug) "
                    "instead of searching across raw pages."
                ),
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "search",
                "description": (
                    "Title-weighted keyword search over raw pages + wiki hubs. Returns up to "
                    "top_k hits with title, snippet, score, layer (raw|wiki), and the id you "
                    "pass to read_page. Use this when you need to find a specific page by "
                    "topic — but prefer read_index + list_hubs first to navigate by structure."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keywords to search for."},
                        "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 15},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "read_page",
                "description": (
                    "Read the full content of a raw page (pass its page_id, a string of digits "
                    "like '488210484') or a wiki hub (pass its slug, e.g. "
                    "'approved-ai-tools-for-university-data'). Read pages before citing them — "
                    "search snippets are not enough to ground a citation. Raw pages include "
                    "their original Confluence source_url. Wiki hubs include source_pages for "
                    "the raw Confluence pages they synthesize."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Page ID (digits) for raw pages, slug for wiki hubs.",
                        }
                    },
                    "required": ["id"],
                },
            },
        ]

    # ---- dispatch -----------------------------------------------------------

    def dispatch(self, name: str, tool_input: dict[str, Any]) -> ToolResult:
        if name == "read_index":
            return self._read_index(tool_input.get("path") or "")
        if name == "list_hubs":
            return self._list_hubs()
        if name == "search":
            return self._search(
                tool_input.get("query") or "",
                top_k=int(tool_input.get("top_k") or 5),
            )
        if name == "read_page":
            return self._read_page(tool_input.get("id") or "")
        return ToolResult(
            text=f"ERROR: unknown tool '{name}'",
            summary=f"error: unknown tool {name!r}",
        )

    # ---- individual tools ---------------------------------------------------

    def _read_index(self, path: str) -> ToolResult:
        o = self._by_relpath.get(path)
        if not o:
            avail = ", ".join(sorted(self._by_relpath.keys()))
            return ToolResult(
                text=f"ERROR: no orientation file at '{path}'. Available: {avail}",
                summary=f"miss: {path}",
            )
        return ToolResult(
            text=f"# {o.title}\n\n(orientation file: {o.relpath})\n\n{o.body}",
            summary=f"{o.relpath} ({len(o.body)} chars)",
        )

    def _list_hubs(self) -> ToolResult:
        if not self.wiki_hubs:
            return ToolResult(text="No reviewed wiki hubs available.", summary="0 hubs")
        items = []
        for w in self.wiki_hubs:
            slug = Path(w.filename).stem
            when_to_use = self._extract_when_to_use(w.body)
            items.append({
                "title": w.title,
                "slug": slug,
                "synthesizes": w.synthesizes,
                "source_pages": self._source_pages_for_hub(w),
                "status": w.status,
                "when_to_use": when_to_use,
            })
        return ToolResult(
            text=json.dumps(items, indent=2),
            summary=f"{len(items)} hubs: " + ", ".join(i["slug"] for i in items),
        )

    @staticmethod
    def _extract_when_to_use(body: str) -> str:
        """Pull the 'When to use this hub' section if present, else first 2 paragraphs."""
        m = re.search(
            r"#+\s*When to use[^\n]*\n+([\s\S]*?)(?=\n#+\s|\Z)",
            body,
            flags=re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()[:600]
        paras = [p.strip() for p in body.split("\n\n") if p.strip()][:2]
        return "\n\n".join(paras)[:600]

    def _search(self, query: str, top_k: int = 5) -> ToolResult:
        q_terms = set(_tokenize(query))
        if not q_terms:
            return ToolResult(text="[]", summary=f"empty-query: {query!r}")

        hits: list[dict[str, Any]] = []

        for p in self.raw_pages:
            title_tokens = _tokenize(p.title)
            body_tokens = _tokenize(p.body)
            title_match = sum(1 for t in title_tokens if t in q_terms)
            body_match = sum(1 for t in body_tokens if t in q_terms)
            covered = q_terms & set(title_tokens + body_tokens)
            if not covered:
                continue
            coverage = len(covered) / len(q_terms)
            score = (3 * title_match + body_match) * (0.5 + 0.5 * coverage)
            hits.append({
                "id": p.page_id,
                "title": p.title,
                "source_url": p.source_url,
                "snippet": _snippet(p.body, q_terms),
                "score": round(score, 2),
                "layer": "raw",
                "path": p.path,
            })

        for w in self.wiki_hubs:
            slug = Path(w.filename).stem
            title_tokens = _tokenize(w.title)
            body_tokens = _tokenize(w.body)
            title_match = sum(1 for t in title_tokens if t in q_terms)
            body_match = sum(1 for t in body_tokens if t in q_terms)
            covered = q_terms & set(title_tokens + body_tokens)
            if not covered:
                continue
            coverage = len(covered) / len(q_terms)
            # Small wiki boost — hubs are synthesis-by-design and answer
            # cross-cutting questions canonically.
            score = (3 * title_match + body_match) * (0.5 + 0.5 * coverage) * 1.15
            hits.append({
                "id": slug,
                "title": w.title,
                "source_pages": self._source_pages_for_hub(w),
                "snippet": _snippet(w.body, q_terms),
                "score": round(score, 2),
                "layer": "wiki",
                "path": f"wiki/{w.filename}",
            })

        hits.sort(key=lambda h: -h["score"])
        top = hits[:top_k]
        summary = (
            f"query={query!r} → {len(top)} hits: "
            + ", ".join(f"{h['id']}({h['layer']},{h['score']})" for h in top)
            if top
            else f"query={query!r} → 0 hits"
        )
        return ToolResult(text=json.dumps(top, indent=2), summary=summary)

    def _read_page(self, ident: str) -> ToolResult:
        ident = ident.strip()
        if not ident:
            return ToolResult(text="ERROR: empty id", summary="empty id")
        if ident.isdigit():
            p = self._by_page_id.get(ident)
            if not p:
                return ToolResult(
                    text=f"ERROR: no raw page with page_id={ident!r}",
                    summary=f"miss: raw {ident}",
                )
            header = (
                f"page_id: {p.page_id}\n"
                f"title: {p.title}\n"
                f"source_url: {p.source_url}\n"
                f"ancestor_path: {' / '.join(p.ancestor_path)}\n"
                f"layer: raw\n"
            )
            return ToolResult(
                text=f"---\n{header}---\n\n# {p.title}\n\n{p.body}",
                summary=f"raw {p.page_id} {p.title!r} ({len(p.body)} chars)",
            )
        w = self._by_slug.get(ident)
        if not w:
            return ToolResult(
                text=(
                    f"ERROR: no wiki hub with slug={ident!r}. "
                    f"Known slugs: {', '.join(sorted(self._by_slug.keys()))}"
                ),
                summary=f"miss: wiki {ident}",
            )
        header = (
            f"slug: {Path(w.filename).stem}\n"
            f"title: {w.title}\n"
            f"synthesizes: {w.synthesizes}\n"
            f"source_pages: {json.dumps(self._source_pages_for_hub(w), ensure_ascii=False)}\n"
            f"status: {w.status}\n"
            f"layer: wiki\n"
        )
        return ToolResult(
            text=f"---\n{header}---\n\n# {w.title}\n\n{w.body}",
            summary=f"wiki {Path(w.filename).stem} ({len(w.body)} chars)",
        )
