#!/usr/bin/env python3
"""Offline/fixture E1 A/B/C/M harness, plus a group D ingest path.

Default mode=fixture never touches the network. Live mode without credentials
writes owner-blocked rows and refuses to fabricate hits.

Group D is a human procedure, not an automatable arm: prompts/d-assistant.txt
goes to a general web-enabled assistant under a 5-minute timebox and every
named repo is existence-checked. ``--d-input`` ingests what the operator
actually recorded (prompts/d-control.template.jsonl) so D becomes comparable
with A/B/C/M. With no recorded row the task stays owner-blocked/未运行.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.parse
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
E1 = HARNESS.parent
SCRIPTS = E1 / "scripts"
sys.path.insert(0, str(SCRIPTS))

import e1_d_control as d_control  # noqa: E402
from e1_batch import load_queries  # noqa: E402
from e1_minimal_runner import run_method  # noqa: E402
from query_generation import (  # noqa: E402
    load_fixtures,
    query_lang,
    variants_from_fixture,
)

HITS_PATH = HARNESS / "fixtures" / "search_hits.json"


def _utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def fixture_http_get(url: str, headers: dict) -> dict:
    del headers
    parsed = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
    data = json.loads(HITS_PATH.read_text(encoding="utf-8"))
    block = data.get(q) or {"items": []}
    return {"total_count": len(block.get("items", [])), "items": block.get("items", [])}


def original_variant(task: dict) -> dict:
    lang = query_lang(task["direction"])
    return {
        "variant_query": task["query"],
        "variant_lang": lang,
        "api_query": task["query"],
    }


def variants_for(task: dict, arm: str) -> list[dict]:
    orig = original_variant(task)
    if arm == "A":
        return [orig]
    extra = variants_from_fixture(task, arm, load_fixtures())
    if arm == "B":
        return [orig] + extra
    # C/M: original plus expansions, budget 4
    merged = [orig]
    seen = {orig["api_query"]}
    for v in extra:
        if v["api_query"] in seen:
            continue
        seen.add(v["api_query"])
        merged.append(v)
        if len(merged) >= 4:
            break
    return merged


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_fixture_batch(batch: str, arms: list[str], out_dir: Path, d_input: str | None = None) -> dict:
    queries = load_queries(E1 / "queries.yaml")
    tasks = queries[batch]
    fixtures = load_fixtures()
    run_id = f"fixture-{_utcnow()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Recorded group D rows, if the operator supplied any. Absent file or an
    # unparsable one must not silently become "no hallucinations".
    d_rows: dict[str, dict] = {}
    d_report: dict | None = None
    if d_input:
        try:
            d_rows = {
                row["task_id"]: row
                for row in d_control.load_rows(Path(d_input))
            }
        except (OSError, ValueError) as exc:
            raise SystemExit(json.dumps({"code": "bad_input", "message": str(exc)}, ensure_ascii=False))
        expected = [t["id"] for t in tasks]
        d_report = d_control.build_report(
            [d_rows[t] for t in expected if t in d_rows], expected, run_id
        )
        (out_dir / "d_control.json").write_text(
            json.dumps(d_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    query_rows = []
    hit_rows = []
    rank_rows = []
    fail_rows = []
    cost_rows = []
    candidate_rows = []

    for task in tasks:
        if task["id"] not in fixtures and any(a in "BCM" for a in arms):
            # A can still run on original query if hits exist; otherwise skip with note
            pass
        for arm in arms:
            if arm == "D":
                recorded = d_rows.get(task["id"])
                if recorded is None:
                    fail_rows.append(
                        {
                            "run_id": run_id,
                            "task_id": task["id"],
                            "arm": "D",
                            "code": "owner_blocked",
                            "message": "D 组为真人强对照：未记录到结果 / group D not recorded.",
                        }
                    )
                    cost_rows.append(
                        {
                            "run_id": run_id,
                            "task_id": task["id"],
                            "arm": "D",
                            "elapsed_ms": 0,
                            "github_requests": 0,
                            "model_requests": 0,
                            "visible_cost": "unknown",
                        }
                    )
                    continue
                # Real recorded control rows: verified hits and hallucinations
                # both stay in the record, with hallucinated names kept visible.
                scored = d_control.score_row(recorded)
                for rank, name in enumerate(recorded["repos"], start=1):
                    verified = recorded["verified"].get(name.lower())
                    hit_rows.append(
                        {
                            "run_id": run_id,
                            "task_id": task["id"],
                            "arm": "D",
                            "repo": name,
                            "rank": rank,
                            "stars": None,
                            "matched_fields": ["owner-recorded"],
                            "source": "owner-recorded",
                            # null means the operator has not checked it yet,
                            # which is not the same as "does not exist".
                            "verified": True if verified is True else (False if verified is False else None),
                            "hallucination": verified is False,
                        }
                    )
                cost_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": "D",
                        "elapsed_ms": scored["elapsed_ms"] or 0,
                        "github_requests": 0,
                        "model_requests": 0,
                        "visible_cost": "unknown",
                    }
                )
                fail_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": "D",
                        "code": "owner_recorded",
                        "message": (
                            f"named={scored['named_count']} verified={scored['verified_count']} "
                            f"hallucination={scored['hallucination_count']} "
                            f"unverified={len(scored['unverified_names'])}"
                        ),
                    }
                )
                continue
            if arm in ("B", "C", "M") and task["id"] not in fixtures:
                fail_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": arm,
                        "code": "owner_blocked",
                        "message": "无 fixture 变体；未调用模型。",
                    }
                )
                continue
            variants = variants_for(task, arm)
            for v in variants:
                query_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": arm,
                        "variant_query": v["variant_query"],
                        "variant_lang": v["variant_lang"],
                        "api_query": v["api_query"],
                        "source": "original" if v["api_query"] == task["query"] else "fixture",
                    }
                )
            started = datetime.datetime.now(datetime.timezone.utc)
            result = run_method(
                run_id=run_id,
                task_id=task["id"],
                direction=task["direction"],
                arm=arm,
                variants=variants,
                http_get=fixture_http_get,
                sleep_seconds=0,
                sleep_func=lambda _s: None,
            )
            elapsed = int(
                (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
                * 1000
            )
            for rec in result["per_query_records"]:
                hit_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": arm,
                        "repo": rec["repo"],
                        "rank": rec["rank"],
                        "stars": rec["stars"],
                        "matched_fields": rec["matched_fields"],
                        "source": "fixture",
                    }
                )
            for i, rec in enumerate(result["merged_candidates"], start=1):
                rank_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": arm,
                        "repo": rec["repo"],
                        "rank_after_merge": i,
                        "source_count": len(rec.get("sources") or [1]),
                    }
                )
                candidate_rows.append(rec)
            for err in result["errors"]:
                fail_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": arm,
                        "code": "bad_response",
                        "message": str(err.get("error")),
                    }
                )
            cost_rows.append(
                {
                    "run_id": run_id,
                    "task_id": task["id"],
                    "arm": arm,
                    "elapsed_ms": elapsed,
                    "github_requests": result["attempted_requests"],
                    "model_requests": 0,
                    "visible_cost": "unknown",
                }
            )

    write_jsonl(out_dir / "queries.jsonl", query_rows)
    write_jsonl(out_dir / "hits.jsonl", hit_rows)
    write_jsonl(out_dir / "rank.jsonl", rank_rows)
    write_jsonl(out_dir / "failures.jsonl", fail_rows)
    write_jsonl(out_dir / "latency_cost.jsonl", cost_rows)
    write_jsonl(out_dir / "candidates.jsonl", candidate_rows)
    manifest = {
        "run_id": run_id,
        "mode": "fixture",
        "batch": batch,
        "arms": arms,
        "status": "fixture-only-not-an-eval-run",
        "note": "未运行真实 GitHub Search / 模型。不得写入 experiments/.../runs/<日期>-*/ 冒充评估。",
        "d_control": (
            {
                "source": "owner-recorded",
                "tasks_recorded": d_report["totals"]["tasks_recorded"],
                "tasks_blocked": d_report["totals"]["tasks_blocked"],
                "repos_named": d_report["totals"]["repos_named"],
                "verified_hits": d_report["totals"]["verified_hits"],
                "hallucinations": d_report["totals"]["hallucinations"],
                "hallucination_rate": d_report["totals"]["hallucination_rate"],
                "repos_unverified": d_report["totals"]["repos_unverified"],
            }
            if d_report
            else {"source": "not-recorded", "status": "未运行"}
        ),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--batch", default="dev", choices=["dev", "eval.batch_1"])
    p.add_argument("--arms", default="A,B,C,M")
    p.add_argument("--mode", default="fixture", choices=["fixture", "live"])
    p.add_argument("--out", required=True)
    p.add_argument(
        "--d-input",
        help="JSONL of owner-recorded group D rows (see prompts/d-control.template.jsonl)",
    )
    args = p.parse_args(argv)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    if args.mode == "live":
        print(
            json.dumps(
                {
                    "code": "owner_blocked",
                    "status": "未运行",
                    "message": "live 路径需要发起人凭据与冻结批次；本命令拒绝编造命中。",
                },
                ensure_ascii=False,
            )
        )
        return 2
    if args.batch == "eval.batch_1":
        print(
            json.dumps(
                {
                    "code": "owner_blocked",
                    "status": "未运行",
                    "message": "eval.batch_1 尚未冻结（SHA 为 null）。fixture 请用 --batch dev。",
                },
                ensure_ascii=False,
            )
        )
        return 2
    manifest = run_fixture_batch(args.batch, arms, Path(args.out), d_input=args.d_input)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
