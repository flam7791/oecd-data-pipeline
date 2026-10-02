import pandas as pd
import pytest

from oecd_pipeline.clean import TIDY_COLUMNS, SchemaError, clean_sdmx_csv
from oecd_pipeline.fetch import latest_snapshot
from oecd_pipeline.summarise import expected_direction, summarise_indicator

from conftest import FIXTURES


def _clean(cfg, raw_dir, ind_id):
    path, meta = latest_snapshot(raw_dir, ind_id)
    return clean_sdmx_csv(path, cfg.indicator(ind_id), cfg.settings.countries, meta)


def _check(result, name):
    found = [c for c in result.checks if c["check"] == name]
    return found[0] if found else None


def test_clean_gives_tidy_table_with_provenance(cfg, raw_dir):
    res = _clean(cfg, raw_dir, "unemployment_rate")
    assert list(res.data.columns) == TIDY_COLUMNS
    assert set(res.data["country_code"]) == {"USA", "FRA", "ITA"}
    assert res.data["source_url"].unique().tolist() == ["https://example.test/unemployment_rate"]
    assert res.data["value"].dtype == float


def test_clean_reports_instead_of_hiding(cfg, raw_dir):
    res = _clean(cfg, raw_dir, "unemployment_rate")
    assert _check(res, "non_numeric_value")["count"] == 1      # ITA 2025-03 is blank
    assert _check(res, "unexpected_country")["count"] == 20    # EA20 not asked for
    assert _check(res, "rows_kept")["count"] == 59             # 3 x 20 - 1


def test_duplicate_series_kept_once_and_reported(cfg, raw_dir):
    res = _clean(cfg, raw_dir, "gdp_growth")
    fra = res.data[(res.data.country_code == "FRA") & (res.data.period == "2025-Q1")]
    assert len(fra) == 1 and fra["value"].iloc[0] == 0.1      # T0102 kept, T0103 dropped
    assert _check(res, "duplicate_series")["count"] == 1


def test_wrong_columns_raise_a_clear_error(cfg):
    with pytest.raises(SchemaError, match="missing column"):
        clean_sdmx_csv(FIXTURES / "broken_download.csv", cfg.indicator("cpi_inflation"), ("USA",))


def test_period_must_match_frequency(cfg, tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("REF_AREA,TIME_PERIOD,OBS_VALUE\nUSA,2025-Q1,1.0\nUSA,2025-02,2.0\nUSA,2025-13,3.0\n")
    res = clean_sdmx_csv(p, cfg.indicator("cpi_inflation"), ("USA",))
    assert res.data["period"].tolist() == ["2025-02"]
    assert _check(res, "bad_period")["count"] == 2


def test_summary_figures(cfg, raw_dir):
    ind = cfg.indicator("unemployment_rate")
    s = summarise_indicator(_clean(cfg, raw_dir, ind.id).data, ind).set_index("country_code")
    usa = s.loc["USA"]
    assert (usa.latest_period, usa.latest_value, usa.previous_value) == ("2025-08", 4.3, 4.2)
    assert usa.change_vs_previous == 0.1 and usa.year_ago_period == "2024-08"
    assert s.loc["ITA"]["flags"] == "large_move"                  # 6.0 -> 6.7
    assert s.loc["FRA"].change_vs_previous == 0.0


def test_quarterly_summary_and_lagging_flag(cfg, raw_dir):
    ind = cfg.indicator("gdp_growth")
    s = summarise_indicator(_clean(cfg, raw_dir, ind.id).data, ind).set_index("country_code")
    assert s.loc["USA"].previous_period == "2025-Q1"
    assert s.loc["USA"].change_vs_previous == 0.9
    assert s.loc["ITA"].latest_period == "2025-Q1" and "lagging" in s.loc["ITA"]["flags"]
    assert s.loc["ITA"].year_ago_period == "2024-Q1"


@pytest.mark.parametrize("change,expected", [(0.1, "up"), (-0.1, "down"), (0.05, "flat"),
                                             (0.0, "flat"), (None, "n/a")])
def test_expected_direction(change, expected):
    assert expected_direction(change, 0.1) == expected
