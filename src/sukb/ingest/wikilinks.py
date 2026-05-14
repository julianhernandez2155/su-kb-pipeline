"""<ac:link> resolution — converts Confluence page references to Obsidian wikilinks.

Spec §4.6 canonical form: [[<page-id> - <title>]]. Out-of-corpus refs degrade
to `[title](source_url)` rather than emit a broken wikilink.

In v1 (single-space ITSAI), cross-space resolution doesn't fire but the code
path exists so v1.5 (CDI added) exercises it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote_plus

from .frontmatter import sanitize_filename_title


# Public host every degraded link points back to (spec §1 item 5).
PUBLIC_HOST = "https://answers.atlassian.syr.edu"


@dataclass
class CorpusIndex:
    """Maps page identifiers we know about to their canonical wikilink target."""

    # page_id -> (title, space_key, source_url)
    pages_by_id: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    # (space_key, title) -> page_id
    pages_by_title: dict[tuple[str, str], str] = field(default_factory=dict)

    def register(self, page_id: str, title: str, space_key: str, source_url: str) -> None:
        self.pages_by_id[page_id] = (title, space_key, source_url)
        self.pages_by_title[(space_key, title)] = page_id
        # Also register under empty-space-key so title-only lookups work
        self.pages_by_title[("", title)] = page_id


class DefaultLinkResolver:
    """LinkResolver impl used by macros + walker."""

    def __init__(
        self,
        corpus: CorpusIndex,
        current_space_key: str,
        current_page_id: str,
        attachments_subpath: str = "attachments",
    ) -> None:
        self.corpus = corpus
        self.current_space_key = current_space_key
        self.current_page_id = current_page_id
        self.attachments_subpath = attachments_subpath

    def resolve_page_link(self, content_title: str | None, space_key: str | None, page_id: str | None) -> str:
        # 1. If we know the page_id outright, prefer that.
        if page_id and page_id in self.corpus.pages_by_id:
            title, _, _ = self.corpus.pages_by_id[page_id]
            return f"[[{page_id} - {sanitize_filename_title(title)}]]"

        # 2. Look up by (space_key, title) — prefer current space, then provided, then global.
        if content_title:
            for sk in (self.current_space_key, space_key or "", ""):
                if sk is None:
                    continue
                pid = self.corpus.pages_by_title.get((sk, content_title))
                if pid:
                    title, _, _ = self.corpus.pages_by_id[pid]
                    return f"[[{pid} - {sanitize_filename_title(title)}]]"

        # 3. Out of corpus — degrade to a real external link, not a placeholder
        # anchor. Spec §4.6: `[title](source_url)`. We don't know the target
        # page_id without an API call (= per-link cost), so the source_url is a
        # Confluence search URL scoped to the originating space + title. This
        # always loads somewhere useful — the spec's "zero broken wikilinks"
        # bar — while avoiding an N+1 API round-trip during conversion.
        if content_title:
            target_space = space_key or self.current_space_key
            params = f"text={quote_plus(content_title)}"
            if target_space:
                params += f"&spaceKey={quote_plus(target_space)}"
            return f"[{content_title}]({PUBLIC_HOST}/wiki/search?{params})"
        return f"[link]({PUBLIC_HOST}/wiki)"

    def resolve_attachment(self, page_id: str, filename: str) -> str:
        return f"{self.attachments_subpath}/{page_id}/{filename}"
