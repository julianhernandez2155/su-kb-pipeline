"""Config loader for sync_config.yaml + three-knob inclusion logic (spec §4.1)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SyncConfig:
    space_categories: dict[str, str]
    default_space_category: str
    min_pages_threshold: int
    include_keys: list[str]
    excluded_keys: list[str]
    enabled_keys: list[str]
    output_dir: Path
    api_base: str
    rate_limit_per_sec: float
    inventory_path: Path
    raw_path: Path = field(init=False)
    config_path: Path = field(init=False)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> SyncConfig:
        config_path = Path(path).resolve()
        with config_path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}

        base_dir = config_path.parent
        output_dir = (base_dir / data.get("output_dir", "./output")).resolve()
        inventory_path = (base_dir / data["inventory_path"]).resolve() if data.get("inventory_path") else base_dir / "inventory.json"

        cfg = cls(
            space_categories=dict(data.get("space_categories", {})),
            default_space_category=data.get("default_space_category", "uncategorized"),
            min_pages_threshold=int(data.get("min_pages_threshold", 5)),
            include_keys=list(data.get("include_keys", [])),
            excluded_keys=list(data.get("excluded_keys", [])),
            enabled_keys=list(data.get("enabled_keys", [])),
            output_dir=output_dir,
            api_base=data.get("api_base", "https://su-jsm.atlassian.net/wiki/api/v2"),
            rate_limit_per_sec=float(data.get("rate_limit_per_sec", 5)),
            inventory_path=inventory_path,
        )
        cfg.raw_path = output_dir / "raw"
        cfg.config_path = config_path
        return cfg

    def category_for(self, space_key: str) -> str:
        return self.space_categories.get(space_key, self.default_space_category)

    def is_enabled(self, space_key: str) -> bool:
        """UI-level gating — which spaces v1 actually pulls."""
        if not self.enabled_keys:
            return True
        return space_key in self.enabled_keys

    def is_included(self, space_key: str, page_count: int) -> bool:
        """Three-knob inclusion logic (spec §4.1).

        final_include = (page_count >= min_pages_threshold
                         OR key in include_keys)
                         AND key not in excluded_keys
        """
        if space_key in self.excluded_keys:
            return False
        return page_count >= self.min_pages_threshold or space_key in self.include_keys
