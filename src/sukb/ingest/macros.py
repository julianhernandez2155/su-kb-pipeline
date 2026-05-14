"""Macro handler registry per pipeline-spec.md v0.4 §4.3.

Recursive walker + flat handler dict (not full visitor pattern). The converter
walks storage XML; whenever it hits <ac:structured-macro ac:name="X">, it
dispatches here. Unknown macros emit a safety callout — never crash.

Adding a new macro = one entry in MACRO_HANDLERS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from lxml import etree

# Confluence storage-XML namespace map. The bodies SU returns prefix elements
# with ac: and ri:; lxml needs the full URIs to query.
NS = {
    "ac": "http://atlassian.com/content",
    "ri": "http://atlassian.com/resource/identifier",
    "atlassian-content": "http://atlassian.com/content",
}


def ac(tag: str) -> str:
    return f"{{{NS['ac']}}}{tag}"


def ri(tag: str) -> str:
    return f"{{{NS['ri']}}}{tag}"


class LinkResolver(Protocol):
    def resolve_page_link(self, content_title: str | None, space_key: str | None, page_id: str | None) -> str: ...
    def resolve_attachment(self, page_id: str, filename: str) -> str: ...


@dataclass
class WalkerContext:
    """Threaded through every handler. Carries the convert function back in
    so handlers can recurse into their own rich-text-body content."""

    page_id: str
    space_key: str
    convert_children: Callable[[etree._Element], str]
    link_resolver: LinkResolver
    warnings: list[str] = field(default_factory=list)


# --- shared emitters (also called by ADF walker) -------------------------------


def render_callout(kind: str, title: str | None, body: str) -> str:
    """Obsidian callout. Used by both Confluence macros and ADF panel/expand.

    Trails a blank line so adjacent callouts don't merge into one giant
    callout block under Obsidian's CommonMark-derived rendering. (`_normalize`
    in converter.py collapses runs of 3+ newlines back to 2, so over-emission
    is safe.)
    """
    header = f"> [!{kind}]"
    if title:
        header += f" {title}"
    body = (body or "").strip()
    if not body:
        return header + "\n\n"
    indented = "\n".join("> " + line if line else ">" for line in body.splitlines())
    return f"{header}\n{indented}\n\n"


def render_collapsible(title: str | None, body: str) -> str:
    """`> [!note]-` — Obsidian collapsed callout. Used by expand macro/node.
    Same trailing-blank-line discipline as render_callout."""
    header = "> [!note]-"
    if title:
        header += f" {title}"
    body = (body or "").strip()
    if not body:
        return header + "\n\n"
    indented = "\n".join("> " + line if line else ">" for line in body.splitlines())
    return f"{header}\n{indented}\n\n"


# --- helpers -------------------------------------------------------------------


def _get_param(macro: etree._Element, name: str) -> str | None:
    for param in macro.findall(ac("parameter")):
        if param.get(ac("name")) == name:
            return (param.text or "").strip() or None
    return None


def _get_body(macro: etree._Element) -> etree._Element | None:
    for body_tag in ("rich-text-body", "plain-text-body"):
        b = macro.find(ac(body_tag))
        if b is not None:
            return b
    return None


def _body_text(macro: etree._Element) -> str:
    """Plain text content of a body — used for code blocks."""
    b = _get_body(macro)
    if b is None:
        return ""
    return "".join(b.itertext())


def _body_markdown(macro: etree._Element, ctx: WalkerContext) -> str:
    b = _get_body(macro)
    if b is None:
        return ""
    return ctx.convert_children(b)


# --- handlers ------------------------------------------------------------------


def info_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    return render_callout("info", _get_param(macro, "title"), _body_markdown(macro, ctx))


def warning_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    return render_callout("warning", _get_param(macro, "title"), _body_markdown(macro, ctx))


def note_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    return render_callout("note", _get_param(macro, "title"), _body_markdown(macro, ctx))


def expand_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    return render_collapsible(_get_param(macro, "title"), _body_markdown(macro, ctx))


def panel_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    """Colored callout. Default-color → [!note]; colored → [!info] or [!quote]
    based on bgColor param (spec §4.3)."""
    bg = (_get_param(macro, "bgColor") or "").lower()
    if not bg:
        kind = "note"
    elif bg in {"#deebff", "#e3fcef", "#fffae6", "#fff0f0", "blue", "green", "yellow"}:
        kind = "info"
    else:
        kind = "quote"
    return render_callout(kind, _get_param(macro, "title"), _body_markdown(macro, ctx))


def anchor_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    """Obsidian block ID `^anchor-name` placed inline. The wikilink form
    `[[<id> - <title>#^name]]` resolves to it."""
    name = _get_param(macro, "") or _get_param(macro, "anchor") or ""
    # First positional <ac:parameter> with no name attribute carries the anchor name
    if not name:
        for param in macro.findall(ac("parameter")):
            if not param.get(ac("name")):
                name = (param.text or "").strip()
                break
    if not name:
        ctx.warnings.append("anchor macro with no name")
        return ""
    return f" ^{name} "


def status_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    title = _get_param(macro, "title") or "STATUS"
    return f"**[{title.upper()}]**"


def code_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    lang = _get_param(macro, "language") or ""
    body = _body_text(macro)
    return f"\n```{lang}\n{body.rstrip()}\n```\n"


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".avif"}


def view_file_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    """`<ac:structured-macro ac:name="view-file">` — Confluence's inline-preview
    macro for an attached file (PDF/DOCX/PS1/...). Proposed in v0.5.

    Shape observed in real SU pages:

        <ac:structured-macro ac:name="view-file">
          <ac:parameter ac:name="name">
            <ri:attachment ri:filename="Install-DevTools.ps1" .../>
          </ac:parameter>
        </ac:structured-macro>

    Emits:
      * Image-ish extensions → `![[attachments/<page-id>/<filename>]]`
      * Everything else      → `[filename](attachments/<page-id>/<filename>)`

    Attachment download + on-disk verification is handled upstream in the
    puller; if the file isn't on disk after the pull, the verifier surfaces
    a `missing attachment` warning.
    """
    name_param: etree._Element | None = None
    for p in macro.findall(ac("parameter")):
        if p.get(ac("name")) == "name":
            name_param = p
            break
    if name_param is None:
        ctx.warnings.append("view-file macro with no name parameter")
        return ""

    ri_att = name_param.find(ri("attachment"))
    if ri_att is None:
        # Some legacy variants put a bare filename string instead of <ri:attachment>
        filename = (name_param.text or "").strip()
    else:
        filename = ri_att.get(ri("filename")) or ""

    if not filename:
        ctx.warnings.append("view-file macro with no filename")
        return ""

    path = ctx.link_resolver.resolve_attachment(ctx.page_id, filename)
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext in _IMAGE_EXTENSIONS:
        return f"![[{path}]]"
    return f"[{filename}]({path})"


def iframe_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    """`<ac:structured-macro ac:name="iframe">` — embedded external content
    (video, dashboard, form). Proposed in v0.5.

    Shape observed in real SU pages:

        <ac:structured-macro ac:name="iframe">
          <ac:parameter ac:name="src"><ri:url ri:value="https://..."/></ac:parameter>
          <ac:parameter ac:name="name">Friendly title</ac:parameter>
          ...
        </ac:structured-macro>

    Emits a callout that preserves the `src` so a reader can manually visit
    the embedded URL. Static Markdown can't render the embed itself.
    """
    src = ""
    title = None
    for p in macro.findall(ac("parameter")):
        pname = p.get(ac("name"))
        if pname == "src":
            ri_url = p.find(ri("url"))
            if ri_url is not None:
                src = ri_url.get(ri("value")) or ""
            else:
                src = (p.text or "").strip()
        elif pname == "name":
            title = (p.text or "").strip() or None

    header = "Embedded iframe"
    if title:
        header += f" — {title}"
    body = f"<{src}>" if src else "(no src attribute)"
    return render_callout("note", header, body)


def page_properties_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    """Promote to frontmatter where keys are known; otherwise emit a table.
    v1: emit the inner body as Markdown (typically a table) — the frontmatter
    promotion happens upstream in frontmatter.py if it pattern-matches.
    """
    body = _body_markdown(macro, ctx).strip()
    if not body:
        return ""
    return body + "\n"


def excerpt_include_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    """`![[<target-id> - <title>#excerpt]]` Obsidian embed; degrade to external
    link if target is out of corpus."""
    target_title = None
    for param in macro.findall(ac("parameter")):
        if param.get(ac("name")) in (None, "", "0"):
            target_title = (param.text or "").strip()
            break
    if not target_title:
        # Newer form nests <ri:page ri:content-title="...">
        ri_page = macro.find(f".//{ri('page')}")
        if ri_page is not None:
            target_title = ri_page.get(ri("content-title"))
    if not target_title:
        ctx.warnings.append("excerpt-include with unresolvable target")
        return ""
    resolved = ctx.link_resolver.resolve_page_link(target_title, None, None)
    if resolved.startswith("[["):
        # Inject #excerpt anchor before closing brackets
        return resolved[:-2] + "#excerpt]]\n"
    return resolved + "\n"


def children_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    """Static snapshot of direct children. The puller injects the list into
    ctx via a side-channel attribute (see converter.py). If absent, emit a
    placeholder rather than firing an API call at conversion time."""
    children = getattr(ctx, "_children_for_page", None) or []
    if not children:
        return "> [!note] Children list (regenerated on sync — empty at conversion time)\n"
    lines = [f"- [[{c['id']} - {c['title']}]]" for c in children]
    return "\n".join(lines) + "\n"


def strip_handler_factory(name: str, placeholder: str | None = None):
    def _handler(macro: etree._Element, ctx: WalkerContext) -> str:
        if placeholder:
            return f"> [!note] {placeholder} — view in Confluence\n"
        return ""
    _handler.__name__ = f"strip_{name}"
    return _handler


def unknown_macro_handler(macro: etree._Element, ctx: WalkerContext) -> str:
    name = macro.get(ac("name")) or "unknown"
    ctx.warnings.append(f"unconverted macro: {name}")
    body = _body_markdown(macro, ctx)
    callout = render_callout("warning", f"Unconverted Confluence macro: `{name}`", body)
    return callout


# --- registry ------------------------------------------------------------------

MACRO_HANDLERS: dict[str, Callable[[etree._Element, WalkerContext], str]] = {
    "info": info_handler,
    "warning": warning_handler,
    "note": note_handler,
    "tip": info_handler,  # legacy alias
    "expand": expand_handler,
    "panel": panel_handler,
    "anchor": anchor_handler,
    "status": status_handler,
    "code": code_handler,
    "page-properties": page_properties_handler,
    "details": page_properties_handler,  # legacy alias used in older spaces
    "excerpt-include": excerpt_include_handler,
    "children": children_handler,
    "view-file": view_file_handler,  # v0.5 — added 2026-05-13
    "iframe": iframe_handler,        # v0.5 — added 2026-05-13
    "toc": strip_handler_factory("toc"),
    "livesearch": strip_handler_factory("livesearch", "Live search widget"),
    "recently-updated": strip_handler_factory("recently-updated", "Recently-updated widget"),
    "listlabels": strip_handler_factory("listlabels", "Pages-by-label widget"),
    "contentbylabel": strip_handler_factory("contentbylabel", "Content-by-label widget"),
}

UNKNOWN_MACRO_HANDLER = unknown_macro_handler
