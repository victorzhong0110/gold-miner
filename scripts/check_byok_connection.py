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

# Hosts that reject a key issued for the other region with a bare 401 or the
# business code 1004, without saying which region is expected.
REGION_HOSTS = {
    "api.minimax.io": "international",
    "api.minimaxi.com": "mainland",
    "api.minimax.chat": "international",
    "api.minimax.cn": "mainland (not in official docs)",
}

# Business codes some OpenAI-compatible gateways return with HTTP 200.
BUSINESS_CODES = {
    "1004": "wrong_region",
    "1008": "insufficient_balance",
    "1010": "invalid_api_key",
}

# Reasoning models spend the whole budget thinking; too small a value returns
# finish_reason="length" with no usable content. Kept equal to
# extension/src/shared.js MODEL_MAX_TOKENS.
DEFAULT_MAX_TOKENS = 2048


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


def host_region(base: str) -> str | None:
    host = urllib.request.urlparse(base).netloc.split(":")[0]
    return REGION_HOSTS.get(host)


def business_code(body: str) -> str | None:
    """Return a mapped business code from a 200-with-error style body."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    candidates = []
    base_resp = data.get("base_resp")
    if isinstance(base_resp, dict):
        candidates.append(base_resp.get("status_code"))
    candidates.append(data.get("code"))
    for raw in candidates:
        if raw is None:
            continue
        text = str(raw)
        if text in BUSINESS_CODES:
            return BUSINESS_CODES[text]
    return None


def classify_http(status: int, body: str, base: str = "") -> str:
    region = host_region(base) if base else None
    code = business_code(body)
    if code == "wrong_region":
        return "wrong_region"
    if code:
        return code
    if status in (401, 403):
        # S3: on a region-specific host a bare 401 is far more often a key/host
        # region mismatch than a dead key, and the raw error never says so.
        if region:
            return "wrong_region"
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
    if "choices" not in data:
        return "bad_response"
    choice = data.get("choices") or [None]
    choice = choice[0] if isinstance(choice, list) and choice else None
    if not isinstance(choice, dict):
        return "bad_response"
    finish = choice.get("finish_reason") or choice.get("finishReason") or ""
    # S6: HTTP 200 with a truncated body is a failure, not a success.
    if str(finish).lower() == "length":
        return "output_truncated"
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else choice.get("text")
    if not isinstance(content, str) or not strip_reasoning(content):
        return "empty_output"
    return "ok"


def strip_reasoning(content: str) -> str:
    """Drop inline <think> reasoning blocks before checking for real output."""
    out = re.sub(r"<think>.*?</think>", "", content, flags=re.S | re.I)
    open_at = re.search(r"<think>", out, flags=re.I)
    if open_at:
        out = out[: open_at.start()]
    return re.sub(r"</?think>", "", out, flags=re.I).strip()



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
        "host_region": host_region(base) if base else None,
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
    try:
        max_tokens = int(os.environ.get("BYOK_MAX_TOKENS") or DEFAULT_MAX_TOKENS)
    except ValueError:
        max_tokens = DEFAULT_MAX_TOKENS
    payload = {
        "model": model,
        "max_tokens": max_tokens,
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
            code = classify_http(resp.status, raw, base)
            record["http_status"] = resp.status
            record["code"] = code
            record["status"] = "ok" if code == "ok" else code
            record["output_chars"] = min(len(raw), max_out)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:4000]
        record["http_status"] = exc.code
        record["code"] = classify_http(exc.code, raw, base)
        record["status"] = record["code"]
    except TimeoutError:
        record["code"] = "timeout"
        record["status"] = "timeout"
        record["message"] = "已发送请求可能已计费；未收到完整响应。"
    except Exception as exc:  # noqa: BLE001 — probe must not crash silently
        record["code"] = "network_error"
        record["status"] = "network_error"
        record["message"] = redact(type(exc).__name__)

    if record.get("code") == "wrong_region":
        record["message"] = (
            "区域不匹配：该主机与 key 所属区域不同。换用同区域主机"
            f"（{record['host_region'] or 'unknown'}），不要先重填 key。"
        )
    elif record.get("code") == "output_truncated":
        record["message"] = (
            "输出被 max_tokens 截断，模型没写完。调大 BYOK_MAX_TOKENS 后重试；"
            "这不是凭据问题。"
        )

    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record.get("code") == "ok" else 3


if __name__ == "__main__":
    sys.exit(main())
