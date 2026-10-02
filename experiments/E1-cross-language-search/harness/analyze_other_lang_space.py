#!/usr/bin/env python3
"""Compare fixture/live rank rows: other-language-only vs just-more-search.

Does not invent metrics from missing live runs. Prints counts from given JSONL.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def analyze(rank_path: Path, query_path: Path | None = None) -> dict:
    ranks = load_jsonl(rank_path)
    by_task_arm: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in ranks:
        by_task_arm[row["task_id"]][row["arm"]].add(row["repo"].lower())

    query_lang = {}
    if query_path and query_path.is_file():
        for row in load_jsonl(query_path):
            query_lang.setdefault(row["task_id"], {})
            query_lang[row["task_id"]].setdefault(row["arm"], [])
            query_lang[row["task_id"]][row["arm"]].append(row)

    summaries = []
    for task_id, arms in sorted(by_task_arm.items()):
        a = arms.get("A", set())
        b = arms.get("B", set())
        c = arms.get("C", set())
        m = arms.get("M", set())
        summaries.append(
            {
                "task_id": task_id,
                "c_minus_a": sorted(c - a),
                "c_minus_b": sorted(c - b),
                "c_minus_m": sorted(c - m),
                "c_intersect_m_minus_a": sorted((c & m) - a),
                "interpretation_hint": {
                    "c_minus_m": "same budget, only C — closer to language-switch space (still not proof)",
                    "c_intersect_m_minus_a": "also in M — may be just more search, not language",
                },
            }
        )
    return {
        "status": "computed-from-provided-files",
        "not_an_eval_conclusion": True,
        "tasks": summaries,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rank", required=True)
    p.add_argument("--queries", default="")
    args = p.parse_args(argv)
    report = analyze(Path(args.rank), Path(args.queries) if args.queries else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
