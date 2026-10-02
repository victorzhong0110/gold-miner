"""Same-session default-field vs in:readme pairing for frozen E1 queries.

Protocol section 3: README expansion is a separate paired diagnosis.
Both sides use the original query text. The README side only adds the
``in:readme`` qualifier. This does not generate B/C/M translations and
does not judge purpose fit.

Network stays behind an injected ``http_get``. The CLI live path is opt-in.
A rate-limit response stops later requests; those tasks are cancelled.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from .e1_batch import build_a_variants, load_queries
    from .e1_w4_run import load_seed_rows, seed_tasks
    from .github_search import canonical
    from .e1_minimal_runner import run_method
except ImportError:  # direct script execution
    from e1_batch import build_a_variants, load_queries  # type: ignore
    from e1_w4_run import load_seed_rows, seed_tasks  # type: ignore
    from github_search import canonical  # type: ignore
    from e1_minimal_runner import run_method  # type: ignore


README_QUALIFIER = "in:readme"


def readme_api_query(query: str) -> str:
    """Append the README qualifier without changing the original words."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    text = query.strip()
    if re.search(r"(?:^|\s)in:readme(?:\s|$)", text):
        api = text
    else:
        api = f"{text} {README_QUALIFIER}"
    if len(api) > 256:
        raise ValueError("api query must be <= 256 characters")
    return api


def build_readme_variants(task: dict) -> list:
    """Arm A shape: variant_query stays original; api_query adds in:readme."""
    base = build_a_variants(task)[0]
    return [
        {
            "variant_query": base["variant_query"],
            "variant_lang": base["variant_lang"],
            "api_query": readme_api_query(base["variant_query"]),
        }
    ]


