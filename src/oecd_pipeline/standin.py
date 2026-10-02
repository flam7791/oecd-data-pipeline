"""A rule-based stand-in for the Copilot step, for testing only.

It fills `direction` and `note` from templates so the whole pipeline can be
run and tested without Copilot. It is NOT the interpretation step: the
point of the real step is wording that templates cannot produce well, and
its output is what the validator is built to check.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .summarise import expected_direction


def _fmt(v) -> str:
    return "not available" if v is None or pd.isna(v) or str(v) == "" else f"{float(v):.1f}"


def standin_answer(row: pd.Series, flat_threshold: float = 0.1) -> tuple[str, str]:
    change = row["change_vs_previous"]
    change = None if change == "" or pd.isna(change) else float(change)
    direction = expected_direction(change, flat_threshold)
    latest = f"{row['country']}: {_fmt(row['latest_value'])} in {row['latest_period']}"
    if direction == "n/a":
        prev = "no previous figure available"
    else:
        verb = {"up": "up from", "down": "down from", "flat": "broadly unchanged from"}[direction]
        prev = f"{verb} {_fmt(row['previous_value'])} in {row['previous_period']}"
    year = row["year_ago_value"]
    if year == "" or pd.isna(year):
        tail = "a year-earlier figure is not available."
    else:
        tail = f"{_fmt(year)} a year earlier."
    return direction, f"{latest}, {prev}; {tail}"


def answer_batches(batch_dir: str | Path, responses_dir: str | Path, flat_threshold: float = 0.1) -> list[Path]:
    batch_dir, responses_dir = Path(batch_dir), Path(responses_dir)
    responses_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for batch in sorted(batch_dir.glob("batch_*.csv")):
        df = pd.read_csv(batch, dtype=str, keep_default_na=False)
        answers = [standin_answer(r, flat_threshold) for _, r in df.iterrows()]
        out = pd.DataFrame({
            "row_id": df["row_id"],
            "direction": [a[0] for a in answers],
            "note": [a[1] for a in answers],
        })
        path = responses_dir / batch.name
        out.to_csv(path, index=False)
        written.append(path)
    return written
