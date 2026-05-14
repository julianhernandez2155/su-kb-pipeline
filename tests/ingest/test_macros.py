"""One unit test per macro handler — acceptance criterion §spec.

Each test wraps the macro XML in a minimal storage-format fragment and asserts
the converter emits the expected Markdown shape.
"""

from __future__ import annotations

import pytest

from sukb.ingest.converter import convert_page


def _convert(body: str, resolver) -> str:
    return convert_page(body, page_id="999", space_key="ITSAI", link_resolver=resolver).markdown


# --- callout-family macros ---------------------------------------------------


def test_info_macro(resolver):
    body = """<ac:structured-macro ac:name="info">
      <ac:rich-text-body><p>Approved AI tools list is in flux.</p></ac:rich-text-body>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[!info]" in out
    assert "Approved AI tools list is in flux." in out


def test_warning_macro(resolver):
    body = """<ac:structured-macro ac:name="warning">
      <ac:parameter ac:name="title">Heads up</ac:parameter>
      <ac:rich-text-body><p>NetID required.</p></ac:rich-text-body>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[!warning] Heads up" in out
    assert "NetID required." in out


def test_note_macro(resolver):
    body = """<ac:structured-macro ac:name="note"><ac:rich-text-body><p>FYI.</p></ac:rich-text-body></ac:structured-macro>"""
    assert "[!note]" in _convert(body, resolver)


def test_expand_macro(resolver):
    body = """<ac:structured-macro ac:name="expand">
      <ac:parameter ac:name="title">Click for details</ac:parameter>
      <ac:rich-text-body><p>hidden body</p></ac:rich-text-body>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[!note]-" in out
    assert "Click for details" in out
    assert "hidden body" in out


def test_panel_default(resolver):
    body = """<ac:structured-macro ac:name="panel"><ac:rich-text-body><p>panel body</p></ac:rich-text-body></ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[!note]" in out
    assert "panel body" in out


def test_panel_colored(resolver):
    body = """<ac:structured-macro ac:name="panel">
      <ac:parameter ac:name="bgColor">#ff8b00</ac:parameter>
      <ac:rich-text-body><p>important</p></ac:rich-text-body>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[!quote]" in out


# --- strip-with-placeholder macros ------------------------------------------


def test_toc_stripped(resolver):
    body = """<ac:structured-macro ac:name="toc"/>"""
    assert _convert(body, resolver).strip() == ""


def test_livesearch_stripped_with_placeholder(resolver):
    body = """<ac:structured-macro ac:name="livesearch"/>"""
    out = _convert(body, resolver)
    assert "Live search widget" in out
    assert "view in Confluence" in out


def test_recently_updated_placeholder(resolver):
    body = """<ac:structured-macro ac:name="recently-updated"/>"""
    assert "Recently-updated widget" in _convert(body, resolver)


def test_listlabels_placeholder(resolver):
    body = """<ac:structured-macro ac:name="listlabels"/>"""
    assert "Pages-by-label widget" in _convert(body, resolver)


# --- structural macros -------------------------------------------------------


def test_anchor_macro_emits_block_id(resolver):
    body = """<ac:structured-macro ac:name="anchor"><ac:parameter>section-a</ac:parameter></ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "^section-a" in out


def test_status_macro(resolver):
    body = """<ac:structured-macro ac:name="status">
      <ac:parameter ac:name="title">in progress</ac:parameter>
    </ac:structured-macro>"""
    assert "**[IN PROGRESS]**" in _convert(body, resolver)


def test_code_macro_with_language(resolver):
    body = """<ac:structured-macro ac:name="code">
      <ac:parameter ac:name="language">python</ac:parameter>
      <ac:plain-text-body>print("hi")</ac:plain-text-body>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "```python" in out
    assert 'print("hi")' in out


def test_page_properties_macro(resolver):
    body = """<ac:structured-macro ac:name="page-properties">
      <ac:rich-text-body><p>owner: aaron</p></ac:rich-text-body>
    </ac:structured-macro>"""
    assert "owner: aaron" in _convert(body, resolver)


def test_excerpt_include_in_corpus(resolver):
    body = """<ac:structured-macro ac:name="excerpt-include">
      <ac:parameter>Claude FAQ</ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "488210484" in out
    assert "#excerpt]]" in out


