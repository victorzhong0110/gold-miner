"""W4 orchestration over the frozen glossary document and seed set.

Network stays behind an injected ``http_get``. The CLI live path is opt-in.
B/C/M with empty glossary lists are recorded as blocked and do not invent
queries. D is not run. Model request count stays 0.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from .e1_batch import build_a_variants, is_eval_frozen, run_batch
    from .e1_glossary_variants import arm_variants
    from .e1_minimal_runner import run_method
except ImportError:  # direct script execution
    from e1_batch import build_a_variants, is_eval_frozen, run_batch  # type: ignore
    from e1_glossary_variants import arm_variants  # type: ignore
    from e1_minimal_runner import run_method  # type: ignore


def load_seed_rows(path: Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def seed_tasks(rows: list[dict]) -> list[dict]:
    tasks = []
    for row in rows:
        tasks.append(
            {
                "id": row["seed_id"],
                "direction": row["direction"],
                "query": row["query"],
                "need": row["source_blurb"],
                "written_at": row["frozen_at"][:10],
                "repo": row["repo"],
            }
        )
    return tasks


def run_seed_arm_a(
    *,
    rows: list[dict],
    run_id: str,
    http_get,
    token: str | None = None,
    per_page: int = 30,
    sleep_func=None,
    sleep_seconds: float = 0,
) -> dict:
    """Run arm A for known-target queries. One GitHub request per seed."""
    task_results = []
    totals = {
        "tasks": 0,
        "tasks_ok": 0,
        "tasks_error": 0,
        "attempted_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
    }
    for task in seed_tasks(rows):
        try:
            out = run_method(
                run_id=run_id,
                task_id=task["id"],
                direction=task["direction"],
                arm="A",
                variants=build_a_variants(task),
                seed_repos={task["repo"]},
                http_get=http_get,
                token=token,
                per_page=per_page,
                sleep_func=sleep_func,
                sleep_seconds=sleep_seconds,
            )
        except Exception as exc:
            task_results.append(
                {
                    "task_id": task["id"],
                    "direction": task["direction"],
                    "status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "merged_candidates": [],
                    "errors": [{"error": f"{type(exc).__name__}: {exc}"}],
                    "attempted_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                }
            )
            totals["tasks"] += 1
            totals["tasks_error"] += 1
            continue
        status = "ok"
        if out["attempted_requests"] > 0 and out["successful_requests"] == 0:
            status = "error"
            totals["tasks_error"] += 1
        else:
            totals["tasks_ok"] += 1
        totals["tasks"] += 1
        totals["attempted_requests"] += out["attempted_requests"]
        totals["successful_requests"] += out["successful_requests"]
        totals["failed_requests"] += out["failed_requests"]
        task_results.append(
            {
                "task_id": task["id"],
                "direction": task["direction"],
                "status": status,
                "target_repo": task["repo"],
                "merged_candidates": out["merged_candidates"],
                "errors": out["errors"],
                "attempted_requests": out["attempted_requests"],
                "successful_requests": out["successful_requests"],
                "failed_requests": out["failed_requests"],
            }
        )
    return {"task_results": task_results, "totals": totals, "hits": seed_hit_at_30(task_results)}


def seed_hit_at_30(task_results: list[dict]) -> list[dict]:
    """Rank of the designated repo inside that task's merged top 30.

    Missing means not in the window. This is not recall.
    """
    hits = []
    for tr in task_results:
        target = str(tr.get("target_repo") or "").lower()
        rank = None
        for index, row in enumerate(tr.get("merged_candidates") or [], start=1):
            if str(row.get("repo") or "").lower() == target:
                rank = index
                break
        hits.append(
            {
                "task_id": tr.get("task_id"),
                "direction": tr.get("direction"),
                "target_repo": tr.get("target_repo"),
                "rank_in_merged_top_30": rank,
                "hit_at_30": rank is not None,
                "status": tr.get("status"),
            }
        )
    return hits


def run_eval_arms(
    *,
    tasks: list,
    glossary_doc: dict,
    run_id: str,
    http_get,
    settings: dict,
    token: str | None = None,
    sleep_func=None,
    sleep_seconds: float = 0,
) -> dict:
    """Run A plus glossary B/C/M. Refuses when freeze markers are empty."""
    if not is_eval_frozen(settings):
        raise RuntimeError("eval.batch_1 freeze markers are null; refusing run")
    if http_get is None:
        raise RuntimeError("no http_get injected: refusing real network by default")
    per_page = int(settings.get("candidate_merge", {}).get("per_query_top_n", 30))
    arms: dict[str, Any] = {}
    a = run_batch(
        tasks=tasks,
        arm="A",
        run_id=run_id,
        http_get=http_get,
        token=token,
        per_page=per_page,
        sleep_func=sleep_func,
        sleep_seconds=sleep_seconds,
    )
    arms["A"] = a
    for arm in ("B", "C", "M"):
        variants = arm_variants(glossary_doc, arm)
        arms[arm] = run_batch(
            tasks=tasks,
            arm=arm,
            run_id=run_id,
            http_get=http_get,
            token=token,
            per_page=per_page,
            variants_by_task=variants,
            sleep_func=sleep_func,
            sleep_seconds=sleep_seconds,
        )
    model_requests = 0
    attempted = sum(arms[name]["totals"]["attempted_requests"] for name in arms)
    return {
        "arms": arms,
        "model_requests": model_requests,
        "attempted_requests": attempted,
        "d_status": "未运行",
        "e9_status": "未展开",
    }


def _write_candidates(path: Path, groups: list[list]) -> int:
    n = 0
    with path.open("w", encoding="utf-8") as handle:
        for rows in groups:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
    return n


def main(argv: list | None = None) -> int:
    """Opt-in live runner. Without --live, do not touch the network."""
    import argparse

    parser = argparse.ArgumentParser(description="W4 E1 live run (opt-in)")
    parser.add_argument("--queries", default="experiments/E1-cross-language-search/queries.yaml")
    parser.add_argument("--run-settings", default="experiments/E1-cross-language-search/run-settings.json")
    parser.add_argument("--glossary", default="experiments/E1-cross-language-search/variants/eval-batch-1-glossary.json")
    parser.add_argument("--seeds", default="experiments/E1-cross-language-search/seed-set.jsonl")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-runs-dir", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=7.0)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    if "runs" in out_dir.parts and not args.allow_runs_dir:
        print("refusing to write into runs/ without --allow-runs-dir")
        return 2
    if not args.live:
        print("no --live: refusing network by design")
        return 5

    try:
        from .e1_batch import load_queries, load_run_settings
        from .github_search import _urllib_get
    except ImportError:
        from e1_batch import load_queries, load_run_settings  # type: ignore
        from github_search import _urllib_get  # type: ignore

    settings = load_run_settings(Path(args.run_settings))
    if not is_eval_frozen(settings):
        print("eval.batch_1 未冻结 (freeze markers null): refusing run")
        return 3
    tasks = load_queries(Path(args.queries))["eval.batch_1"]
    glossary_doc = json.loads(Path(args.glossary).read_text(encoding="utf-8"))
    seed_rows = load_seed_rows(Path(args.seeds))
    token_used = bool(os.environ.get("GITHUB_TOKEN", "").strip())
    started_at = _utcnow_z()
    eval_out = run_eval_arms(
        tasks=tasks,
        glossary_doc=glossary_doc,
        run_id=args.run_id,
        http_get=_urllib_get,
        settings=settings,
        sleep_seconds=args.sleep_seconds,
    )
    seed_out = run_seed_arm_a(
        rows=seed_rows,
        run_id=args.run_id,
        http_get=_urllib_get,
        sleep_seconds=args.sleep_seconds,
    )
    finished_at = _utcnow_z()
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = []
    for arm_name, arm_out in eval_out["arms"].items():
        for tr in arm_out["task_results"]:
            groups.append(tr.get("merged_candidates") or [])
    for tr in seed_out["task_results"]:
        groups.append(tr.get("merged_candidates") or [])
    n_rows = _write_candidates(out_dir / "candidates.jsonl", groups)
    manifest = {
        "run_id": args.run_id,
        "batch": "eval.batch_1+seed-set",
        "materials_commit": settings["freeze"].get("eval_frozen_commit"),
        "freeze": settings.get("freeze"),
        "prompt_version": "prompts/ unused; glossary-mechanical-v1; model_requests=0",
        "model": None,
        "reading_setup": settings.get("reading_setup"),
        "field_config": (settings.get("field_config") or {}).get("main"),
        "started_at": started_at,
        "finished_at": finished_at,
        "github_token_used": token_used,
        "sleep_seconds": args.sleep_seconds,
        "model_requests": 0,
        "d_status": "未运行",
        "e9_status": "未展开",
        "candidate_rows": n_rows,
        "eval_arms": {
            name: arm_out["totals"] for name, arm_out in eval_out["arms"].items()
        },
        "eval_blocked_reasons": {
            name: sorted(
                {
                    tr.get("reason", "")
                    for tr in arm_out["task_results"]
                    if tr.get("status") == "blocked"
                }
            )
            for name, arm_out in eval_out["arms"].items()
        },
        "seed_a": seed_out["totals"],
        "seed_hits_at_30": seed_out["hits"],
        "errors": {
            "eval": {
                name: [
                    {"task_id": tr.get("task_id"), "errors": tr.get("errors", [])}
                    for tr in arm_out["task_results"]
                    if tr.get("errors")
                ]
                for name, arm_out in eval_out["arms"].items()
            },
            "seed": [
                {"task_id": tr.get("task_id"), "errors": tr.get("errors", [])}
                for tr in seed_out["task_results"]
                if tr.get("errors")
            ],
        },
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    a_ok = eval_out["arms"]["A"]["totals"]["successful_requests"]
    print(
        f"eval A successful_requests={a_ok} "
        f"seed successful_requests={seed_out['totals']['successful_requests']} "
        f"rows={n_rows} model_requests=0 out={out_dir}"
    )
    if a_ok == 0 and seed_out["totals"]["successful_requests"] == 0:
        return 2
    return 0


def _utcnow_z() -> str:
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


if __name__ == "__main__":
    import sys

    sys.exit(main())

