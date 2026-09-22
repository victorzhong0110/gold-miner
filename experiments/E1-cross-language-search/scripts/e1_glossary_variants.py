"""Mechanical E1 variants from the unverified E9 glossary.

This is a pre-run technical procedure, not a decision that the glossary
phrases are synonyms. Rules:

- A concept matches only when one of its source-language phrases occurs
  in the original query (Chinese substring, English word-boundary).
- If two concepts tie for the longest match, the task is blocked
  (``glossary_ambiguous``). No phrase is invented to break the tie.
- After removing every source-language phrase of the winning concept,
  any remaining letter or CJK character blocks the task
  (``glossary_remainder``). Dropping a negation or extra condition
  would change the demand, so those queries are not rewritten.
- No match blocks the task (``glossary_uncovered``).
- B/C/M lists stay empty when blocked. Callers must not fill them.
- Model calls are always zero. Phrases come only from ``terms.yaml``.

B: original query plus the first other-language phrase.
C: original plus at most two other-language phrases (budget 4, no padding).
M: original plus at most three other same-language phrases (no padding).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "glossary-mechanical-v1"
QUERY_SOURCE = "glossary-unverified-mechanical-v1"

try:
    from .e1_batch import load_queries
except ImportError:  # direct script execution
    from e1_batch import load_queries  # type: ignore


def load_terms(path: Path) -> list[dict]:
    """Parse the small terms.yaml subset (id / zh / en / notes)."""
    text = Path(path).read_text(encoding="utf-8")
    terms: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        if "id" not in current or "zh" not in current or "en" not in current:
            raise ValueError(f"term missing id/zh/en: {current}")
        terms.append(current)
        current = None

    for raw in text.splitlines():
        if raw.startswith("- id:"):
            flush()
            current = {"id": raw.split(":", 1)[1].strip(), "zh": [], "en": [], "notes": ""}
            continue
        if current is None:
            continue
        stripped = raw.strip()
        if stripped.startswith("zh:"):
            current["zh"] = _split_list(stripped.split(":", 1)[1])
        elif stripped.startswith("en:"):
            current["en"] = _split_list(stripped.split(":", 1)[1])
        elif stripped.startswith("notes:"):
            current["notes"] = stripped.split(":", 1)[1].strip()
    flush()
    if not terms:
        raise ValueError(f"no terms parsed from {path}")
    return terms


def _split_list(body: str) -> list[str]:
    text = body.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    items = []
    for part in text.split(","):
        item = part.strip().strip("\"'")
        if item:
            items.append(item)
    return items


def _source_lang(direction: str) -> str:
    if direction == "zh2en":
        return "zh"
    if direction == "en2zh":
        return "en"
    raise ValueError(f"unknown direction {direction}")


def _other_lang(lang: str) -> str:
    return "en" if lang == "zh" else "zh"


def _en_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + re.escape(phrase.strip()) + r"(?!\w)", re.IGNORECASE)


def _phrases(term: dict, lang: str) -> list[str]:
    return list(term.get(lang) or [])


def _matching_phrases(query: str, lang: str, term: dict) -> list[str]:
    found = []
    for phrase in _phrases(term, lang):
        if not phrase:
            continue
        if lang == "zh":
            if phrase in query:
                found.append(phrase)
        else:
            if _en_pattern(phrase).search(query):
                found.append(phrase)
    return found


def _leftover(query: str, lang: str, phrases: list[str]) -> str:
    text = query
    for phrase in sorted(phrases, key=len, reverse=True):
        if lang == "zh":
            text = text.replace(phrase, " ")
        else:
            text = _en_pattern(phrase).sub(" ", text)
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _variant(query: str, lang: str) -> dict:
    return {
        "variant_query": query,
        "variant_lang": lang,
        "api_query": query,
        "query_source": QUERY_SOURCE,
    }


def classify_task(task: dict, terms: list[dict]) -> dict:
    """Return blocked or covered record. Never invents a query string."""
    query = str(task.get("query") or "")
    direction = str(task.get("direction") or "")
    lang = _source_lang(direction)
    hits: list[tuple[int, dict, list[str]]] = []
    for term in terms:
        matched = _matching_phrases(query, lang, term)
        if not matched:
            continue
        longest = max(len(p) for p in matched)
        hits.append((longest, term, matched))
    if not hits:
        return _blocked(task, "glossary_uncovered", None, "")
    best = max(h[0] for h in hits)
    winners = [h for h in hits if h[0] == best]
    term_ids = [h[1]["id"] for h in winners]
    if len({i for i in term_ids}) > 1:
        return _blocked(task, "glossary_ambiguous", None, "", term_ids=term_ids)
    _longest, term, matched = winners[0]
    all_source = _phrases(term, lang)
    present = _matching_phrases(query, lang, term)
    left = _leftover(query, lang, present)
    if left:
        return _blocked(task, "glossary_remainder", term["id"], left)
    other = _other_lang(lang)
    other_phrases = []
    for phrase in _phrases(term, other):
        if phrase not in other_phrases:
            other_phrases.append(phrase)
    same_phrases = []
    for phrase in all_source:
        if phrase in matched:
            continue
        if phrase not in same_phrases:
            same_phrases.append(phrase)
    original = _variant(query, lang)
    b_extra = other_phrases[:1]
    c_extra = other_phrases[:2]
    m_extra = same_phrases[:3]
    arms = {
        "B": [original, *(_variant(p, other) for p in b_extra)],
        "C": [original, *(_variant(p, other) for p in c_extra)],
        "M": [original, *(_variant(p, lang) for p in m_extra)],
    }
    # B/C without an other-language phrase would be a duplicate of A.
    # Refuse that instead of pretending a translation exists.
    if len(arms["B"]) < 2:
        return _blocked(task, "glossary_no_other_language_phrase", term["id"], "")
    if len(arms["C"]) < 2:
        return _blocked(task, "glossary_no_other_language_phrase", term["id"], "")
    return {
        "task_id": task["id"],
        "direction": direction,
        "status": "covered",
        "reason": "",
        "matched_term_id": term["id"],
        "remainder": "",
        "ambiguous_term_ids": [],
        "model_requests": 0,
        "arms": arms,
    }


def _blocked(
    task: dict,
    reason: str,
    term_id: str | None,
    remainder: str,
    term_ids: list | None = None,
) -> dict:
    return {
        "task_id": task.get("id", ""),
        "direction": task.get("direction", ""),
        "status": "blocked",
        "reason": reason,
        "matched_term_id": term_id,
        "remainder": remainder,
        "ambiguous_term_ids": list(term_ids or []),
        "model_requests": 0,
        "arms": {"B": [], "C": [], "M": []},
    }


def build_document(tasks: list, terms: list[dict], terms_path: str) -> dict:
    classified = [classify_task(task, terms) for task in tasks]
    return {
        "version": VERSION,
        "query_source": QUERY_SOURCE,
        "terms_path": terms_path,
        "model_requests": 0,
        "synonym_guarantee": False,
        "note": (
            "未验证词表的机械匹配。未覆盖、有剩余词或歧义则该任务 B/C/M 为空，"
            "不得补造查询。这不是同义结论，也不是模型改写。"
        ),
        "tasks": classified,
    }


def arm_variants(document: dict, arm: str) -> dict:
    """Map task id -> variant list (empty list means blocked)."""
    if arm not in ("B", "C", "M"):
        raise ValueError("arm must be B, C, or M")
    out = {}
    for row in document.get("tasks") or []:
        variants = ((row.get("arms") or {}).get(arm)) or []
        out[row["task_id"]] = variants
    return out


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build frozen glossary variant document")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--terms", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    tasks = load_queries(Path(args.queries))["eval.batch_1"]
    terms = load_terms(Path(args.terms))
    doc = build_document(tasks, terms, str(args.terms))
    Path(args.out).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    covered = sum(1 for row in doc["tasks"] if row["status"] == "covered")
    print(f"tasks={len(doc['tasks'])} covered={covered} model_requests=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
