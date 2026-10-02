"""Stage 3a - Prepare batches for Copilot.

Splits the summary into small CSV files. Each file has the figures for a
set of rows plus two empty columns, `direction` and `note`, which Copilot
fills in by following the saved prompt in prompts/copilot_prompt.md.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

BATCH_COLUMNS = [
    "row_id",
    "country",
    "indicator_name",
    "unit",
    "latest_period",
    "latest_value",
    "previous_period",
    "previous_value",
    "change_vs_previous",
    "year_ago_period",
    "year_ago_value",
    "change_vs_year_ago",
    "flags",
    "direction",
    "note",
]


def write_batches(
    summary: pd.DataFrame,
    out_dir: str | Path,
    batch_size: int,
    prompt_path: str | Path | None = None,
) -> list[Path]:
    out_dir = Path(out_dir)
    if out_dir.exists():
        for old in out_dir.glob("batch_*.csv"):
            old.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    table = summary.copy()
    table["direction"] = ""
    table["note"] = ""
    table = table[BATCH_COLUMNS]

    paths = []
    for n, start in enumerate(range(0, len(table), batch_size), start=1):
        path = out_dir / f"batch_{n:02d}.csv"
        table.iloc[start:start + batch_size].to_csv(path, index=False)
        paths.append(path)

    if prompt_path and Path(prompt_path).exists():
        shutil.copy(prompt_path, out_dir / "COPILOT_PROMPT.md")
    return paths
