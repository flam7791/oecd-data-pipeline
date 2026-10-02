# Design decisions

Short record of the choices behind this MVP and what they trade off.

## 1. Rules first, AI only for wording

The OECD API already returns structured data, so fetching, cleaning and every
calculation are done in Python. The AI step is limited to what rules do
poorly: turning a row of figures into a readable sentence. Anything a rule can
do stays in code, because code gives the same result on every run and can be
audited.

## 2. Copilot instead of an API model

Target users have Microsoft 365 Copilot but no API access or Agent Builder.
The interpretation step therefore runs as a saved prompt in Copilot Chat on
batches of about 40 rows. This costs nothing extra and needs no new approvals,
at the price of a manual step and outputs that can vary between runs. For
larger or scheduled runs, the same batch files and validator work with a model
called through an API; only the middle step changes.

## 3. The AI never calculates

Every number a note may use (latest value, changes, year-ago value) is computed
in Python and placed in the batch row. Copilot only puts them into words. This
makes the main failure, invented or recalculated figures, checkable.

## 4. Nothing the AI writes is accepted unchecked

The validator recomputes what it can and rejects a row if:

- it was not returned, or returned twice;
- `direction` does not match the figures;
- the note is empty or longer than 30 words;
- the note contains a number that is not in that row.

Rejected rows go to `review.csv` with the reason, for a person. Figures in the
final output always come from the summary, never from Copilot's text.

## 5. Report problems, do not fix them silently

Cleaning drops blank values, unexpected countries, malformed periods and
duplicate series, and records each one with a count in `source_checks.csv`.
A user can see what was removed and why.

## 6. Keep the raw download

Each API response is saved unchanged with its URL, time and SHA-256 hash.
Later stages read the saved copy, so results can be traced to the exact
download and re-run without calling the API again (it is rate-limited).

## 7. Configuration, not code, defines the indicators

Indicators are entries in `config/indicators.toml`, copied from Data
Explorer's Developer API panel. Adding one needs no code change.

## 8. Tests run offline

Tests use synthetic downloads (invented numbers, clearly labelled) so CI does
not depend on the OECD API being reachable. The trade-off: the live API format
is checked only when the pipeline is run for real.
