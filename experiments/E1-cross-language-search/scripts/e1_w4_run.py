"""W4 orchestration over the frozen glossary document and seed set.

Network stays behind an injected ``http_get``. The CLI live path is opt-in.
B/C/M with empty glossary lists are recorded as blocked and do not invent
queries. D is not run. Model request count stays 0.
"""

from __future__ import annotations

import json
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
