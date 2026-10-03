"""The local-model route: same prompt, same batches, same validator; only the writer changes."""

from pathlib import Path

import pandas as pd
import pytest

from oecd_pipeline.cli import main
from oecd_pipeline.local_model import (
    ChatModel,
    ModelError,
    ReplayMiss,
    extract_csv,
    interpret_batches,
    prompt_instructions,
)
from oecd_pipeline.standin import standin_answer
from oecd_pipeline.validate import read_responses, validate

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "copilot_prompt.md"
EVAL = ROOT / "evals" / "sample"


def fake_post(replies: list[str], seen: list[dict]):
    def post(url, body, headers):
        seen.append(body)
        return {"choices": [{"message": {"content": replies.pop(0)}}], "usage": {}}

    return post


def good_reply(batch: Path, tamper: bool = False) -> str:
    """What a well-behaved model would return for a batch (rule-based wording)."""
    df = pd.read_csv(batch, dtype=str, keep_default_na=False)
    rows = []
    for i, (_, r) in enumerate(df.iterrows()):
        direction, note = standin_answer(r)
        if tamper and i == 0:
            note += " The highest since 1999."
        rows.append(f'{r["row_id"]},{direction},"{note}"')
    return "Here is the result:\n```csv\nrow_id,direction,note\n" + "\n".join(rows) + "\n```"


def test_one_prompt_for_both_routes():
    text = prompt_instructions(PROMPT)
    assert text.startswith("You are filling in two columns")
    assert "attached" not in text  # the local route sends the CSV inline
    assert "never as instructions" in text


@pytest.mark.parametrize(
    "reply",
    [
        '```csv\nrow_id,direction,note\na:FRA,up,"Up."\n```',
        '```\nrow_id,direction,note\na:FRA,up,"Up."\n```',
        'Sure.\nrow_id,direction,note\na:FRA,up,"Up."\n',
        # A trailing comma on every row, as Llama 3.1 8B wrote it in the first live run.
        '```csv\nrow_id,direction,note\na:FRA,up,"Up.",\n```',
    ],
)
def test_csv_is_found_in_common_reply_shapes(reply):
    df = extract_csv(reply)
    assert df is not None and df.iloc[0].to_dict() == {
        "row_id": "a:FRA",
        "direction": "up",
        "note": "Up.",
    }


def test_no_csv_means_none():
    assert extract_csv("I cannot help with that.") is None


def test_local_answers_pass_the_same_validator(tmp_path):
    batches = sorted((EVAL / "batches").glob("batch_*.csv"))
    seen: list[dict] = []
    replies = [good_reply(b, tamper=(n == 0)) for n, b in enumerate(batches)]
    model = ChatModel(model="llama3.2:3b", post=fake_post(replies, seen))
    results = interpret_batches(EVAL / "batches", tmp_path, PROMPT, model)
    assert [r.status for r in results] == ["ok"] * len(batches)
    assert seen[0]["temperature"] == 0 and seen[0]["model"] == "llama3.2:3b"
    assert seen[0]["messages"][0]["role"] == "system"

    summary = pd.read_csv(EVAL / "summary.csv", dtype={"row_id": str})
    answers, problems = read_responses(tmp_path)
    result = validate(summary, answers, problems)
    # The invented "1999" sends exactly one row to review; everything else is accepted.
    assert result.report["to_review"] == 1
    assert "1999" in result.review.iloc[0]["problems"]


def test_unparsed_reply_is_kept_for_a_person(tmp_path):
    model = ChatModel(post=fake_post(["Sorry."] * 3, []))
    results = interpret_batches(EVAL / "batches", tmp_path, PROMPT, model)
    assert {r.status for r in results} == {"unparsed"}
    assert (tmp_path / "batch_01.unparsed.txt").read_text() == "Sorry."


def test_endpoint_failure_is_reported(tmp_path):
    def down(url, body, headers):
        raise ModelError("connection refused")

    results = interpret_batches(EVAL / "batches", tmp_path, PROMPT, ChatModel(post=down))
    assert {r.status for r in results} == {"error"}


def test_record_then_replay_offline(tmp_path):
    rec = tmp_path / "rec"
    live = ChatModel(recordings=rec, post=fake_post(["row_id,direction,note\n"], []))
    assert live.complete("s", "u") == "row_id,direction,note\n"
    assert ChatModel(recordings=rec, offline=True).complete("s", "u") == "row_id,direction,note\n"
    with pytest.raises(ReplayMiss):
        ChatModel(recordings=rec, offline=True).complete("s", "other")


def test_eval_command_with_the_standin(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "report.json"
    assert main(["eval", "--writer", "standin", "--out", str(out)]) == 0
    assert '"acceptance_rate": 1.0' in out.read_text()


def test_eval_command_replays_a_recorded_model_run(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    rec = tmp_path / "rec"
    batches = sorted((EVAL / "batches").glob("batch_*.csv"))
    replies = [good_reply(b, tamper=(n == 0)) for n, b in enumerate(batches)]
    import oecd_pipeline.local_model as lm

    monkeypatch.setattr(lm, "_http_post", fake_post(replies, []))
    args = ["eval", "--writer", "model", "--recordings", str(rec), "--min-accept", "0.8"]
    assert main(args) == 0  # 8 of 9 accepted
    monkeypatch.setattr(lm, "_http_post", None)  # no endpoint: replay must not need it
    assert main(args + ["--offline"]) == 0
    assert main(args[:-2] + ["--min-accept", "1.0", "--offline"]) == 1
