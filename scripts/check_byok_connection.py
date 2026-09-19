#!/usr/bin/env python3
"""Minimal BYOK connection probe.

Reads OPENAI_BASE_URL / OPENAI_MODEL / OPENAI_API_KEY from the environment.
Never prints the key. Without a key, exits 2 with missing_credentials and
「未运行 / owner-blocked」.

A live request is sent only when --live is passed AND a key is present.
Default is a dry configuration check.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

SECRET_RES = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
)


def redact(text: str) -> str:
    out = text
    key = os.environ.get("OPENAI_API_KEY") or ""
    if key:
        out = out.replace(key, "[redacted]")
    for pat in SECRET_RES:
        out = pat.sub("[redacted]", out)
    return out


def classify_config(base: str, model: str, key: str) -> str | None:
    if not key.strip():
        return "missing_credentials"
    if not base.startswith(("http://", "https://")):
        return "invalid_endpoint"
    if not model.strip():
        return "invalid_model"
    return None


def classify_http(status: int, body: str) -> str:
    if status in (401, 403):
        return "auth_rejected"
    if status == 429:
        return "rate_limited"
    if status == 404:
        return "model_unavailable"
    if status >= 500:
        return "bad_response"
    if status != 200:
        return "bad_response"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return "bad_response"
    if not isinstance(data, dict):
        return "bad_response"
    if "choices" not in data and "error" in data:
        return "bad_response"
    if "choices" not in data:
        return "bad_response"
    return "ok"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="BYOK config / optional live probe")
    p.add_argument(
        "--live",
        action="store_true",
        help="Send one tiny chat request. Default is config-only.",
    )
    args = p.parse_args(argv)

    base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    model = os.environ.get("OPENAI_MODEL") or ""
    key = os.environ.get("OPENAI_API_KEY") or ""
    timeout = float(os.environ.get("BYOK_TIMEOUT_SECONDS") or "20")
    max_out = int(os.environ.get("BYOK_MAX_OUTPUT_CHARS") or "64")

    cfg_err = classify_config(base, model, key)
    record = {
        "mode": "live" if args.live else "config-only",
        "base_url_host": urllib.request.urlparse(base).netloc if base else "",
        "model": model or None,
        "has_key": bool(key.strip()),
        "code": cfg_err or "ok",
        "status": "未运行",
    }

    if cfg_err:
        record["status"] = "owner-blocked" if cfg_err == "missing_credentials" else "invalid"
        record["message"] = (
            "未运行 / owner-blocked：本地没有 OPENAI_API_KEY。"
            if cfg_err == "missing_credentials"
            else f"configuration error: {cfg_err}"
        )
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 2

    if not args.live:
        record["status"] = "config-ok-not-called"
        record["message"] = "配置齐全，但未加 --live，零请求。"
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    url = base + "/chat/completions"
    payload = {
        "model": model,
        "max_tokens": 16,
        "messages": [
            {
                "role": "user",
                "content": "Reply with the single word pong.",
            }
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": "gold-miner-byok-check/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")[:4000]
            code = classify_http(resp.status, raw)
            record["http_status"] = resp.status
            record["code"] = code
            record["status"] = "ok" if code == "ok" else code
            record["output_chars"] = min(len(raw), max_out)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:4000]
        record["http_status"] = exc.code
        record["code"] = classify_http(exc.code, raw)
        record["status"] = record["code"]
    except TimeoutError:
        record["code"] = "timeout"
        record["status"] = "timeout"
        record["message"] = "已发送请求可能已计费；未收到完整响应。"
    except Exception as exc:  # noqa: BLE001 — probe must not crash silently
        record["code"] = "network_error"
        record["status"] = "network_error"
        record["message"] = redact(type(exc).__name__)

    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record.get("code") == "ok" else 3


if __name__ == "__main__":
    sys.exit(main())
