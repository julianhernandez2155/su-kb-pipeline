"""Wiki citation lint — every `[[<page-id>]]` and `synthesizes:` ID must resolve.

Phase 1 / Phase 3 (2026-05-19). Implements the F-10 followup: ensure wiki hubs
in `output/wiki/` cite real raw pages. A citation that points at a deleted or
renamed page is a silent bug (the hub still reads fine but the link target is
gone). This lint catches that on every CI run.

Checks per wiki file:
  1. Every `[[<digits>]]` (or `[[<digits> - <title>]]`) wikilink resolves to a
     real raw page file `output/raw/.../<digits> - *.md`.
  2. Every page-id listed under the hub's `synthesizes:` frontmatter key
     resolves to a real raw page file.

Exits 0 on success, non-zero on any unresolved citation. Also surfaces
inline-citation page-ids that aren't listed in `synthesizes:` (these are not
fatal but flagged as warnings — per `output/CLAUDE.md`, a hub that cites a
page should declare it).

Usage:
    python scripts/lint_wiki_citations.py
    python scripts/lint_wiki_citations.py --wiki-dir output/wiki --raw-dir output/raw
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


WIKILINK_RE = re.compile(r"\[\[(\d+)(?:\s*-\s*[^\]]+)?\]\]")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_frontmatter(md_path: Path) -> tuple[dict[str, Any] | None, str]:
    """Returns (frontmatter_dict_or_None, body_text_after_frontmatter)."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return None, ""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    body = text[end + 5:]
    try:
        parsed = yaml.safe_load(text[4:end + 1])
    except yaml.YAMLError:
        return None, body
    return (parsed if isinstance(parsed, dict) else None), body


def build_raw_page_id_set(raw_dir: Path) -> set[str]:
    """Returns the set of page-ids reachable as files in raw/."""
    if not raw_dir.exists():
        return set()
    ids: set[str] = set()
    for path in raw_dir.rglob("*.md"):
        if not path.is_file():
            continue
        stem = path.stem  # "<pid> - <title>"
        pid, _sep, _rest = stem.partition(" - ")
        if pid.isdigit():
            ids.add(pid)
    return ids


def check_hub(
    hub_path: Path,
    raw_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings) for one hub file."""
    errors: list[str] = []
    warnings: list[str] = []

    fm, body = parse_frontmatter(hub_path)

    synthesizes_ids: set[str] = set()
    if fm is not None:
        raw_syn = fm.get("synthesizes") or []
        if isinstance(raw_syn, list):
            for item in raw_syn:
                pid = str(item)
                if pid.isdigit():
                    synthesizes_ids.add(pid)
                    if pid not in raw_ids:
                        errors.append(
                            f"synthesizes references missing raw page id={pid}"
                        )
                else:
                    warnings.append(f"synthesizes entry is not a page id: {item!r}")
        else:
            warnings.append("`synthesizes:` is not a list")

    inline_ids: set[str] = set()
    for match in WIKILINK_RE.finditer(body):
        pid = match.group(1)
        inline_ids.add(pid)
        if pid not in raw_ids:
            errors.append(f"wikilink [[{pid}]] does not resolve to a raw page")

    # Inline-cited ids that aren't in synthesizes are a soft warning per
    # `output/CLAUDE.md`: hubs should declare every page they cite.
    if fm is not None:
        for pid in sorted(inline_ids - synthesizes_ids):
            warnings.append(f"inline citation [[{pid}]] not listed in `synthesizes:`")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint wiki hub citations against the raw corpus.")
    parser.add_argument(
        "--wiki-dir",
        type=Path,
        default=_project_root() / "output" / "wiki",
        help="Path to output/wiki/. Defaults to <project>/output/wiki.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=_project_root() / "output" / "raw",
        help="Path to output/raw/. Defaults to <project>/output/raw.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (inline citations missing from synthesizes:).",
    )
    args = parser.parse_args(argv)

    if not args.wiki_dir.exists():
        print(f"wiki dir does not exist: {args.wiki_dir}", file=sys.stderr)
        return 0  # nothing to lint isn't a failure

    raw_ids = build_raw_page_id_set(args.raw_dir)

    total_errors = 0
    total_warnings = 0
    files_checked = 0

    def display(p: Path) -> str:
        try:
            return str(p.relative_to(_project_root()))
        except ValueError:
            return str(p)

    for hub_path in sorted(args.wiki_dir.rglob("*.md")):
        if hub_path.name.lower() in ("index.md",):
            continue  # index files are not hubs
        files_checked += 1
        errors, warnings = check_hub(hub_path, raw_ids)
        for err in errors:
            print(f"ERROR  {display(hub_path)}: {err}")
        for warn in warnings:
            print(f"warn   {display(hub_path)}: {warn}")
        total_errors += len(errors)
        total_warnings += len(warnings)

    print(
        f"\n{files_checked} hub(s) checked: "
        f"{total_errors} error(s), {total_warnings} warning(s).",
        file=sys.stderr,
    )

    if total_errors > 0:
        return 1
    if args.strict and total_warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
