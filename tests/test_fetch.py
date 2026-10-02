import json
from datetime import datetime, timezone

import pytest

from oecd_pipeline.fetch import FetchError, build_url, fetch_indicator, latest_snapshot


class FakeResponse:
    def __init__(self, status, body=b""):
        self.status_code = status
        self.content = body
        self.text = body.decode()


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, timeout, headers):
        self.urls.append(url)
        return self.responses.pop(0)


def test_build_url_inserts_countries(cfg):
    url = build_url(cfg.settings, cfg.indicator("cpi_inflation"))
    assert url == (
        "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
        "USA+FRA+ITA.M.N.CPI.PA._T.N.GY?startPeriod=2023&format=csvfile"
    )


def test_fetch_keeps_raw_bytes_and_provenance(cfg, tmp_path):
    body = b"REF_AREA,TIME_PERIOD,OBS_VALUE\nUSA,2025-01,3.0\n"
    session = FakeSession([FakeResponse(200, body)])
    when = datetime(2025, 10, 1, 8, 0, tzinfo=timezone.utc)
    snap = fetch_indicator(cfg, cfg.indicator("cpi_inflation"), tmp_path, session=session, now=when)
    assert snap.csv_path.read_bytes() == body
    meta = json.loads(snap.meta_path.read_text())
    assert meta["url"] == session.urls[0]
    assert meta["retrieved_at"] == "2025-10-01T08:00:00+00:00"
    assert len(meta["sha256"]) == 64
    path, meta2 = latest_snapshot(tmp_path, "cpi_inflation")
    assert path == snap.csv_path and meta2["sha256"] == meta["sha256"]


def test_fetch_does_not_retry_a_bad_request(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr("oecd_pipeline.fetch.time.sleep", lambda s: None)
    session = FakeSession([FakeResponse(404, b"NoResultsFound")])
    with pytest.raises(FetchError, match="404"):
        fetch_indicator(cfg, cfg.indicator("gdp_growth"), tmp_path, session=session)
    assert len(session.urls) == 1


def test_fetch_retries_when_rate_limited(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr("oecd_pipeline.fetch.time.sleep", lambda s: None)
    ok = b"REF_AREA,TIME_PERIOD,OBS_VALUE\nUSA,2025-Q1,0.5\n"
    session = FakeSession([FakeResponse(429, b"slow down"), FakeResponse(200, ok)])
    snap = fetch_indicator(cfg, cfg.indicator("gdp_growth"), tmp_path, session=session)
    assert snap.csv_path.read_bytes() == ok and len(session.urls) == 2


def test_missing_snapshot_explains_what_to_do(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch step"):
        latest_snapshot(tmp_path, "cpi_inflation")
