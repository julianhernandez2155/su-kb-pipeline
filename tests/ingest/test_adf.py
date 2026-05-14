"""ADF pipeline tests — fallback-first + JSON walker (spec §4.3a)."""

from __future__ import annotations

import json

import pytest

from sukb.ingest.adf import render_adf
from sukb.ingest.converter import convert_page


def test_adf_routing_uses_fallback_when_present(resolver):
    body = """<ac:adf-extension>
      <ac:adf-content>{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"json text"}]}]}</ac:adf-content>
      <ac:adf-fallback><p>fallback text</p></ac:adf-fallback>
    </ac:adf-extension>"""
    result = convert_page(body, page_id="999", space_key="ITSAI", link_resolver=resolver)
    assert result.used_adf
    assert "fallback text" in result.markdown
    # JSON path should not also be rendered when fallback is present
    assert "json text" not in result.markdown


def test_adf_routing_walks_json_when_fallback_missing(resolver):
    body = """<ac:adf-extension>
      <ac:adf-content>{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"json only"}]}]}</ac:adf-content>
    </ac:adf-extension>"""
    result = convert_page(body, page_id="999", space_key="ITSAI", link_resolver=resolver)
    assert result.used_adf
    assert "json only" in result.markdown


def test_adf_routing_walks_json_when_fallback_empty(resolver):
    body = """<ac:adf-extension>
      <ac:adf-content>{"type":"doc","content":[{"type":"heading","attrs":{"level":2},"content":[{"type":"text","text":"hello"}]}]}</ac:adf-content>
      <ac:adf-fallback/>
    </ac:adf-extension>"""
    result = convert_page(body, page_id="999", space_key="ITSAI", link_resolver=resolver)
    assert "## hello" in result.markdown


def test_adf_invalid_json_hard_fails(resolver):
    body = """<ac:adf-extension>
      <ac:adf-content>{not valid json</ac:adf-content>
    </ac:adf-extension>"""
    with pytest.raises(ValueError):
        convert_page(body, page_id="999", space_key="ITSAI", link_resolver=resolver)


# --- ADF JSON walker direct tests ----------------------------------------------


def test_adf_paragraph_with_marks():
    doc = {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "bold", "marks": [{"type": "strong"}]},
                {"type": "text", "text": " and "},
                {"type": "text", "text": "italic", "marks": [{"type": "em"}]},
            ],
        }],
    }
    out = render_adf(doc)
    assert "**bold**" in out
    assert "*italic*" in out


def test_adf_panel_node():
    doc = {"type": "doc", "content": [{
        "type": "panel",
        "attrs": {"panelType": "warning"},
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "be careful"}]}],
    }]}
    out = render_adf(doc)
    assert "[!warning]" in out
    assert "be careful" in out


def test_adf_table():
    doc = {"type": "doc", "content": [{
        "type": "table",
        "content": [
            {"type": "tableRow", "content": [
                {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "h1"}]}]},
                {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "h2"}]}]},
            ]},
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "a"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "b"}]}]},
            ]},
        ],
    }]}
    out = render_adf(doc)
    assert "| h1 | h2 |" in out
    assert "| a | b |" in out


def test_adf_task_list():
    doc = {"type": "doc", "content": [{
        "type": "taskList",
        "content": [
            {"type": "taskItem", "attrs": {"state": "DONE"}, "content": [{"type": "text", "text": "done thing"}]},
            {"type": "taskItem", "attrs": {"state": "TODO"}, "content": [{"type": "text", "text": "pending thing"}]},
        ],
    }]}
    out = render_adf(doc)
    assert "- [x] done thing" in out
    assert "- [ ] pending thing" in out


def test_adf_code_block():
    doc = {"type": "doc", "content": [{
        "type": "codeBlock",
        "attrs": {"language": "python"},
        "content": [{"type": "text", "text": "print('x')"}],
    }]}
    out = render_adf(doc)
    assert "```python" in out
    assert "print('x')" in out
