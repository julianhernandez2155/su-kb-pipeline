"""Chat-style query interface over the converted corpus (v1.5, Step 2).

Loads raw Markdown (and optional wiki hubs) from disk, serializes them into a
cached system prompt, sends the user's question to Claude Sonnet 4.6, and
parses out the `[[<page-id>]]` citations the model includes inline.

Design notes:
  - The corpus is static between queries; the corpus block is sent with
    `cache_control: ephemeral` so subsequent queries pay ~10% of the input
    token cost. First query primes the cache.
  - `answer_query` accepts an injectable `client` so tests can run without
    touching the network or needing an API key.
  - Wiki support is best-effort: if `output/wiki/` is missing or empty,
    "raw+wiki" mode degrades gracefully to "raw".
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

from ..config import SyncConfig

MODEL = "claude-sonnet-4-6"
MAX_TOKENS_OUT = 2000

# Sonnet 4.6 pricing (USD per million tokens) — used for the best-effort
# cost estimate returned to the UI. Pricing snapshot: 2026-05.
PRICE_INPUT_PER_MTOK = 3.00
PRICE_OUTPUT_PER_MTOK = 15.00
PRICE_CACHE_WRITE_PER_MTOK = 3.75
PRICE_CACHE_READ_PER_MTOK = 0.30

SYSTEM_INSTRUCTIONS = """\
You are the Syracuse University AI Knowledge Base assistant. You answer \
questions about Syracuse's AI tools, policies, and procedures using ONLY the \
pages in the corpus provided below.

