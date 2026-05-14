"""Atlassian Document Format (ADF) handling per spec §4.3a.

Fallback-first conversion strategy:
  1. Detect ac:adf-* elements.
  2. If <ac:adf-fallback> is present and non-empty → use it (storage-XML shaped,
     so the §4.3 macro registry applies recursively). Preferred path.
  3. If fallback missing/empty → walk the JSON inside <ac:adf-content>.
  4. If JSON conversion fails → hard fail (dead-letter per strictness boundary).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from lxml import etree

from .macros import NS, ac, render_callout, render_collapsible

ADF_DETECT_PREFIX = "{" + NS["ac"] + "}adf-"


def page_uses_adf(root: etree._Element) -> bool:
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.startswith(ADF_DETECT_PREFIX):
            return True
    return False


def find_fallback(root: etree._Element) -> etree._Element | None:
    """Return the first non-empty <ac:adf-fallback> under root, if any."""
    for el in root.iter(ac("adf-fallback")):
        if (el.text and el.text.strip()) or len(list(el)) > 0:
            return el
    return None


def find_adf_content_json(root: etree._Element) -> list[dict[str, Any]]:
    """Extract every <ac:adf-content> JSON payload, parsed."""
    payloads: list[dict[str, Any]] = []
    for el in root.iter(ac("adf-content")):
        text = (el.text or "").strip()
        if not text:
            continue
        try:
            payloads.append(json.loads(text))
        except json.JSONDecodeError:
            # Some pages embed JSON in a <![CDATA[ ... ]]> child or descendant
            inner = "".join(el.itertext()).strip()
            if inner:
                payloads.append(json.loads(inner))
    return payloads


# --- JSON walker -------------------------------------------------------------


def render_adf(node: dict[str, Any] | list[dict[str, Any]]) -> str:
    """Convert an ADF JSON tree (or doc node) to Markdown."""
    if isinstance(node, list):
        return "\n".join(render_adf(n) for n in node if n)
    if not isinstance(node, dict):
        return ""
    nodetype = node.get("type", "")
    handler = _NODE_HANDLERS.get(nodetype, _unknown_node)
    return handler(node)


def _children_md(node: dict[str, Any], sep: str = "") -> str:
    return sep.join(render_adf(c) for c in node.get("content", []) if c)


def _text_node(node: dict[str, Any]) -> str:
    text = node.get("text", "")
    for mark in node.get("marks", []) or []:
        mtype = mark.get("type")
        if mtype == "strong":
            text = f"**{text}**"
        elif mtype == "em":
            text = f"*{text}*"
        elif mtype == "code":
            text = f"`{text}`"
        elif mtype == "strike":
            text = f"~~{text}~~"
        elif mtype == "link":
            href = (mark.get("attrs") or {}).get("href", "")
            text = f"[{text}]({href})"
    return text


def _doc(node: dict[str, Any]) -> str:
    return _children_md(node, sep="\n\n")


def _paragraph(node: dict[str, Any]) -> str:
    return _children_md(node) + "\n"


def _heading(node: dict[str, Any]) -> str:
    level = int((node.get("attrs") or {}).get("level", 1))
    return f"{'#' * level} {_children_md(node).strip()}\n"


def _bullet_list(node: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in node.get("content", []) or []:
        body = render_adf(item).rstrip("\n")
        first, *rest = body.split("\n") if body else [""]
        lines.append(f"- {first}")
        for line in rest:
            lines.append(f"  {line}")
    return "\n".join(lines) + "\n"


def _ordered_list(node: dict[str, Any]) -> str:
    lines: list[str] = []
    for i, item in enumerate(node.get("content", []) or [], start=1):
        body = render_adf(item).rstrip("\n")
        first, *rest = body.split("\n") if body else [""]
        lines.append(f"{i}. {first}")
        for line in rest:
            lines.append(f"   {line}")
    return "\n".join(lines) + "\n"


def _list_item(node: dict[str, Any]) -> str:
    return _children_md(node).rstrip()


def _table(node: dict[str, Any]) -> str:
    rows: list[list[str]] = []
    for row in node.get("content", []) or []:
        cells = [render_adf(c).replace("\n", " ").strip() for c in row.get("content", []) or []]
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join("---" for _ in range(width)) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows[1:])
    return f"{header}\n{sep}\n{body}\n" if body else f"{header}\n{sep}\n"


def _table_cell(node: dict[str, Any]) -> str:
    return _children_md(node).strip()


def _panel(node: dict[str, Any]) -> str:
    ptype = (node.get("attrs") or {}).get("panelType", "info")
    kind = {"info": "info", "warning": "warning", "note": "note", "error": "warning", "success": "info"}.get(ptype, "note")
    return render_callout(kind, None, _children_md(node))


def _expand(node: dict[str, Any]) -> str:
    title = (node.get("attrs") or {}).get("title")
    return render_collapsible(title, _children_md(node))


def _code_block(node: dict[str, Any]) -> str:
    lang = (node.get("attrs") or {}).get("language", "")
    body = _children_md(node)
    return f"\n```{lang}\n{body.rstrip()}\n```\n"


def _blockquote(node: dict[str, Any]) -> str:
    body = _children_md(node).strip()
    return "\n".join("> " + line if line else ">" for line in body.splitlines()) + "\n"


def _rule(node: dict[str, Any]) -> str:
    return "\n---\n"


def _hard_break(node: dict[str, Any]) -> str:
    return "  \n"


def _media_single(node: dict[str, Any]) -> str:
    for child in node.get("content", []) or []:
        attrs = child.get("attrs") or {}
        alt = attrs.get("alt", "")
        media_id = attrs.get("id") or attrs.get("url", "")
        return f"![{alt}]({media_id})\n"
    return ""


def _inline_card(node: dict[str, Any]) -> str:
    url = (node.get("attrs") or {}).get("url", "")
    return f"<{url}>"


def _mention(node: dict[str, Any]) -> str:
    text = (node.get("attrs") or {}).get("text") or "@user"
    return text


def _emoji(node: dict[str, Any]) -> str:
    return (node.get("attrs") or {}).get("text") or (node.get("attrs") or {}).get("shortName", "")


def _status(node: dict[str, Any]) -> str:
    text = (node.get("attrs") or {}).get("text", "STATUS")
    return f"**[{text.upper()}]**"


def _decision_list(node: dict[str, Any]) -> str:
    lines = [f"- {_children_md(item)}" for item in node.get("content", []) or []]
    return "\n".join(lines) + "\n"


def _task_list(node: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in node.get("content", []) or []:
        state = (item.get("attrs") or {}).get("state", "TODO")
        mark = "x" if state == "DONE" else " "
        lines.append(f"- [{mark}] {_children_md(item).strip()}")
    return "\n".join(lines) + "\n"


def _unknown_node(node: dict[str, Any]) -> str:
    # Tolerant: render children if any, else empty.
    return _children_md(node)


_NODE_HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "doc": _doc,
    "paragraph": _paragraph,
    "text": _text_node,
    "heading": _heading,
    "bulletList": _bullet_list,
    "orderedList": _ordered_list,
    "listItem": _list_item,
    "table": _table,
    "tableRow": lambda n: " | ".join(render_adf(c) for c in n.get("content", []) or []),
    "tableCell": _table_cell,
    "tableHeader": _table_cell,
    "panel": _panel,
    "expand": _expand,
    "nestedExpand": _expand,
    "mediaSingle": _media_single,
    "mediaGroup": _media_single,
    "inlineCard": _inline_card,
    "mention": _mention,
    "emoji": _emoji,
    "status": _status,
    "decisionList": _decision_list,
    "decisionItem": _list_item,
    "taskList": _task_list,
    "taskItem": _list_item,
    "codeBlock": _code_block,
    "blockquote": _blockquote,
    "rule": _rule,
    "hardBreak": _hard_break,
    "blockCard": _inline_card,
}
