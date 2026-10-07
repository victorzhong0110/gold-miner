#!/usr/bin/env python3
"""B/C/M query generation with auditable JSONL records.

Modes:
- fixture: use frozen fixture variants; no model call.
- live: require an injected client, or allow_network=True plus OPENAI_*.
  Without a client and without allow_network, write owner-blocked (no billing).

Never invent GitHub repos. Never write secrets into records.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Protocol

from secret_scrub import redact, sha256_text

E1 = Path(__file__).resolve().parents[1]
ROOT = E1.parents[1]
FIXTURES = E1 / "harness" / "fixtures" / "query_variants.json"
PROMPTS = {
    "B": E1 / "prompts" / "b-translate.txt",
    "C": E1 / "prompts" / "c-rewrite.txt",
    "M": E1 / "prompts" / "m-rewrite.txt",
}

MAX_OUTPUT_TOKENS = 2048

# How much raw model text a failure record may carry. Enough to diagnose a
# parse failure, small enough that a run record stays readable in git.
RAW_CAPTURE_LIMIT = 16000
EXCERPT_LIMIT = 500

HttpPost = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class QueryClientError(Exception):
    """A model call failed.

    `raw_output` / `answer_text` carry the provider's actual reply so the
    failure can be diagnosed from the committed record. Without them a parse
    failure is unrecoverable: the run may not be re-driven into the same
    batch, so the evidence has to be written down the first time.
    """

    def __init__(
        self,
        code: str,
        notes: str = "",
        raw_output: str = "",
        answer_text: str = "",
    ) -> None:
        super().__init__(code)
        self.code = code
        self.notes = notes
        self.raw_output = raw_output
        self.answer_text = answer_text


class QueryClient(Protocol):
    def generate_variants(self, task: dict, arm: str, prompt: str) -> list[dict]:
        ...


def _utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def prompt_paths(profile: str = "eval.batch_1") -> dict[str, Path]:
    if profile == "eval.batch_1":
        return dict(PROMPTS)
    if profile == "eval.batch_2":
        directory = E1 / "batches" / profile / "prompts"
        return {arm: directory / path.name for arm, path in PROMPTS.items()}
    raise ValueError("unknown prompt profile")


def prompt_hash(arm: str, profile: str = "eval.batch_1") -> str:
    text = prompt_paths(profile)[arm].read_text(encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def input_hash(task: dict) -> str:
    payload = json.dumps(
        {"id": task["id"], "query": task["query"], "direction": task["direction"]},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_queries_yaml(path: Path) -> list[dict]:
    sys.path.insert(0, str(E1 / "scripts"))
    from e1_batch import load_queries  # type: ignore

    data = load_queries(path)
    return [task for tasks in data.values() for task in tasks]


def load_fixtures() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def other_lang(direction: str) -> str:
    return "en" if direction == "zh2en" else "zh"


def query_lang(direction: str) -> str:
    return "zh" if direction == "zh2en" else "en"


def variants_from_fixture(task: dict, arm: str, fixtures: dict) -> list[dict]:
    block = fixtures.get(task["id"], {}).get(arm)
    if not block:
        raise KeyError(f"no fixture for {task['id']} arm {arm}")
    return list(block["variants"])


def record_row(
    *,
    task: dict,
    arm: str,
    mode: str,
    variants: list[dict] | None,
    code: str,
    notes: str,
    prompt_profile: str = "eval.batch_1",
    prompt_text: str | None = None,
) -> dict:
    return {
        "recorded_at": _utcnow(),
        "task_id": task["id"],
        "direction": task["direction"],
        "arm": arm,
        "mode": mode,
        "prompt_file": str(prompt_paths(prompt_profile)[arm].relative_to(ROOT)),
        "prompt_sha256_16": hashlib.sha256((prompt_text if prompt_text is not None else
            prompt_paths(prompt_profile)[arm].read_text(encoding="utf-8")).encode()).hexdigest()[:16],
        "input_sha256_16": input_hash(task),
        "original_query": task["query"],
        "variants": variants or [],
        "code": code,
        "notes": notes,
    }


def _strip_think(text: str) -> str:
    """Drop inline <think> reasoning, matching the parser's own rule."""
    out = re.sub(r"<think\b[^>]*>[\s\S]*?</think\s*>", "", text or "", flags=re.I)
    return re.sub(r"<think\b[^>]*>[\s\S]*$", "", out, flags=re.I).strip()


