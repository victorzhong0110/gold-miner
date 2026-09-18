"""E1 batch orchestration over queries.yaml (owner-independent part).

Basis:
- experiments/E1-cross-language-search/protocol.md Sections 2-5
- experiments/E1-cross-language-search/run-settings.json (budgets, top_n)
- experiments/E1-cross-language-search/queries.yaml (dev + eval.batch_1)
- docs/engineering/prerequisites.md Section 1 (serial, no fixed-interval
  guarantee, failures recorded, public sources first)

Scope (honest, owner-independent):
- A-arm batch runs natively: variant = original query, default field,
  no model, no owner input. Works with any injected ``http_get``.
- B/C/M/D are NOT generated here: they need a model, a fixed wordlist
  decision, or a networked assistant (owner/personal-API dependent).
  Callers must supply explicit ``variants`` per task via
  ``variants_by_task`` (e.g. from a frozen file). Without them the batch
  refuses that arm with a ``blocked`` record instead of fabricating
  queries. Task IDs in the variants file are checked against the batch
  (coverage miss = blocked). CLI treats blocked / coverage miss as a
  non-zero exit and prints ok/blocked/fail counts plus the reason.
  D is always refused (tool control, no GitHub budget).
- eval.batch_1 refuses to run while freeze markers are null, unless the
  caller passes ``allow_unfrozen=True`` explicitly for a local dry-run.
  Dry-runs never write into ``runs/`` unless ``allow_runs_dir=True`` AND
  a real ``http_get`` was used; by default output goes to the given
  ``out_dir`` (suggest /tmp) or is returned in-memory.
- No network by default: ``http_get=None`` raises inside
  ``e1_minimal_runner.run_method``; the batch records per-task errors
  and never fabricates candidates.
- No secrets inside: token flows via explicit arg or ``GITHUB_TOKEN``
  env inside ``github_search``; this module never logs headers or keys.
- Serial execution only; ``should_cancel`` stops before each new task
  (remaining tasks marked cancelled, already-finished tasks kept).

Machine-readable output:
- candidates JSONL rows conform to schemas/candidates.schema.json
  required fields (merged rows carry ``sources``).
- manifest JSON with run_id, batch, arm, materials_commit (git HEAD or
  "unknown"), settings snapshot bits, per-task counters, totals, errors.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
from pathlib import Path
from collections.abc import Callable
from typing import Any

try:
    from .e1_minimal_runner import (
        ARM_BUDGETS,
        MERGED_TOP_N,
        PER_QUERY_TOP_N,
        run_method,
    )
except ImportError:  # direct script execution
    from e1_minimal_runner import (  # type: ignore
        ARM_BUDGETS,
        MERGED_TOP_N,
        PER_QUERY_TOP_N,
        run_method,
    )

ALLOWED_ARMS = frozenset(ARM_BUDGETS)
ALLOWED_BATCHES = ("dev", "eval.batch_1")


def _utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def materials_commit(repo_root: Path | None = None) -> str:
    """Return git HEAD SHA or "unknown" (never fabricate)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root) if repo_root else None,
            capture_output=True,
            text=True,
            timeout=15,
        )
        sha = (out.stdout or "").strip()
        if out.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
        return "unknown"
    except Exception:
        return "unknown"


def load_queries(path: Path) -> dict:
    """Parse the small subset of queries.yaml we need (no pyyaml).

    Returns {"dev": [...], "eval.batch_1": [...]} where each task has
    id/direction/type/query/need/written_at. Raises on missing fields.
    """
    text = Path(path).read_text(encoding="utf-8")
    dev: list = []
    eval1: list = []
    section: str | None = None
    current: dict | None = None

    def flush() -> None:
        if current is None:
            return
        for f in ("id", "direction", "type", "query", "need", "written_at"):
            if f not in current or not str(current[f]).strip():
                raise ValueError(f"task missing field {f}: {current.get('id')}")
        if section == "dev":
            dev.append(dict(current))
        elif section == "batch_1":
            eval1.append(dict(current))

    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped == "dev:":
            flush()
            current = None
            section = "dev"
            continue
        if stripped == "eval:":
            flush()
            current = None
            section = "eval"
            continue
        if stripped == "batch_1:":
            flush()
            current = None
            section = "batch_1"
            continue
        m = re.match(r"^(\s*)-\s+id:\s*(\S+)\s*$", raw)
        if m:
            flush()
            current = {"id": m.group(2)}
            continue
        if current is not None:
            fm = re.match(
                r"^\s+(direction|type|query|need|written_at):\s*(.+?)\s*$", raw
            )
            if fm:
                current[fm.group(1)] = fm.group(2)
    flush()
    return {"dev": dev, "eval.batch_1": eval1}