RULES:
1. Every factual claim MUST cite the source page using the `[[<page-id>]]` \
format inline at the end of the sentence. Example: "Claude retains chats for \
2 years [[488210484]]." These wiki-style ids are for backend/admin traceability.
2. If the corpus does not contain enough information to answer the question, \
say so explicitly. Do NOT make up content. Acceptable phrasings: "The corpus \
does not specify..." or "I don't have information on..."
3. If the question requires synthesizing across multiple pages, cite each \
page you draw from.
4. Prefer concise, structured answers. Use bullet points or short paragraphs.
5. End every answer with a "Sources:" section listing each cited page as a \
Markdown link to its original Confluence `source_url`, followed by the trace \
id. Example: "- [Claude FAQ](https://answers.atlassian.syr.edu/...) \
[[488210484]]". The Confluence link is the user-facing citation; the `[[id]]` \
is the backend trace citation.\
"""

# `[[488210484]]` or `[[488210484 - Some Title]]` — capture the leading digits.
CITATION_RE = re.compile(r"\[\[(\d+)(?:\s*-\s*[^\]]+)?\]\]")
# Filenames look like `488210484 - Title.md`.
PAGE_FILE_RE = re.compile(r"^(\d+)\s*-\s*.+\.md$")

# Page-tree segments that flag content-team test fixtures, not real KB articles.
# Excluded from the query corpus by default to avoid eval noise. If Aaron wants
# these in the demo corpus later, plumb a flag through to `load_raw_corpus`.
_TEST_PATH_SEGMENTS = ("(Test)", "Summer Intern 2026")


def _is_test_page(rel_parts: tuple[str, ...]) -> bool:
    """Return True if any path segment or filename marks this as a test page."""
    for part in rel_parts:
        if any(seg in part for seg in _TEST_PATH_SEGMENTS):
            return True
    return False


@dataclass
class RawPage:
    page_id: str
    title: str
    source_url: str
    ancestor_path: list[str]
    body: str
    path: str  # relative to raw_path
    # Phase 1.1 Step 3 (ADR-0009): access classification from the page's
    # frontmatter. Default `unknown` so any page that somehow loads
    # without a v3 frontmatter is treated as restricted by the MCP filter.
    visibility_signal: str = "unknown"

    def to_citation(self) -> dict[str, Any]:
        return {"page_id": self.page_id, "title": self.title, "source_url": self.source_url}


# Public-query allowlist (Phase 1.1 Step 3). Only this exact value is
# queryable via the chat / agentic surfaces. Any other value — including
# `restricted_direct`, `restricted_inherited`, `space_restricted`, `unknown`,
# legacy `accessible_to_sync_user` — is filtered.
PUBLIC_VISIBILITY_SIGNAL = "no_read_restrictions_seen"


@dataclass
class WikiHub:
    title: str
    filename: str  # e.g. "approved-ai-tools-for-university-data.md"
    synthesizes: list[str]
    body: str
    status: str = "draft"
    # Phase 1.1 Step 3 (ADR-0009): tracks the synthesizes IDs that point
    # at restricted (or unknown) raw pages. Hubs with a non-empty value
    # here are EXCLUDED from `load_wiki_corpus` by default — the hub body
    # may contain citations / quoted material from the restricted source.
    restricted_source_ids: list[str] = field(default_factory=list)

    def to_citation(self) -> dict[str, Any]:
        return {"title": self.title, "filename": self.filename, "synthesizes": self.synthesizes}


@dataclass
class OrientationFile:
    """A `CLAUDE.md` or `index.md` that helps the model navigate the corpus.

    Distinct from wiki hubs: orientation files describe relationships and route
    questions; hubs synthesize content with citations. The plan's architectural
    pivot (`next-phase-plan-v2.md`) treats these as load-bearing for the
    agentic-MCP architecture.
    """
    relpath: str  # path relative to output_dir, e.g. "CLAUDE.md" or "raw/knowledge-bases/.../index.md"
    title: str
    body: str


@dataclass
class QueryResult:
    answer: str
    citations: list[dict[str, Any]]
    context_used: dict[str, list[str]]
    cost_usd: float
    latency_ms: int
    mode: str
    raw_pages_loaded: int
    wiki_pages_loaded: int
    orientation_files_loaded: int = 0
    usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- corpus loaders ---------------------------------------------------------


def load_raw_corpus(
    config: SyncConfig,
    max_pages: int | None = None,
    include_test_pages: bool = False,
    include_restricted: bool = False,
) -> list[RawPage]:
    """Walk `config.raw_path` and return every page-id-prefixed Markdown file.

    Skips: (a) hidden dirs like `.meta/`, (b) non-page Markdown files (e.g.
    READMEs without a page-id prefix), and (c) by default:
      - intern/test pages under `(Test) …` or `Summer Intern 2026` — these
        are fixture content that pollutes eval scores (belt-and-braces
        alongside the access classifier per ADR-0007 Step 3).
      - pages whose frontmatter `visibility_signal` is not exactly
        `no_read_restrictions_seen` — restricted, unknown, and legacy
        `accessible_to_sync_user` are all filtered. This is the canonical
        Phase 1.1 Step 3 enforcement layer; ADR-0009.

    Stable order: by ancestor_path then page_id.

    Parameters
    ----------
    include_test_pages
        If True, keep `(Test)` / `Summer Intern 2026` path-segment pages.
        Defaults to False (eval/MCP path).
    include_restricted
        If True, return ALL pages regardless of `visibility_signal`. Use
        only for the puller / probe / admin paths that need to inspect
        restricted content. NEVER True for chat/agentic surfaces — the
        public-query path must be fail-safe.
    """
    root = config.raw_path
    if not root.exists():
        return []

    pages: list[RawPage] = []
    for md in sorted(root.rglob("*.md")):
        rel_parts = md.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        m = PAGE_FILE_RE.match(md.name)
        if not m:
            continue
        if not include_test_pages and _is_test_page(rel_parts):
            continue
        text = md.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        page_id = str(fm.get("page_id") or m.group(1))
        visibility = str(fm.get("visibility_signal") or "unknown")
        if not include_restricted and visibility != PUBLIC_VISIBILITY_SIGNAL:
            continue
        pages.append(
            RawPage(
                page_id=page_id,
                title=str(fm.get("title") or md.stem),
                source_url=str(fm.get("source_url") or ""),
                ancestor_path=list(fm.get("ancestor_path") or []),
                body=body.strip(),
                path=str(md.relative_to(root)),
                visibility_signal=visibility,
            )
        )

    pages.sort(key=lambda p: ("/".join(p.ancestor_path), p.page_id))
    if max_pages is not None and max_pages > 0:
        pages = pages[:max_pages]
    return pages


def load_wiki_corpus(
    config: SyncConfig,
    allowed_raw_ids: set[str] | None = None,
    include_restricted: bool = False,
) -> list[WikiHub]:
    """Walk `output/wiki/` and return reviewed+evergreen hubs.

    Draft hubs are excluded — the wiki-operating-model rule is "human promotes
    before it counts." Non-hub files (`type: index`, etc.) are also excluded
    here; the wiki index is loaded via `load_orientation_files` instead.
    If the wiki directory doesn't exist (Step 2 runs before Step 5), return [].

    Phase 1.1 Step 3 (ADR-0009): when `allowed_raw_ids` is provided, hubs
    are EXCLUDED if any of their `synthesizes` IDs are not in the allowed
    set. The hub body may contain citations or quoted material from the
    restricted source page, so partial filtering is unsafe. Better to drop
    the whole hub than to surface a partially-redacted version that the
    reviewer originally wrote against a different audience.

    The `restricted_source_ids` field on the returned WikiHub objects
    records the synthesizes IDs that were filtered — useful for trace /
    debugging but never surfaced to the model.

    Parameters
    ----------
    allowed_raw_ids
        Set of raw page IDs that ARE queryable (i.e., classified
        `no_read_restrictions_seen`). Usually `{p.page_id for p in
        load_raw_corpus(config)}`. None disables the filter (callers
        running outside the chat surface).
    include_restricted
        If True, return all hubs regardless of restricted source pages.
        Defense-of-last-resort escape hatch for admin/audit paths.
    """
    wiki_root = config.output_dir / "wiki"
    if not wiki_root.exists():
        return []

    hubs: list[WikiHub] = []
    for md in sorted(wiki_root.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        status = str(fm.get("status") or "draft").lower()
        if status not in ("reviewed", "evergreen"):
            continue  # don't expose drafts or deprecated hubs to queries
        if str(fm.get("type") or "hub").lower() != "hub":
            continue  # type: index files are orientation, not hubs

        synthesizes = [str(x) for x in (fm.get("synthesizes") or [])]
        restricted_source_ids: list[str] = []
        if allowed_raw_ids is not None:
            restricted_source_ids = [sid for sid in synthesizes if sid not in allowed_raw_ids]
            if restricted_source_ids and not include_restricted:
                continue  # drop the hub entirely — see docstring

        hubs.append(
            WikiHub(
                title=str(fm.get("title") or md.stem),
                filename=md.name,
                synthesizes=synthesizes,
                body=body.strip(),
                status=status,
                restricted_source_ids=restricted_source_ids,
            )
        )
    return hubs


def load_orientation_files(config: SyncConfig) -> list[OrientationFile]:
    """Return the layered navigation surfaces: `CLAUDE.md` + every `index.md`.

    Loads, in stable order:
      1. `output/CLAUDE.md` (agent rules)
      2. `output/index.md` (global map)
      3. `output/wiki/index.md` (hub map)
      4. every `output/raw/**/index.md` (space-level indexes), sorted by path

    The plan's architectural pivot treats these as load-bearing for the
    agentic MCP shape: they let the model orient before drilling down,
    which is what Step 6 (ceiling eval) and Step 7 (agentic sim) measure.
    Missing files are silently skipped — the corpus can still answer
    questions without them.
    """
    output_dir = config.output_dir
    if not output_dir.exists():
        return []

    files: list[OrientationFile] = []

    def _maybe_load(p: Path) -> None:
        if not p.exists() or not p.is_file():
            return
        text = p.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        title = str(fm.get("title") or "")
        if not title:
            # First H1 from body, else relpath
            for line in body.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        relpath = str(p.relative_to(output_dir)).replace("\\", "/")
        files.append(OrientationFile(relpath=relpath, title=title or relpath, body=body.strip()))

    _maybe_load(output_dir / "CLAUDE.md")
    _maybe_load(output_dir / "index.md")
    _maybe_load(output_dir / "wiki" / "index.md")

    raw_root = output_dir / "raw"
    if raw_root.exists():
        for idx in sorted(raw_root.rglob("index.md")):
            _maybe_load(idx)

    return files


# --- prompt assembly --------------------------------------------------------


def serialize_corpus(
    raw_pages: list[RawPage],
    wiki_pages: list[WikiHub],
    orientation_files: list[OrientationFile] | None = None,
) -> str:
    """Stitch the corpus into the single big text block we cache.

    Order: orientation files → raw pages → wiki hubs. Orientation goes first
    because it's how the model is meant to navigate the rest.
    """
    parts: list[str] = []
    if orientation_files:
        parts.append("=== ORIENTATION FILES ===")
        for o in orientation_files:
            parts.append(
                f"\n--- path: {o.relpath}, title: {o.title} ---\n"
                f"{o.body}\n"
            )
        parts.append("")
    parts.append("=== RAW PAGES ===")
    for p in raw_pages:
        parts.append(
            f"\n--- page_id: {p.page_id}, title: {p.title}, source_url: {p.source_url} ---\n"
            f"{p.body}\n"
        )
    if wiki_pages:
        parts.append("\n=== WIKI HUBS ===")
        for w in wiki_pages:
            syn = ", ".join(w.synthesizes) if w.synthesizes else ""
            parts.append(
                f"\n--- title: {w.title}, synthesizes: [{syn}] ---\n"
                f"{w.body}\n"
            )
    return "\n".join(parts)


def build_messages_payload(
    question: str,
    raw_pages: list[RawPage],
    wiki_pages: list[WikiHub],
    orientation_files: list[OrientationFile] | None = None,
) -> dict[str, Any]:
    """Return the kwargs dict to pass to `client.messages.create`."""
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS_OUT,
        "system": [
            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
            {
                "type": "text",
                "text": serialize_corpus(raw_pages, wiki_pages, orientation_files),
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "messages": [{"role": "user", "content": question}],
    }


# --- citation parsing -------------------------------------------------------


def extract_citations(
    answer: str,
    raw_pages: Iterable[RawPage],
    restricted_page_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Pull `[[<page-id>]]` references from the answer, dedupe, resolve to titles.

    Phase 1.1 Step 3 (ADR-0009): citations that resolve to filtered pages
    are surfaced as `(restricted — not available)` rather than `(unresolved)`.
    This distinguishes a real corpus gap from an access-policy gap for the
    UI / trace, but both forms hide the underlying page's title and URL.

    `restricted_page_ids`, when provided, names IDs we know to be filtered
    by the access classifier. Without it, all unresolved citations are
    surfaced as generic `(unresolved)` — backward-compatible.
    """
    seen: list[str] = []
    by_id = {p.page_id: p for p in raw_pages}
    restricted = restricted_page_ids or set()
    for m in CITATION_RE.finditer(answer):
        pid = m.group(1)
        if pid in seen:
            continue
        seen.append(pid)

    out: list[dict[str, Any]] = []
    for pid in seen:
        p = by_id.get(pid)
        if p:
            out.append(p.to_citation())
        elif pid in restricted:
            # Citation points at a page the access classifier filtered out.
            # Surface a sentinel — never the real title or URL.
            out.append({"page_id": pid, "title": "(restricted — not available)", "source_url": ""})
        else:
            # Citation that doesn't resolve to any page in the corpus.
            out.append({"page_id": pid, "title": "(unresolved)", "source_url": ""})
    return out