def _failure_diagnostics(exc: QueryClientError, secret: str = "") -> dict:
    """Model text to store with a failed row, scrubbed and bounded.

    Mirrors what e1_d_assistant.py already records for the D arm, so a B/C/M
    parse failure is diagnosable from the committed run the same way a D
    failure is.
    """
    if not exc.raw_output and not exc.answer_text:
        return {}
    raw = exc.raw_output or ""
    answer = exc.answer_text or ""
    fields = {
        "raw_output_sha256": sha256_text(raw),
        "raw_output_chars": len(raw),
        "think_present": "<think" in raw.lower(),
    }
    if answer:
        fields["answer_text"] = redact(answer, secret)[:EXCERPT_LIMIT]
    if raw and len(raw) <= RAW_CAPTURE_LIMIT:
        fields["raw_output"] = redact(raw, secret)
    return fields


def _top_level_brace_groups(text: str) -> list[str]:
    """Return every balanced top-level {...} span, ignoring braces in strings.

    Used to refuse an ambiguous reply instead of guessing. `find("{")` /
    `rfind("}")` silently returns the FIRST brace group, so a reply shaped
    like `Example: {"zh":["demo"]} -> your answer` would have "demo" recorded
    as a real search query with no trace that it came from a prose example.
    """
    groups: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    groups.append(text[start : index + 1])
                    start = -1
    return groups


def _extract_json_object(text: str) -> dict:
    raw = _strip_think(text)
    groups = _top_level_brace_groups(raw)
    if not groups:
        raise QueryClientError("bad_response", "model output was not a JSON object")
    if len(groups) > 1:
        # More than one object means we cannot tell which one the model meant.
        # Refusing is the honest outcome; guessing would put an unrelated
        # string into the candidate set as if it were a real query.
        raise QueryClientError(
            "ambiguous_model_output",
            f"model output contained {len(groups)} JSON objects; refusing to guess which was the answer",
        )
    # A single example object inside prose is just as ambiguous as two objects.
    # Accept the requested JSON, optionally fenced, but never select an object
    # out of an explanation or a JSON array.
    envelope = re.sub(r"^```(?:json)?\s*\n?([\s\S]*?)\n?```$", r"\1", raw, flags=re.I).strip()
    if envelope != groups[0]:
        raise QueryClientError("ambiguous_model_output", "model output must contain only one JSON object (optional code fence)")
    try:
        data = json.loads(groups[0])
    except json.JSONDecodeError as exc:
        raise QueryClientError("bad_response", "model output JSON parse failed") from exc
    if not isinstance(data, dict):
        raise QueryClientError("bad_response", "model output JSON was not an object")
    return data


def parse_model_variants(arm: str, direction: str, text: str) -> list[dict]:
    data = _extract_json_object(text)
    variants: list[dict] = []
    if arm == "B":
        q = str(data.get("query") or "").strip()
        lang = str(data.get("other_lang") or other_lang(direction))
        if q:
            variants.append(
                {"variant_query": q, "variant_lang": lang, "api_query": q}
            )
        return variants
    if arm == "C":
        for lang_key in ("zh", "en"):
            for q in data.get(lang_key) or []:
                s = str(q).strip()
                if s:
                    variants.append(
                        {
                            "variant_query": s,
                            "variant_lang": lang_key,
                            "api_query": s,
                        }
                    )
        return variants
    if arm == "M":
        lang = str(data.get("same_lang") or query_lang(direction))
        for q in data.get("queries") or []:
            s = str(q).strip()
            if s:
                variants.append(
                    {"variant_query": s, "variant_lang": lang, "api_query": s}
                )
        return variants
    raise QueryClientError("bad_response", f"unknown arm {arm}")


class _NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_http_post(
    url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        opener = urllib.request.build_opener(_NoCredentialRedirect())
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:8000]
            return {"status": int(resp.status), "body": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:8000]
        return {"status": int(exc.code), "body": body}
    except TimeoutError as exc:
        raise QueryClientError("timeout", "model request timed out") from exc
    except Exception as exc:  # noqa: BLE001 — classify, do not invent variants
        raise QueryClientError("network_error", type(exc).__name__) from exc


