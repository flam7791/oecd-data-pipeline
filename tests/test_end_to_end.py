"""Whole pipeline, offline: synthetic downloads -> batches -> stand-in answers -> checks."""

import pandas as pd

from oecd_pipeline.cli import main

from conftest import FIXTURES


def test_offline_run(raw_dir, capsys):
    data = raw_dir.parent
    args = ["--config", str(FIXTURES / "test_indicators.toml"), "--data-dir", str(data)]

    assert main(args + ["process"]) == 0
    summary = pd.read_csv(data / "out" / "summary.csv")
    assert len(summary) == 9                                   # 3 indicators x 3 countries
    batches = sorted((data / "out" / "batches").glob("batch_*.csv"))
    assert len(batches) == 3                                   # batch_size = 4 in the test config
    checks = pd.read_csv(data / "out" / "source_checks.csv")
    assert {"non_numeric_value", "unexpected_country", "duplicate_series"} <= set(checks["check"])

    assert main(args + ["standin"]) == 0
    code = main(args + ["validate", "--responses", str(data / "standin_responses")])
    final = pd.read_csv(data / "out" / "final.csv")
    assert code == 0 and len(final) == 9
    assert final["note"].str.len().gt(0).all()

    # Simulate Copilot dropping a row and inventing a figure.
    resp = pd.read_csv(data / "standin_responses" / "batch_01.csv")
    resp = resp.iloc[1:].copy()
    resp.loc[resp.index[0], "note"] = resp.loc[resp.index[0], "note"] + " Highest since 1999."
    resp.to_csv(data / "standin_responses" / "batch_01.csv", index=False)
    code = main(args + ["validate", "--responses", str(data / "standin_responses")])
    review = pd.read_csv(data / "out" / "review.csv")
    assert code == 2 and len(review) == 2
    assert "1999" in (data / "out" / "validation_report.md").read_text()
