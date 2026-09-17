"""E1 minimal runner (W3): budgets, merge, structured records.

Basis:
- experiments/E1-cross-language-search/protocol.md Sections 3-5
- experiments/E1-cross-language-search/run-settings.json (budgets, top_n, windows)
- experiments/E1-cross-language-search/schemas/candidates.schema.json
  (candidate row required fields)
- docs/engineering/prerequisites.md Section 1 (serial, budgets counted
  separately, no fixed-interval guarantee, failures recorded)

Design for testability and honesty:
- No network by default: ``http_get`` is required (same contract as
  ``github_search.search_repos``). Without it, raise instead of calling
  api.github.com.
- No tokens inside: token comes from the explicit argument or
  ``GITHUB_TOKEN`` env inside ``github_search``. This module never reads
  or writes secrets itself.
- D arm (networked AI assistant) is NOT executed here: it has no fixed
  GitHub budget and its behaviour is tool-dependent. Requesting D raises
  ``ValueError`` so callers cannot silently record it as a GitHub run.
- Cancellation: pass ``should_cancel`` callable returning True to stop
  before each new GitHub request. Already-sent requests stay recorded;
  each remaining pending variant gets one ``cancelled`` entry in errors,
  never fabricated candidates.
- Errors (HTTP failures, timeouts, bad payloads) are recorded per
  variant in ``errors`` and do not poison other variants. Missing
  ``text_matches`` becomes ``["unknown"]`` via ``github_search``.
- Two-phase merge: run ALL budgeted variants first (respecting cancel),
  collecting per-query raw hits into ``per_query_records``; only after
  every query finishes, dedupe by ``canonical``/merge/sort/truncate to
  ``MERGED_TOP_N``. Never break the outer loop early just because one
  query filled the merge window.
- Sources: ``per_query_records`` keeps every hit with its
  variant/query/rank/page; ``merged_candidates`` dedupes but retains ALL
  source associations as
  ``sources: [{variant_query, api_query, variant_lang, rank, page}, ...]``,
  not first-seen only.
- Counters: ``attempted_requests`` counts every GitHub call tried
  (successful + failed); ``successful_requests`` counts only successes;
  ``failed_requests`` counts exceptions; ``cancelled_variants`` counts
  variants skipped by cancel. Failed attempts count toward cost;
  success count alone is not cost. ``actual_requests`` is kept as a
  deprecated alias of ``successful_requests`` for backward compatibility.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

try:
    from .github_search import canonical, search_repos
except ImportError:  # direct script execution
    from github_search import canonical, search_repos  # type: ignore

ARM_BUDGETS = {"A": 1, "B": 2, "C": 4, "M": 4}
ALLOWED_ARMS = frozenset(ARM_BUDGETS)
ALLOWED_DIRECTIONS = frozenset({"zh2en", "en2zh"})
ALLOWED_VARIANT_LANGS = frozenset({"zh", "en"})
PER_QUERY_TOP_N = 30
MERGED_TOP_N = 30


def _utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _validate_variant(variant: dict) -> dict:
    if not isinstance(variant, dict):
        raise TypeError("variant must be dict")
    for key in ("variant_query", "variant_lang", "api_query"):
        value = variant.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"variant.{key} must be a non-empty string")
        if len(value) > 256:
            raise ValueError(f"variant.{key} must be <= 256 characters")
    if variant["variant_lang"] not in ALLOWED_VARIANT_LANGS:
        raise ValueError("variant_lang must be zh or en")
    return {
        "variant_query": variant["variant_query"],
        "variant_lang": variant["variant_lang"],
        "api_query": variant["api_query"],
    }


def build_candidate_row(
    *,
    run_id: str,
    task_id: str,
    direction: str,
    arm: str,
    variant_query: str,
    variant_lang: str,
    api_query: str,
    page: int,
    rank: int,
    repo: str,
    stars: int,
    matched_fields: list,
    is_seed_target: bool,
    fetched_at: str,
) -> dict:
    """Build one schema-conformant candidate row, raising on bad input."""
    if not run_id or not isinstance(run_id, str):
        raise ValueError("run_id must be a non-empty string")
    if not task_id or not isinstance(task_id, str):
        raise ValueError("task_id must be a non-empty string")
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError("direction must be zh2en or en2zh")
    if arm not in ALLOWED_ARMS:
        raise ValueError("arm must be one of A/B/C/M")
    if variant_lang not in ALLOWED_VARIANT_LANGS:
        raise ValueError("variant_lang must be zh or en")
    for label, value in (
        ("variant_query", variant_query),
        ("api_query", api_query),
        ("repo", repo),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be a non-empty string")
    if not isinstance(page, int) or page < 1:
        raise ValueError("page must be int >= 1")
    if not isinstance(rank, int) or rank < 1:
        raise ValueError("rank must be int >= 1")
    if not isinstance(stars, int) or stars < 0:
        raise ValueError("stars must be int >= 0")
    if (
        not isinstance(matched_fields, list)
        or not matched_fields
        or any(
            f not in ("name", "description", "readme", "unknown")
            for f in matched_fields
        )
    ):
        raise ValueError(
            "matched_fields must be a non-empty list of "
            "name/description/readme/unknown"
        )
    if not isinstance(is_seed_target, bool):
        raise ValueError("is_seed_target must be bool")
    if not isinstance(fetched_at, str) or not fetched_at:
        raise ValueError("fetched_at must be a non-empty string")
    return {
        "run_id": run_id,
        "task_id": task_id,
        "direction": direction,
        "arm": arm,
        "variant_query": variant_query,
        "variant_lang": variant_lang,
        "api_query": api_query,
        "page": page,
        "rank": rank,
        "repo": repo,
        "stars": stars,
        "matched_fields": list(matched_fields),
        "is_seed_target": is_seed_target,
        "fetched_at": fetched_at,
    }


def run_method(
    *,
    run_id: str,
    task_id: str,
    direction: str,
    arm: str,
    variants: list,
    seed_repos: set | None = None,
    http_get: Callable[[str, dict], Any] | None = None,
    token: str | None = None,
    per_page: int = PER_QUERY_TOP_N,
    should_cancel: Callable[[], bool] | None = None,
    sleep_func: Callable[[float], None] | None = None,
    sleep_seconds: float = 0,
) -> dict:
    """Run one (task, arm) with a fixed GitHub budget, return records.

    Two phases:
    1. Run ALL budgeted variants first (respecting ``should_cancel``),
       collecting per-query raw hits into ``per_query_records``.
    2. Only after every query finishes, dedupe/merge/sort/truncate to
       ``MERGED_TOP_N`` into ``merged_candidates`` (with ``candidates``
       as a backward-compatible alias).

    Returns ``{"per_query_records": [...every hit...],
    "merged_candidates": [...deduped, truncated, with sources...],
    "candidates": [...alias of merged_candidates...],
    "errors": [...], "requested_budget": int,
    "attempted_requests": int, "successful_requests": int,
    "failed_requests": int, "cancelled_variants": int,
    "actual_requests": int (deprecated alias of successful_requests)}``.
    Rows conform to candidates.schema.json required fields; merged rows
    additionally carry ``sources``.
    """
    if arm == "D":
        raise ValueError("arm D is a networked-assistant control, not a GitHub run")
    if arm not in ALLOWED_ARMS:
        raise ValueError("arm must be one of A/B/C/M")
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError("direction must be zh2en or en2zh")
    if not run_id or not task_id:
        raise ValueError("run_id and task_id must be non-empty strings")
    if http_get is None:
        raise RuntimeError(
            "no http_get injected: refusing real network by default"
        )
    if not isinstance(variants, list) or not variants:
        raise ValueError("variants must be a non-empty list")
    requested_budget = ARM_BUDGETS[arm]
    clean_variants = [_validate_variant(v) for v in variants]
    if len(clean_variants) > requested_budget:
        raise ValueError(
            f"arm {arm} allows at most {requested_budget} variants, "
            f"got {len(clean_variants)}"
        )
    seeds = {s.lower() for s in (seed_repos or set()) if isinstance(s, str)}

    per_query_records: list = []
    errors: list = []
    attempted_requests = 0
    successful_requests = 0
    failed_requests = 0
    cancelled_variants = 0
    fetched_at = _utcnow()
    # Phase 1: run ALL budgeted variants first (respect cancel),
    # collecting per-query raw hits. No merge truncation here.
    for index, variant in enumerate(clean_variants):
        if should_cancel is not None and should_cancel():
            for pending in range(index, len(clean_variants)):
                errors.append(
                    {
                        "variant_index": pending,
                        "api_query": clean_variants[pending]["api_query"],
                        "error": "cancelled",
                    }
                )
                cancelled_variants += 1
            break
        try:
            repos = search_repos(
                variant["api_query"],
                per_page=per_page,
                page=1,
                token=token,
                http_get=http_get,
                sleep_func=sleep_func,
                sleep_seconds=sleep_seconds,
            )
        except Exception as exc:  # record, do not fabricate candidates
            attempted_requests += 1
            failed_requests += 1
            errors.append(
                {
                    "variant_index": index,
                    "api_query": variant["api_query"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        attempted_requests += 1
        successful_requests += 1
        for rank0, repo_item in enumerate(repos[:per_page], start=1):
            full_name = repo_item.get("full_name") or repo_item.get("repo") or ""
            key = canonical(full_name) if full_name else ""
            if not full_name:
                continue
            per_query_records.append(
                build_candidate_row(
                    run_id=run_id,
                    task_id=task_id,
                    direction=direction,
                    arm=arm,
                    variant_query=variant["variant_query"],
                    variant_lang=variant["variant_lang"],
                    api_query=variant["api_query"],
                    page=1,
                    rank=rank0,
                    repo=full_name,
                    stars=int(repo_item.get("stars", 0)),
                    matched_fields=list(
                        repo_item.get("matched_fields", ["unknown"])
                    ),
                    is_seed_target=key in seeds,
                    fetched_at=fetched_at,
                )
            )
    # Phase 2: merge/dedupe/sort/truncate only after every query finishes.
    # First-seen order (variant order, then rank) is preserved; truncation
    # to MERGED_TOP_N happens here, never by breaking the outer loop early.
    merged_by_key: dict = {}
    order: list = []
    for rec in per_query_records:
        key = canonical(rec["repo"])
        src = {
            "variant_query": rec["variant_query"],
            "api_query": rec["api_query"],
            "variant_lang": rec["variant_lang"],
            "rank": rec["rank"],
            "page": rec["page"],
        }
        if key not in merged_by_key:
            merged_entry = dict(rec)
            merged_entry["sources"] = [src]
            merged_by_key[key] = merged_entry
            order.append(key)
        else:
            merged_by_key[key]["sources"].append(src)
    merged = [merged_by_key[k] for k in order][:MERGED_TOP_N]
    return {
        "per_query_records": per_query_records,
        "merged_candidates": merged,
        "candidates": merged,
        "errors": errors,
        "requested_budget": requested_budget,
        "attempted_requests": attempted_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "cancelled_variants": cancelled_variants,
        "actual_requests": successful_requests,
    }


__all__ = [
    "ARM_BUDGETS",
    "ALLOWED_ARMS",
    "PER_QUERY_TOP_N",
    "MERGED_TOP_N",
    "build_candidate_row",
    "run_method",
]