class HttpQueryClient:
    """OpenAI-compatible chat client. http_post is injectable."""

    def __init__(
        self,
        http_post: HttpPost | None = None,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout: float = 60.0,
    ) -> None:
        self.http_post = http_post or _default_http_post
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.last_usage: dict | None = None

    def generate_variants(self, task: dict, arm: str, prompt: str) -> list[dict]:
        url = self.base_url + "/chat/completions"
        user = f"用户原话：{task['query']}"
        if arm == "B":
            user += f"\n方向：{other_lang(task['direction'])}"
        elif arm == "M":
            user += f"\n查询语言：{query_lang(task['direction'])}"
        self.last_usage = None
        payload = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user},
            ],
        }
        packed = self.http_post(
            url,
            {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.api_key,
                "User-Agent": "gold-miner-query-generation/0.1",
            },
            payload,
            self.timeout,
        )
        status = int(packed.get("status") or 0)
        body = str(packed.get("body") or "")
        if status in (401, 403):
            raise QueryClientError("auth_rejected", f"http {status}")
        if status == 429:
            raise QueryClientError("rate_limited", "http 429")
        if status == 404:
            raise QueryClientError("model_unavailable", "http 404")
        if status != 200:
            raise QueryClientError("bad_response", f"http {status}")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise QueryClientError("bad_response", "response was not JSON") from exc
        if not isinstance(data, dict):
            raise QueryClientError("bad_response", "response was not an object")
        self.last_usage = _visible_usage(data.get("usage"))
        base_resp = data.get("base_resp")
        if isinstance(base_resp, dict) and base_resp.get("status_code") == 1004:
            raise QueryClientError("auth_rejected", "provider auth rejection; check key and platform region")
        if data.get("error") or (isinstance(base_resp, dict) and base_resp.get("status_code")):
            raise QueryClientError("bad_response", "provider returned an error")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise QueryClientError("bad_response", "response missing valid choices")
        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if finish_reason == "length":
            raise QueryClientError(
                "model_output_truncated", f"completion exceeded the {MAX_OUTPUT_TOKENS}-token cap",
                raw_output=content if isinstance(content, str) else "",
                answer_text=_strip_think(content) if isinstance(content, str) else "",
            )
        if not isinstance(content, str) or not content.strip():
            raise QueryClientError(
                "empty_model_output",
                "response missing a final answer",
                raw_output=json.dumps(content)[:RAW_CAPTURE_LIMIT]
                if content is not None
                else "",
            )
        try:
            variants = parse_model_variants(arm, task["direction"], str(content))
        except QueryClientError as exc:
            # The reply is the only evidence of what the model actually said.
            exc.raw_output = exc.raw_output or content
            exc.answer_text = exc.answer_text or _strip_think(content)
            raise
        if not variants:
            raise QueryClientError(
                "bad_response",
                "model returned no variants",
                raw_output=content,
                answer_text=_strip_think(content),
            )
        return variants


