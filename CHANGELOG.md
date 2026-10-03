# Changelog

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
