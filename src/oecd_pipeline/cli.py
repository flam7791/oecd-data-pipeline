"""Command line: python -m oecd_pipeline <command>

  fetch      download every indicator from the OECD API into data/raw/
  process    clean the latest downloads, compute figures, write Copilot batches
  interpret  have a local open-weight model (Ollama, vLLM, any OpenAI-compatible
             endpoint) write the notes instead of Copilot; same prompt, same checks
  validate   check the answers (Copilot or local) and write final.csv / review.csv
  standin    fill the batches with rule-based answers (testing without a model)
  eval       run the evaluation set through a writer and the validator; report and gate
  run        fetch + process
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

from . import __version__
from .batches import write_batches
from .clean import clean_sdmx_csv
from .config import load_config
from .fetch import fetch_all, latest_snapshot
from .local_model import DEFAULT_BASE_URL, DEFAULT_MODEL, ChatModel, ReplayMiss, interpret_batches
from .standin import answer_batches
from .summarise import summarise_indicator
from .validate import read_responses, validate, write_outputs


def _paths(args) -> dict[str, Path]:
    data = Path(args.data_dir)
    return {
        "raw": data / "raw",
        "out": data / "out",
        "batches": data / "out" / "batches",
        "responses": Path(args.responses) if getattr(args, "responses", None) else data / "copilot_responses",
        "standin": data / "standin_responses",
        "local": data / "local_responses",
    }


PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "copilot_prompt.md"


def _prompt_path(args) -> Path:
    near_config = Path(args.config).resolve().parent.parent / "prompts" / "copilot_prompt.md"
    return near_config if near_config.exists() else PROMPT


def _model(args) -> ChatModel:
    return ChatModel(
        base_url=args.base_url,
        model=args.model,
        api_key=os.environ.get("OECD_PIPELINE_API_KEY", ""),
        recordings=args.recordings,
        offline=args.offline,
    )


def cmd_interpret(args) -> int:
    p = _paths(args)
    out = Path(args.responses) if args.responses else p["local"]
    results = interpret_batches(p["batches"], out, _prompt_path(args), _model(args))
    for r in results:
        print(f"  {r.batch}: {r.status}, {r.returned}/{r.rows} rows returned {r.detail}".rstrip())
    print(f"  Local model answers ({args.model}) written to {out}")
    print(f"  Validate them with: python -m oecd_pipeline validate --responses {out}")
    return 0 if all(r.status == "ok" for r in results) else 2


def cmd_eval(args) -> int:
    """Evaluation set -> writer (stand-in, live local model or replay) -> validator -> report."""
    eval_dir = Path(args.set)
    summary = pd.read_csv(eval_dir / "summary.csv", dtype={"row_id": str})
    with tempfile.TemporaryDirectory() as tmp:
        responses = Path(tmp) / "responses"
        if args.writer == "standin":
            answer_batches(eval_dir / "batches", responses)
            writer = "rule-based stand-in (not a model)"
        else:
            try:
                interpret_batches(eval_dir / "batches", responses, _prompt_path(args), _model(args))
            except ReplayMiss as exc:
                print(f"replay miss: {exc}", file=sys.stderr)
                return 2
            writer = args.model
        answers, problems = read_responses(responses)
        result = validate(summary, answers, problems)
    r = result.report
    reasons: dict[str, int] = {}
    for text in result.review.get("problems", []):
        for reason in str(text).split("; "):
            key = reason.split(":")[0].split("(")[0].strip()
            reasons[key] = reasons.get(key, 0) + 1
    rate = r["accepted"] / r["rows_expected"] if r["rows_expected"] else 0.0
    report = {"writer": writer, "rows": r["rows_expected"], "accepted": r["accepted"],
              "acceptance_rate": round(rate, 3), "to_review": r["to_review"],
              "review_reasons": reasons}
    print(f"  writer: {writer}")
    print(f"  accepted {r['accepted']}/{r['rows_expected']} ({rate:.0%}), "
          f"to review {r['to_review']}")
    for reason, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {n} x {reason}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if rate >= args.min_accept else 1


def cmd_fetch(args) -> int:
    config = load_config(args.config)
    p = _paths(args)
    for snap in fetch_all(config, p["raw"]):
        print(f"  {snap.indicator_id}: {snap.n_bytes:,} bytes -> {snap.csv_path}")
    return 0


def cmd_process(args) -> int:
    config = load_config(args.config)
    p = _paths(args)
    p["out"].mkdir(parents=True, exist_ok=True)
    tidy_frames, summaries, checks = [], [], []
    for ind in config.indicators:
        csv_path, meta = latest_snapshot(p["raw"], ind.id)
        result = clean_sdmx_csv(csv_path, ind, config.settings.countries, meta)
        tidy_frames.append(result.data)
        checks.extend(result.checks)
        summaries.append(summarise_indicator(result.data, ind))
        print(f"  {ind.id}: {len(result.data)} clean rows from {csv_path.name}")

    tidy = pd.concat(tidy_frames, ignore_index=True)
    summary = pd.concat(summaries, ignore_index=True)
    checks_df = pd.DataFrame(checks)
    tidy.to_csv(p["out"] / "clean.csv", index=False)
    summary.to_csv(p["out"] / "summary.csv", index=False)
    checks_df.to_csv(p["out"] / "source_checks.csv", index=False)

    prompt = Path(args.config).resolve().parent.parent / "prompts" / "copilot_prompt.md"
    batches = write_batches(summary, p["batches"], config.settings.batch_size, prompt)
    warnings = checks_df[checks_df["severity"] == "warning"] if len(checks_df) else checks_df
    print(f"  clean.csv: {len(tidy)} rows | summary.csv: {len(summary)} rows | "
          f"{len(batches)} batch file(s) in {p['batches']}")
    if len(warnings):
        print(f"  {len(warnings)} source-check warning(s): see {p['out'] / 'source_checks.csv'}")
    return 0


def cmd_standin(args) -> int:
    p = _paths(args)
    written = answer_batches(p["batches"], p["standin"])
    print(f"  Stand-in answers (NOT Copilot) written to {p['standin']}: {len(written)} file(s)")
    print(f"  Validate them with: python -m oecd_pipeline validate --responses {p['standin']}")
    return 0


def cmd_validate(args) -> int:
    p = _paths(args)
    summary = pd.read_csv(p["out"] / "summary.csv", dtype={"row_id": str})
    responses, problems = read_responses(p["responses"])
    result = validate(summary, responses, problems)
    paths = write_outputs(result, p["out"])
    r = result.report
    print(f"  {r['accepted']}/{r['rows_expected']} rows accepted -> {paths['final']}")
    print(f"  {r['to_review']} row(s) to review -> {paths['review']}")
    print(f"  Report: {paths['report']}")
    return 0 if r["to_review"] == 0 else 2


def cmd_run(args) -> int:
    return cmd_fetch(args) or cmd_process(args)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="oecd_pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", default="config/indicators.toml")
    parser.add_argument("--data-dir", default="data")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("fetch", cmd_fetch), ("process", cmd_process), ("standin", cmd_standin),
                     ("run", cmd_run)]:
        sub.add_parser(name).set_defaults(func=fn)
    def model_options(parser):
        parser.add_argument("--base-url", default=os.environ.get(
            "OECD_PIPELINE_BASE_URL", DEFAULT_BASE_URL), help="OpenAI-compatible endpoint")
        parser.add_argument("--model", default=os.environ.get(
            "OECD_PIPELINE_MODEL", DEFAULT_MODEL), help="model name, e.g. an Ollama tag")
        parser.add_argument("--recordings", help="record replies here, or replay from here")
        parser.add_argument("--offline", action="store_true", help="replay recordings only")

    i = sub.add_parser("interpret", help="write the notes with a local open-weight model")
    i.add_argument("--responses", help="output folder (default data/local_responses)")
    model_options(i)
    i.set_defaults(func=cmd_interpret)

    e = sub.add_parser("eval", help="evaluate a writer on the evaluation set")
    e.add_argument("--set", default="evals/sample", help="folder with summary.csv and batches/")
    e.add_argument("--writer", choices=["standin", "model"], default="standin")
    e.add_argument("--min-accept", type=float, default=1.0)
    e.add_argument("--out", help="write the report as JSON")
    model_options(e)
    e.set_defaults(func=cmd_eval)

    v = sub.add_parser("validate")
    v.add_argument("--responses", help="folder with Copilot answers (default data/copilot_responses)")
    v.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