def _visible_usage(usage: Any) -> dict | None:
    """Keep only numeric token counters the provider returned; never guess."""
    if not isinstance(usage, dict):
        return None
    def num(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    details = usage.get("completion_tokens_details")
    prompt_details = usage.get("prompt_tokens_details")
    return {
        "prompt_tokens": num(usage.get("prompt_tokens")),
        "completion_tokens": num(usage.get("completion_tokens")),
        "reasoning_tokens": num(details.get("reasoning_tokens")) if isinstance(details, dict) else None,
        "cached_prompt_tokens": num(prompt_details.get("cached_tokens")) if isinstance(prompt_details, dict) else None,
        "total_tokens": num(usage.get("total_tokens")),
    }


def default_client_from_env(*, http_post: HttpPost | None = None) -> HttpQueryClient | None:
    key = os.environ.get("OPENAI_API_KEY") or ""
    base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    model = os.environ.get("OPENAI_MODEL") or ""
    if not key.strip():
        return None
    if not base.startswith(("http://", "https://")):
        return None
    if not model.strip():
        return None
    timeout = float(os.environ.get("BYOK_TIMEOUT_SECONDS") or "60")
    return HttpQueryClient(
        http_post,
        base_url=base,
        model=model,
        api_key=key,
        timeout=timeout,
    )


def generate(
    task: dict,
    arm: str,
    mode: str,
    client: QueryClient | None = None,
    *,
    allow_network: bool = False,
    http_post: HttpPost | None = None,
    prompt_profile: str = "eval.batch_1",
    expected_prompt_sha256: str | None = None,
) -> dict:
    paths = prompt_paths(prompt_profile)
    if arm not in paths:
        raise ValueError("arm must be B, C or M")
    prompt = paths[arm].read_text(encoding="utf-8")
    if expected_prompt_sha256 is not None and hashlib.sha256(prompt.encode()).hexdigest() != expected_prompt_sha256:
        raise ValueError("prompt materials digest changed before dispatch")
    if mode == "fixture":
        variants = variants_from_fixture(task, arm, load_fixtures())
        return record_row(
            task=task,
            arm=arm,
            mode="fixture",
            variants=variants,
            code="ok",
            notes="fixture; not a model run",
            prompt_profile=prompt_profile, prompt_text=prompt,
        )
    if mode != "live":
        raise ValueError("mode must be fixture or live")
    if client is None and allow_network:
        client = default_client_from_env(http_post=http_post)
    if client is None:
        key = os.environ.get("OPENAI_API_KEY") or ""
        notes = (
            "未运行 / owner-blocked：缺少 OPENAI_API_KEY，未调用模型。"
            if not key.strip()
            else "未运行 / owner-blocked：未注入 client 且 allow_network=False，不自动计费。"
        )
        return record_row(
            task=task,
            arm=arm,
            mode="live",
            variants=None,
            code="owner_blocked",
            notes=notes,
            prompt_profile=prompt_profile, prompt_text=prompt,
        )
    started = time.monotonic()
    def recorded(**fields):
        row = record_row(**fields, prompt_profile=prompt_profile, prompt_text=prompt)
        if isinstance(client, HttpQueryClient):
            row["request_parameters"] = {"model": client.model,
                "base_url_host": urllib.request.urlparse(client.base_url).hostname,
                "max_tokens": MAX_OUTPUT_TOKENS, "timeout_seconds": client.timeout,
                "max_model_requests": 1, "automatic_retries": 0}
            # Visible counters only; None means the provider gave none (e.g. timeout).
            row["usage"] = client.last_usage
            row["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return row
    try:
        variants = client.generate_variants(task, arm, prompt)
    except QueryClientError as exc:
        secret = client.api_key if isinstance(client, HttpQueryClient) else ""
        row = recorded(
            task=task,
            arm=arm,
            mode="live",
            variants=None,
            code=exc.code,
            notes=redact(exc.notes or exc.code, secret),
        )
        # Keep the evidence: without it this failure cannot be diagnosed later.
        row.update(_failure_diagnostics(exc, secret))
        return row
    return recorded(
        task=task,
        arm=arm,
        mode="live",
        variants=variants,
        code="ok",
        notes="live model client",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task-id", required=True)
    p.add_argument("--arm", required=True, choices=["B", "C", "M"])
    p.add_argument("--mode", default="fixture", choices=["fixture", "live"])
    p.add_argument("--queries", default=str(E1 / "queries.yaml"))
    p.add_argument("--out", default="")
    p.add_argument("--prompt-profile", choices=["eval.batch_1", "eval.batch_2"], default="eval.batch_1")
    args = p.parse_args(argv)

    from e1_batch import load_queries
    batches = load_queries(Path(args.queries))
    if args.prompt_profile == "eval.batch_2":
        if not batches.get("eval.batch_2"):
            p.error("batch_2 prompt profile requires batch_2 query materials")
        if args.mode == "live":
            p.error("use e1_pipeline.py with frozen batch_2 settings for a live evaluation")
        selected = batches["dev"] + batches["eval.batch_2"]
    else:
        selected = batches["dev"] + batches["eval.batch_1"]
    tasks = {t["id"]: t for t in selected}
    if args.task_id not in tasks:
        print(json.dumps({"code": "bad_response", "message": "unknown task"}, ensure_ascii=False))
        return 2
    row = generate(
        tasks[args.task_id],
        args.arm,
        args.mode,
        allow_network=args.mode == "live",
        prompt_profile=args.prompt_profile,
    )
    line = json.dumps(row, ensure_ascii=False)
    if any(re.search(pat, line) for pat in (r"sk-[A-Za-z0-9]{8,}", r"ghp_[A-Za-z0-9]+")):
        raise RuntimeError("refusing to write a record that looks like a secret")
    print(line)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        dest = out / "query_generation.jsonl"
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return 0 if row["code"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