# --- cost estimation --------------------------------------------------------


def estimate_cost_usd(usage: dict[str, int]) -> float:
    """Best-effort dollar estimate from a `Usage` object (or dict from one)."""
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    return round(
        (inp * PRICE_INPUT_PER_MTOK
         + out * PRICE_OUTPUT_PER_MTOK
         + cw * PRICE_CACHE_WRITE_PER_MTOK
         + cr * PRICE_CACHE_READ_PER_MTOK) / 1_000_000,
        6,
    )


# --- main entrypoint --------------------------------------------------------


Mode = Literal["raw", "raw+wiki"]


def answer_query(
    question: str,
    config: SyncConfig,
    mode: Mode = "raw+wiki",
    max_pages: int | None = None,
    client: Any | None = None,
) -> QueryResult:
    """Run one question through the corpus. `client` is the Anthropic client;
    if None we construct the default one (which requires ANTHROPIC_API_KEY)."""
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    raw_pages = load_raw_corpus(config, max_pages=max_pages)
    allowed_raw_ids = {p.page_id for p in raw_pages}
    # Discover the restricted set in one extra pass — the chat surface
    # uses this to differentiate restricted citations from unresolved.
    # Cheap (just the same disk walk again with include_restricted=True),
    # and only runs at the chat-request boundary, not per-token.
    all_pages = load_raw_corpus(config, max_pages=max_pages, include_restricted=True)
    restricted_page_ids = {p.page_id for p in all_pages if p.page_id not in allowed_raw_ids}

    wiki_pages = load_wiki_corpus(config, allowed_raw_ids=allowed_raw_ids) if mode == "raw+wiki" else []
    orientation = load_orientation_files(config) if mode == "raw+wiki" else []
    effective_mode = "raw+wiki" if (mode == "raw+wiki" and wiki_pages) else "raw"

    if client is None:
        client = _default_client()

    payload = build_messages_payload(question, raw_pages, wiki_pages, orientation)
    t0 = time.perf_counter()
    response = client.messages.create(**payload)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    answer = _extract_text(response)
    citations = extract_citations(answer, raw_pages, restricted_page_ids=restricted_page_ids)
    usage = _usage_dict(response)
    cost = estimate_cost_usd(usage)

    return QueryResult(
        answer=answer,
        citations=citations,
        context_used={
            "raw_pages": [p.page_id for p in raw_pages],
            "wiki_pages": [w.filename for w in wiki_pages],
            "orientation_files": [o.relpath for o in orientation],
        },
        cost_usd=cost,
        latency_ms=latency_ms,
        mode=effective_mode,
        raw_pages_loaded=len(raw_pages),
        wiki_pages_loaded=len(wiki_pages),
        orientation_files_loaded=len(orientation),
        usage=usage,
    )


def _default_client() -> Any:
    """Lazy-import the Anthropic client so tests don't need the SDK installed."""
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as e:  # pragma: no cover — only hit when SDK missing
        raise RuntimeError(
            "anthropic SDK not installed. `pip install anthropic` and set ANTHROPIC_API_KEY."
        ) from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to .env / environment to use the Query tab."
        )
    return Anthropic()


# --- helpers ----------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, text[m.end():]


def _extract_text(response: Any) -> str:
    """Pull the assistant text out of an Anthropic `Message` (or a dict shim)."""
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if not content:
        return ""
    block = content[0]
    text = getattr(block, "text", None)
    if text is None and isinstance(block, dict):
        text = block.get("text", "")
    return text or ""


def _usage_dict(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {}
    # Both SDK object and dict-shaped fakes are supported.
    if isinstance(usage, dict):
        return {k: int(v or 0) for k, v in usage.items()}
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "cache_creation_input_tokens": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        "cache_read_input_tokens": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
    }
