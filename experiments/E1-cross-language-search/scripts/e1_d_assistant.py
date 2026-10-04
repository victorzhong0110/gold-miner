#!/usr/bin/env python3
"""E1 arm D: networked-assistant control against MiniMax-M3.

Protocol section 3: same demand as the other arms, asked of an actually
available networked assistant. 2026-10-04 owner decision (docs/decisions/0004):
MiniMax-M3 on https://api.minimax.cn/v1, no task cap, full eval.batch_1.

The official MiniMax server tool ``web_search`` is exposed on
``POST /v1/responses``, not on chat completions. This runner uses that
endpoint. It does not attach a GitHub search tool. After the assistant
answers, each named repository is checked with the GitHub API. Missing
repositories are hallucinations, not candidates.

No network unless ``--live``. Missing credentials write nothing under
``runs/`` and exit as 未运行 / owner-blocked. Quota stops are resumable.

A task counts as completed only when the model returned a parseable list and
every name was checked. Timeouts, HTTP errors and answers without a list stay
retryable: the next run with the same ``--out`` asks the model again (up to
``--model-attempts`` per run). GitHub 301/302 answers for renamed or
transferred repositories are followed and counted as existing under the new
``canonical_repo``; unresolved checks are re-run on resume without a new model
call.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

SCRIPT = Path(__file__).resolve().parent
E1 = SCRIPT.parent
sys.path.insert(0, str(SCRIPT))

from e1_batch import load_queries, materials_commit  # noqa: E402
from github_search import canonical  # noqa: E402

PROMPT_PATH = E1 / "prompts" / "d-assistant.txt"
PLACEHOLDER = "【在此粘贴一条用户原话】"
SEED_PATH = E1 / "verified-seeds.jsonl"
HISTORICAL_A = E1 / "runs" / "2026-09-22-w4-first" / "candidates.jsonl"
DECISION = "docs/decisions/0004-minimax-d-group.md"
DEFAULT_BASE = "https://api.minimax.cn/v1"
DEFAULT_MODEL = "MiniMax-M3"
MAX_OUTPUT_TOKENS = 8192
REPO_LIMIT = 10
QUOTA_WAIT_SECONDS = 5 * 60 * 60
QUOTA_BUSINESS = {1002, 2045, 2056}
AUTH_BUSINESS = {1004, 2049}
BALANCE_BUSINESS = {1008}
USER_AGENT = "gold-miner-e1-d/0.1"

HttpPost = Callable[[str, dict, dict, float], dict]
HttpGet = Callable[[str, dict, float], dict]
SleepFn = Callable[[float], None]

_THINK_CLOSED = re.compile(r"<think\b[^>]*>[\s\S]*?</think\s*>", re.I)
_THINK_OPEN = re.compile(r"<think\b[^>]*>[\s\S]*$", re.I)
_BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_GITHUB_URL = re.compile(
    r"https?://(?:www\.)?github\.com/"
    r"([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"([A-Za-z0-9._-]{1,100})",
    re.I,
)
_BARE_REPO = re.compile(
    r"^([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})$"
)
_SECRET_RES = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"ghs_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.I),
)


def utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def redact(text: str, extra: str = "") -> str:
    out = text or ""
    if extra:
        out = out.replace(extra, "[redacted]")
    key = os.environ.get("OPENAI_API_KEY") or ""
    token = os.environ.get("GITHUB_TOKEN") or ""
    minimax = os.environ.get("MINIMAX_API_KEY") or ""
    for secret in (key, token, minimax):
        if secret:
            out = out.replace(secret, "[redacted]")
    for pat in _SECRET_RES:
        out = pat.sub("[redacted]", out)
    return out


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_think(content: str) -> str:
    if not isinstance(content, str):
        return ""
    text = _THINK_CLOSED.sub("", content)
    text = _THINK_OPEN.sub("", text)
    return text.strip()


def render_prompt(template: str, query: str) -> str:
    if PLACEHOLDER not in template:
        raise ValueError("d-assistant.txt is missing the query placeholder")
    return template.replace(PLACEHOLDER, query, 1)


def _clean_repo_name(name: str) -> str:
    cleaned = name.strip().removesuffix(".git").strip(".")
    return cleaned


def extract_repos_from_line(line: str) -> list[str]:
    stripped = _BULLET.sub("", line.strip()).strip("`").strip()
    stripped = stripped.strip("，。；;、")
    found: list[str] = []
    for owner, repo in _GITHUB_URL.findall(stripped):
        repo = _clean_repo_name(repo)
        if owner and repo:
            found.append(f"{owner}/{repo}")
    if found:
        return found
    bare = _BARE_REPO.fullmatch(stripped)
    if not bare:
        return []
    owner, repo = bare.group(1), _clean_repo_name(bare.group(2))
    if not owner or not repo:
        return []
    return [f"{owner}/{repo}"]


def parse_assistant_repos(text: str, limit: int = REPO_LIMIT) -> dict:
    """Take the assistant's repository list, at most ``limit`` names.

    Leading non-repo lines are skipped. After the first repository line, a
    blank line or a non-repo line ends the list (the prompt puts explanations
    after the list).
    """
    lines = strip_think(text).splitlines()
    repos: list[str] = []
    seen: set[str] = set()
    started = False
    ignored_over_cap = 0
    for line in lines:
        if not line.strip():
            if started:
                break
            continue
        found = extract_repos_from_line(line)
        if not found:
            if started:
                break
            continue
        started = True
        for name in found:
            key = canonical(name)
            if key in seen:
                continue
            if len(repos) >= limit:
                ignored_over_cap += 1
                continue
            seen.add(key)
            repos.append(name)
    return {"repos": repos, "ignored_over_cap": ignored_over_cap}


def _business_code(data: dict) -> int | None:
    base = data.get("base_resp")
    if not isinstance(base, dict):
        return None
    code = base.get("status_code")
    if code in (None, ""):
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def classify_model_response(status: int, body: str) -> dict:
    """Classify one model HTTP result. Does not invent an answer."""
    parsed: dict | None = None
    try:
        loaded = json.loads(body) if body else None
        if isinstance(loaded, dict):
            parsed = loaded
    except json.JSONDecodeError:
        parsed = None
    business = _business_code(parsed) if parsed else None
    blob = body or ""
    if business is not None:
        blob = f"{blob} {business}"
    lowered = blob.lower()
    quota = status == 429 or business in QUOTA_BUSINESS or (
        "quota" in lowered or "rate limit" in lowered or "资源限制" in blob
    )
    if status in (401, 403) or business in AUTH_BUSINESS:
        code = "auth_rejected"
    elif business in BALANCE_BUSINESS or "余额不足" in blob:
        code = "insufficient_balance"
    elif quota and (status != 200 or (business not in (None, 0))):
        code = "quota_limited"
    elif status == 404 or business == 2013 and (
        "web_search" in lowered or "tool" in lowered or "responses" in lowered
    ):
        code = "tool_unavailable"
    elif business not in (None, 0) or (status and status != 200):
        code = "bad_response"
    elif parsed is None:
        code = "bad_response"
    else:
        answer = extract_answer(parsed)
        status_text = str(parsed.get("status") or "")
        finish = status_text or str(
            (parsed.get("choices") or [{}])[0].get("finish_reason") or ""
        )
        if finish in {"length", "incomplete"} and not strip_think(answer):
            code = "model_output_truncated"
        elif not strip_think(answer):
            code = "empty_model_output"
        else:
            code = "ok"
    retry_after = None
    return {
        "code": code,
        "business_code": business,
        "parsed": parsed,
        "retry_after": retry_after,
    }


def extract_answer(data: dict) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") in {
                        "output_text",
                        "text",
                    }:
                        parts.append(str(block.get("text") or ""))
    if parts:
        return "\n".join(parts)
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def extract_search_calls(data: dict) -> list[dict]:
    calls: list[dict] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "web_search_call":
                continue
            action = item.get("action") if isinstance(item.get("action"), dict) else {}
            calls.append(
                {
                    "query": action.get("query") if isinstance(action.get("query"), str) else "",
                    "status": item.get("status") if isinstance(item.get("status"), str) else "",
                }
            )
    content = data.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "server_tool_use" and block.get("name") == "web_search":
                tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                query = tool_input.get("query")
                calls.append(
                    {
                        "query": query if isinstance(query, str) else "",
                        "status": "server_tool_use",
                    }
                )
    return calls


def extract_usage(data: dict) -> dict:
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    details = usage.get("input_tokens_details")
    cached = None
    if isinstance(details, dict):
        cached = details.get("cached_tokens")
    if cached is None:
        cached = usage.get("cache_read_input_tokens")

    def _int_or_none(value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None

    return {
        "input_tokens": _int_or_none(
            usage.get("input_tokens", usage.get("prompt_tokens"))
        ),
        "output_tokens": _int_or_none(
            usage.get("output_tokens", usage.get("completion_tokens"))
        ),
        "total_tokens": _int_or_none(usage.get("total_tokens")),
        "cached_tokens": _int_or_none(cached),
    }


def load_seed_canonicals(path: Path = SEED_PATH) -> set[str]:
    if not path.is_file():
        return set()
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        repo = row.get("repo")
        if isinstance(repo, str) and "/" in repo:
            found.add(canonical(repo))
    return found


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def query_lang(direction: str) -> str:
    return "zh" if direction == "zh2en" else "en"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


def default_model_post(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read(2_000_000).decode("utf-8", errors="replace")
            retry = resp.headers.get("Retry-After")
            return {"status": int(resp.status), "body": body, "retry_after": retry}
    except urllib.error.HTTPError as exc:
        body = exc.read(200_000).decode("utf-8", errors="replace")
        retry = exc.headers.get("Retry-After") if exc.headers else None
        return {"status": int(exc.code), "body": body, "retry_after": retry}
    except TimeoutError as exc:
        raise TimeoutError("model request timed out") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TimeoutError("model request timed out") from exc
        raise ConnectionError("model request failed: " + type(exc.reason).__name__) from exc
    except (http.client.HTTPException, OSError) as exc:
        raise ConnectionError("model request failed: " + type(exc).__name__) from exc


def default_github_get(url: str, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read(1_000_000).decode("utf-8", errors="replace")
            return {
                "status": int(resp.status),
                "body": body,
                "headers": {"Location": resp.headers.get("Location")},
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(200_000).decode("utf-8", errors="replace")
        location = exc.headers.get("Location") if exc.headers else None
        retry = exc.headers.get("Retry-After") if exc.headers else None
        remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
        return {
            "status": int(exc.code),
            "body": raw,
            "headers": {
                "Location": location,
                "Retry-After": retry,
                "X-RateLimit-Remaining": remaining,
            },
        }
    except (urllib.error.URLError, TimeoutError, http.client.HTTPException, OSError) as exc:
        return {"status": 0, "body": "", "headers": {}, "error": type(exc).__name__}


def _retry_after_seconds(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def model_payload(model: str, prompt: str, *, include_max_tokens: bool) -> dict:
    payload: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "tools": [{"type": "web_search"}],
    }
    if include_max_tokens:
        payload["max_output_tokens"] = MAX_OUTPUT_TOKENS
    return payload


GITHUB_API_HOST = "api.github.com"
REDIRECT_STATUSES = (301, 302, 307, 308)
MAX_GITHUB_REDIRECTS = 3
# Verification codes that are final for a name. Anything else (redirect not
# resolved, GitHub rate limit, network or bad response) is re-checked on resume.
FINAL_VERIFY_CODES = {"exists", "github_not_found"}
# Model-call codes that stop the whole invocation (same cause for every task).
FATAL_MODEL_CODES = {"auth_rejected", "insufficient_balance", "tool_unavailable"}
QUOTA_MODEL_CODES = {"quota_limited", "rate_limited"}


def _github_headers(token: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _classify_repo_response(status: int, body: str, hdrs: dict) -> dict:
    if status == 200:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return {"code": "bad_response", "http_status": status, "exists": False}
        if not isinstance(data, dict) or not isinstance(data.get("full_name"), str):
            return {"code": "bad_response", "http_status": status, "exists": False}
        stars = data.get("stargazers_count")
        if not isinstance(stars, int) or isinstance(stars, bool) or stars < 0:
            return {
                "code": "bad_response",
                "http_status": status,
                "exists": False,
                "message": "missing stargazers_count",
            }
        return {
            "code": "exists",
            "http_status": 200,
            "exists": True,
            "canonical_repo": data["full_name"],
            "stars": stars,
            "private": bool(data.get("private")),
            "description": data.get("description") if isinstance(data.get("description"), str) else "",
        }
    if status == 404:
        return {"code": "github_not_found", "http_status": 404, "exists": False}
    remaining = hdrs.get("X-RateLimit-Remaining")
    if status in (403, 429) or remaining == "0":
        return {
            "code": "rate_limited",
            "http_status": status,
            "exists": False,
            "retry_after": hdrs.get("Retry-After"),
        }
    if not status:
        return {"code": "github_network_error", "http_status": None, "exists": False}
    return {"code": "bad_response", "http_status": status, "exists": False}


def verify_repo(
    full_name: str,
    github_get: HttpGet,
    token: str,
    timeout: float,
    *,
    sleep: SleepFn | None = None,
    sleep_seconds: float = 0.0,
    max_redirects: int = MAX_GITHUB_REDIRECTS,
) -> dict:
    """Check one name with ``GET /repos/{owner}/{repo}``.

    A renamed or transferred repository answers 301 with ``Location`` pointing
    at ``/repositories/{id}`` (or another ``/repos/...`` URL). The redirect is
    followed on api.github.com only, up to ``max_redirects`` hops; the final
    ``full_name`` becomes ``canonical_repo`` and the hop is recorded. The
    result carries ``github_requests`` (every hop is one request).
    """
    owner, repo = full_name.split("/", 1)
    url = "https://api.github.com/repos/" + urllib.parse.quote(owner) + "/" + urllib.parse.quote(repo)
    headers = _github_headers(token)
    hops: list[dict] = []
    requests = 0
    result: dict | None = None
    for hop in range(max_redirects + 1):
        if hop and sleep and sleep_seconds:
            sleep(sleep_seconds)
        packed = github_get(url, headers, timeout)
        requests += 1
        status = int(packed.get("status") or 0)
        body = str(packed.get("body") or "")
        hdrs = packed.get("headers") if isinstance(packed.get("headers"), dict) else {}
        if status in REDIRECT_STATUSES:
            location = str(hdrs.get("Location") or "")
            target = urllib.parse.urljoin(url, location) if location else ""
            parsed = urllib.parse.urlparse(target)
            hops.append({"http_status": status, "location": target})
            if not target or parsed.scheme != "https" or parsed.netloc.lower() != GITHUB_API_HOST:
                result = {
                    "code": "github_migrated",
                    "http_status": status,
                    "exists": False,
                    "location": target,
                    "message": "redirect without a followable api.github.com Location",
                }
                break
            if hop == max_redirects:
                result = {
                    "code": "github_migrated",
                    "http_status": status,
                    "exists": False,
                    "location": target,
                    "message": "too many redirects",
                }
                break
            url = target
            continue
        result = _classify_repo_response(status, body, hdrs)
        break
    assert result is not None
    result["github_requests"] = requests
    if hops:
        result["redirect"] = {
            "from": full_name,
            "first_http_status": hops[0]["http_status"],
            "hops": hops,
        }
        if result.get("exists"):
            result["redirected_from"] = full_name
    return result


def _model_headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
        "User-Agent": USER_AGENT,
    }


def call_model(
    *,
    base_url: str,
    model: str,
    api_key: str,
    prompt: str,
    http_post: HttpPost,
    timeout: float,
) -> dict:
    url = base_url.rstrip("/") + "/responses"
    include_cap = True
    attempts = []
    for _ in range(2):
        payload = model_payload(model, prompt, include_max_tokens=include_cap)
        started = time.monotonic()
        try:
            packed = http_post(url, _model_headers(api_key), payload, timeout)
        except (TimeoutError, ConnectionError) as exc:
            attempts.append(
                {
                    "code": "timeout" if isinstance(exc, TimeoutError) else "network_error",
                    "http_status": None,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "include_max_tokens": include_cap,
                    "timeout_s": timeout,
                    "sent": True,
                    "error_excerpt": redact(str(exc))[:300],
                }
            )
            break
        elapsed_ms = int((time.monotonic() - started) * 1000)
        status = int(packed.get("status") or 0)
        body = str(packed.get("body") or "")
        classified = classify_model_response(status, body)
        classified["elapsed_ms"] = elapsed_ms
        classified["http_status"] = status
        classified["include_max_tokens"] = include_cap
        classified["retry_after"] = packed.get("retry_after")
        classified["sent"] = True
        classified["timeout_s"] = timeout
        if classified["code"] != "ok":
            classified["error_excerpt"] = redact(body)[:500]
        attempts.append(classified)
        message = body.lower()
        if (
            classified["code"] == "bad_response"
            and include_cap
            and classified.get("business_code") == 2013
            and "max_output_tokens" in message
        ):
            include_cap = False
            continue
        break
    last = attempts[-1]
    parsed = last.get("parsed") if isinstance(last.get("parsed"), dict) else {}
    answer = extract_answer(parsed) if parsed else ""
    return {
        "attempts": [
            {
                "code": item["code"],
                "http_status": item.get("http_status"),
                "business_code": item.get("business_code"),
                "elapsed_ms": item.get("elapsed_ms"),
                "include_max_tokens": item.get("include_max_tokens"),
                "timeout_s": item.get("timeout_s"),
                "sent": True,
                **({"error_excerpt": item["error_excerpt"]} if item.get("error_excerpt") else {}),
            }
            for item in attempts
        ],
        "code": last["code"],
        "http_status": last.get("http_status"),
        "business_code": last.get("business_code"),
        "elapsed_ms": sum(int(item.get("elapsed_ms") or 0) for item in attempts),
        "model_requests": len(attempts),
        "retry_after": last.get("retry_after"),
        "answer": answer,
        "searches": extract_search_calls(parsed) if parsed else [],
        "usage": extract_usage(parsed) if parsed else {},
        "response_status": parsed.get("status") if isinstance(parsed.get("status"), str) else None,
    }


def candidate_from_verification(
    *,
    run_id: str,
    task: dict,
    rank: int,
    verified: dict,
    fetched_at: str,
    seeds: set[str],
) -> dict:
    repo = verified["canonical_repo"]
    lang = query_lang(task["direction"])
    return {
        "run_id": run_id,
        "task_id": task["id"],
        "direction": task["direction"],
        "arm": "D",
        "variant_query": task["query"],
        "variant_lang": lang,
        "api_query": task["query"],
        "page": 1,
        "rank": rank,
        "repo": repo,
        "stars": verified["stars"],
        "matched_fields": ["unknown"],
        "is_seed_target": canonical(repo) in seeds,
        "fetched_at": fetched_at,
        "sources": [
            {
                "variant_query": task["query"],
                "api_query": task["query"],
                "variant_lang": lang,
                "rank": rank,
                "page": 1,
            }
        ],
    }


def overlap_with_historical_a(
    d_candidates: list[dict],
    a_candidates: list[dict],
    task_ids: list[str] | None = None,
) -> dict:
    """Set overlap only. Not a suitability comparison.

    With ``task_ids`` the table has one row per batch task, in batch order,
    including tasks where D or A has nothing. A tasks outside the batch are
    listed separately and are not part of the totals.
    """
    a_by_task: dict[str, list[str]] = {}
    for row in a_candidates:
        if row.get("arm") != "A":
            continue
        task_id = str(row.get("task_id") or "")
        repo = row.get("repo")
        if not task_id or not isinstance(repo, str):
            continue
        a_by_task.setdefault(task_id, [])
        key = canonical(repo)
        if key not in a_by_task[task_id]:
            a_by_task[task_id].append(key)
    d_by_task: dict[str, list[str]] = {}
    for row in d_candidates:
        task_id = str(row.get("task_id") or "")
        repo = row.get("repo")
        if not task_id or not isinstance(repo, str):
            continue
        d_by_task.setdefault(task_id, [])
        key = canonical(repo)
        if key not in d_by_task[task_id]:
            d_by_task[task_id].append(key)
    if task_ids is None:
        ordered = sorted(set(a_by_task) | set(d_by_task))
        outside: list[str] = []
    else:
        ordered = list(task_ids)
        outside = sorted(set(a_by_task) - set(ordered))
    per_task = []
    for task_id in ordered:
        a_set = a_by_task.get(task_id, [])
        d_set = d_by_task.get(task_id, [])
        a_keys = set(a_set)
        inter = [name for name in d_set if name in a_keys]
        per_task.append(
            {
                "task_id": task_id,
                "d_existing": len(d_set),
                "a_candidates": len(a_set),
                "intersection": len(inter),
                "d_only": len(d_set) - len(inter),
                "intersection_repos": inter,
            }
        )
    return {
        "kind": "canonical-repo-set-overlap",
        "suitability": "未运行",
        "per_task": per_task,
        "a_tasks_outside_batch": [
            {"task_id": task_id, "a_candidates": len(a_by_task[task_id])} for task_id in outside
        ],
        "d_existing": sum(row["d_existing"] for row in per_task),
        "a_candidates": sum(row["a_candidates"] for row in per_task),
        "intersection": sum(row["intersection"] for row in per_task),
        "d_only": sum(row["d_only"] for row in per_task),
    }


def _event_key(row: dict) -> str:
    if row.get("call_id"):
        return str(row["call_id"])
    return f"{row.get('task_id')}@{row.get('recorded_at')}@{row.get('input_sha256')}@{row.get('code')}"


def model_call_events(rows: list[dict]) -> list[dict]:
    """Distinct model-call events. Terminal marker rows repeat their event."""
    seen: set[str] = set()
    events = []
    for row in rows:
        if not row.get("task_id"):
            continue
        key = _event_key(row)
        if key in seen:
            continue
        seen.add(key)
        events.append(row)
    return events


def latest_calls(rows: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in rows:
        if row.get("task_id"):
            latest[str(row["task_id"])] = row
    return latest


def is_completed(row: dict | None) -> bool:
    """A task counts as completed only after an ok answer with a parseable
    list whose verification pass finished. Timeouts, bad responses and empty
    lists stay retryable, whatever ``terminal`` an older runner wrote."""
    return bool(
        row
        and row.get("code") == "ok"
        and row.get("terminal")
        and row.get("parsed_repos")
    )


def latest_verifications(rows: list[dict]) -> dict[tuple[str, str], dict]:
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        name = row.get("model_repo")
        if not row.get("task_id") or not isinstance(name, str):
            continue
        latest[(str(row["task_id"]), canonical(name))] = row
    return latest


def _fmt_rate(num: int, den: int) -> str:
    if not den:
        return "未知"
    return f"{num}/{den} = {num / den * 100:.1f}%"


def render_report(summary: dict) -> str:
    usage = summary["usage"]
    repos = summary["repos"]
    lines = [
        f"# E1 D 组运行 {summary['run_id']}",
        "",
        f"- 批次：`{summary['batch']}`。协议第 3 节 D 组，联网助手强对照。",
        f"- 模型：`{summary['model']}`。端点：`POST /v1/responses`，服务端工具 `web_search`。",
        f"- 决定：{DECISION}（2026-10-04）。输出上限 {MAX_OUTPUT_TOKENS}。",
        f"- 材料提交：`{summary['materials_commit']}`。",
        f"- 开始 {summary.get('started_at') or '未知'}，结束 {summary.get('finished_at') or '未结束'}（UTC）。"
        f"修复后的 runner 调用 {len(summary.get('invocations') or [])} 次（见 checkpoint.json `invocations`；首轮调用未逐次记录）。",
        f"- 状态：`{summary['status']}`。",
        "",
        "## 任务",
        "",
        f"- 任务完成 {summary['tasks_completed']} / {summary['tasks_total']}。失败（可续跑重试）{summary['tasks_failed']}。未尝试 {summary['tasks_not_attempted']}。",
        "- 「完成」= 模型返回可解析名单且 GitHub 核对已跑完。超时、HTTP 错误、没有可解析名单的任务不算完成，续跑时重新请求模型。",
    ]
    if summary["failed_tasks"]:
        lines.append(
            "- 仍失败："
            + "，".join(f"`{row['task_id']}`（{row['code']}，已请求 {row['model_requests']} 次）" for row in summary["failed_tasks"])
            + "。"
        )
    if summary["retried_tasks"]:
        lines.append(
            "- 经过重试才完成："
            + "，".join(
                f"`{row['task_id']}`（先前 {'、'.join(row['failed_codes'])}，共请求 {row['model_requests']} 次）"
                for row in summary["retried_tasks"]
            )
            + "。"
        )
    lines += [
        f"- 模型请求 {summary['model_requests']}（含失败与重试；参数重试也计入）。GitHub 核对请求 {summary['github_requests']}（含跳转跟随与重核）。",
        f"- 服务端 web_search 调用（响应里可见的）：全部请求合计 {summary['web_search_calls']}；完成任务的最终回答合计 {summary['web_search_calls_completed']}。完成任务里模型没发起搜索的 {summary['tasks_without_search']}。",
        f"- 可见 token（全部请求合计）：输入 {usage.get('input_tokens')}，其中缓存 {usage.get('cached_tokens')}；输出 {usage.get('output_tokens')}。缺计数的请求不计入，不把 null 当成 0。",
        f"- 可见费用：{summary['visible_cost']}。",
        "- 人工用途判断：未运行。阅读对照：未运行。B/C/M 在本模型上：未运行。",
        "",
        "## 仓库核对",
        "",
        f"- 完成任务里模型提名 {repos['proposed']} 个（每题最多 {REPO_LIMIT}，题内去重）。",
        f"- GitHub 存在 {repos['exists']}（公开 {repos['exists_public']}，私有 {repos['exists_private']}）。其中经 301/302 跳转（改名或转移）跟随后存在 {repos['redirected']}。",
        f"- 幻觉（GitHub 404）{repos['hallucinated']}。幻觉率（占提名）{_fmt_rate(repos['hallucinated'], repos['proposed'])}。",
        f"- 核对未决（跳转跟不到、GitHub 限流或错误，续跑时重核）{repos['unresolved']}。",
        f"- 公开存在、写入 candidates.jsonl 的去重仓库 {summary['existing_repos']}。",
    ]
    if repos["redirect_rows"]:
        lines.append("")
        lines.append("| 任务 | 模型给的名字 | GitHub 跳转 | 现名（canonical_repo） |")
        lines.append("|---|---|---|---|")
        for row in repos["redirect_rows"]:
            lines.append(
                f"| {row['task_id']} | {row['model_repo']} | {row['http_status']} → {row['location']} | {row['canonical_repo'] or '未解析'} |"
            )
    if repos["hallucinated_rows"]:
        lines.append("")
        lines.append("404 名单：" + "，".join(f"`{row['model_repo']}`（{row['task_id']}）" for row in repos["hallucinated_rows"]) + "。")
    lines.append("")
    lines.append("failures.jsonl 是只追加的事件记录。上面数字取每个任务、每个名字的最新状态；较早的 timeout / bad_response / github_migrated 行若已被后来的成功覆盖，在这里不再算失败。")
    lines.append("")
    if summary.get("stopped_before_task_id"):
        lines.append(
            f"停在尚未完成的任务 `{summary['stopped_before_task_id']}`，代码 `{summary.get('stop_code')}`。"
        )
        lines.append("")
    remaining = summary.get("remaining_task_ids") or []
    lines.append("尚未完成：" + (", ".join(remaining) if remaining else "无"))
    lines.append("")
    lines.append("## 每题")
    lines.append("")
    lines.append("| 任务 | D 状态 | 模型请求 | web_search | 提名 | 存在 | 404 | 跳转 | 未决 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in summary["per_task"]:
        lines.append(
            f"| {row['task_id']} | {row['status']} | {row['model_requests']} | {row['web_search_calls']} | {row['proposed']} | {row['exists']} | {row['hallucinated']} | {row['redirected']} | {row['unresolved']} |"
        )
    lines.append("")
    lines.append("## 与历史 A 组的仓库集合交集")
    lines.append("")
    lines.append(
        "A 组来自 `runs/2026-09-22-w4-first`（2026-09-22，无模型，B/C/M 当时全部 blocked）。这是仓库全名集合的交集，不是用途适合度，也不是同一时刻的配对实验。协议第 7 节「强对照同样好用」需要用途判断，本批该项未观察。"
    )
    lines.append("")
    overlap = summary.get("overlap") or {}
    lines.append(
        f"本批 {summary['tasks_total']} 题：D 存在仓库 {overlap.get('d_existing', 0)}，该次 A 组候选 {overlap.get('a_candidates', 0)}，交集 {overlap.get('intersection', 0)}，只在 D 出现 {overlap.get('d_only', 0)}。"
    )
    lines.append("")
    lines.append("| 任务 | D 状态 | D 存在 | A 条数 | 交集 | 只在 D |")
    lines.append("|---|---|---:|---:|---:|---:|")
    status_by_task = {row["task_id"]: row["status"] for row in summary["per_task"]}
    for row in overlap.get("per_task") or []:
        lines.append(
            f"| {row['task_id']} | {status_by_task.get(row['task_id'], '—')} | {row['d_existing']} | {row['a_candidates']} | {row['intersection']} | {row['d_only']} |"
        )
    outside = overlap.get("a_tasks_outside_batch") or []
    if outside:
        lines.append("")
        lines.append(
            "A 组那次还跑了不在本批的任务，不计入上表合计："
            + "，".join(f"{row['task_id']}（{row['a_candidates']} 条）" for row in outside)
            + "。"
        )
    lines.append("")
    lines.append("## 不能下的结论")
    lines.append("")
    lines.append(
        "不能由这份名单宣布跨语言增益、产品效果或应该缩小功能。人工判断未运行。B、C、M 未在本模型上运行。费用未知。"
    )
    lines.append(
        "「存在」只说明 GitHub 上有这个仓库，不说明它适合用户原话里的需求；与 A 组交集低也不说明哪一组更好用。幻觉率只按 GitHub 404 计，不含存在但答非所问的仓库。"
    )
    lines.append("")
    return "\n".join(lines)


def _sum_usage(rows: list[dict]) -> dict:
    totals = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
    known = {"input_tokens": False, "output_tokens": False, "cached_tokens": False}
    for row in rows:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        for key in totals:
            if isinstance(usage.get(key), int):
                totals[key] += usage[key]
                known[key] = True
    return {key: totals[key] if known[key] else None for key in totals}


def summarize(out_dir: Path, state: dict, tasks: list[dict]) -> dict:
    call_rows = read_jsonl(out_dir / "model_calls.jsonl")
    events = model_call_events(call_rows)
    latest = latest_calls(call_rows)
    candidates = read_jsonl(out_dir / "candidates.jsonl")
    costs = read_jsonl(out_dir / "latency_cost.jsonl")
    verifications = latest_verifications(read_jsonl(out_dir / "verifications.jsonl"))
    events_by_task: dict[str, list[dict]] = {}
    for row in events:
        events_by_task.setdefault(str(row["task_id"]), []).append(row)

    per_task = []
    repos = {
        "proposed": 0,
        "exists": 0,
        "exists_public": 0,
        "exists_private": 0,
        "redirected": 0,
        "hallucinated": 0,
        "unresolved": 0,
        "redirect_rows": [],
        "hallucinated_rows": [],
    }
    failed_tasks = []
    retried_tasks = []
    completed_ids = set()
    for task in tasks:
        task_id = task["id"]
        row = latest.get(task_id)
        task_events = events_by_task.get(task_id, [])
        entry = {
            "task_id": task_id,
            "model_requests": sum(int(e.get("model_requests") or 0) for e in task_events),
            "web_search_calls": sum(len(e.get("searches") or []) for e in task_events),
            "proposed": 0,
            "exists": 0,
            "hallucinated": 0,
            "redirected": 0,
            "unresolved": 0,
        }
        if is_completed(row):
            completed_ids.add(task_id)
            entry["status"] = "完成"
            names = list(row.get("parsed_repos") or [])
            entry["proposed"] = len(names)
            for name in names:
                checked = verifications.get((task_id, canonical(name)))
                code = checked.get("code") if checked else None
                redirect = checked.get("redirect") if checked else None
                if code == "exists":
                    entry["exists"] += 1
                    if checked.get("private"):
                        repos["exists_private"] += 1
                    else:
                        repos["exists_public"] += 1
                elif code == "github_not_found":
                    entry["hallucinated"] += 1
                    repos["hallucinated_rows"].append({"task_id": task_id, "model_repo": name})
                else:
                    entry["unresolved"] += 1
                if isinstance(redirect, dict):
                    hops = redirect.get("hops") or [{}]
                    if code == "exists":
                        entry["redirected"] += 1
                    repos["redirect_rows"].append(
                        {
                            "task_id": task_id,
                            "model_repo": name,
                            "http_status": redirect.get("first_http_status"),
                            "location": hops[-1].get("location") or "",
                            "canonical_repo": checked.get("canonical_repo") if code == "exists" else None,
                        }
                    )
            failed_codes = [e.get("code") for e in task_events if e.get("code") != "ok"]
            if failed_codes:
                retried_tasks.append(
                    {"task_id": task_id, "failed_codes": failed_codes, "model_requests": entry["model_requests"]}
                )
        elif row is None:
            entry["status"] = "未尝试"
        elif row.get("code") == "ok":
            entry["status"] = "核对未完"
            failed_tasks.append({"task_id": task_id, "code": "verification_incomplete", "model_requests": entry["model_requests"]})
        else:
            entry["status"] = f"失败（{row.get('code')}）"
            failed_tasks.append({"task_id": task_id, "code": row.get("code"), "model_requests": entry["model_requests"]})
        for key in ("proposed", "exists", "hallucinated", "redirected", "unresolved"):
            repos[key] += entry[key]
        per_task.append(entry)

    remaining = [task["id"] for task in tasks if task["id"] not in completed_ids]
    seen_candidates: set[tuple[str, str]] = set()
    public_candidates = []
    for row in candidates:
        key = (str(row.get("task_id")), canonical(str(row.get("repo"))))
        if row.get("task_id") not in completed_ids or key in seen_candidates:
            continue
        seen_candidates.add(key)
        public_candidates.append(row)
    historical = read_jsonl(
        state.get("historical_a_path") and Path(state["historical_a_path"]) or HISTORICAL_A
    )
    overlap = overlap_with_historical_a(public_candidates, historical, [task["id"] for task in tasks])
    complete = not remaining and not state.get("stop_code") and repos["unresolved"] == 0
    completed_events = [latest[task_id] for task_id in completed_ids]
    return {
        "run_id": state["run_id"],
        "batch": state["batch"],
        "model": state["model"],
        "base_url_host": urllib.parse.urlparse(state["base_url"]).netloc,
        "materials_commit": state["materials_commit"],
        "prompt_sha256": state["prompt_sha256"],
        "started_at": state.get("started_at"),
        "finished_at": (state.get("finished_at") or utcnow()) if complete else None,
        "invocations": state.get("invocations") or [],
        "tasks_total": len(tasks),
        "tasks_completed": len(completed_ids),
        "tasks_failed": len(failed_tasks),
        "tasks_not_attempted": sum(1 for row in per_task if row["status"] == "未尝试"),
        "failed_tasks": failed_tasks,
        "retried_tasks": retried_tasks,
        "model_requests": sum(int(row.get("model_requests") or 0) for row in events),
        "github_requests": sum(int(row.get("github_requests") or 0) for row in costs),
        "existing_repos": len(public_candidates),
        "hallucinations": repos["hallucinated"],
        "hallucination_rate": (repos["hallucinated"] / repos["proposed"]) if repos["proposed"] else None,
        "repos": repos,
        "web_search_calls": sum(len(row.get("searches") or []) for row in events),
        "web_search_calls_completed": sum(len(row.get("searches") or []) for row in completed_events),
        "tasks_without_search": sum(1 for row in completed_events if not row.get("searches")),
        "usage": _sum_usage(events),
        "visible_cost": "未知",
        "stopped_before_task_id": state.get("stopped_before_task_id"),
        "stop_code": state.get("stop_code"),
        "remaining_task_ids": remaining,
        "per_task": per_task,
        "overlap": overlap,
        "human_judgment": "未运行",
        "b_c_m": "未运行",
        "status": "complete" if complete else "incomplete",
    }


def write_outputs(out_dir: Path, state: dict, tasks: list[dict]) -> dict:
    summary = summarize(out_dir, state, tasks)
    if summary["finished_at"]:
        state["finished_at"] = summary["finished_at"]
    else:
        state.pop("finished_at", None)
    repos = summary["repos"]
    manifest = {
        "run_id": summary["run_id"],
        "batch": summary["batch"],
        "arm": "D",
        "materials_commit": summary["materials_commit"],
        "prompt_version": f"prompts/d-assistant.txt sha256:{summary['prompt_sha256']}",
        "model": summary["model"],
        "base_url_host": summary["base_url_host"],
        "endpoint": "POST /v1/responses",
        "server_tool": "web_search",
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reading_setup": "reading-baseline.md v1",
        "reading_applied": False,
        "method": "D",
        "field_config": "not-a-github-search",
        "requested_budget": "eval.batch_1 full; no task cap; GitHub search budget 0",
        "actual_requests": {
            "model": summary["model_requests"],
            "github_verification": summary["github_requests"],
            "web_search_calls_visible": summary["web_search_calls"],
        },
        "tasks": {
            "total": summary["tasks_total"],
            "completed": summary["tasks_completed"],
            "failed": summary["tasks_failed"],
            "not_attempted": summary["tasks_not_attempted"],
            "failed_task_ids": [row["task_id"] for row in summary["failed_tasks"]],
        },
        "repos": {
            "proposed": repos["proposed"],
            "exists": repos["exists"],
            "exists_public": repos["exists_public"],
            "exists_private": repos["exists_private"],
            "redirected": repos["redirected"],
            "hallucinated_404": repos["hallucinated"],
            "unresolved": repos["unresolved"],
            "hallucination_rate_of_proposed": (
                round(summary["hallucination_rate"], 4) if summary["hallucination_rate"] is not None else None
            ),
            "candidates_public_distinct": summary["existing_repos"],
        },
        "started_at": summary["started_at"],
        "finished_at": summary["finished_at"],
        "invocations": summary["invocations"],
        "elapsed_note": "per-task elapsed_ms is in latency_cost.jsonl",
        "errors": summary["stop_code"],
        "visible_cost": "未知",
        "usage_tokens": summary["usage"],
        "human_judgment": "未运行",
        "status": summary["status"],
        "stopped_before_task_id": summary["stopped_before_task_id"],
        "remaining_task_ids": summary["remaining_task_ids"],
        "decision": DECISION,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "checkpoint.json").write_text(
        json.dumps(
            {
                **{k: state[k] for k in (
                    "run_id",
                    "batch",
                    "model",
                    "base_url",
                    "materials_commit",
                    "prompt_sha256",
                    "started_at",
                ) if k in state},
                "stopped_before_task_id": state.get("stopped_before_task_id"),
                "stop_code": state.get("stop_code"),
                "remaining_task_ids": summary["remaining_task_ids"],
                "failed_task_ids": [row["task_id"] for row in summary["failed_tasks"]],
                "quota_waits": state.get("quota_waits") or [],
                "sent_but_incomplete": state.get("sent_but_incomplete") or [],
                "invocations": state.get("invocations") or [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(render_report(summary), encoding="utf-8")
    judgments = out_dir / "judgments.jsonl"
    if not judgments.exists():
        judgments.write_text("", encoding="utf-8")
    for name in (
        "candidates.jsonl",
        "failures.jsonl",
        "verifications.jsonl",
        "latency_cost.jsonl",
        "model_calls.jsonl",
    ):
        path = out_dir / name
        if not path.exists():
            path.write_text("", encoding="utf-8")
    return summary


def run_d_group(
    *,
    out_dir: Path,
    tasks: list[dict],
    run_id: str,
    base_url: str,
    model: str,
    api_key: str,
    github_token: str,
    prompt_template: str,
    http_post: HttpPost,
    github_get: HttpGet,
    sleep: SleepFn = time.sleep,
    github_sleep_seconds: float = 0.8,
    model_timeout: float = 300.0,
    github_timeout: float = 30.0,
    materials: str = "unknown",
    seeds: set[str] | None = None,
    historical_a: list[dict] | None = None,
    wait_for_quota: bool = False,
    quota_wait_seconds: float = QUOTA_WAIT_SECONDS,
    max_quota_waits: int = 1,
    model_attempts: int = 3,
    retry_backoff_seconds: float = 30.0,
    reverify_only: bool = False,
) -> dict:
    """Run or resume arm D.

    Resume rules: a task is skipped only when ``is_completed``. A task whose
    latest model call failed (timeout, network, HTTP error, no parseable list)
    is asked again, up to ``model_attempts`` requests per invocation. For
    completed tasks, names whose latest verification is not final (unfollowed
    redirect, GitHub rate limit or error) are re-checked without calling the
    model again. ``reverify_only`` skips every model call.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "checkpoint.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {
            "run_id": run_id,
            "batch": "eval.batch_1",
            "model": model,
            "base_url": base_url,
            "materials_commit": materials,
            "prompt_sha256": sha256_text(prompt_template),
            "started_at": utcnow(),
            "quota_waits": [],
        }
    state["historical_a_path"] = str(HISTORICAL_A)
    state.setdefault("invocations", []).append(
        {
            "started_at": utcnow(),
            "runner_materials_commit": materials,
            "model_timeout_s": model_timeout,
            "model_attempts": model_attempts,
            "reverify_only": reverify_only,
        }
    )
    seeds = seeds if seeds is not None else load_seed_canonicals()
    call_rows = read_jsonl(out_dir / "model_calls.jsonl")
    calls = latest_calls(call_rows)
    event_counts: dict[str, int] = {}
    for row in model_call_events(call_rows):
        event_counts[str(row["task_id"])] = event_counts.get(str(row["task_id"]), 0) + 1
    quota_waits = list(state.get("quota_waits") or [])
    waits_this_run = 0

    def persist(stop_code: str | None = None, stopped_before: str | None = None) -> dict:
        state["stop_code"] = stop_code
        state["stopped_before_task_id"] = stopped_before
        state["quota_waits"] = quota_waits
        if historical_a is not None:
            hist_path = out_dir / "_historical_a.jsonl"
            with hist_path.open("w", encoding="utf-8") as fh:
                for row in historical_a:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            state["historical_a_path"] = str(hist_path)
        return write_outputs(out_dir, state, tasks)

    def build_record(task: dict, prompt: str, result: dict) -> dict:
        raw = result["answer"] or ""
        answer = strip_think(raw)
        parsed = parse_assistant_repos(answer)
        seq = event_counts.get(task["id"], 0) + 1
        event_counts[task["id"]] = seq
        code = result["code"]
        if code == "ok" and not parsed["repos"]:
            code = "no_parseable_list"
        record = {
            "run_id": run_id,
            "task_id": task["id"],
            "call_id": f"{task['id']}#{seq}",
            "direction": task["direction"],
            "arm": "D",
            "code": code,
            "http_status": result["http_status"],
            "business_code": result["business_code"],
            "model_requests": result["model_requests"],
            "elapsed_ms": result["elapsed_ms"],
            "attempts": result["attempts"],
            "searches": result["searches"],
            "usage": result["usage"],
            "response_status": result["response_status"],
            "parsed_repos": parsed["repos"],
            "ignored_over_cap": parsed["ignored_over_cap"],
            "answer_text": redact(answer),
            "raw_output_sha256": sha256_text(raw),
            "raw_output_chars": len(raw),
            "think_present": "<think" in raw.lower(),
            "input_sha256": sha256_text(prompt),
            "terminal": False,
            "retryable": code != "ok",
            "recorded_at": utcnow(),
        }
        if len(raw) <= 16000:
            record["raw_output"] = redact(raw)
        return record

    def log_model_failure(task: dict, record: dict, message: str) -> None:
        append_jsonl(out_dir / "model_calls.jsonl", record)
        calls[task["id"]] = record
        append_jsonl(
            out_dir / "failures.jsonl",
            {
                "run_id": run_id,
                "task_id": task["id"],
                "arm": "D",
                "code": record["code"],
                "message": message,
            },
        )
        append_jsonl(
            out_dir / "latency_cost.jsonl",
            {
                "run_id": run_id,
                "task_id": task["id"],
                "arm": "D",
                "elapsed_ms": int(record["elapsed_ms"] or 0),
                "github_requests": 0,
                "model_requests": int(record["model_requests"] or 0),
                "visible_cost": "未知",
            },
        )

    def verify_task(task: dict, existing: dict, *, reverify: bool) -> dict | None:
        repos = list(existing.get("parsed_repos") or [])
        current = latest_verifications(read_jsonl(out_dir / "verifications.jsonl"))
        pending = [
            (index, name)
            for index, name in enumerate(repos, start=1)
            if (current.get((task["id"], canonical(name))) or {}).get("code") not in FINAL_VERIFY_CODES
        ]
        if reverify and not pending:
            return None
        have = {
            canonical(str(row.get("repo")))
            for row in read_jsonl(out_dir / "candidates.jsonl")
            if row.get("task_id") == task["id"]
        }
        github_requests = 0
        verify_started = time.monotonic()
        stopped = False
        for index, name in pending:
            if github_sleep_seconds:
                sleep(github_sleep_seconds)
            checked = verify_repo(
                name,
                github_get,
                github_token,
                github_timeout,
                sleep=sleep,
                sleep_seconds=github_sleep_seconds,
            )
            github_requests += int(checked.get("github_requests") or 1)
            redirect = checked.get("redirect")
            row = {
                "run_id": run_id,
                "task_id": task["id"],
                "arm": "D",
                "model_repo": name,
                "rank": index,
                "http_status": checked.get("http_status"),
                "code": checked["code"],
                "exists": bool(checked.get("exists")),
                "canonical_repo": checked.get("canonical_repo"),
                "stars": checked.get("stars"),
                "private": checked.get("private"),
                "redirect": redirect,
                "reverify": reverify,
                "fetched_at": utcnow(),
            }
            if isinstance(redirect, dict) and checked.get("exists"):
                row["note"] = (
                    f"GitHub {redirect.get('first_http_status')} 跳转：{name} 现为 {checked.get('canonical_repo')}"
                    "（改名或转移），按存在计。"
                )
            append_jsonl(out_dir / "verifications.jsonl", row)
            if checked["code"] == "exists" and not checked.get("private"):
                key = canonical(checked["canonical_repo"])
                if key not in have:
                    have.add(key)
                    append_jsonl(
                        out_dir / "candidates.jsonl",
                        candidate_from_verification(
                            run_id=run_id,
                            task=task,
                            rank=index,
                            verified=checked,
                            fetched_at=row["fetched_at"],
                            seeds=seeds,
                        ),
                    )
            elif checked["code"] == "exists" and checked.get("private"):
                append_jsonl(
                    out_dir / "failures.jsonl",
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": "D",
                        "code": "private_skipped",
                        "message": "GitHub 返回私有仓库，不写入公开候选。",
                    },
                )
            elif checked["code"] == "github_not_found":
                append_jsonl(
                    out_dir / "failures.jsonl",
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": "D",
                        "code": "github_not_found",
                        "message": f"幻觉：{name} 不存在",
                    },
                )
            elif checked["code"] == "rate_limited":
                append_jsonl(
                    out_dir / "failures.jsonl",
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": "D",
                        "code": "rate_limited",
                        "message": f"GitHub 限流，停在 {name}，该名及之后未核对完。",
                    },
                )
                stopped = True
                break
            else:
                append_jsonl(
                    out_dir / "failures.jsonl",
                    {
                        "run_id": run_id,
                        "task_id": task["id"],
                        "arm": "D",
                        "code": checked["code"],
                        "message": f"核对 {name} 未决，http {checked.get('http_status')}，续跑时重核。",
                    },
                )
        verify_ms = int((time.monotonic() - verify_started) * 1000)
        model_ms = 0 if reverify else int(existing.get("elapsed_ms") or 0)
        append_jsonl(
            out_dir / "latency_cost.jsonl",
            {
                "run_id": run_id,
                "task_id": task["id"],
                "arm": "D",
                "elapsed_ms": model_ms + verify_ms,
                "github_requests": github_requests,
                "model_requests": 0 if reverify else int(existing.get("model_requests") or 0),
                "visible_cost": "未知",
            },
        )
        if stopped:
            summary = persist("rate_limited", task["id"])
            return {"code": "rate_limited", "stopped_before_task_id": task["id"], "status": summary["status"]}
        if not reverify:
            marker = {
                **existing,
                "terminal": True,
                "verification_complete": True,
                "verification_elapsed_ms": verify_ms,
            }
            append_jsonl(out_dir / "model_calls.jsonl", marker)
            calls[task["id"]] = marker
        persist(None, None)
        return None

    for task in tasks:
        latest = calls.get(task["id"])
        if is_completed(latest):
            stop = verify_task(task, latest, reverify=True)
            if stop:
                return stop
            continue
        if reverify_only:
            continue
        existing = latest if latest and latest.get("code") == "ok" and latest.get("parsed_repos") else None
        if existing is None:
            prompt = render_prompt(prompt_template, task["query"])
            used = 0
            while used < model_attempts:
                result = call_model(
                    base_url=base_url,
                    model=model,
                    api_key=api_key,
                    prompt=prompt,
                    http_post=http_post,
                    timeout=model_timeout,
                )
                used += 1
                record = build_record(task, prompt, result)
                code = record["code"]
                if code in QUOTA_MODEL_CODES:
                    append_jsonl(out_dir / "model_calls.jsonl", record)
                    calls[task["id"]] = record
                    state.setdefault("sent_but_incomplete", []).append(
                        {
                            "task_id": task["id"],
                            "code": code,
                            "model_requests": result["model_requests"],
                            "recorded_at": record["recorded_at"],
                        }
                    )
                    if wait_for_quota and waits_this_run < max_quota_waits:
                        hinted = _retry_after_seconds(result.get("retry_after"))
                        delay = hinted if hinted and 0 < hinted <= quota_wait_seconds else quota_wait_seconds
                        quota_waits.append(
                            {
                                "task_id": task["id"],
                                "code": code,
                                "wait_seconds": delay,
                                "started_at": utcnow(),
                            }
                        )
                        waits_this_run += 1
                        persist(code, task["id"])
                        sleep(delay)
                        used -= 1  # a quota wait does not use up a retry
                        continue
                    persist(code, task["id"])
                    return {"code": code, "stopped_before_task_id": task["id"], "status": "incomplete"}
                if code in FATAL_MODEL_CODES:
                    log_model_failure(task, record, "模型请求失败，未核对仓库。整批停在此题，修好后续跑。")
                    summary = persist(code, task["id"])
                    return {"code": code, "stopped_before_task_id": task["id"], "status": summary["status"]}
                if code == "ok":
                    append_jsonl(out_dir / "model_calls.jsonl", record)
                    calls[task["id"]] = record
                    existing = record
                    break
                if code == "no_parseable_list":
                    message = "模型回答里没有可解析的仓库名单，不算完成，可续跑重试。"
                elif code in {"timeout", "network_error"}:
                    message = f"模型请求{'超时' if code == 'timeout' else '网络失败'}（{model_timeout:g}s），未核对仓库，可续跑重试。"
                else:
                    message = f"模型没有返回可解析的名单（http {record.get('http_status')}），可续跑重试。"
                log_model_failure(task, record, message + f" 本次第 {used}/{model_attempts} 次。")
                if used < model_attempts and retry_backoff_seconds:
                    sleep(retry_backoff_seconds * used)
            if existing is None:
                persist(None, None)
                continue
        stop = verify_task(task, existing, reverify=False)
        if stop:
            return stop

    summary = persist(None, None)
    code = "ok" if summary["status"] == "complete" else "tasks_incomplete"
    return {
        "code": code,
        "status": summary["status"],
        "stopped_before_task_id": None,
        "failed_task_ids": [row["task_id"] for row in summary["failed_tasks"]],
    }


