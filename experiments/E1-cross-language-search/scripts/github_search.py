"""GitHub repository search client for E1 cross-language search (1a script stage).

Basis:
- docs/engineering/prerequisites.md Section 1 (text-match header, 2s serial interval)
- experiments/E1-cross-language-search/protocol.md Section 7 candidates fields
  (repo, stars, matched_fields come from parsing here)

Design for testability:
- HTTP is injectable: pass ``http_get(url, headers)`` explicitly.
- By default ``http_get=None`` and :func:`search_repos` raises without touching
  the network. Tests must inject a fake; they must NOT pass the real urllib
  helper and must NOT hit api.github.com.
- Token comes from the explicit ``token`` argument or ``GITHUB_TOKEN`` env var.
  No token is hardcoded here.
- ``full_name`` is stored exactly as the API returned it. :func:`canonical`
  lowercases ``owner/repo`` only for dedup/merge keys.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

SEARCH_URL = "https://api.github.com/search/repositories"
ACCEPT_TEXT_MATCH = "application/vnd.github.text-match+json"
DEFAULT_SLEEP_SECONDS = 2
USER_AGENT = "E1-cross-language-search/1a"


def canonical(full_name: str) -> str:
    """Return dedup key for ``owner/repo`` in lowercase.

    The API value itself is preserved elsewhere; this is only the merge key.
    """
    if not isinstance(full_name, str):
        raise TypeError("full_name must be str")
    cleaned = full_name.strip()
    parts = cleaned.split("/")
    if len(parts) == 2:
        owner, repo = parts
        return f"{owner.strip().lower()}/{repo.strip().lower()}"
    return cleaned.lower()


def _map_property(prop: Any) -> str:
    if not isinstance(prop, str):
        return "unknown"
    lowered = prop.strip().lower()
    if lowered == "name":
        return "name"
    if lowered == "description":
        return "description"
    if "readme" in lowered:
        return "readme"
    return "unknown"


def extract_matched_fields(item: dict) -> list[str]:
    """Map ``item['text_matches'][*]['property']`` to name/description/readme/unknown.

    Missing or empty ``text_matches`` yields ``["unknown"]`` per protocol 7.
    Result is de-duplicated, first-seen order preserved.
    """
    text_matches = item.get("text_matches") if isinstance(item, dict) else None
    if not text_matches:
        return ["unknown"]
    if not isinstance(text_matches, list):
        return ["unknown"]
    seen: list[str] = []
    for entry in text_matches:
        prop = entry.get("property") if isinstance(entry, dict) else None
        field = _map_property(prop)
        if field not in seen:
            seen.append(field)
    return seen if seen else ["unknown"]


def parse_repo_item(item: dict) -> dict:
    """Parse one Search API ``items[]`` entry into a stable dict.

    Keeps ``full_name`` exactly as returned; adds ``canonical`` for dedup,
    ``matched_fields`` for protocol 7, plus ``stars`` alias for convenience.
    """
    if not isinstance(item, dict):
        raise TypeError("item must be dict")
    full_name = item.get("full_name", "")
    if not isinstance(full_name, str):
        full_name = str(full_name)
    stargazers = item.get("stargazers_count", 0)
    if not isinstance(stargazers, int):
        try:
            stargazers = int(stargazers)
        except (TypeError, ValueError):
            stargazers = 0
    description = item.get("description")
    topics = item.get("topics", [])
    if not isinstance(topics, list):
        topics = []
    else:
        topics = list(topics)
    text_matches = item.get("text_matches", [])
    if text_matches is None:
        text_matches = []
    if not isinstance(text_matches, list):
        text_matches = []
    return {
        "full_name": full_name,
        "repo": full_name,
        "canonical": canonical(full_name) if full_name else "",
        "stargazers_count": stargazers,
        "stars": stargazers,
        "description": description,
        "topics": topics,
        "text_matches": text_matches,
        "matched_fields": extract_matched_fields(item),
    }


def dedup_repos(repos: list[dict]) -> list[dict]:
    """De-duplicate parsed repos by :func:`canonical`, keep first, keep order."""
    seen: set[str] = set()
    out: list[dict] = []
    for repo in repos:
        key = repo.get("canonical") if isinstance(repo, dict) else None
        if not key:
            raw = ""
            if isinstance(repo, dict):
                raw = repo.get("full_name") or repo.get("repo") or ""
            try:
                key = canonical(raw) if raw else ""
            except TypeError:
                key = ""
        if key not in seen:
            seen.add(key)
            out.append(repo)
    return out


def _resolve_token(token: str | None) -> str | None:
    if token is not None:
        cleaned = token.strip() if isinstance(token, str) else token
        return cleaned or None
    env_token = os.environ.get("GITHUB_TOKEN", "")
    env_token = env_token.strip() if isinstance(env_token, str) else ""
    return env_token or None


def _build_headers(token: str | None) -> dict:
    headers = {
        "Accept": ACCEPT_TEXT_MATCH,
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _build_url(
    query: str, *, per_page: int = 30, page: int = 1, sort: str | None = None
) -> str:
    params: dict[str, Any] = {
        "q": query,
        "per_page": per_page,
        "page": page,
    }
    if sort is not None:
        params["sort"] = sort
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def _urllib_get(url: str, headers: dict) -> dict:
    """Real network helper (opt-in only). Tests must NOT use this."""
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        body = response.read()
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("unexpected search response shape")
    return data


def _coerce_json(payload: Any) -> dict:
    if isinstance(payload, dict):
        return payload
    json_fn = getattr(payload, "json", None)
    if callable(json_fn):
        data = json_fn()
        if isinstance(data, dict):
            return data
        raise ValueError("unexpected search response shape")
    if isinstance(payload, (bytes, str)):
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    raise TypeError("http_get must return dict or response with .json()")


def search_repos(
    query: str,
    *,
    per_page: int = 30,
    page: int = 1,
    sort: str | None = None,
    token: str | None = None,
    http_get: Callable[[str, dict], Any] | None = None,
    sleep_func: Callable[[float], None] | None = None,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
) -> list[dict]:
    """Search repositories once and return parsed, de-duplicated repos.

    Args:
        query: GitHub search query string (<=256 chars, non-empty).
        per_page: 1..100, default 30.
        page: >=1, default 1.
        sort: optional Search API sort (e.g. "stars", "updated").
        token: explicit PAT; falls back to ``GITHUB_TOKEN`` env var.
        http_get: ``callable(url, headers) -> dict``. Required; default None
            raises instead of doing network I/O so tests never hit real API.
        sleep_func: ``callable(seconds)``; defaults to ``time.sleep``.
            Tests inject a no-op.
        sleep_seconds: wait after the call to space serial requests; default 2.

    Returns:
        List of :func:`parse_repo_item` dicts, de-duplicated by canonical name.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if len(query) > 256:
        raise ValueError("query must be <= 256 characters")
    if not isinstance(per_page, int) or not 1 <= per_page <= 100:
        raise ValueError("per_page must be int in 1..100")
    if not isinstance(page, int) or page < 1:
        raise ValueError("page must be int >= 1")
    if sort is not None and (not isinstance(sort, str) or not sort.strip()):
        raise ValueError("sort must be a non-empty string or None")

    if http_get is None:
        raise RuntimeError(
            "no http_get injected: refusing real network by default; "
            "pass http_get explicitly (tests use a fake)"
        )

    resolved_token = _resolve_token(token)
    headers = _build_headers(resolved_token)
    url = _build_url(query, per_page=per_page, page=page, sort=sort)

    raw = http_get(url, headers)
    data = _coerce_json(raw)
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("unexpected search response: items is not a list")

    parsed = [parse_repo_item(item) for item in items]
    result = dedup_repos(parsed)

    if sleep_seconds and sleep_seconds > 0:
        sleeper = sleep_func if sleep_func is not None else time.sleep
        sleeper(sleep_seconds)

    return result
