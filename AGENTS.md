# AGENTS.md: oecd-data-pipeline

Instructions for coding agents (and people) changing this repository. Read this first.

A small, auditable pipeline: fetch headline indicators from the public OECD Data Explorer API,
clean and summarise them in Python, have Microsoft 365 Copilot (or a local open-weight model)
write a short note per country, then check every note in Python before accepting it. Code
computes, the model writes, code checks.

## Commands

```bash
pip install -e ".[dev]"
pytest -q                                          # offline, synthetic fixtures
python -m oecd_pipeline eval                       # evaluation with the rule-based stand-in: must be 100%
for dir in evals/recordings/*/; do [ -d "$dir" ] && python -m oecd_pipeline eval --writer model --model "$(basename "$dir" | sed 's/-/:/')" --recordings "$dir" --offline --min-accept 0; done
python -m oecd_pipeline standin && python -m oecd_pipeline validate --responses data/standin_responses
```

`python -m oecd_pipeline run` fetches live data and needs the network; tests never do.

## Layout

- `src/oecd_pipeline/fetch.py`: download with retries, raw file and provenance kept
- `src/oecd_pipeline/clean.py`, `summarise.py`, `periods.py`, `countries.py`: the rules
- `src/oecd_pipeline/batches.py`: batches and the prompt copy for Copilot
- `src/oecd_pipeline/validate.py`: the checks every model answer must pass
- `src/oecd_pipeline/local_model.py`, `standin.py`: the local-model writer and the stand-in
- `config/indicators.toml`: which indicators, as configuration; `prompts/copilot_prompt.md`: the prompt
- `evals/sample/`: synthetic evaluation set; `evals/results/`: recorded runs

## Invariants: never weaken these

1. **The model never calculates** (decision 3). Every figure in a note must match a figure the
   code computed; the validator rejects anything else.
2. **Nothing the model writes is accepted unchecked** (decision 4). Rows that fail go to
   `review.csv` for a person, with the reason.
3. **Problems are reported, not fixed silently** (decision 5): no auto-correction of model text
   or source data.
4. **The raw download is kept** with its provenance (decision 6).
5. **Tests use synthetic fixtures** in `tests/fixtures/`; never commit real downloads as fixtures
   or present fixture numbers as OECD statistics.

## Working rules

- A bad note that slipped through becomes a test or an evaluation row before the fix.
- A change to the prompt or the model makes recordings stale: re-record, never edit them.
- Indicators are configuration, not code (decision 7).
- Record every change in `CHANGELOG.md`; a design change goes in `docs/decisions.md`.
- Independent project, not affiliated with the OECD; only public data. Commits carry no AI
  co-author trailers.