def _is_rate_limit(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "403" in text or "rate limit" in text


def _cancelled_result(task: dict) -> dict:
    return {
        "task_id": task["id"],
        "direction": task["direction"],
        "status": "cancelled",
        "merged_candidates": [],
        "errors": [{"error": "cancelled"}],
        "attempted_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
    }


def _status_of(out: dict) -> str:
    if out.get("cancelled_variants") and out.get("attempted_requests", 0) == 0:
        return "cancelled"
    if out.get("attempted_requests", 0) > 0 and out.get("successful_requests", 0) == 0:
        return "error"
    return "ok"


def run_pair(
    *,
    tasks: list[dict],
    run_id: str,
    http_get,
    token: str | None = None,
    per_page: int = 30,
    sleep_func=None,
    sleep_seconds: float = 0,
    seed_repos_by_task: dict | None = None,
) -> dict:
    """Run default then in:readme for each task. Stop after a rate limit.

    ``http_get`` is required. Tests inject a fake. This function does not
    choose the real urllib helper.
    """
    if http_get is None:
        raise RuntimeError("no http_get injected: refusing real network by default")
    if not tasks:
        raise ValueError("tasks must be a non-empty list")

    stop = {"rate_limited": False}

    def guarded(url, headers):
        try:
            return http_get(url, headers)
        except Exception as exc:
            if _is_rate_limit(exc):
                stop["rate_limited"] = True
            raise

    def one(task: dict, variants: list) -> dict:
        if stop["rate_limited"]:
            return _cancelled_result(task)
        seeds = set()
        if seed_repos_by_task and task["id"] in seed_repos_by_task:
            seeds = set(seed_repos_by_task[task["id"]] or set())
        try:
            out = run_method(
                run_id=run_id,
                task_id=task["id"],
                direction=task["direction"],
                arm="A",
                variants=variants,
                seed_repos=seeds,
                http_get=guarded,
                token=token,
                per_page=per_page,
                should_cancel=lambda: stop["rate_limited"],
                sleep_func=sleep_func,
                sleep_seconds=sleep_seconds,
            )
        except Exception as exc:
            if _is_rate_limit(exc):
                stop["rate_limited"] = True
            return {
                "task_id": task["id"],
                "direction": task["direction"],
                "status": "error",
                "merged_candidates": [],
                "errors": [{"error": f"{type(exc).__name__}: {exc}"}],
                "attempted_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
            }
        result = {
            "task_id": task["id"],
            "direction": task["direction"],
            "status": _status_of(out),
            "merged_candidates": out["merged_candidates"],
            "errors": out["errors"],
            "attempted_requests": out["attempted_requests"],
            "successful_requests": out["successful_requests"],
            "failed_requests": out["failed_requests"],
        }
        if result["errors"] and any(
            _is_rate_limit(RuntimeError(err.get("error", "")))
            for err in result["errors"]
            if isinstance(err, dict)
        ):
            stop["rate_limited"] = True
        return result

    rows = []
    for task in tasks:
        default = one(task, build_a_variants(task))
        readme = one(task, build_readme_variants(task))
        rows.append({"task": task, "default": default, "readme": readme})
    return {
        "rows": rows,
        "rate_limited": stop["rate_limited"],
        "attempted_requests": sum(
            side["attempted_requests"]
            for row in rows
            for side in (row["default"], row["readme"])
        ),
        "successful_requests": sum(
            side["successful_requests"]
            for row in rows
            for side in (row["default"], row["readme"])
        ),
    }


def _names(candidates: list) -> list[str]:
    ordered = []
    seen = set()
    for row in sorted(candidates or [], key=lambda item: int(item.get("rank") or 0)):
        repo = str(row.get("repo") or "")
        key = canonical(repo) if repo else ""
        if key and key not in seen:
            seen.add(key)
            ordered.append(repo)
    return ordered


def _error_text(result: dict) -> str:
    parts = []
    for err in result.get("errors") or []:
        if isinstance(err, dict) and err.get("error"):
            parts.append(str(err["error"]))
    return "; ".join(parts)


def pair_task(task: dict, default: dict, readme: dict, *, kind: str) -> dict:
    """Compare two same-session windows. Counts come only from returned rows."""
    default_names = _names(default.get("merged_candidates") or []) if default.get("status") == "ok" else []
    readme_names = _names(readme.get("merged_candidates") or []) if readme.get("status") == "ok" else []
    default_keys = {canonical(name): name for name in default_names}
    readme_keys = {canonical(name): name for name in readme_names}
    both_keys = [key for key in readme_keys if key in default_keys]
    only_default = [default_keys[key] for key in default_keys if key not in readme_keys]
    only_readme = [readme_keys[key] for key in readme_keys if key not in default_keys]
    target = task.get("repo")
    target_key = canonical(target) if isinstance(target, str) and target else ""

    def _hit(names: list[str], status: str):
        if status != "ok" or not target_key:
            return None
        for index, name in enumerate(names, start=1):
            if canonical(name) == target_key:
                return index
        return None

    return {
        "task_id": task["id"],
        "direction": task["direction"],
        "kind": kind,
        "query": task["query"],
        "default_status": default.get("status"),
        "readme_status": readme.get("status"),
        "default_error": _error_text(default),
        "readme_error": _error_text(readme),
        "default_count": len(default_names) if default.get("status") == "ok" else None,
        "readme_count": len(readme_names) if readme.get("status") == "ok" else None,
        "both": [readme_keys[key] for key in both_keys],
        "only_default": only_default,
        "only_readme": only_readme,
        "target_repo": target if target_key else None,
        "target_rank_default": _hit(default_names, default.get("status")),
        "target_rank_readme": _hit(readme_names, readme.get("status")),
    }


def build_pair_rows(run_out: dict, *, eval_ids: set[str]) -> list[dict]:
    paired = []
    for row in run_out["rows"]:
        task = row["task"]
        kind = "eval" if task["id"] in eval_ids else "seed"
        paired.append(pair_task(task, row["default"], row["readme"], kind=kind))
    return paired


def _count(items: list) -> int:
    return len(items)


def summarize_matched_fields(rows: list[dict]) -> dict:
    """Count saved matched_fields. Empty text_matches stay unknown."""
    summary = {"default": {}, "readme": {}}
    for row in rows:
        api_query = str(row.get("api_query") or "")
        side = "readme" if api_query.endswith(f" {README_QUALIFIER}") else "default"
        fields = row.get("matched_fields") or ["unknown"]
        key = ",".join(str(field) for field in fields)
        bucket = summary[side]
        bucket[key] = bucket.get(key, 0) + 1
    return summary


def render_report(doc: dict) -> str:
    """Chinese report. Field pairing only; section 7 stays undecided."""
    tasks = doc["tasks"]
    lines = [
        f"# E1 默认字段与 README 字段配对（{doc['run_id']}）",
        "",
        "对应协议第 3 节：README 扩展是另一轮配对诊断，和默认字段分开报告。",
        "同一会话里，每条原始查询先按默认仓库搜索请求一次，再追加 `in:readme` 请求一次。",
        "查询词没有改写。这不是 B/C/M，也不是跨语言增益。",
        "",
        "## 1 做了什么",
        "",
        f"- 运行 `{doc['run_id']}`。材料指针仍是 `{doc['materials_commit']}`。",
        f"- 时间：{doc['started_at']} 至 {doc['finished_at']}。",
        f"- `github_token_used` 为 {str(doc['github_token_used']).lower()}。间隔 {doc['sleep_seconds']} 秒。",
        "- 模型请求 0。D 未运行。E9 未展开。B/C/M 未运行。",
        "- 用途适合、硬条件、是否值得继续看：未运行。",
        "",
        "## 2 请求",
        "",
        f"- 尝试请求 {doc['attempted_requests']}，成功 {doc['successful_requests']}。",
        f"- 限流后停止后续请求：{str(doc['rate_limited']).lower()}。",
        "",
        "失败或取消的原文留在 `manifest.json`。这里不另写剩余额度。",
        "",
        "## 3 同一会话窗口",
        "",
        "两边都成功时才比较仓库集合。0 条只说明这次返回的窗口里没有候选。",
        "数字只统计这次保存的前 30，不外推到窗口之外。",
        "",
        "| 任务 | 侧 | 默认状态 | README 状态 | 两边都有 | 仅默认 | 仅 README |",
        "|---|---|---|---|---|---|---|",
    ]
    for task in tasks:
        if task["default_status"] == "ok" and task["readme_status"] == "ok":
            both_n = _count(task["both"])
            only_d = _count(task["only_default"])
            only_r = _count(task["only_readme"])
        else:
            both_n = only_d = only_r = "未比较"
        lines.append(
            f"| `{task['task_id']}` | {task['kind']} | {task['default_status']} | "
            f"{task['readme_status']} | {both_n} | {only_d} | {only_r} |"
        )
    lines.extend(["", "### 默认窗口为 0、README 窗口有候选时的前 5 个仅 README 仓库", ""])
    any_listed = False
    for task in tasks:
        if task["default_status"] != "ok" or task["readme_status"] != "ok":
            continue
        if task["default_count"] != 0 or not task["only_readme"]:
            continue
        any_listed = True
        top = task["only_readme"][:5]
        lines.append(f"- `{task['task_id']}`：" + "、".join(f"`{name}`" for name in top))
    if not any_listed:
        lines.append("- 无。")
    listed_names = []
    for task in tasks:
        if task["default_status"] != "ok" or task["readme_status"] != "ok":
            continue
        if task["default_count"] != 0 or not task["only_readme"]:
            continue
        listed_names.extend(task["only_readme"][:5])
    if any("awesome" in name.lower() for name in listed_names):
        lines.append("")
        lines.append(
            "这些前排名字里有的包含 awesome。这只描述列出的名字，不是对全部候选的种类判定。"
        )
    lines.extend(
        [
            "",
            "完整候选在 `candidates.jsonl`。上表没有出现的仓库不代表不存在。",
            "",
            "### 已知目标是否进入该侧前 30",
            "",
            "只对种子任务。未进入窗口不等于全体找不到。请求没成功则记未比较。",
            "",
        ]
    )
    seed_lines = [task for task in tasks if task["kind"] == "seed"]
    if not seed_lines:
        lines.append("- 本次没有种子任务。")
    for task in seed_lines:
        target = task.get("target_repo") or "未知"
        lines.append(
            f"- `{task['task_id']}` 目标 `{target}`："
            f"默认 {_rank_text(task['default_status'], task['target_rank_default'])}；"
            f"README {_rank_text(task['readme_status'], task['target_rank_readme'])}。"
        )
    failed = [
        task
        for task in tasks
        if task["default_status"] != "ok" or task["readme_status"] != "ok"
    ]
    lines.extend(["", "## 4 失败或未比较", ""])
    if not failed:
        lines.append("- 两侧请求都有返回。返回 0 条候选仍算这次请求成功。")
    for task in failed:
        bits = []
        if task["default_status"] != "ok":
            err = task["default_error"] or task["default_status"]
            bits.append(f"默认 {task['default_status']}：{err}")
        if task["readme_status"] != "ok":
            err = task["readme_error"] or task["readme_status"]
            bits.append(f"README {task['readme_status']}：{err}")
        lines.append(f"- `{task['task_id']}`：" + "；".join(bits))
    lines.extend(
        [
            "",
            "## 5 匹配字段",
            "",
        ]
    )
    field_summary = doc.get("matched_fields")
    if not field_summary:
        lines.append("- 本报告没有另附匹配字段计数。")
    else:
        lines.append(
            "README 侧候选的 `matched_fields` 来自接口的 `text_matches`。"
            "接口没有给出可映射字段时保持 unknown，不改写成 readme。"
        )
        for side, label in (("default", "默认侧"), ("readme", "README 侧")):
            bucket = field_summary.get(side) or {}
            if not bucket:
                lines.append(f"- {label}：无候选行。")
                continue
            parts = [f"{name} {count} 行" for name, count in sorted(bucket.items())]
            lines.append(f"- {label}：" + "；".join(parts) + "。")
    shape = doc.get("shape_check")
    if shape:
        lines.extend(
            [
                "",
                f"配对的 {doc['attempted_requests']} 次之外，为核对响应形状又发了 1 次 GET，不计入上面的请求数。",
                f"查询与 `{shape['task_id']}` 的 README 侧相同。`text_matches` 长度为 {shape['text_matches_len']}。",
                "前 5 名：" + "、".join(f"`{name}`" for name in shape["top"]) + "。",
            ]
        )
    lines.extend(
        [
            "",
            "## 6 不能下的结论",
            "",
            "协议第 7 节的继续、缩小或暂停：未决定。",
            "B/C/M 未运行，不能把字段差异写成跨语言增益。",
            "用途判定未运行。有价值的新发现：未运行。",
            "D 未运行。E9 未展开。",
            "",
        ]
    )
    text = "\n".join(lines)
    if "%" in text or "召回率" in text:
        raise RuntimeError("report must not state a rate or percent")
    return text


def _rank_text(status: str, rank: int | None) -> str:
    if status != "ok":
        return "未比较"
    if rank is None:
        return "未进入窗口"
    return f"第 {rank}"


def _write_candidates(path: Path, groups: list[list]) -> int:
    n = 0
    with path.open("w", encoding="utf-8") as handle:
        for rows in groups:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
    return n


def _utcnow_z() -> str:
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def main(argv: list | None = None) -> int:
    """Opt-in live pairing. Without --live, do not touch the network."""
    import argparse

    parser = argparse.ArgumentParser(description="E1 default vs in:readme pair")
    parser.add_argument("--queries", default="experiments/E1-cross-language-search/queries.yaml")
    parser.add_argument("--run-settings", default="experiments/E1-cross-language-search/run-settings.json")
    parser.add_argument("--seeds", default="experiments/E1-cross-language-search/seed-set.jsonl")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-runs-dir", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=8.0)
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    if "runs" in out_dir.parts and not args.allow_runs_dir:
        print("refusing to write into runs/ without --allow-runs-dir")
        return 2
    if not args.live:
        print("no --live: refusing network by design")
        return 5

    try:
        from .e1_batch import is_eval_frozen, load_run_settings
        from .github_search import _urllib_get
    except ImportError:
        from e1_batch import is_eval_frozen, load_run_settings  # type: ignore
        from github_search import _urllib_get  # type: ignore

    settings = load_run_settings(Path(args.run_settings))
    if not is_eval_frozen(settings):
        print("eval.batch_1 未冻结 (freeze markers null): refusing run")
        return 3
    eval_tasks = load_queries(Path(args.queries))["eval.batch_1"]
    seed_rows = [] if args.eval_only else load_seed_rows(Path(args.seeds))
    seed_task_rows = seed_tasks(seed_rows)
    tasks = list(eval_tasks) + list(seed_task_rows)
    seed_repos = {row["id"]: {row["repo"]} for row in seed_task_rows}
    token_used = bool(os.environ.get("GITHUB_TOKEN", "").strip())
    started_at = _utcnow_z()
    run_out = run_pair(
        tasks=tasks,
        run_id=args.run_id,
        http_get=_urllib_get,
        per_page=int(settings.get("candidate_merge", {}).get("per_query_top_n", 30)),
        sleep_seconds=args.sleep_seconds,
        seed_repos_by_task=seed_repos,
    )
    finished_at = _utcnow_z()
    paired = build_pair_rows(run_out, eval_ids={task["id"] for task in eval_tasks})
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = []
    for row in run_out["rows"]:
        groups.append(row["default"].get("merged_candidates") or [])
        groups.append(row["readme"].get("merged_candidates") or [])
    n_rows = _write_candidates(out_dir / "candidates.jsonl", groups)
    (out_dir / "judgments.jsonl").write_text("", encoding="utf-8")
    saved_rows = [row for group in groups for row in group]
    doc = {
        "run_id": args.run_id,
        "materials_commit": settings["freeze"].get("eval_frozen_commit"),
        "started_at": started_at,
        "finished_at": finished_at,
        "github_token_used": token_used,
        "sleep_seconds": args.sleep_seconds,
        "attempted_requests": run_out["attempted_requests"],
        "successful_requests": run_out["successful_requests"],
        "rate_limited": run_out["rate_limited"],
        "tasks": paired,
        "matched_fields": summarize_matched_fields(saved_rows),
    }
    report = render_report(doc)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    manifest = {
        "run_id": args.run_id,
        "batch": "eval.batch_1" + ("" if args.eval_only else "+seed-set"),
        "diagnosis": "default-vs-in-readme",
        "materials_commit": doc["materials_commit"],
        "field_config": {"default": "repository search default", "readme": "original query plus in:readme"},
        "started_at": started_at,
        "finished_at": finished_at,
        "github_token_used": token_used,
        "sleep_seconds": args.sleep_seconds,
        "model_requests": 0,
        "d_status": "未运行",
        "e9_status": "未展开",
        "bcm_status": "未运行",
        "judgments_status": "未运行",
        "section_7": "未决定",
        "candidate_rows": n_rows,
        "attempted_requests": run_out["attempted_requests"],
        "successful_requests": run_out["successful_requests"],
        "rate_limited": run_out["rate_limited"],
        "matched_fields": doc["matched_fields"],
        "pair": paired,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"attempted={run_out['attempted_requests']} "
        f"successful={run_out['successful_requests']} "
        f"rows={n_rows} rate_limited={str(run_out['rate_limited']).lower()} "
        f"out={out_dir}"
    )
    if run_out["successful_requests"] == 0:
        return 2
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
