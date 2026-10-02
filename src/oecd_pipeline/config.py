"""Load and check the indicator configuration (config/indicators.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

VALID_FREQUENCIES = {"M", "Q", "A"}


class ConfigError(ValueError):
    """Raised when the configuration file is missing a field or is inconsistent."""


@dataclass(frozen=True)
class Indicator:
    id: str
    name: str
    dataflow: str
    key: str
    frequency: str
    unit: str
    flat_threshold: float = 0.1
    large_move_threshold: float = 1.0


@dataclass(frozen=True)
class Settings:
    base_url: str
    countries: tuple[str, ...]
    start_period: str
    request_pause_seconds: float = 3.0
    batch_size: int = 40


@dataclass(frozen=True)
class Config:
    settings: Settings
    indicators: tuple[Indicator, ...] = field(default_factory=tuple)

    def indicator(self, indicator_id: str) -> Indicator:
        for ind in self.indicators:
            if ind.id == indicator_id:
                return ind
        raise KeyError(f"Unknown indicator id: {indicator_id!r}")


_REQUIRED_INDICATOR_FIELDS = ("id", "name", "dataflow", "key", "frequency", "unit")


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    s = raw.get("settings") or {}
    for name in ("base_url", "countries", "start_period"):
        if name not in s:
            raise ConfigError(f"[settings] is missing '{name}'")
    countries = tuple(str(c).strip().upper() for c in s["countries"])
    if not countries:
        raise ConfigError("[settings] countries is empty")

    settings = Settings(
        base_url=str(s["base_url"]).rstrip("/"),
        countries=countries,
        start_period=str(s["start_period"]),
        request_pause_seconds=float(s.get("request_pause_seconds", 3)),
        batch_size=int(s.get("batch_size", 40)),
    )
    if settings.batch_size < 1:
        raise ConfigError("[settings] batch_size must be at least 1")

    indicators = []
    seen = set()
    for i, item in enumerate(raw.get("indicator") or [], start=1):
        missing = [f for f in _REQUIRED_INDICATOR_FIELDS if f not in item]
        if missing:
            raise ConfigError(f"[[indicator]] #{i} is missing: {', '.join(missing)}")
        if item["id"] in seen:
            raise ConfigError(f"Duplicate indicator id: {item['id']!r}")
        seen.add(item["id"])
        freq = str(item["frequency"]).upper()
        if freq not in VALID_FREQUENCIES:
            raise ConfigError(
                f"Indicator {item['id']!r}: frequency must be one of {sorted(VALID_FREQUENCIES)}"
            )
        if "{countries}" not in item["key"]:
            raise ConfigError(
                f"Indicator {item['id']!r}: key must contain {{countries}} so the country list applies"
            )
        indicators.append(
            Indicator(
                id=item["id"],
                name=item["name"],
                dataflow=item["dataflow"],
                key=item["key"],
                frequency=freq,
                unit=item["unit"],
                flat_threshold=float(item.get("flat_threshold", 0.1)),
                large_move_threshold=float(item.get("large_move_threshold", 1.0)),
            )
        )
    if not indicators:
        raise ConfigError("No [[indicator]] entries found")
    return Config(settings=settings, indicators=tuple(indicators))