def credentials_from_env() -> dict:
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("MINIMAX_API_KEY") or "").strip()
    base = (os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE).rstrip("/")
    model = (os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL).strip()
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    return {"api_key": key, "base_url": base, "model": model, "github_token": token}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run E1 arm D against MiniMax web_search")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--batch", default="eval.batch_1")
    parser.add_argument("--out", default="")
    parser.add_argument("--run-id", default="2026-10-04-d-minimax")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--wait-for-quota", action="store_true")
    parser.add_argument("--max-quota-waits", type=int, default=3,
                        help="quota waits allowed in this invocation (each ~5h)")
    parser.add_argument("--model-timeout", type=float, default=300.0,
                        help="client timeout per model request, seconds")
    parser.add_argument("--model-attempts", type=int, default=3,
                        help="model requests per unfinished task in this invocation")
    parser.add_argument("--retry-backoff", type=float, default=30.0,
                        help="seconds before retry n is multiplied by n")
    parser.add_argument("--reverify-only", action="store_true",
                        help="no model calls; only re-check unresolved GitHub names")
    args = parser.parse_args(argv)
    if args.batch != "eval.batch_1":
        print(json.dumps({
            "code": "refused",
            "status": "未运行",
            "message": "D 组正式运行只覆盖 eval.batch_1。",
        }, ensure_ascii=False))
        return 2
    if not args.live:
        print(json.dumps({
            "code": "owner_blocked",
            "status": "未运行",
            "message": "未加 --live，零请求。fixture 不能冒充 D 组。",
        }, ensure_ascii=False))
        return 2
    creds = credentials_from_env()
    if not creds["api_key"]:
        print(json.dumps({
            "code": "missing_credentials",
            "status": "未运行",
            "message": "未运行 / owner-blocked：没有 OPENAI_API_KEY 或 MINIMAX_API_KEY。",
        }, ensure_ascii=False))
        return 2
    if creds["model"] != DEFAULT_MODEL:
        print(json.dumps({
            "code": "invalid_model",
            "status": "未运行",
            "message": f"本批冻结模型是 {DEFAULT_MODEL}。",
        }, ensure_ascii=False))
        return 2
    if not args.out:
        print(json.dumps({"code": "refused", "status": "未运行", "message": "需要 --out"}, ensure_ascii=False))
        return 2
    out_dir = Path(args.out)
    if "runs" in out_dir.parts and not args.live:
        return 2
    tasks = load_queries(E1 / "queries.yaml")["eval.batch_1"]
    template = PROMPT_PATH.read_text(encoding="utf-8")
    root = E1.parents[1]
    result = run_d_group(
        out_dir=out_dir,
        tasks=tasks,
        run_id=args.run_id,
        base_url=creds["base_url"],
        model=creds["model"],
        api_key=creds["api_key"],
        github_token=creds["github_token"],
        prompt_template=template,
        http_post=default_model_post,
        github_get=default_github_get,
        materials=materials_commit(root),
        wait_for_quota=args.wait_for_quota,
        max_quota_waits=max(args.max_quota_waits, 0),
        model_timeout=args.model_timeout,
        model_attempts=max(args.model_attempts, 1),
        retry_backoff_seconds=max(args.retry_backoff, 0.0),
        reverify_only=args.reverify_only,
    )
    public = {
        "code": result["code"],
        "status": result["status"],
        "stopped_before_task_id": result.get("stopped_before_task_id"),
        "failed_task_ids": result.get("failed_task_ids") or [],
        "out": str(out_dir),
    }
    print(json.dumps(public, ensure_ascii=False))
    if result["code"] == "ok" and result["status"] == "complete":
        return 0
    if result["code"] in {"quota_limited", "rate_limited"}:
        return 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
