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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Protocol

E1 = Path(__file__).resolve().parents[1]
ROOT = E1.parents[1]
FIXTURES = E1 / "harness" / "fixtures" / "query_variants.json"
PROMPTS = {
    "B": E1 / "prompts" / "b-translate.txt",
    "C": E1 / "prompts" / "c-rewrite.txt",
    "M": E1 / "prompts" / "m-rewrite.txt",
}

HttpPost = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class QueryClientError(Exception):
    def __init__(self, code: str, notes: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.notes = notes


class QueryClient(Protocol):
    def generate_variants(self, task: dict, arm: str, prompt: str) -> list[dict]:
        ...


def _utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def prompt_hash(arm: str) -> str:
    text = PROMPTS[arm].read_text(encoding="utf-8")
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
    return data["dev"] + data["eval.batch_1"]


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
) -> dict:
    return {
        "recorded_at": _utcnow(),
        "task_id": task["id"],
        "direction": task["direction"],
        "arm": arm,
        "mode": mode,
        "prompt_file": str(PROMPTS[arm].relative_to(ROOT)),
        "prompt_sha256_16": prompt_hash(arm),
        "input_sha256_16": input_hash(task),
        "original_query": task["query"],
        "variants": variants or [],
        "code": code,
        "notes": notes,
    }


def _extract_json_object(text: str) -> dict:
    raw = (text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise QueryClientError("bad_response", "model output was not a JSON object")
    try:
        data = json.loads(raw[start : end + 1])
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        timeout: float = 20.0,
    ) -> None:
        self.http_post = http_post or _default_http_post
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def generate_variants(self, task: dict, arm: str, prompt: str) -> list[dict]:
        url = self.base_url + "/chat/completions"
        user = f"用户原话：{task['query']}"
        if arm == "B":
            user += f"\n方向：{other_lang(task['direction'])}"
        elif arm == "M":
            user += f"\n查询语言：{query_lang(task['direction'])}"
        payload = {
            "model": self.model,
            "max_tokens": 256,
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
        if not isinstance(data, dict) or "choices" not in data:
            raise QueryClientError("bad_response", "response missing choices")
        content = (
            data.get("choices")
            and data["choices"][0].get("message", {}).get("content")
        ) or ""
        variants = parse_model_variants(arm, task["direction"], str(content))
        if not variants:
            raise QueryClientError("bad_response", "model returned no variants")
        return variants


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
    timeout = float(os.environ.get("BYOK_TIMEOUT_SECONDS") or "20")
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
) -> dict:
    if arm not in PROMPTS:
        raise ValueError("arm must be B, C or M")
    if mode == "fixture":
        variants = variants_from_fixture(task, arm, load_fixtures())
        return record_row(
            task=task,
            arm=arm,
            mode="fixture",
            variants=variants,
            code="ok",
            notes="fixture; not a model run",
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
        )
    prompt = PROMPTS[arm].read_text(encoding="utf-8")
    try:
        variants = client.generate_variants(task, arm, prompt)
    except QueryClientError as exc:
        return record_row(
            task=task,
            arm=arm,
            mode="live",
            variants=None,
            code=exc.code,
            notes=exc.notes or exc.code,
        )
    return record_row(
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
    args = p.parse_args(argv)

    tasks = {t["id"]: t for t in load_queries_yaml(Path(args.queries))}
    if args.task_id not in tasks:
        print(json.dumps({"code": "bad_response", "message": "unknown task"}, ensure_ascii=False))
        return 2
    row = generate(
        tasks[args.task_id],
        args.arm,
        args.mode,
        allow_network=args.mode == "live",
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
