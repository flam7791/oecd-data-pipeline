"""Stage 2 - Clean, using rules only.

Turns a raw SDMX-CSV download into a tidy table with one row per
country and period, and records every problem found as a "source check"
rather than fixing it silently. No AI is involved at this stage: every
step is a rule that gives the same result on every run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import Indicator
from .countries import country_name
from .periods import is_valid_period, parse_period

REQUIRED_COLUMNS = ("REF_AREA", "TIME_PERIOD", "OBS_VALUE")

TIDY_COLUMNS = [
    "indicator_id",
    "indicator_name",
    "country_code",
    "country",
    "period",
    "frequency",
    "value",
    "unit",
    "source_url",
    "retrieved_at",
]


class SchemaError(ValueError):
    """Raised when a download does not have the columns the pipeline needs."""


@dataclass
class CleanResult:
    data: pd.DataFrame
    checks: list[dict] = field(default_factory=list)


def _check(indicator_id: str, check: str, severity: str, detail: str, count: int = 0) -> dict:
    return {
        "indicator_id": indicator_id,
        "check": check,
        "severity": severity,
        "count": count,
        "detail": detail,
    }


def clean_sdmx_csv(
    csv_path: str | Path,
    indicator: Indicator,
    countries: tuple[str, ...],
    meta: dict | None = None,
) -> CleanResult:
    meta = meta or {}
    ind = indicator.id
    raw = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    raw.columns = [c.strip() for c in raw.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise SchemaError(
            f"{ind}: download is missing column(s) {missing}. "
            f"Columns found: {list(raw.columns)[:15]}. "
            "Check the dataflow and key, or whether the API returned an error page."
        )

    checks = [_check(ind, "rows_downloaded", "info", "Rows in the raw download", len(raw))]
    df = raw.copy()
    for col in REQUIRED_COLUMNS:
        df[col] = df[col].str.strip()

    # 1. Values must be numbers.
    df["value"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    bad_value = df["value"].isna()
    if bad_value.any():
        examples = ", ".join(sorted(set(df.loc[bad_value, "OBS_VALUE"]))[:5]) or "(blank)"
        checks.append(
            _check(ind, "non_numeric_value", "warning",
                   f"Rows dropped because OBS_VALUE is blank or not a number (e.g. {examples})",
                   int(bad_value.sum()))
        )
    df = df[~bad_value]

    # 2. Only the countries that were asked for.
    df["REF_AREA"] = df["REF_AREA"].str.upper()
    unexpected = ~df["REF_AREA"].isin(countries)
    if unexpected.any():
        codes = ", ".join(sorted(df.loc[unexpected, "REF_AREA"].unique()))
        checks.append(
            _check(ind, "unexpected_country", "warning",
                   f"Rows dropped for areas not in the config: {codes}", int(unexpected.sum()))
        )
    df = df[~unexpected]

    # 3. Periods must match the indicator's frequency.
    period_ok = df["TIME_PERIOD"].map(lambda p: is_valid_period(p, indicator.frequency))
    if (~period_ok).any():
        examples = ", ".join(sorted(df.loc[~period_ok, "TIME_PERIOD"].unique())[:5])
        checks.append(
            _check(ind, "bad_period", "warning",
                   f"Rows dropped because the period does not match frequency "
                   f"{indicator.frequency} (e.g. {examples})", int((~period_ok).sum()))
        )
    df = df[period_ok]

    # 4. One value per country and period. If the key matched several series,
    #    keep a deterministic first one and say so.
    other_cols = sorted(c for c in df.columns if c not in {"OBS_VALUE", "value"})
    df = df.sort_values(other_cols, kind="mergesort")
    dup = df.duplicated(["REF_AREA", "TIME_PERIOD"], keep="first")
    if dup.any():
        conflicting = (
            df[df.duplicated(["REF_AREA", "TIME_PERIOD"], keep=False)]
            .groupby(["REF_AREA", "TIME_PERIOD"])["value"].nunique()
        )
        n_conflict = int((conflicting > 1).sum())
        checks.append(
            _check(ind, "duplicate_series", "warning",
                   "More than one row per country and period: the key matched several series. "
                   f"Kept the first; {n_conflict} country-period pairs had different values. "
                   "Narrow the key in config/indicators.toml.", int(dup.sum()))
        )
    df = df[~dup]

    # 5. Countries that came back with no data at all.
    missing_countries = sorted(set(countries) - set(df["REF_AREA"]))
    if missing_countries:
        checks.append(
            _check(ind, "missing_country", "warning",
                   f"No usable data for: {', '.join(missing_countries)}", len(missing_countries))
        )

    tidy = pd.DataFrame({
        "indicator_id": ind,
        "indicator_name": indicator.name,
        "country_code": df["REF_AREA"],
        "country": df["REF_AREA"].map(country_name),
        "period": df["TIME_PERIOD"],
        "frequency": indicator.frequency,
        "value": df["value"].astype(float),
        "unit": indicator.unit,
        "source_url": meta.get("url", ""),
        "retrieved_at": meta.get("retrieved_at", ""),
    })[TIDY_COLUMNS]
    tidy["_sort"] = tidy["period"].map(lambda p: parse_period(p, indicator.frequency))
    tidy = tidy.sort_values(["country_code", "_sort"]).drop(columns="_sort").reset_index(drop=True)

    checks.append(_check(ind, "rows_kept", "info", "Rows in the cleaned table", len(tidy)))
    return CleanResult(data=tidy, checks=checks)
