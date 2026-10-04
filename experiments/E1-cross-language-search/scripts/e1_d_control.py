#!/usr/bin/env python3
"""E1 group D ("strong control") ingest and comparison.

D is a **human procedure**, not an automatable arm: paste the user query into a
general-purpose web-enabled AI assistant, time-box it to 5 minutes, record every
repo it names, then verify each repo exists. Hallucinated names are the whole
point of the control, so they must be recorded rather than silently dropped.

This module therefore does NOT run an assistant. It ingests what a human
recorded and turns it into the same machine-readable shape as A/B/C/M so the
comparison is possible. It never invents a D result:

- a task with no recorded row is reported as ``owner_blocked`` / 未运行
- a row missing verification for a named repo is treated as unverified
- a named repo that failed verification is counted as a hallucination and kept
- ``evidence_kind`` stays ``owner-recorded``; nothing here is a live API call

Input JSONL, one row per task (see ``d-control.template.jsonl``)::

    {"task_id": "...", "assistant": "...", "recorded_at": "...",
     "elapsed_ms": 300000, "repos": ["owner/repo", ...],
     "verified": {"owner/repo": true, "owner/does-not-exist": false}}

Output (stdout, JSON):
  {"run_id": ..., "arm": "D", "status": ..., "per_task": [...], "totals": {...}}
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

# owner/repo as GitHub itself accepts it: alphanumerics, dot, dash, underscore.
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

# A human records a plain name; canonicalise case-insensitively for dedupe only.
# GitHub owner/repo is case-insensitive for lookup but preserves display case,
# so dedupe key is lowercase and the first-seen spelling is kept.
MAX_REPOS = 10  # the d-assistant.txt prompt caps output at 10
TIMEBOX_MS = 5 * 60 * 1000


def _utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def normalize_repo(raw: object) -> str:
    """Return a canonical owner/repo string, or "" when unusable."""
    if not isinstance(raw, str):
        return ""
    name = raw.strip().strip("`").strip()
    # Tolerate a full URL pasted by the human.
    if name.startswith("http://") or name.startswith("https://"):
        parts = name.split("github.com/", 1)
        if len(parts) != 2:
            return ""
        name = parts[1].split("?")[0].split("#")[0]
    name = name.rstrip("/")
    # Drop a leading ./- noise but keep dots inside the name.
    name = name.strip(".")
    if not REPO_RE.match(name):
        return ""
    return name


def normalize_row(row: object, index: int) -> dict:
    """Validate one recorded row. Raises ValueError on unusable input."""
    if not isinstance(row, dict):
        raise ValueError(f"row {index} is not an object")
    task_id = row.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError(f"row {index} has no task_id")

    raw_repos = row.get("repos")
    if raw_repos is None:
        raw_repos = []
    if not isinstance(raw_repos, list):
        raise ValueError(f"row {index} repos must be a list")

    verified_raw = row.get("verified") or {}
    if not isinstance(verified_raw, dict):
        raise ValueError(f"row {index} verified must be an object")

    verified: dict[str, bool] = {}
    for key, value in verified_raw.items():
        name = normalize_repo(key)
        if not name:
            continue
        verified[name.lower()] = bool(value)

    ordered: list[str] = []
    seen: set[str] = set()
    rejected: list[str] = []
    for raw in raw_repos:
        name = normalize_repo(raw)
        if not name:
            rejected.append(str(raw)[:120])
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(name)

    elapsed = row.get("elapsed_ms")
    if not isinstance(elapsed, (int, float)) or elapsed < 0:
        elapsed = None

    return {
        "task_id": task_id.strip(),
        "assistant": str(row.get("assistant") or "unrecorded"),
        "recorded_at": row.get("recorded_at") or _utcnow(),
        "elapsed_ms": int(elapsed) if elapsed is not None else None,
        "repos": ordered[:MAX_REPOS],
        "over_limit": len(ordered) > MAX_REPOS,
        "rejected_names": rejected,
        "verified": verified,
        "unverified": [n for n in ordered if n.lower() not in verified],
    }


def score_row(row: dict) -> dict:
    """Split named repos into real hits, hallucinations, and unchecked names.

    Three distinct states, never collapsed:
    - verified true  -> a real hit
    - verified false -> a hallucination (the control's key signal)
    - no entry       -> unchecked; NOT a hit and NOT a hallucination

    Treating an unchecked name as either would invent a finding. The protocol
    requires every named repo to be checked, so ``unverified_names`` stays
    visible as work the operator still owes.
    """
    hits, hallucinations = [], []
    for name in row["repos"]:
        state = row["verified"].get(name.lower())
        if state is True:
            hits.append(name)
        elif state is False:
            hallucinations.append(name)
    named = len(row["repos"])
    checked = len(hits) + len(hallucinations)
    return {
        "task_id": row["task_id"],
        "assistant": row["assistant"],
        "recorded_at": row["recorded_at"],
        "elapsed_ms": row["elapsed_ms"],
        "within_timebox": (
            None if row["elapsed_ms"] is None else row["elapsed_ms"] <= TIMEBOX_MS
        ),
        "named_count": named,
        "checked_count": checked,
        "verified_hits": hits,
        "verified_count": len(hits),
        "hallucinations": hallucinations,
        "hallucination_count": len(hallucinations),
        "unverified_names": row["unverified"],
        "rejected_names": row["rejected_names"],
        "over_limit": row["over_limit"],
        # Rate over CHECKED repos only. Including unchecked names would report a
        # rate before the verification step the protocol requires is finished.
        "hallucination_rate": (len(hallucinations) / checked) if checked else None,
        "fully_checked": checked == named,
    }


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(normalize_row(json.loads(line), index))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {index} is not valid JSON: {exc}") from exc
    return rows


def build_report(rows: list[dict], expected_tasks: list[str] | None, run_id: str) -> dict:
    scored = [score_row(r) for r in rows]
    by_task = {r["task_id"]: r for r in scored}

    blocked = []
    for task_id in expected_tasks or []:
        if task_id not in by_task:
            blocked.append(
                {
                    "task_id": task_id,
                    "arm": "D",
                    "code": "owner_blocked",
                    "status": "未运行",
                    "message": "D 组未记录 / group D not recorded by the operator.",
                }
            )

    total_named = sum(r["named_count"] for r in scored)
    total_checked = sum(r["checked_count"] for r in scored)
    total_hits = sum(r["verified_count"] for r in scored)
    total_halluc = sum(r["hallucination_count"] for r in scored)
    total_unchecked = sum(len(r["unverified_names"]) for r in scored)
    timed = [r for r in scored if r["within_timebox"] is not None]
    status = "owner-recorded" if scored else "not-run"
    return {
        "run_id": run_id,
        "arm": "D",
        "status": status,
        "evidence_kind": "owner-recorded",
        "generated_at": _utcnow(),
        "note": (
            "D 为真人操作记录，非自动运行，也不是 live API 调用。"
            " Hallucinations are counted, not discarded. 未记录任务保持 owner-blocked。"
            " 未逐个核实的名字既不算命中也不算幻觉，单列在 unverified_names。"
        ),
        "per_task": scored,
        "blocked": blocked,
        "totals": {
            "tasks_recorded": len(scored),
            "tasks_blocked": len(blocked),
            "repos_named": total_named,
            "repos_checked": total_checked,
            "repos_unverified": total_unchecked,
            "verified_hits": total_hits,
            "hallucinations": total_halluc,
            "hallucination_rate": (total_halluc / total_checked) if total_checked else None,
            "tasks_fully_checked": sum(1 for r in scored if r["fully_checked"]),
            "tasks_within_timebox": sum(1 for r in timed if r["within_timebox"]),
            "tasks_over_timebox": sum(1 for r in timed if not r["within_timebox"]),
            "elapsed_ms_median": (
                sorted(r["elapsed_ms"] for r in timed)[len(timed) // 2] if timed else None
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Ingest owner-recorded group D rows and summarize the control."
    )
    p.add_argument("--input", required=True, help="JSONL of recorded D rows")
    p.add_argument("--tasks", help="optional file with one task_id per line; missing ones become owner-blocked")
    p.add_argument("--run-id", default="d-control")
    args = p.parse_args(argv)

    try:
        rows = load_rows(Path(args.input))
    except (OSError, ValueError) as exc:
        print(json.dumps({"code": "bad_input", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    expected = None
    if args.tasks:
        expected = [
            line.strip()
            for line in Path(args.tasks).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    report = build_report(rows, expected, args.run_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # No recorded rows at all is "not run", not a failure.
    return 0 if report["status"] == "owner-recorded" else 3


if __name__ == "__main__":
    sys.exit(main())
