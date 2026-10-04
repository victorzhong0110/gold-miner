#!/usr/bin/env python3
"""Report how the B/C/M prompts line up with the pipeline's query rule.

The main comparison is A (plain default search) against B/C/M. The pipeline
rejects field/star/repo qualifiers in a variant query, because if any arm may use
them it searches a different space than A and the difference stops measuring
cross-language rewriting. So the prompts have to agree with that rule.

This deliberately does NOT guess whether a Chinese prompt sentence permits or
forbids a qualifier. A first attempt did, and produced false findings: it read
C's "本步不要写 in:readme" as permission and M's "不准加…stars:" as permission.
Both are prohibitions. A checker that invents problems is worse than none.

So this reports only what is mechanically true:

- which rejected qualifiers each prompt mentions at all (presence, not intent)
- which qualifiers it therefore never tells the model to avoid
- the line that carries its prohibition, cited by file and line

A permission claim ("C tells the model it may use in:description") is recorded in
materials-status.json by a human, with a citation, and test_e1_materials_check.py
re-asserts the cited text still says that. If a prompt is ever corrected, that
test fails and the record must be updated.

    python3 scripts/e1_materials_check.py
    python3 scripts/e1_materials_check.py --write-status ../materials-status.json

Exit: 0 no uncovered qualifiers, 3 some prompt never mentions, 4 unreadable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e1_pipeline import FORBIDDEN_QUERY_SYNTAX, forbidden_query_syntax  # noqa: E402

E1 = Path(__file__).resolve().parents[1]
ROOT = E1.parents[1]
PROMPT_DIR = E1 / "prompts"
ARMS = {"B": "b-translate.txt", "C": "c-rewrite.txt", "M": "m-rewrite.txt"}

# Spellings a prompt may use for each qualifier the pipeline refuses.
FORMS = {
    "in:readme": ("in:readme",),
    "in:description": ("in:description",),
    "in:name": ("in:name",),
    "stars": ("stars:", "stars"),
    "language": ("language:",),
    "repo": ("repo:",),
    "user": ("user:",),
    "org": ("org:",),
}
PROHIBITION_MARKERS = ("不准", "不要", "不得", "禁止", "forbid", "must not")


def _lines(text: str) -> list[str]:
    return text.splitlines()


def check() -> dict:
    arms: dict[str, dict] = {}
    for arm, filename in ARMS.items():
        path = PROMPT_DIR / filename
        lines = _lines(path.read_text(encoding="utf-8"))
        mentioned: dict[str, list[int]] = {}
        prohibitions: list[dict] = []
        for index, line in enumerate(lines, start=1):
            low = line.lower()
            for qualifier, spellings in FORMS.items():
                if any(s in low for s in spellings):
                    mentioned.setdefault(qualifier, []).append(index)
            if any(m in line for m in PROHIBITION_MARKERS) and any(
                s in low for spellings in FORMS.values() for s in spellings
            ):
                prohibitions.append({"line": index, "text": line.strip()[:200]})
        # A blanket rule ("不准加任何…等") covers qualifiers never spelled out.
        blanket = any(
            ("任何" in t["text"] or "any" in t["text"].lower()) for t in prohibitions
        )
        uncovered = (
            []
            if blanket
            else [q for q in FORMS if q not in mentioned and forbidden_query_syntax(q + ":")]
        )
        arms[arm] = {
            "prompt_file": str(path.relative_to(ROOT)),
            "mentioned_qualifiers": {k: v for k, v in sorted(mentioned.items())},
            "prohibition_lines": prohibitions,
            "blanket_prohibition": blanket,
            "never_mentioned": uncovered,
        }
    uncovered_total = {a: v["never_mentioned"] for a, v in arms.items() if v["never_mentioned"]}
    return {
        "pipeline_rule": FORBIDDEN_QUERY_SYNTAX.pattern,
        "arms": arms,
        "arms_with_uncovered_qualifiers": uncovered_total,
        "all_qualifiers_covered": not uncovered_total,
        "note": (
            "本检查只报告「提示词是否提到某个被 pipeline 拒绝的限定符」，"
            "不判断允许还是禁止——中文散文的意图判断会产生假发现"
            "（曾把「本步不要写 in:readme」误读为允许）。"
            " 允许/禁止的判定由 materials-status.json 人工记录并附 file:line 引用，"
            " 由 test_e1_materials_check.py 断言引用处文本未变。"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Report prompt/pipeline rule coverage.")
    p.add_argument("--write-status", help="write the machine-readable result here")
    args = p.parse_args(argv)
    try:
        result = check()
    except OSError as exc:
        print(json.dumps({"code": "unreadable", "message": str(exc)}, ensure_ascii=False))
        return 4
    if args.write_status:
        Path(args.write_status).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_qualifiers_covered"] else 3


if __name__ == "__main__":
    sys.exit(main())
