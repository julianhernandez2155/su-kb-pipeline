"""Pytest fixtures + path setup.

Keeps the sukb package importable without `pip install -e .`.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from sukb.ingest.wikilinks import CorpusIndex, DefaultLinkResolver


@pytest.fixture
def corpus() -> CorpusIndex:
    idx = CorpusIndex()
    idx.register("488210484", "Claude FAQ", "ITSAI", "https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/488210484/Claude+FAQ")
    idx.register("836698117", "Copilot FAQ", "ITSAI", "https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/836698117/Copilot+FAQ")
    return idx


@pytest.fixture
def resolver(corpus) -> DefaultLinkResolver:
    return DefaultLinkResolver(corpus=corpus, current_space_key="ITSAI", current_page_id="488210484")
