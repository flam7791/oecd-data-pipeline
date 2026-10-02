"""Strict parsing of SDMX time periods (2025-07, 2025-Q2, 2025)."""

from __future__ import annotations

import re

import pandas as pd

_PATTERNS = {
    "M": re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$"),
    "Q": re.compile(r"^(\d{4})-Q([1-4])$"),
    "A": re.compile(r"^(\d{4})$"),
}
_PANDAS_FREQ = {"M": "M", "Q": "Q", "A": "Y"}


def parse_period(value: str, freq: str) -> pd.Period:
    """Parse an SDMX period string; raise ValueError if it does not match freq."""
    m = _PATTERNS[freq].match(str(value).strip())
    if not m:
        raise ValueError(f"{value!r} is not a valid period for frequency {freq}")
    year = int(m.group(1))
    if freq == "M":
        return pd.Period(year=year, month=int(m.group(2)), freq="M")
    if freq == "Q":
        return pd.Period(year=year, quarter=int(m.group(2)), freq="Q")
    return pd.Period(year=year, freq=_PANDAS_FREQ[freq])


def is_valid_period(value: str, freq: str) -> bool:
    try:
        parse_period(value, freq)
    except ValueError:
        return False
    return True


def format_period(p: pd.Period, freq: str) -> str:
    """Write a period the way the OECD API does: 2025-07, 2025-Q2, 2025."""
    if freq == "Q":
        return f"{p.year}-Q{p.quarter}"
    if freq == "M":
        return f"{p.year}-{p.month:02d}"
    return str(p.year)
