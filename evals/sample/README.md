# Evaluation set

Nine rows built by `process` from the **synthetic** downloads in `tests/fixtures/` (invented
numbers, not OECD statistics): three indicators for three countries, including a large move and
a flat change. `python -m oecd_pipeline eval` runs a writer over `batches/` and checks every
answer against `summary.csv` with the same validator as a real run.
