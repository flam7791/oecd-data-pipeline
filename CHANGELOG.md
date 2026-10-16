# Changelog

## 0.2.2 (2026-10)

- Lint in CI, with the same ruff rules as the other repositories (`ruff check`, `ruff format
  --check`): imports sorted, unused imports removed, `datetime.UTC`, explicit `zip(strict=...)`,
  long lines wrapped. No behaviour change: tests, the stand-in evaluation and both recorded
  model runs give the same results.
- `AGENTS.md` (commands, layout, invariants) for coding agents; `CLAUDE.md` imports it.
- The README opens with the framework pattern this repository implements and a link to the
  other repositories.
- `CITATION.cff`, so GitHub offers "Cite this repository".

## 0.2.1 (2026-10)

- First live run with Llama 3.1 8B through Ollama: 7/9 rows accepted, recorded and replayed in CI.
- Parser accepts rows ending with a stray comma (found in the live run).
- Review reasons are grouped without the model's text in the key.

## 0.2.0 (2026-10)

- `interpret`: a local open-weight model (Ollama, vLLM, any OpenAI-compatible endpoint) writes the notes, with the same prompt and validator as the Copilot route. Replies can be recorded and replayed offline.
- `eval`: a fixed evaluation set (`evals/sample`, synthetic figures) reports the acceptance rate and review reasons per writer; CI runs it with the stand-in and replays recorded model runs.
- CI: dependency vulnerability scan.

## 0.1.0 (2026-10)

- Fetch with provenance, rule-based cleaning, Copilot batches and prompt, validator.