def test_excerpt_include_out_of_corpus(resolver):
    body = """<ac:structured-macro ac:name="excerpt-include">
      <ac:parameter>Unknown Page Title</ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "Unknown Page Title" in out
    # Out-of-corpus degrades to a non-wikilink link
    assert "[[" not in out or "#unresolved" in out


def test_children_handler_emits_static_list(resolver):
    body = """<ac:structured-macro ac:name="children"/>"""
    # No children supplied → falls back to placeholder, never crashes.
    out = _convert(body, resolver)
    assert "[!note]" in out


# --- v0.5 additions ----------------------------------------------------------


def test_view_file_macro_image(resolver):
    body = """<ac:structured-macro ac:name="view-file">
      <ac:parameter ac:name="name">
        <ri:attachment ri:filename="diagram.png"/>
      </ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "![[attachments/999/diagram.png]]" in out


def test_view_file_macro_pdf(resolver):
    body = """<ac:structured-macro ac:name="view-file">
      <ac:parameter ac:name="name">
        <ri:attachment ri:filename="policy.pdf"/>
      </ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[policy.pdf](attachments/999/policy.pdf)" in out


def test_view_file_macro_powershell_script_like_real_su_page(resolver):
    # Shape verified against page 986841103 (Claude Code Setup) on 2026-05-13.
    body = """<ac:structured-macro ac:name="view-file" ac:schema-version="1">
      <ac:parameter ac:name="name">
        <ri:attachment ri:filename="Install-DevTools.ps1" ri:version-at-save="4"/>
      </ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[Install-DevTools.ps1](attachments/999/Install-DevTools.ps1)" in out


def test_view_file_macro_no_filename_warns(resolver):
    body = """<ac:structured-macro ac:name="view-file"/>"""
    from sukb.ingest.converter import convert_page
    result = convert_page(body, page_id="999", space_key="ITSAI", link_resolver=resolver)
    assert any("view-file" in w for w in result.warnings)


def test_iframe_macro_preserves_src(resolver):
    body = """<ac:structured-macro ac:name="iframe">
      <ac:parameter ac:name="src"><ri:url ri:value="https://example.com/embed"/></ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "[!note]" in out
    assert "Embedded iframe" in out
    assert "<https://example.com/embed>" in out


def test_iframe_macro_with_name(resolver):
    # Shape verified against page 895451142 (Clementine Class Search).
    body = """<ac:structured-macro ac:name="iframe">
      <ac:parameter ac:name="src"><ri:url ri:value="https://video.syr.edu/embed/secure/iframe/..."/></ac:parameter>
      <ac:parameter ac:name="width">100%</ac:parameter>
      <ac:parameter ac:name="name">Clementine Video</ac:parameter>
      <ac:parameter ac:name="height">720</ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "Embedded iframe — Clementine Video" in out
    assert "https://video.syr.edu/embed/secure/iframe/..." in out


def test_iframe_macro_with_bare_src_string(resolver):
    body = """<ac:structured-macro ac:name="iframe">
      <ac:parameter ac:name="src">https://example.com/dashboard</ac:parameter>
    </ac:structured-macro>"""
    out = _convert(body, resolver)
    assert "<https://example.com/dashboard>" in out


def test_unknown_macro_handler_safety_callout(resolver):
    body = """<ac:structured-macro ac:name="totally-bogus-macro-xyz">
      <ac:rich-text-body><p>preserved content</p></ac:rich-text-body>
    </ac:structured-macro>"""
    result = convert_page(body, page_id="999", space_key="ITSAI", link_resolver=resolver)
    assert "[!warning]" in result.markdown
    assert "Unconverted Confluence macro" in result.markdown
    assert "preserved content" in result.markdown
    assert any("unconverted macro" in w for w in result.warnings)
