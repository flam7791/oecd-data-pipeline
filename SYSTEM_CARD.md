# System card: oecd-data-pipeline

| | |
|---|---|
| Pattern | P3 code computes, model writes, code checks ([ai-engineering-framework](https://github.com/flam7791/ai-engineering-framework)) |
| Models | Microsoft 365 Copilot by hand, or a local open-weight model (`interpret`); only for the wording step |
| Data source | Public OECD Data Explorer API. Independent project, not affiliated with the OECD |

## Intended use

Turn headline indicators into short, plain-English country notes in which every figure comes from
the data and has been checked.

## Out of scope

Analysis, causes or forecasts; any figure the model computes (it never does: all figures are in
its input row).

## Data

Public statistics, saved unchanged with their URL, time and SHA-256 hash. With the local route,
nothing leaves the machine; with Copilot, the batch files are attached in the user's own tenant.

## How it can fail

- A note that is grammatical but misleading in emphasis: the validator checks figures, direction
  and length, not tone. Notes are short and neutral by instruction, and reviewed before use.
- A model that skips rows or returns no usable CSV: those rows go to `review.csv`.

## Evaluation

The validator runs on every answer. `evals/sample` (synthetic figures) measures the acceptance
rate and the review reasons per writer; CI runs it with the rule-based stand-in and replays
recorded model runs.

## Human oversight

Every rejected row goes to `review.csv` with its reasons, for a person; the final figures always
come from the computed summary, never from the model's text.
