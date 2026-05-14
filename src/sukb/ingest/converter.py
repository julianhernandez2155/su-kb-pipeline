"""Storage XML → Markdown converter (spec §4.3).

Recursive walker. Dispatches:
  - <ac:structured-macro> → macros.MACRO_HANDLERS
  - <ac:adf-extension>     → adf.render_adf or recursive walk of <ac:adf-fallback>
  - <ac:link>, <ac:image>  → LinkResolver
  - HTML elements          → Markdown equivalents
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from lxml import etree

from . import adf as adf_mod
from .macros import (
    MACRO_HANDLERS,
    NS,
    UNKNOWN_MACRO_HANDLER,
    WalkerContext,
    ac,
    ri,
)
from .wikilinks import DefaultLinkResolver

# Block-level HTML tags — separated by blank line in output.
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "blockquote", "pre", "hr", "div"}

# Legacy Confluence emoticons → Unicode. Source has these as `:blue-star:` etc.
# which Obsidian doesn't render. Keep the list to the genuinely common ones —
# anything not mapped falls through to the `:shortcode:` form.
_LEGACY_EMOTICON_MAP = {
    "smile": "🙂", "sad": "🙁", "cheeky": "😛", "laugh": "😄", "wink": "😉",
    "thumbs-up": "👍", "thumbs-down": "👎",
    "information": "ℹ️", "tick": "✅", "cross": "❌", "warning": "⚠️",
    "plus": "➕", "minus": "➖", "question": "❓",
    "light-on": "💡", "light-off": "🔦",
    "yellow-star": "⭐", "red-star": "⭐", "green-star": "🌟", "blue-star": "⭐", "star": "⭐",
    "heart": "❤️", "heart-broken": "💔",
}


@dataclass
class ConversionResult:
    markdown: str
    warnings: list[str]
    used_adf: bool


def _wrap_storage(xml_fragment: str) -> etree._Element:
    """Wrap a storage-XML fragment in a namespaced root so lxml can parse it."""
    wrapped = (
        '<root xmlns:ac="http://atlassian.com/content" '
        'xmlns:ri="http://atlassian.com/resource/identifier">'
        f"{xml_fragment}"
        "</root>"
    )
    parser = etree.XMLParser(recover=True, huge_tree=True)
    return etree.fromstring(wrapped.encode("utf-8"), parser=parser)


def convert_page(
    storage_xml: str,
    page_id: str,
    space_key: str,
    link_resolver: DefaultLinkResolver,
    children_for_page: list[dict[str, str]] | None = None,
) -> ConversionResult:
    """Top-level convert. Returns (markdown, warnings, used_adf)."""
    root = _wrap_storage(storage_xml or "")
    used_adf = adf_mod.page_uses_adf(root)

    ctx = WalkerContext(
        page_id=page_id,
        space_key=space_key,
        convert_children=lambda el: _walk(el, ctx),  # closure recursion
        link_resolver=link_resolver,
    )
    # Side-channel: pass children list to children macro handler
    setattr(ctx, "_children_for_page", children_for_page or [])

    md = _walk(root, ctx)
    md = _normalize(md)
    return ConversionResult(markdown=md, warnings=ctx.warnings, used_adf=used_adf)


# --- walker --------------------------------------------------------------------


def _walk(el: etree._Element, ctx: WalkerContext) -> str:
    out: list[str] = []
    if el.text:
        out.append(_escape_inline(el.text))
    for child in el:
        out.append(_handle_element(child, ctx))
        if child.tail:
            out.append(_escape_inline(child.tail))
    return "".join(out)


def _handle_element(el: etree._Element, ctx: WalkerContext) -> str:
    tag = el.tag
    if not isinstance(tag, str):
        return ""

    # Comments, processing instructions
    if tag is etree.Comment or tag is etree.ProcessingInstruction:
        return ""

    # ac: / ri: namespaced
    if tag.startswith("{" + NS["ac"] + "}"):
        return _handle_ac(el, ctx)
    if tag.startswith("{" + NS["ri"] + "}"):
        # Most ri:* elements are inside ac:link / ac:image and handled there.
        return ""

    # Plain HTML
    local = etree.QName(tag).localname.lower()
    handler = _HTML_HANDLERS.get(local, _html_passthrough)
    return handler(el, ctx)


def _handle_ac(el: etree._Element, ctx: WalkerContext) -> str:
    local = etree.QName(el.tag).localname

    if local == "structured-macro":
        name = el.get(ac("name")) or ""
        handler = MACRO_HANDLERS.get(name, UNKNOWN_MACRO_HANDLER)
        return handler(el, ctx)

    if local == "link":
        return _handle_link(el, ctx)

    if local == "image":
        return _handle_image(el, ctx)

    if local == "adf-extension" or local == "adf-node":
        return _handle_adf_extension(el, ctx)

    if local in {"placeholder"}:
        return ""

    if local == "inline-comment-marker":
        # Strip review markers, walk children (the actual content lives inside)
        return _walk(el, ctx)

    if local == "task-list":
        return _handle_task_list(el, ctx)

    if local == "task":
        return _handle_task(el, ctx)

    if local == "emoticon":
        name = el.get(ac("name")) or el.get(ac("emoji-shortname")) or ""
        if not name:
            return ""
        # Map common Confluence emoticon shortnames to Unicode. Obsidian
        # doesn't render `:shortcode:` natively, and the source has these
        # everywhere (decorative bullets, section headers). Keep the map
        # small and obvious — not a full emoji subsystem.
        return _LEGACY_EMOTICON_MAP.get(name, f":{name}:")

    # adf-fallback, parameter, etc. — walk through transparently
    return _walk(el, ctx)


def _handle_adf_extension(el: etree._Element, ctx: WalkerContext) -> str:
    """Fallback-first ADF conversion (spec §4.3a)."""
    fallback = el.find(f".//{ac('adf-fallback')}")
    if fallback is not None and (
        (fallback.text and fallback.text.strip()) or len(list(fallback)) > 0
    ):
        return _walk(fallback, ctx)

    content_el = el.find(f".//{ac('adf-content')}")
    if content_el is None:
        return _walk(el, ctx)
    raw = (content_el.text or "").strip() or "".join(content_el.itertext()).strip()
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        # Hard fail — content would be silently dropped (spec §4.3 strictness).
        raise ValueError(f"ADF content failed to parse: {e}") from e
    return adf_mod.render_adf(payload) + "\n"


def _handle_link(el: etree._Element, ctx: WalkerContext) -> str:
    ri_page = el.find(ri("page"))
    ri_attachment = el.find(ri("attachment"))
    body_el = el.find(ac("link-body"))
    if body_el is None:
        body_el = el.find(ac("plain-text-link-body"))
    body_text = ("".join(body_el.itertext()).strip() if body_el is not None else "") or None

    if ri_page is not None:
        title = ri_page.get(ri("content-title"))
        space_key = ri_page.get(ri("space-key"))
        link = ctx.link_resolver.resolve_page_link(title, space_key, None)
        if body_text and body_text != title and link.startswith("[["):
            # [[id - title|display]] — escape | for YAML safety not needed here
            return link[:-2] + f"|{body_text}]]"
        return link

    if ri_attachment is not None:
        filename = ri_attachment.get(ri("filename")) or ""
        if not filename:
            ctx.warnings.append("ri:attachment with no filename")
            return body_text or ""
        path = ctx.link_resolver.resolve_attachment(ctx.page_id, filename)
        display = body_text or filename
        return f"[{display}]({path})"

    # External anchor (<ac:link href="...">) or plain
    href = el.get(ac("anchor")) or el.get("href") or ""
    if href and body_text:
        return f"[{body_text}]({href})"
    return body_text or ""


def _handle_image(el: etree._Element, ctx: WalkerContext) -> str:
    """`<ac:image>` always emits at block level. Trailing `\\n\\n` keeps
    Markdown's block-break rule honoured: in Confluence the source pattern
    `<ac:image/><p>caption</p>` or `<ac:image/><table>...</table>` renders the
    image and the next block as separate visual blocks. Without the trailing
    break, the embed runs into the next block on the same line. `_normalize`
    collapses overrun newlines, so this is safe even when the image is the
    last element on the page."""
    ri_att = el.find(ri("attachment"))
    ri_url = el.find(ri("url"))
    width = el.get(ac("width"))
    alt = el.get(ac("alt")) or ""

    if ri_att is not None:
        filename = ri_att.get(ri("filename")) or ""
        if not filename:
            ctx.warnings.append("ri:attachment image with no filename")
            return ""
        path = ctx.link_resolver.resolve_attachment(ctx.page_id, filename)
        size_suffix = f"|{width}" if width else ""
        return f"![[{path}{size_suffix}]]\n\n"

    if ri_url is not None:
        url = ri_url.get(ri("value")) or ""
        return f"![{alt}]({url})\n\n"

    return ""


def _handle_task_list(el: etree._Element, ctx: WalkerContext) -> str:
    body = _walk(el, ctx)
    return body + "\n"


def _handle_task(el: etree._Element, ctx: WalkerContext) -> str:
    status_el = el.find(ac("task-status"))
    body_el = el.find(ac("task-body"))
    done = (status_el is not None) and (status_el.text or "").strip().lower() == "complete"
    body = _walk(body_el, ctx) if body_el is not None else ""
    return f"- [{'x' if done else ' '}] {body.strip()}\n"


# --- HTML handlers -------------------------------------------------------------


def _heading(level: int):
    def _h(el: etree._Element, ctx: WalkerContext) -> str:
        return f"\n{'#' * level} {_walk(el, ctx).strip()}\n\n"
    return _h


def _para(el: etree._Element, ctx: WalkerContext) -> str:
    body = _walk(el, ctx).strip()
    return body + "\n\n" if body else ""


def _strong(el: etree._Element, ctx: WalkerContext) -> str:
    inner = _walk(el, ctx).strip()
    return f"**{inner}**" if inner else ""


def _em(el: etree._Element, ctx: WalkerContext) -> str:
    inner = _walk(el, ctx).strip()
    return f"*{inner}*" if inner else ""


def _code(el: etree._Element, ctx: WalkerContext) -> str:
    inner = "".join(el.itertext())
    return f"`{inner}`"


def _del_(el: etree._Element, ctx: WalkerContext) -> str:
    return f"~~{_walk(el, ctx).strip()}~~"


def _br(el: etree._Element, ctx: WalkerContext) -> str:
    return "  \n"


def _hr(el: etree._Element, ctx: WalkerContext) -> str:
    return "\n---\n"


def _pre(el: etree._Element, ctx: WalkerContext) -> str:
    inner = "".join(el.itertext())
    return f"\n```\n{inner.rstrip()}\n```\n"


def _blockquote(el: etree._Element, ctx: WalkerContext) -> str:
    body = _walk(el, ctx).strip()
    return "\n".join("> " + line if line else ">" for line in body.splitlines()) + "\n"


def _list(ordered: bool):
    def _l(el: etree._Element, ctx: WalkerContext) -> str:
        lines: list[str] = []
        for i, li in enumerate(el.findall("li"), start=1):
            body = _walk(li, ctx).strip()
            first, *rest = body.split("\n") if body else [""]
            prefix = f"{i}." if ordered else "-"
            lines.append(f"{prefix} {first}")
            for line in rest:
                lines.append(f"   {line}" if ordered else f"  {line}")
        return "\n".join(lines) + "\n\n"
    return _l


def _anchor(el: etree._Element, ctx: WalkerContext) -> str:
    href = el.get("href") or ""
    body = _walk(el, ctx).strip() or href
    if not href:
        return body
    # Confluence stores bare-URL links as `<a href="X">X</a>`. The literal
    # `[X](X)` form is technically correct Markdown but adds visual + index
    # noise; collapse to the autolink form when text == href.
    if body == href:
        return f"<{href}>"
    return f"[{body}]({href})"


def _img(el: etree._Element, ctx: WalkerContext) -> str:
    src = el.get("src") or ""
    alt = el.get("alt") or ""
    return f"![{alt}]({src})"


def _table(el: etree._Element, ctx: WalkerContext) -> str:
    rows: list[list[str]] = []
    is_header = []
    for tr in el.iter("tr"):
        cells = []
        header_row = False
        for cell in tr:
            ctag = etree.QName(cell.tag).localname.lower()
            if ctag == "th":
                header_row = True
            cells.append(_walk(cell, ctx).strip().replace("\n", " ").replace("|", "\\|"))
        if cells:
            rows.append(cells)
            is_header.append(header_row)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    # Use the first row as the header if no row was th-marked
    header_idx = is_header.index(True) if any(is_header) else 0
    header = rows[header_idx]
    body_rows = rows[:header_idx] + rows[header_idx + 1:]
    sep = "| " + " | ".join("---" for _ in range(width)) + " |"
    lines = [
        "| " + " | ".join(header) + " |",
        sep,
        *("| " + " | ".join(r) + " |" for r in body_rows),
    ]
    return "\n".join(lines) + "\n\n"


def _html_passthrough(el: etree._Element, ctx: WalkerContext) -> str:
    # Walk children; emit text as-is. Unknown tags lose presentation, keep content.
    return _walk(el, ctx)


_HTML_HANDLERS = {
    "p": _para,
    "h1": _heading(1),
    "h2": _heading(2),
    "h3": _heading(3),
    "h4": _heading(4),
    "h5": _heading(5),
    "h6": _heading(6),
    "strong": _strong,
    "b": _strong,
    "em": _em,
    "i": _em,
    "code": _code,
    "del": _del_,
    "s": _del_,
    "strike": _del_,
    "br": _br,
    "hr": _hr,
    "pre": _pre,
    "blockquote": _blockquote,
    "ul": _list(False),
    "ol": _list(True),
    "a": _anchor,
    "img": _img,
    "table": _table,
}


# --- post-processing -----------------------------------------------------------


def _escape_inline(text: str) -> str:
    if not text:
        return ""
    return text


def _normalize(md: str) -> str:
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    return md.strip() + "\n"
