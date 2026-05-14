"""Config + three-knob inclusion logic (spec §4.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sukb.config import SyncConfig


@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    yaml_text = """
space_categories:
  ITSAI: knowledge-bases
  CDIAPPS: knowledge-bases
  ITHELP: its
default_space_category: uncategorized
min_pages_threshold: 5
include_keys:
  - COMPOFFC
excluded_keys:
  - T002
  - INFRASB
enabled_keys:
  - ITSAI
output_dir: ./output
api_base: https://su-jsm.atlassian.net/wiki/api/v2
rate_limit_per_sec: 4
inventory_path: ./inv.json
"""
    p = tmp_path / "sync_config.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    (tmp_path / "inv.json").write_text("[]", encoding="utf-8")
    return p


def test_three_knob_inclusion_threshold(cfg_path):
    cfg = SyncConfig.load(cfg_path)
    # Above threshold: included
    assert cfg.is_included("ITSAI", 32) is True
    assert cfg.is_included("ITHELP", 342) is True
    # Below threshold AND not in include_keys: excluded
    assert cfg.is_included("HMPID", 0) is False
    # Below threshold BUT explicitly included: included
    assert cfg.is_included("COMPOFFC", 4) is True
    # Excluded always wins
    assert cfg.is_included("T002", 100) is False
    assert cfg.is_included("INFRASB", 100) is False


def test_category_resolution(cfg_path):
    cfg = SyncConfig.load(cfg_path)
    assert cfg.category_for("ITSAI") == "knowledge-bases"
    assert cfg.category_for("ITHELP") == "its"
    assert cfg.category_for("UNKNOWN") == "uncategorized"


def test_enabled_gating(cfg_path):
    cfg = SyncConfig.load(cfg_path)
    assert cfg.is_enabled("ITSAI") is True
    assert cfg.is_enabled("CDIAPPS") is False  # v1 only enables ITSAI
