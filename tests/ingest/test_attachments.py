"""Attachment verifier — catches the v1 false-green Codex flagged: emitted
embeds with no files on disk (spec §4.3 acceptance criterion)."""

from __future__ import annotations

from pathlib import Path

from sukb.ingest.attachments import verify_attachment_references


def test_verifier_returns_nothing_when_files_exist(tmp_path: Path):
    root = tmp_path
    (root / "123").mkdir()
    (root / "123" / "diagram.png").write_bytes(b"\x89PNG")
    md = "Some text ![[attachments/123/diagram.png]] more text"
    assert verify_attachment_references(md, root) == []


def test_verifier_flags_missing_image_embed(tmp_path: Path):
    root = tmp_path
    md = "![[attachments/123/missing.png|400]]"
    warnings = verify_attachment_references(md, root)
    assert len(warnings) == 1
    assert "attachments/123/missing.png" in warnings[0]


def test_verifier_flags_missing_file_link(tmp_path: Path):
    root = tmp_path
    md = "Check [policy doc](attachments/456/policy.pdf)"
    warnings = verify_attachment_references(md, root)
    assert any("456/policy.pdf" in w for w in warnings)


def test_verifier_dedupes_repeated_refs(tmp_path: Path):
    root = tmp_path
    md = """
    ![[attachments/123/a.png]]
    later in the doc: ![[attachments/123/a.png]]
    even later: ![[attachments/123/a.png]]
    """
    warnings = verify_attachment_references(md, root)
    assert len(warnings) == 1  # one ref, one warning, not three


def test_verifier_handles_filenames_with_spaces(tmp_path: Path):
    # Confluence filenames frequently contain spaces:
    # "Screenshot 2026-03-10 203239.png". The verifier must treat them as one
    # filename, not truncate at the first space.
    root = tmp_path
    (root / "483525103").mkdir()
    (root / "483525103" / "Screenshot 2026-03-10 203239.png").write_bytes(b"x")
    md = "Header ![[attachments/483525103/Screenshot 2026-03-10 203239.png|652]] body"
    assert verify_attachment_references(md, root) == []

    # Same body but file missing → exactly one warning, with the full name
    (root / "483525103" / "Screenshot 2026-03-10 203239.png").unlink()
    warnings = verify_attachment_references(md, root)
    assert len(warnings) == 1
    assert "Screenshot 2026-03-10 203239.png" in warnings[0]


def test_verifier_handles_filenames_with_parens(tmp_path: Path):
    # Confluence auto-duplicates create names like "image (1).png". Parens must
    # not terminate the filename inside a wikilink (they would inside a markdown
    # link, but the verifier uses separate regexes for the two cases).
    root = tmp_path
    (root / "988774401").mkdir()
    (root / "988774401" / "image (1).png").write_bytes(b"x")
    md = "![[attachments/988774401/image (1).png|400]]"
    assert verify_attachment_references(md, root) == []


def test_verifier_handles_mixed_present_and_missing(tmp_path: Path):
    root = tmp_path
    (root / "1").mkdir()
    (root / "1" / "ok.png").write_bytes(b"x")
    md = "![[attachments/1/ok.png]] and ![[attachments/2/missing.png]]"
    warnings = verify_attachment_references(md, root)
    assert len(warnings) == 1
    assert "2/missing.png" in warnings[0]
