"""Stage 2b - Compute the figures the notes will be written from.

For each indicator and country: latest value, change from the previous
period, change from a year earlier, and rule-based flags. All numbers are
computed here, in Python, so the AI step never has to calculate anything;
it only has to put these figures into words.
"""

from __future__ import annotations

import pandas as pd

from .config import Indicator
from .periods import format_period, parse_period

PERIODS_PER_YEAR = {"M": 12, "Q": 4, "A": 1}

SUMMARY_COLUMNS = [
    "row_id",
    "indicator_id",
    "indicator_name",
    "country_code",
    "country",
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
    "flat_threshold",
    "source_url",
    "retrieved_at",
]


def _r(x):
    return None if x is None or pd.isna(x) else round(float(x), 1)


def _diff(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 1)


def summarise_indicator(tidy: pd.DataFrame, indicator: Indicator) -> pd.DataFrame:
    """One summary row per country for one indicator."""
    if tidy.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    freq = indicator.frequency
    df = tidy.copy()
    df["_p"] = df["period"].map(lambda p: parse_period(p, freq))
    overall_latest = df["_p"].max()
    rows = []
    for code, g in df.groupby("country_code", sort=True):
        g = g.sort_values("_p")
        by_period = dict(zip(g["_p"], g["value"]))
        latest_p = g["_p"].iloc[-1]
        latest = _r(by_period[latest_p])

        prev_p = latest_p - 1
        prev = _r(by_period.get(prev_p))
        year_p = latest_p - PERIODS_PER_YEAR[freq]
        year_ago = _r(by_period.get(year_p))

        change_prev = _diff(latest, prev)
        change_year = _diff(latest, year_ago)

        flags = []
        if change_prev is not None and abs(change_prev) >= indicator.large_move_threshold:
            flags.append("large_move")
        if latest_p < overall_latest:
            flags.append("lagging")
        if prev is None:
            flags.append("no_previous")
        if year_ago is None:
            flags.append("no_year_ago")

        first = g.iloc[0]
        rows.append({
            "row_id": f"{indicator.id}:{code}",
            "indicator_id": indicator.id,
            "indicator_name": indicator.name,
            "country_code": code,
            "country": first["country"],
            "unit": indicator.unit,
            "latest_period": str(g["period"].iloc[-1]),
            "latest_value": latest,
            "previous_period": format_period(prev_p, freq) if prev is not None else "",
            "previous_value": prev,
            "change_vs_previous": change_prev,
            "year_ago_period": format_period(year_p, freq) if year_ago is not None else "",
            "year_ago_value": year_ago,
            "change_vs_year_ago": change_year,
            "flags": ";".join(flags),
            "flat_threshold": indicator.flat_threshold,
            "source_url": first["source_url"],
            "retrieved_at": first["retrieved_at"],
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def expected_direction(change, flat_threshold: float) -> str:
    """Rule used to check the AI's 'direction' answer."""
    if change is None or pd.isna(change):
        return "n/a"
    if abs(change) < flat_threshold:
        return "flat"
    return "up" if change > 0 else "down"