def load_run_settings(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_eval_frozen(settings: dict) -> bool:
    freeze = settings.get("freeze", {}) if isinstance(settings, dict) else {}
    keys = (
        "eval_frozen_commit",
        "prompts_frozen_commit",
        "seed_set_frozen_commit",
        "run_settings_commit",
    )
    return all(freeze.get(k) not in (None, "null", "") for k in keys)


def check_variant_coverage(tasks: list, variants_by_task: dict | None) -> dict:
    """Compare batch task IDs to a variants mapping.

    A task is missing when its id is absent or the supplied list is empty.
    Extra variant keys (not in the batch) are reported but do not fail
    completeness: the batch only requires every task to be covered.
    """
    if not isinstance(tasks, list):
        raise ValueError("tasks must be a list")
    task_ids = [str(t.get("id", "")).strip() for t in tasks]
    provided = variants_by_task if isinstance(variants_by_task, dict) else {}
    missing: list[str] = []
    for tid in task_ids:
        supplied = provided.get(tid)
        if not supplied:
            missing.append(tid)
    extra = [k for k in provided if k not in set(task_ids)]
    return {
        "task_ids": task_ids,
        "missing_task_ids": missing,
        "extra_variant_ids": extra,
        "covered": len(task_ids) - len(missing),
        "complete": len(missing) == 0 and len(task_ids) > 0,
    }


def decide_exit(
    totals: dict,
    coverage: dict | None = None,
) -> tuple[int, str]:
    """Map batch totals / coverage to a process exit code and reason.

    0: all attempted work ok (and coverage complete when checked).
    1: mixed failure — any error/partial, or some-but-not-all blocked.
    2: requests were attempted and every request failed.
    7: coverage miss or every task blocked (no useful coverage).
    """
    n_tasks = int(totals.get("tasks", 0) or 0)
    n_blocked = int(totals.get("tasks_blocked", 0) or 0)
    n_error = int(totals.get("tasks_error", 0) or 0)
    n_partial = int(totals.get("tasks_partial", 0) or 0)
    attempted = int(totals.get("attempted_requests", 0) or 0)
    successful = int(totals.get("successful_requests", 0) or 0)

    if coverage is not None and not coverage.get("complete", True):
        n_miss = len(coverage.get("missing_task_ids") or [])
        return 7, f"coverage miss: {n_miss} task id(s) missing from variants"
    if n_blocked > 0 and n_tasks > 0 and n_blocked == n_tasks:
        return 7, f"all {n_blocked} tasks blocked"
    if n_blocked > 0:
        return 1, f"blocked tasks: {n_blocked}"
    if attempted > 0 and successful == 0:
        return 2, "all requests failed"
    if n_error > 0 or n_partial > 0:
        return 1, "error/partial tasks"
    return 0, "ok"


def format_batch_summary(
    *,
    totals: dict,
    coverage: dict | None = None,
    exit_code: int = 0,
    exit_reason: str = "",
    n_rows: int = 0,
    n_raw: int = 0,
    out_dir: Path | str | None = None,
) -> str:
    """Terminal summary: ok / blocked / fail counts and exit reason."""
    n_ok = int(totals.get("tasks_ok", 0) or 0)
    n_blocked = int(totals.get("tasks_blocked", 0) or 0)
    n_error = int(totals.get("tasks_error", 0) or 0)
    n_partial = int(totals.get("tasks_partial", 0) or 0)
    n_cancelled = int(totals.get("tasks_cancelled", 0) or 0)
    n_fail = n_error + n_partial
    lines = [
        (
            f"summary: tasks={totals.get('tasks', 0)} ok={n_ok} "
            f"blocked={n_blocked} fail={n_fail} partial={n_partial} "
            f"error={n_error} cancelled={n_cancelled} rows={n_rows} raw={n_raw}"
        )
    ]
    if coverage is not None:
        missing = coverage.get("missing_task_ids") or []
        n_ids = len(coverage.get("task_ids") or [])
        miss_ids = ",".join(missing) if missing else "-"
        lines.append(
            f"coverage: covered={coverage.get('covered', 0)}/{n_ids} "
            f"missing={len(missing)} ids={miss_ids}"
        )
    if out_dir is not None:
        lines.append(f"out={out_dir}")
    lines.append(f"exit={exit_code} reason={exit_reason}")
    return "\n".join(lines)


def build_a_variants(task: dict) -> list:
    """Deterministic A-arm variants: original query only, default field."""
    query = task["query"]
    direction = task["direction"]
    variant_lang = "zh" if direction == "zh2en" else "en"
    if direction not in ("zh2en", "en2zh"):
        raise ValueError(f"unknown direction {direction}")
    if not query or not query.strip():
        raise ValueError("task query must be non-empty")
    if len(query) > 256:
        raise ValueError("task query must be <= 256 characters")
    return [
        {
            "variant_query": query,
            "variant_lang": variant_lang,
            "api_query": query,
        }
    ]


def run_batch(
    *,
    tasks: list,
    arm: str,
    run_id: str,
    http_get: Callable[[str, dict], Any] | None = None,
    token: str | None = None,
    per_page: int = PER_QUERY_TOP_N,
    variants_by_task: dict | None = None,
    seed_repos_by_task: dict | None = None,
    should_cancel: Callable[[], bool] | None = None,
    sleep_func: Callable[[float], None] | None = None,
    sleep_seconds: float = 0,
) -> dict:
    """Run one arm over tasks serially. Never fabricates candidates.

    Returns {"task_results": [...], "totals": {...}, "coverage": ...}.
    Each task_result has task_id/direction/status ("ok"/"blocked"/
    "cancelled"/"error"/"partial"), per_query_records/merged_candidates
    (empty unless ok/partial), errors, and counters. For B/C/M, coverage
    lists task IDs missing from variants_by_task.
    """
    if arm == "D":
        raise ValueError("arm D is a networked-assistant control, not a GitHub run")
    if arm not in ALLOWED_ARMS:
        raise ValueError("arm must be one of A/B/C/M")
    if not run_id or not isinstance(run_id, str):
        raise ValueError("run_id must be a non-empty string")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks must be a non-empty list")

    task_results: list = []
    totals = {
        "tasks": 0,
        "tasks_ok": 0,
        "tasks_partial": 0,
        "tasks_blocked": 0,
        "tasks_cancelled": 0,
        "tasks_error": 0,
        "attempted_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "cancelled_variants": 0,
        "per_query_records": 0,
        "merged_candidates": 0,
    }
    coverage = None
    if arm in ("B", "C", "M"):
        coverage = check_variant_coverage(tasks, variants_by_task)

    for task in tasks:
        task_id = task.get("id", "")
        direction = task.get("direction", "")
        if should_cancel is not None and should_cancel():
            remaining = len(tasks) - len(task_results)
            for _ in range(remaining):
                pass
            task_results.append(
                {
                    "task_id": task_id,
                    "direction": direction,
                    "status": "cancelled",
                    "per_query_records": [],
                    "merged_candidates": [],
                    "candidates": [],
                    "errors": [
                        {
                            "variant_index": -1,
                            "api_query": "",
                            "error": "cancelled",
                        }
                    ],
                    "attempted_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "cancelled_variants": 1,
                }
            )
            totals["tasks"] += 1
            totals["tasks_cancelled"] += 1
            totals["cancelled_variants"] += 1
            # Mark every still-unstarted task cancelled as well.
            idx = len(task_results) - 1
            for later in tasks[idx + 1 :]:
                task_results.append(
                    {
                        "task_id": later.get("id", ""),
                        "direction": later.get("direction", ""),
                        "status": "cancelled",
                        "per_query_records": [],
                        "merged_candidates": [],
                        "candidates": [],
                        "errors": [
                            {
                                "variant_index": -1,
                                "api_query": "",
                                "error": "cancelled",
                            }
                        ],
                        "attempted_requests": 0,
                        "successful_requests": 0,
                        "failed_requests": 0,
                        "cancelled_variants": 1,
                    }
                )
                totals["tasks"] += 1
                totals["tasks_cancelled"] += 1
                totals["cancelled_variants"] += 1
            break

        if arm == "A":
            variants = build_a_variants(task)
        else:
            supplied = (variants_by_task or {}).get(task_id)
            if not supplied:
                if variants_by_task:
                    block_reason = (
                        f"arm {arm} coverage miss: task {task_id} absent "
                        "or empty in variants_by_task; refusing to fabricate"
                    )
                else:
                    block_reason = (
                        f"arm {arm} needs explicit variants_by_task "
                        "(model/wordlist owner-dependent); refusing to "
                        "fabricate queries"
                    )
                task_results.append(
                    {
                        "task_id": task_id,
                        "direction": direction,
                        "status": "blocked",
                        "reason": block_reason,
                        "per_query_records": [],
                        "merged_candidates": [],
                        "candidates": [],
                        "errors": [],
                        "attempted_requests": 0,
                        "successful_requests": 0,
                        "failed_requests": 0,
                        "cancelled_variants": 0,
                    }
                )
                totals["tasks"] += 1
                totals["tasks_blocked"] += 1
                continue
            variants = supplied

        seeds = set()
        if seed_repos_by_task and task_id in seed_repos_by_task:
            seeds = set(seed_repos_by_task[task_id] or set())

        try:
            out = run_method(
                run_id=run_id,
                task_id=task_id,
                direction=direction,
                arm=arm,
                variants=variants,
                seed_repos=seeds,
                http_get=http_get,
                token=token,
                per_page=per_page,
                should_cancel=None,
                sleep_func=sleep_func,
                sleep_seconds=sleep_seconds,
            )
        except Exception as exc:
            task_results.append(
                {
                    "task_id": task_id,
                    "direction": direction,
                    "status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "per_query_records": [],
                    "merged_candidates": [],
                    "candidates": [],
                    "errors": [
                        {
                            "variant_index": -1,
                            "api_query": "",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    ],
                    "attempted_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "cancelled_variants": 0,
                }
            )
            totals["tasks"] += 1
            totals["tasks_error"] += 1
            continue

        entry = {
            "task_id": task_id,
            "direction": direction,
            "status": "ok",
            "per_query_records": out["per_query_records"],
            "merged_candidates": out["merged_candidates"],
            "candidates": out["candidates"],
            "errors": out["errors"],
            "attempted_requests": out["attempted_requests"],
            "successful_requests": out["successful_requests"],
            "failed_requests": out["failed_requests"],
            "cancelled_variants": out["cancelled_variants"],
            "requested_budget": out["requested_budget"],
        }
        attempted = out["attempted_requests"]
        successful = out["successful_requests"]
        failed = out["failed_requests"]
        cancelled = out.get("cancelled_variants", 0)
        # Distinguish success / partial / all-failed / cancelled.
        # All timeouts must NOT look like "ok with zero hits".
        if cancelled and attempted == 0:
            entry["status"] = "cancelled"
            totals["tasks_cancelled"] += 1
        elif attempted > 0 and successful == 0:
            entry["status"] = "error"
            entry["reason"] = "all requests failed"
            totals["tasks_error"] += 1
        elif failed > 0 and successful > 0:
            entry["status"] = "partial"
            totals["tasks_partial"] += 1
        elif cancelled:
            entry["status"] = "cancelled"
            totals["tasks_cancelled"] += 1
        else:
            totals["tasks_ok"] += 1
        totals["tasks"] += 1
        totals["attempted_requests"] += out["attempted_requests"]
        totals["successful_requests"] += out["successful_requests"]
        totals["failed_requests"] += out["failed_requests"]
        totals["cancelled_variants"] += out["cancelled_variants"]
        totals["per_query_records"] += len(out["per_query_records"])
        totals["merged_candidates"] += len(out["merged_candidates"])
        task_results.append(entry)

    return {
        "task_results": task_results,
        "totals": totals,
        "coverage": coverage,
    }


def build_manifest(
    *,
    run_id: str,
    batch: str,
    arm: str,
    repo_root: Path | None,
    settings: dict,
    totals: dict,
    started_at: str,
    finished_at: str,
    http_mode: str,
    allow_unfrozen: bool = False,
) -> dict:
    return {
        "run_id": run_id,
        "batch": batch,
        "arm": arm,
        "materials_commit": materials_commit(repo_root),
        "protocol_version": settings.get("protocol_version", "v0.4"),
        "freeze": settings.get("freeze", {}),
        "eval_frozen": is_eval_frozen(settings),
        "allow_unfrozen": allow_unfrozen,
        "budgets": settings.get("budget", {}),
        "per_query_top_n": settings.get("candidate_merge", {}).get(
            "per_query_top_n", PER_QUERY_TOP_N
        ),
        "truncate_merged_top_n": settings.get("candidate_merge", {}).get(
            "truncate_merged_top_n", MERGED_TOP_N
        ),
        "started_at": started_at,
        "finished_at": finished_at,
        "http_mode": http_mode,
        "totals": totals,
    }


def write_candidates_jsonl(path: Path, task_results: list) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for tr in task_results:
            for row in tr.get("merged_candidates", []):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
    return n


def write_per_query_jsonl(path: Path, task_results: list) -> int:
    """Persist ALL raw per-query hits (pre-merge truncation)."""
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for tr in task_results:
            task_id = tr.get("task_id", "")
            for row in tr.get("per_query_records", []):
                payload = dict(row)
                payload.setdefault("task_id", task_id)
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                n += 1
    return n


def write_task_results_jsonl(path: Path, task_results: list) -> int:
    """Persist per-task status, counters, and errors for audit."""
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for tr in task_results:
            payload = {
                "task_id": tr.get("task_id", ""),
                "direction": tr.get("direction", ""),
                "status": tr.get("status", ""),
                "reason": tr.get("reason", ""),
                "attempted_requests": tr.get("attempted_requests", 0),
                "successful_requests": tr.get("successful_requests", 0),
                "failed_requests": tr.get("failed_requests", 0),
                "cancelled_variants": tr.get("cancelled_variants", 0),
                "requested_budget": tr.get("requested_budget"),
                "per_query_record_count": len(tr.get("per_query_records", [])),
                "merged_candidate_count": len(tr.get("merged_candidates", [])),
                "errors": tr.get("errors", []),
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            n += 1
    return n


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E1 owner-independent batch (A-arm native; B/C/M need "
        "explicit variants; D refused; eval gated on freeze)."
    )
    parser.add_argument("--queries", required=True)
    parser.add_argument("--run-settings", required=True)
    parser.add_argument("--batch", required=True, choices=list(ALLOWED_BATCHES))
    parser.add_argument("--arm", required=True, choices=sorted(ALLOWED_ARMS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--allow-unfrozen", action="store_true")
    parser.add_argument("--allow-runs-dir", action="store_true")
    parser.add_argument("--variants-json", default=None)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--token", default=None)
    parser.add_argument("--sleep-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    if "runs" in out_dir.parts and not args.allow_runs_dir:
        print("refusing to write into runs/ without --allow-runs-dir")
        return 2
    if args.arm == "D":
        print("arm D is a networked-assistant control, not a GitHub run")
        return 2

    queries = load_queries(Path(args.queries))
    settings = load_run_settings(Path(args.run_settings))
    tasks = queries[args.batch]

    if args.batch == "eval.batch_1" and not is_eval_frozen(settings):
        if not args.allow_unfrozen:
            print("eval.batch_1 未冻结 (freeze markers null): refusing run")
            return 3

    variants_by_task = None
    if args.variants_json:
        variants_by_task = json.loads(Path(args.variants_json).read_text())
    coverage = None
    if args.arm in ("B", "C", "M"):
        if not variants_by_task:
            print(
                f"arm {args.arm} needs --variants-json with explicit per-task "
                "variants (model/wordlist owner-dependent); refusing to fabricate"
            )
            return 4
        coverage = check_variant_coverage(tasks, variants_by_task)
        if not coverage["complete"] and not args.live:
            preview = {
                "tasks": len(tasks),
                "tasks_ok": 0,
                "tasks_partial": 0,
                "tasks_blocked": len(coverage["missing_task_ids"]),
                "tasks_cancelled": 0,
                "tasks_error": 0,
                "attempted_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
            }
            code, reason = decide_exit(preview, coverage)
            print(
                format_batch_summary(
                    totals=preview,
                    coverage=coverage,
                    exit_code=code,
                    exit_reason=reason,
                    out_dir=out_dir,
                )
            )
            return code

    if not args.live:
        print("no live http_get: dry-run refuses network by design")
        return 5

    try:
        from github_search import _urllib_get  # type: ignore
    except ImportError:
        try:
            from .github_search import _urllib_get  # type: ignore
        except ImportError:
            print("cannot import live http helper")
            return 6

    started_at = _utcnow()
    out = run_batch(
        tasks=tasks,
        arm=args.arm,
        run_id=args.run_id,
        http_get=_urllib_get,
        token=args.token,
        per_page=int(
            settings.get("candidate_merge", {}).get(
                "per_query_top_n", PER_QUERY_TOP_N
            )
        ),
        variants_by_task=variants_by_task,
        sleep_func=None,
        sleep_seconds=args.sleep_seconds,
    )
    finished_at = _utcnow()
    out_dir.mkdir(parents=True, exist_ok=True)
    n = write_candidates_jsonl(out_dir / "candidates.jsonl", out["task_results"])
    n_raw = write_per_query_jsonl(
        out_dir / "per_query_records.jsonl", out["task_results"]
    )
    n_tasks = write_task_results_jsonl(
        out_dir / "task_results.jsonl", out["task_results"]
    )
    manifest = build_manifest(
        run_id=args.run_id,
        batch=args.batch,
        arm=args.arm,
        repo_root=Path(args.queries).resolve().parents[3],
        settings=settings,
        totals=out["totals"],
        started_at=started_at,
        finished_at=finished_at,
        http_mode="live-urllib",
        allow_unfrozen=args.allow_unfrozen,
    )
    manifest["artifacts"] = {
        "candidates_jsonl": "candidates.jsonl",
        "per_query_records_jsonl": "per_query_records.jsonl",
        "task_results_jsonl": "task_results.jsonl",
        "candidates_rows": n,
        "per_query_rows": n_raw,
        "task_result_rows": n_tasks,
    }
    coverage = out.get("coverage") or coverage
    if coverage is not None:
        manifest["variant_coverage"] = {
            "complete": coverage.get("complete"),
            "covered": coverage.get("covered"),
            "missing_task_ids": coverage.get("missing_task_ids", []),
            "extra_variant_ids": coverage.get("extra_variant_ids", []),
        }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    totals = out["totals"]
    code, reason = decide_exit(totals, coverage)
    print(
        format_batch_summary(
            totals=totals,
            coverage=coverage,
            exit_code=code,
            exit_reason=reason,
            n_rows=n,
            n_raw=n_raw,
            out_dir=out_dir,
        )
    )
    return code


__all__ = [
    "ALLOWED_ARMS",
    "ALLOWED_BATCHES",
    "build_a_variants",
    "build_manifest",
    "check_variant_coverage",
    "decide_exit",
    "format_batch_summary",
    "is_eval_frozen",
    "load_queries",
    "load_run_settings",
    "materials_commit",
    "run_batch",
    "write_candidates_jsonl",
    "write_per_query_jsonl",
    "write_task_results_jsonl",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
