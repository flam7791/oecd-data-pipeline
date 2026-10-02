import json
import shutil
from pathlib import Path

import pytest

from oecd_pipeline.config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cfg():
    return load_config(FIXTURES / "test_indicators.toml")


@pytest.fixture
def raw_dir(tmp_path, cfg):
    """A data/raw folder holding the synthetic downloads and their metadata."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    for ind in cfg.indicators:
        src = FIXTURES / f"{ind.id}_20251001T080000Z.csv"
        dst = raw / src.name
        shutil.copy(src, dst)
        dst.with_suffix(".meta.json").write_text(json.dumps({
            "indicator_id": ind.id,
            "url": f"https://example.test/{ind.id}",
            "retrieved_at": "2025-10-01T08:00:00+00:00",
        }))
    return raw
