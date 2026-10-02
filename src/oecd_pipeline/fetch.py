"""Stage 1 - Acquire.

Download each indicator from the OECD SDMX API as SDMX-CSV and keep the
response unchanged on disk, with a small metadata file recording where it
came from, when, and its SHA-256 hash. Later stages read these snapshots,
so a result can always be traced back to the exact download it came from.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import Config, Indicator, Settings

USER_AGENT = "oecd-data-pipeline/0.1 (+https://github.com/flam7791/oecd-data-pipeline)"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """Raised when a download fails after retries."""


@dataclass(frozen=True)
class Snapshot:
    indicator_id: str
    csv_path: Path
    meta_path: Path
    url: str
    retrieved_at: str
    sha256: str
    n_bytes: int


def build_url(settings: Settings, indicator: Indicator) -> str:
    """Return the SDMX REST data URL for one indicator."""
    key = indicator.key.format(countries="+".join(settings.countries))
    return (
        f"{settings.base_url}/{indicator.dataflow}/{key}"
        f"?startPeriod={settings.start_period}&format=csvfile"
    )


def _get_with_retries(session, url: str, attempts: int = 3, backoff: float = 5.0):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            resp = session.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
        except requests.RequestException as exc:  # network error
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                return resp
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            if resp.status_code not in RETRY_STATUSES:
                break
        if attempt < attempts:
            time.sleep(backoff * attempt)
    raise FetchError(f"Download failed for {url} -> {last_error}")


def fetch_indicator(
    config: Config,
    indicator: Indicator,
    raw_dir: str | Path,
    session=None,
    now: datetime | None = None,
) -> Snapshot:
    """Download one indicator and write <id>_<timestamp>.csv plus .meta.json."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = session or requests.Session()
    url = build_url(config.settings, indicator)

    resp = _get_with_retries(session, url)
    body = resp.content
    if not body.strip():
        raise FetchError(f"Empty response for {indicator.id} ({url})")

    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    csv_path = raw_dir / f"{indicator.id}_{stamp}.csv"
    meta_path = raw_dir / f"{indicator.id}_{stamp}.meta.json"
    csv_path.write_bytes(body)

    digest = hashlib.sha256(body).hexdigest()
    meta = {
        "indicator_id": indicator.id,
        "indicator_name": indicator.name,
        "url": url,
        "retrieved_at": now.isoformat(timespec="seconds"),
        "sha256": digest,
        "bytes": len(body),
        "source": "OECD Data Explorer API (sdmx.oecd.org)",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return Snapshot(
        indicator_id=indicator.id,
        csv_path=csv_path,
        meta_path=meta_path,
        url=url,
        retrieved_at=meta["retrieved_at"],
        sha256=digest,
        n_bytes=len(body),
    )


def fetch_all(config: Config, raw_dir: str | Path, session=None) -> list[Snapshot]:
    """Download every configured indicator, pausing politely between calls."""
    snapshots = []
    for i, ind in enumerate(config.indicators):
        if i:
            time.sleep(config.settings.request_pause_seconds)
        snapshots.append(fetch_indicator(config, ind, raw_dir, session=session))
    return snapshots


def latest_snapshot(raw_dir: str | Path, indicator_id: str) -> tuple[Path, dict]:
    """Return the newest saved CSV for an indicator and its metadata."""
    raw_dir = Path(raw_dir)
    candidates = sorted(raw_dir.glob(f"{indicator_id}_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No saved download for {indicator_id!r} in {raw_dir}. Run the fetch step first."
        )
    csv_path = candidates[-1]
    meta_path = csv_path.with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return csv_path, meta
