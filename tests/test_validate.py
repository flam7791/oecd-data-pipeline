import pandas as pd
import pytest

from oecd_pipeline.validate import allowed_numbers, check_row, read_responses, validate

ROW = pd.Series({
    "row_id": "cpi_inflation:FRA", "country": "France",
    "indicator_name": "Consumer price inflation, all items, year-on-year",
    "unit": "% change over 12 months",
    "latest_period": "2025-08", "latest_value": 0.9,
    "previous_period": "2025-07", "previous_value": 1.0, "change_vs_previous": -0.1,
    "year_ago_period": "2024-08", "year_ago_value": 1.8, "change_vs_year_ago": -0.9,
    "flags": "", "flat_threshold": 0.1,
})


def resp(direction="down", note="France: inflation was 0.9% in 2025-08, down from 1.0% in 2025-07 and 1.8% a year earlier."):
    return pd.Series({"row_id": ROW["row_id"], "direction": direction, "note": note, "source_file": "b.csv"})


def test_good_answer_passes():
    assert check_row(ROW, resp()) == []


def test_invented_number_is_caught():
    problems = check_row(ROW, resp(note="France: inflation fell to 0.9%, the lowest in 4 years."))
    assert any("not in the row" in p and "4.0" in p for p in problems)


def test_wrong_direction_is_caught():
    assert any("expected 'down'" in p for p in check_row(ROW, resp(direction="up")))


def test_unknown_direction_and_empty_note():
    problems = check_row(ROW, resp(direction="rising", note=""))
    assert any("not one of" in p for p in problems) and "note is empty" in problems


def test_long_note_is_caught():
    assert any("words" in p for p in check_row(ROW, resp(note="word " * 31)))


def test_numbers_from_period_and_unit_are_allowed():
    allowed = allowed_numbers(ROW)
    assert {0.9, 1.0, 0.1, 1.8, 2025.0, 8.0, 12.0} <= allowed


def test_validate_routes_rows(tmp_path):
    summary = pd.DataFrame([ROW.to_dict(), {**ROW.to_dict(), "row_id": "cpi_inflation:ITA"},
                            {**ROW.to_dict(), "row_id": "cpi_inflation:USA"}])
    (tmp_path / "batch_01.csv").write_text(
        "row_id,direction,note\n"
        'cpi_inflation:FRA,down,"France: 0.9 in 2025-08, down from 1.0."\n'
        'cpi_inflation:ITA,Down ,"Italy: 0.9 in 2025-08, down from 1.0 but 7.5 is invented."\n'
        'cpi_inflation:XXX,up,"made-up row"\n'
    )
    (tmp_path / "bad.csv").write_text("id,text\n1,2\n")
    responses, problems = read_responses(tmp_path)
    result = validate(summary, responses, problems)
    assert result.final["row_id"].tolist() == ["cpi_inflation:FRA"]
    review = result.review.set_index("row_id")["problems"]
    assert "7.5" in review["cpi_inflation:ITA"]          # direction 'Down ' normalised, number caught
    assert review["cpi_inflation:USA"] == "not returned by Copilot"
    assert result.report["unexpected_row_ids"] == ["cpi_inflation:XXX"]
    assert any("bad.csv" in p for p in result.report["file_problems"])


def test_duplicate_answers_go_to_review(tmp_path):
    summary = pd.DataFrame([ROW.to_dict()])
    (tmp_path / "a.csv").write_text('row_id,direction,note\ncpi_inflation:FRA,down,"France: 0.9."\n')
    (tmp_path / "b.csv").write_text('row_id,direction,note\ncpi_inflation:FRA,down,"France: 0.9."\n')
    responses, _ = read_responses(tmp_path)
    result = validate(summary, responses)
    assert len(result.final) == 0 and "returned 2 times" in result.review["problems"].iloc[0]
