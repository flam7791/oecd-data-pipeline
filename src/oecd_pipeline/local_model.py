"""Stage 3, local alternative: an open-weight model writes the notes.

Same saved prompt, same batch files, same validator as the Copilot route; only the writer
changes. The model runs behind any OpenAI-compatible endpoint: Ollama on a laptop (the
default), vLLM or llama.cpp on a server, or an LLM gateway. Nothing leaves the machine with the
default settings, no licence is needed, and the step can run unattended on many batches.

The validator is what makes a small model acceptable here: it cannot add a number that is not
in the row, contradict the computed direction, or skip a row without the row going to review.
A weaker model raises the review rate; it does not lower the quality of what is accepted.

Replies can be recorded and replayed offline (`--recordings`), so an evaluation run against a
local model can be committed and re-checked in CI without the model.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

DEFAULT_BASE_URL = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible API
DEFAULT_MODEL = "llama3.2:3b"


class ModelError(RuntimeError):
    pass


class ReplayMiss(ModelError):
    """Offline replay found no recording for a request."""


@dataclass
class BatchResult:
    batch: str
    rows: int
    returned: int
    status: str  # ok, unparsed, error
    detail: str = ""


def prompt_instructions(prompt_path: str | Path) -> str:
    """The instructions between the two `---` lines of the saved Copilot prompt.

    One prompt for both routes, so a wording change reaches Copilot users and the local model
    alike.
    """
    text = Path(prompt_path).read_text(encoding="utf-8")
    parts = re.split(r"^---\s*$", text, flags=re.M)
    if len(parts) < 3:
        raise ValueError(f"{prompt_path}: expected the instructions between two '---' lines")
    instructions = parts[1].strip()
    return instructions.replace("the attached CSV file", "the CSV file below")


def extract_csv(reply: str) -> pd.DataFrame | None:
    """The `row_id,direction,note` table in a reply, from a code block or bare text."""
    blocks = re.findall(r"```(?:csv)?\s*\n(.*?)```", reply, flags=re.S)
    candidates = blocks + [reply]
    for text in candidates:
        start = text.lower().find("row_id")
        if start == -1:
            continue
        try:
            df = pd.read_csv(io.StringIO(text[start:]), dtype=str, keep_default_na=False)
        except Exception:  # noqa: BLE001 - any parse failure means "not usable"
            continue
        df.columns = [c.strip().lower() for c in df.columns]
        if {"row_id", "direction", "note"} <= set(df.columns):
            return df[["row_id", "direction", "note"]]
    return None


Post = Callable[[str, dict, dict], dict]


def _http_post(url: str, body: dict, headers: dict, timeout: float = 600.0) -> dict:
    try:
        response = requests.post(url, json=body, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise ModelError(f"{url}: {exc}") from exc


class ChatModel:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_key: str = "",
        recordings: str | Path | None = None,
        offline: bool = False,
        post: Post | None = None,
    ):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.recordings = Path(recordings) if recordings else None
        self.offline = offline
        self.post = post or _http_post
        if offline and not self.recordings:
            raise ValueError("offline replay needs a recordings folder")

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        path = None
        if self.recordings:
            key = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
            path = self.recordings / f"{key[:32]}.json"
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))["reply"]
            if self.offline:
                raise ReplayMiss(f"no recording {path.name}; record a live run first")
        data = self.post(self.url, body, self.headers)
        try:
            reply = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"unexpected reply from {self.url}") from exc
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {"model": self.model, "reply": reply, "usage": data.get("usage", {})}
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8")
        return reply


def interpret_batches(
    batch_dir: str | Path,
    responses_dir: str | Path,
    prompt_path: str | Path,
    model: ChatModel,
) -> list[BatchResult]:
    """Ask the model to fill every batch; write its answers where the validator reads them."""
    batch_dir, responses_dir = Path(batch_dir), Path(responses_dir)
    responses_dir.mkdir(parents=True, exist_ok=True)
    for old in responses_dir.glob("batch_*.csv"):
        old.unlink()
    system = prompt_instructions(prompt_path)
    results = []
    for batch in sorted(batch_dir.glob("batch_*.csv")):
        table = pd.read_csv(batch, dtype=str, keep_default_na=False)
        user = f"The CSV file ({batch.name}):\n\n```csv\n{batch.read_text(encoding='utf-8')}```"
        try:
            reply = model.complete(system, user)
        except ReplayMiss:
            raise
        except ModelError as exc:
            results.append(BatchResult(batch.name, len(table), 0, "error", str(exc)))
            continue
        answers = extract_csv(reply)
        if answers is None:
            # Keep the raw reply for a person; the validator will send these rows to review.
            (responses_dir / f"{batch.stem}.unparsed.txt").write_text(reply, encoding="utf-8")
            results.append(BatchResult(batch.name, len(table), 0, "unparsed", "no CSV found"))
            continue
        answers.to_csv(responses_dir / batch.name, index=False)
        results.append(BatchResult(batch.name, len(table), len(answers), "ok"))
    return results
