# Operations: Indicator notes pipeline

Owner: _name_ · Backup: _name_ · Review: every three months

## Monitoring

| Signal | Source | Frequency | Act when |
|---|---|---|---|
| Rows sent to review | `validation_report.md` | each run | above 20%: check the model or the prompt |
| Source-check warnings | `source_checks.csv` | each run | new warning types: check the API format |
| Fetch failures | command exit code | each run | any: the API key or dataflow changed |
| Acceptance rate per writer | `python -m oecd_pipeline eval` | after any prompt or model change | drop of 10 points |

## Runbook

- API format changed (no rows): re-copy the query from Data Explorer's Developer API panel into `config/indicators.toml`.
- Local model unavailable: run the Copilot route by hand, or point `--base-url` at another endpoint.
- A note with a wrong figure found after publication: the validator should have caught it; add the row to the evaluation set and fix the check first.

## Change and release

- Every change runs the tests and the evaluation in CI; a recorded model run is re-recorded when the prompt or the model changes.
- Versions and changes are listed in CHANGELOG.md; the previous release tag is the rollback.
