"""Tag inventory — dumps the label/tag distribution across the raw corpus.

Phase 1 / Phase 3 (2026-05-19). Seeds the F-05 work in Aaron's followups:
inventory all existing Confluence labels, see what's in there, and propose a
seed taxonomy. No API calls — reads `output/raw/**/*.md` directly.

Usage:
    python scripts/tag_inventory.py
    python scripts/tag_inventory.py --out research/kb-ingestion-project/tag-inventory-2026-05-19.md
    python scripts/tag_inventory.py --raw-dir output/raw --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_frontmatter(md_path: Path) -> dict[str, Any] | None:
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        parsed = yaml.safe_load(text[4:end + 1])
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def walk_raw_pages(raw_dir: Path) -> list[Path]:
    if not raw_dir.exists():
        return []
    return sorted(p for p in raw_dir.rglob("*.md") if p.is_file())


def collect_labels(pages: list[Path]) -> tuple[Counter[str], dict[str, list[str]]]:
    """Returns (frequency counter, label → list of page_ids that carry it)."""
    counter: Counter[str] = Counter()
    by_label: dict[str, list[str]] = {}
    for page in pages:
        fm = parse_frontmatter(page)
        if not fm:
            continue
        pid = str(fm.get("page_id") or "")
        # tags_original is the v2 schema name; fall back to legacy `labels`
        labels = fm.get("tags_original") or fm.get("labels") or []
        if not isinstance(labels, list):
            continue
        for label in labels:
            if not isinstance(label, str) or not label.strip():
                continue
            counter[label] += 1
            by_label.setdefault(label, []).append(pid)
    return counter, by_label


def render_markdown(counter: Counter[str], by_label: dict[str, list[str]], total_pages: int) -> str:
    lines: list[str] = []
    lines.append("# Tag Inventory")
    lines.append("")
    lines.append(f"_Generated from `output/raw/` — {total_pages} pages scanned._")
    lines.append("")
    lines.append("## Frequency")
    lines.append("")
    if not counter:
        lines.append("_No labels found in the corpus._")
        lines.append("")
        return "\n".join(lines)
    lines.append("| Label | Pages | Page IDs |")
    lines.append("|---|---|---|")
    for label, count in counter.most_common():
        ids = ", ".join(by_label[label])
        lines.append(f"| `{label}` | {count} | {ids} |")
    lines.append("")
    lines.append("## Seed taxonomy notes")
    lines.append("")
    lines.append(
        "This is raw data, not a proposed canonical tag set. To propose a taxonomy: "
        "cluster semantically similar labels, drop one-off labels with no reuse, and "
        "flag inconsistencies (singular vs plural, casing, synonyms). Then check the "
        "proposal against the eval queries to confirm the chosen tags would help "
        "retrieval, not just describe the corpus."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory Confluence labels across the raw corpus.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=_project_root() / "output" / "raw",
        help="Path to output/raw/. Defaults to <project>/output/raw.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write markdown report to this path. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of markdown. Useful for piping into other tools.",
    )
    args = parser.parse_args(argv)

    pages = walk_raw_pages(args.raw_dir)
    counter, by_label = collect_labels(pages)

    if args.json:
        payload = {
            "raw_dir": str(args.raw_dir),
            "pages_scanned": len(pages),
            "labels": [
                {"label": label, "count": count, "page_ids": by_label[label]}
                for label, count in counter.most_common()
            ],
        }
        out = json.dumps(payload, indent=2)
    else:
        out = render_markdown(counter, by_label, total_pages=len(pages))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out, encoding="utf-8")
        print(f"Wrote {args.out} ({len(pages)} pages scanned, {len(counter)} unique labels).", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
