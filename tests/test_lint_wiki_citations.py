"""Tests for `scripts/lint_wiki_citations.py`.

Phase 1 / Phase 3 (2026-05-19). Two layers of coverage:
  1. Unit tests against synthetic fixtures (controls error/warning surfaces).
  2. Regression test against the real `output/` corpus — fails if any wiki
     hub references a missing raw page (the F-10 follow-up's whole point).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINT_SCRIPT = PROJECT_ROOT / "scripts" / "lint_wiki_citations.py"


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("lint_wiki_citations", LINT_SCRIPT)
    assert spec and spec.loader, "could not load lint_wiki_citations.py spec"
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_wiki_citations"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lint_mod():
    return _load_lint_module()


def _write_raw(raw_dir: Path, pid: str, title: str = "x") -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{pid} - {title}.md").write_text(
        "---\npage_id: '" + pid + "'\n---\nbody\n",
        encoding="utf-8",
    )


def _write_hub(wiki_dir: Path, name: str, body: str, synthesizes: list[str] | None = None) -> None:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    fm = ["---", "title: hub", "type: hub", "status: reviewed"]
    if synthesizes is not None:
        fm.append("synthesizes:")
        for pid in synthesizes:
            fm.append(f"  - {pid}")
    fm.append("---")
    fm.append("")
    fm.append(body)
    (wiki_dir / f"{name}.md").write_text("\n".join(fm) + "\n", encoding="utf-8")


def test_lint_passes_when_all_citations_resolve(tmp_path, lint_mod):
    raw = tmp_path / "raw"
    wiki = tmp_path / "wiki"
    _write_raw(raw, "100")
    _write_raw(raw, "200")
    _write_hub(
        wiki, "hub-a",
        body="Claim [[100]]. Other [[200]].",
        synthesizes=["100", "200"],
    )
    rc = lint_mod.main(["--wiki-dir", str(wiki), "--raw-dir", str(raw)])
    assert rc == 0


def test_lint_flags_missing_inline_citation(tmp_path, lint_mod, capsys):
    raw = tmp_path / "raw"
    wiki = tmp_path / "wiki"
    _write_raw(raw, "100")
    _write_hub(
        wiki, "hub-bad",
        body="Real cite [[100]]. Phantom cite [[9999]].",
        synthesizes=["100"],
    )
    rc = lint_mod.main(["--wiki-dir", str(wiki), "--raw-dir", str(raw)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "[[9999]]" in out


def test_lint_flags_missing_synthesizes_entry(tmp_path, lint_mod, capsys):
    raw = tmp_path / "raw"
    wiki = tmp_path / "wiki"
    _write_raw(raw, "100")
    _write_hub(
        wiki, "hub-missing-syn",
        body="cite [[100]]",
        synthesizes=["100", "9999"],  # 9999 doesn't exist
    )
    rc = lint_mod.main(["--wiki-dir", str(wiki), "--raw-dir", str(raw)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "9999" in out


def test_lint_warns_when_inline_not_in_synthesizes(tmp_path, lint_mod, capsys):
    raw = tmp_path / "raw"
    wiki = tmp_path / "wiki"
    _write_raw(raw, "100")
    _write_raw(raw, "200")
    _write_hub(
        wiki, "hub-undeclared",
        body="declared [[100]]. undeclared [[200]].",
        synthesizes=["100"],  # 200 is cited inline but not declared
    )
    # Default (non-strict): exit 0, warning surfaced
    rc = lint_mod.main(["--wiki-dir", str(wiki), "--raw-dir", str(raw)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[[200]]" in out
    # Strict mode: warning escalates to failure
    rc_strict = lint_mod.main(["--wiki-dir", str(wiki), "--raw-dir", str(raw), "--strict"])
    assert rc_strict == 1


def test_lint_ignores_index_files(tmp_path, lint_mod):
    raw = tmp_path / "raw"
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    # index.md with a broken citation should be ignored
    (wiki / "index.md").write_text("---\n---\n[[9999]]\n", encoding="utf-8")
    rc = lint_mod.main(["--wiki-dir", str(wiki), "--raw-dir", str(raw)])
    assert rc == 0


def test_lint_no_failure_when_wiki_dir_absent(tmp_path, lint_mod):
    rc = lint_mod.main([
        "--wiki-dir", str(tmp_path / "nope"),
        "--raw-dir", str(tmp_path / "also-nope"),
    ])
    assert rc == 0


def test_lint_against_real_corpus(lint_mod):
    """Regression guard — the live corpus must stay clean.

    If you add a wiki hub that cites a deleted/renamed raw page, this fails
    in CI. That is the entire point of F-10.
    """
    rc = lint_mod.main([
        "--wiki-dir", str(PROJECT_ROOT / "output" / "wiki"),
        "--raw-dir", str(PROJECT_ROOT / "output" / "raw"),
    ])
    assert rc == 0
