"""Stage 4 - Check what Copilot returned before accepting any of it.

Copilot's answers are matched back to the summary by row_id and checked
with rules:

- every row came back exactly once, and no unknown rows were added;
- `direction` is one of up / down / flat / n/a and agrees with the
  figures (recomputed here, not trusted);
- `note` is present, at most 30 words, and contains no number that is not
  in that row - the main guard against invented figures.

Rows that pass go to final.csv. Rows that fail go to review.csv with the
reasons, for a person to look at. Nothing Copilot wrote overwrites the
figures: the figures always come from the summary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .summarise import expected_direction

ALLOWED_DIRECTIONS = {"up", "down", "flat", "n/a"}
MAX_NOTE_WORDS = 30
NUMERIC_FIELDS = [
    "latest_value",
    "previous_value",
    "change_vs_previous",
    "year_ago_value",
    "change_vs_year_ago",
]
TEXT_FIELDS_WITH_NUMBERS = [
    "latest_period",
    "previous_period",
    "year_ago_period",
    "unit",
    "indicator_name",
]
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class ValidationResult:
    final: pd.DataFrame
    review: pd.DataFrame
    report: dict


def read_responses(responses_dir: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Read every CSV in the responses folder into one table."""
    responses_dir = Path(responses_dir)
    frames, problems = [], []
    for path in sorted(responses_dir.glob("*.csv")):
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except Exception as exc:  # malformed file
            problems.append(f"{path.name}: could not be read ({exc})")
            continue
        df.columns = [c.strip().lower() for c in df.columns]
        missing = {"row_id", "direction", "note"} - set(df.columns)
        if missing:
            problems.append(f"{path.name}: missing column(s) {sorted(missing)}")
            continue
        df = df[["row_id", "direction", "note"]].copy()
        df["source_file"] = path.name
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["row_id", "direction", "note", "source_file"]), problems
    out = pd.concat(frames, ignore_index=True)
    for col in ("row_id", "direction", "note"):
        out[col] = out[col].astype(str).str.strip()
    out["direction"] = out["direction"].str.lower()
    return out, problems


def _as_float(x) -> float | None:
    if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() == "":
        return None
    try:
        return float(str(x).replace(",", "."))
    except ValueError:
        return None


def allowed_numbers(row: pd.Series) -> set[float]:
    """Numbers a note for this row may mention."""
    allowed: set[float] = set()
    for field in NUMERIC_FIELDS:
        v = _as_float(row.get(field))
        if v is not None:
            allowed.add(round(abs(v), 1))
    for field in TEXT_FIELDS_WITH_NUMBERS:
        for token in _NUMBER.findall(str(row.get(field, ""))):
            allowed.add(round(abs(float(token.replace(",", "."))), 1))
    return allowed


def numbers_in(text: str) -> list[float]:
    return [round(float(t.replace(",", ".")), 1) for t in _NUMBER.findall(text)]


def check_row(row: pd.Series, response: pd.Series) -> list[str]:
    """Return the list of problems with one Copilot answer (empty = pass)."""
    problems = []
    direction = response["direction"]
    if direction not in ALLOWED_DIRECTIONS:
        problems.append(f"direction '{direction}' is not one of {sorted(ALLOWED_DIRECTIONS)}")
    else:
        expected = expected_direction(_as_float(row["change_vs_previous"]), float(row["flat_threshold"]))
        if direction != expected:
            problems.append(f"direction '{direction}' does not match the figures (expected '{expected}')")

    note = response["note"]
    if not note:
        problems.append("note is empty")
    else:
        words = len(note.split())
        if words > MAX_NOTE_WORDS:
            problems.append(f"note has {words} words (max {MAX_NOTE_WORDS})")
        allowed = allowed_numbers(row)
        invented = sorted({n for n in numbers_in(note) if n not in allowed})
        if invented:
            problems.append(f"note mentions number(s) not in the row: {invented}")
    return problems


def validate(summary: pd.DataFrame, responses: pd.DataFrame, file_problems: list[str] | None = None) -> ValidationResult:
    file_problems = list(file_problems or [])
    summary = summary.copy()
    summary["row_id"] = summary["row_id"].astype(str)
    known = set(summary["row_id"])

    unexpected = sorted(set(responses["row_id"]) - known)
    dup_ids = set(responses.loc[responses["row_id"].duplicated(keep=False), "row_id"])

    final_rows, review_rows = [], []
    by_id = {rid: grp for rid, grp in responses.groupby("row_id")}
    for _, row in summary.iterrows():
        rid = row["row_id"]
        base = row.to_dict()
        if rid not in by_id:
            review_rows.append({**base, "direction": "", "note": "", "source_file": "",
                                "problems": "not returned by Copilot"})
            continue
        resp = by_id[rid].iloc[-1]
        problems = check_row(row, resp)
        if rid in dup_ids:
            problems.insert(0, f"returned {len(by_id[rid])} times (last one checked)")
        record = {**base, "direction": resp["direction"], "note": resp["note"],
                  "source_file": resp["source_file"]}
        if problems:
            review_rows.append({**record, "problems": "; ".join(problems)})
        else:
            final_rows.append(record)

    final_cols = list(summary.columns) + ["direction", "note", "source_file"]
    final = pd.DataFrame(final_rows, columns=final_cols)
    review = pd.DataFrame(review_rows, columns=final_cols + ["problems"])
    report = {
        "rows_expected": len(summary),
        "responses_read": len(responses),
        "accepted": len(final),
        "to_review": len(review),
        "not_returned": int((review["problems"] == "not returned by Copilot").sum()) if len(review) else 0,
        "unexpected_row_ids": unexpected,
        "file_problems": file_problems,
    }
    return ValidationResult(final=final, review=review, report=report)


def write_outputs(result: ValidationResult, out_dir: str | Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "final": out_dir / "final.csv",
        "review": out_dir / "review.csv",
        "report": out_dir / "validation_report.md",
    }
    result.final.to_csv(paths["final"], index=False)
    result.review.to_csv(paths["review"], index=False)

    r = result.report
    lines = [
        "# Validation report",
        "",
        f"- Rows expected: {r['rows_expected']}",
        f"- Copilot answers read: {r['responses_read']}",
        f"- Accepted (final.csv): {r['accepted']}",
        f"- Sent to review (review.csv): {r['to_review']}",
        f"- Not returned by Copilot: {r['not_returned']}",
    ]
    if r["unexpected_row_ids"]:
        lines.append(f"- Answers for unknown row_ids (ignored): {', '.join(r['unexpected_row_ids'])}")
    if r["file_problems"]:
        lines.append("- Response files that could not be used:")
        lines += [f"  - {p}" for p in r["file_problems"]]
    if len(result.review):
        lines += ["", "## Rows to review", ""]
        for _, row in result.review.iterrows():
            lines.append(f"- `{row['row_id']}`: {row['problems']}")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths
