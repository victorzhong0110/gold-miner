#!/usr/bin/env python3
"""Check whether the recorded E1 freeze still describes the real materials.

``run-settings.json`` records freeze pointers (commit SHAs). A pointer is only
honest if the commit it names actually contains the material it claims to freeze.
This script verifies that, and reports any material that exists now but was
absent at the pointed-at commit.

It never edits the freeze. Re-freezing is a deliberate protocol act: the freeze
checklist requires the pointers be backfilled in a separate commit after the
materials commit exists, and the model id must be chosen first.

Usage:
    python3 scripts/e1_freeze_check.py            # human/JSON report
    python3 scripts/e1_freeze_check.py --write-status <path>
Exit codes: 0 consistent, 3 stale/drifted, 4 unreadable repository state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
E1 = HARNESS.parent
RUN_SETTINGS = E1 / "run-settings.json"

# Every artifact a run depends on. The freeze is only meaningful if all of them
# are covered by the recorded pointer.
MATERIALS = [
    "experiments/E1-cross-language-search/queries.yaml",
    "experiments/E1-cross-language-search/run-settings.json",
    "experiments/E1-cross-language-search/seed-set.jsonl",
    "experiments/E1-cross-language-search/verified-seeds.jsonl",
    "experiments/E1-cross-language-search/prompts/b-translate.txt",
    "experiments/E1-cross-language-search/prompts/c-rewrite.txt",
    "experiments/E1-cross-language-search/prompts/m-rewrite.txt",
    "experiments/E1-cross-language-search/prompts/d-assistant.txt",
    "experiments/E1-cross-language-search/prompts/d-control.template.jsonl",
    "experiments/E1-cross-language-search/prompts/README.md",
]

# Which recorded pointer is supposed to cover which material.
POINTER_FOR = {
    "run-settings.json": "run_settings_commit",
    "queries.yaml": "eval_frozen_commit",
    "seed-set.jsonl": "seed_set_frozen_commit",
    "verified-seeds.jsonl": "seed_set_frozen_commit",
    "prompts/b-translate.txt": "prompts_frozen_commit",
    "prompts/c-rewrite.txt": "prompts_frozen_commit",
    "prompts/m-rewrite.txt": "prompts_frozen_commit",
    "prompts/d-assistant.txt": "prompts_frozen_commit",
    "prompts/d-control.template.jsonl": "prompts_frozen_commit",
    "prompts/README.md": "prompts_frozen_commit",
}


def _git(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args], cwd=str(E1.parent.parent), capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip()


def commit_exists(sha: str) -> bool:
    if not sha:
        return False
    code, _ = _git("cat-file", "-e", f"{sha}^{{commit}}")
    return code == 0


def path_at_commit(sha: str, rel: str) -> bool:
    code, _ = _git("cat-file", "-e", f"{sha}:{rel}")
    return code == 0


def blob_at_commit(sha: str, rel: str) -> str:
    code, out = _git("rev-parse", f"{sha}:{rel}")
    return out if code == 0 else ""


def blob_now(rel: str) -> str:
    proc = subprocess.run(
        ["git", "hash-object", rel],
        cwd=str(E1.parent.parent),
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def check(repo_root: Path | None = None) -> dict:
    settings = json.loads(RUN_SETTINGS.read_text(encoding="utf-8"))
    freeze = settings.get("freeze") or {}
    pointers = {
        key: freeze.get(key)
        for key in (
            "eval_frozen_commit",
            "prompts_frozen_commit",
            "run_settings_commit",
            "seed_set_frozen_commit",
        )
    }
    unique = {sha for sha in pointers.values() if sha}

    result = {
        "freeze_status_field": freeze.get("status"),
        "concrete_model_id": (settings.get("model") or {}).get("concrete_model_id"),
        "pointers": pointers,
        "pointers_exist": {sha: commit_exists(sha) for sha in sorted(unique)},
        "missing_pointers": sorted(sha for sha in unique if not commit_exists(sha)),
        "absent_at_frozen_commit": [],
        "modified_since_freeze": [],
        "unreadable_pointers": [],
    }

    for rel in MATERIALS:
        rel_e1 = rel.split("experiments/E1-cross-language-search/", 1)[-1]
        key = POINTER_FOR.get(rel_e1)
        sha = pointers.get(key) if key else None
        if not sha:
            result["unreadable_pointers"].append({"material": rel, "reason": "no pointer recorded"})
            continue
        if not commit_exists(sha):
            result["absent_at_frozen_commit"].append(
                {"material": rel, "pointer": key, "sha": sha, "reason": "pointer commit does not exist"}
            )
            continue
        if not path_at_commit(sha, rel):
            result["absent_at_frozen_commit"].append(
                {
                    "material": rel,
                    "pointer": key,
                    "sha": sha,
                    "reason": "material did not exist at the frozen commit",
                }
            )
            continue
        if blob_at_commit(sha, rel) != blob_now(rel):
            result["modified_since_freeze"].append({"material": rel, "sha": sha})

    result["stale"] = bool(
        result["absent_at_frozen_commit"] or result["unreadable_pointers"] or result["missing_pointers"]
    )
    result["status"] = "stale" if result["stale"] else "pointers-consistent"
    result["model_configured"] = bool(result["concrete_model_id"])
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify the recorded E1 freeze is still honest.")
    p.add_argument("--write-status", help="write the machine-readable result to this path")
    p.add_argument("--json", action="store_true", help="print JSON only")
    args = p.parse_args(argv)

    try:
        result = check()
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"code": "unreadable", "message": str(exc)}, ensure_ascii=False))
        return 4

    if args.write_status:
        Path(args.write_status).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 3 if result["stale"] else 0


if __name__ == "__main__":
    sys.exit(main())
