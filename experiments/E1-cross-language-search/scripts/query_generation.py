#!/usr/bin/env python3
"""B/C/M query generation with auditable JSONL records.

Modes:
- fixture: use frozen fixture variants; no model call.
- live: require OPENAI_* env; without key write owner-blocked and exit 2.

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
from pathlib import Path

E1 = Path(__file__).resolve().parents[1]
ROOT = E1.parents[1]
FIXTURES = E1 / "harness" / "fixtures" / "query_variants.json"
PROMPTS = {
    "B": E1 / "prompts" / "b-translate.txt",
    "C": E1 / "prompts" / "c-rewrite.txt",
    "M": E1 / "prompts" / "m-rewrite.txt",
}


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


def generate(task: dict, arm: str, mode: str) -> dict:
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
    key = os.environ.get("OPENAI_API_KEY") or ""
    if not key.strip():
        return record_row(
            task=task,
            arm=arm,
            mode="live",
            variants=None,
            code="owner_blocked",
            notes="未运行 / owner-blocked：缺少 OPENAI_API_KEY，未调用模型。",
        )
    return record_row(
        task=task,
        arm=arm,
        mode="live",
        variants=None,
        code="owner_blocked",
        notes="未运行：本脚本的 live 模型客户端未在无发起人确认下发出请求。配置存在也不自动计费。",
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
    row = generate(tasks[args.task_id], args.arm, args.mode)
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
