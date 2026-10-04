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


def final_text(content):
    if not isinstance(content, str):
        return ""
    content = re.sub(r"<think\b[^>]*>[\s\S]*?</think\s*>", "", content, flags=re.I)
    return re.sub(r"<think\b[^>]*>[\s\S]*$", "", content, flags=re.I).strip()


def auth_hint(base):
    if urllib.request.urlparse(base).hostname in {"api.minimax.io", "api.minimaxi.com", "api.minimax.cn"}:
        return "检查密钥有效性及注册平台区域：国际 api.minimax.io；大陆按控制台端点。401不能单独证明区域错配。"
    return ""


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
    base_resp = data.get("base_resp")
    base_resp = base_resp if isinstance(base_resp, dict) else {}
    if base_resp.get("status_code") == 1004:
        return "auth_rejected"
    if data.get("error") or base_resp.get("status_code", 0):
        return "bad_response"
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return "bad_response"
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        return "model_output_truncated"
    message = choice.get("message")
    answer = final_text(message.get("content") if isinstance(message, dict) else None)
    if not answer:
        return "empty_model_output"
    if not re.fullmatch(r"pong[.!]?", answer, re.I):
        return "unexpected_model_output"
    return "ok"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="BYOK config / optional live probe")
    p.add_argument(
        "--live",
        action="store_true",
        help="Send one bounded chat request (up to 2048 completion tokens, including thinking). Default is config-only.",
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
        "max_tokens": 2048,
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
            raw = resp.read(256 * 1024 + 1).decode("utf-8", errors="replace")
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

    if record.get("code") == "auth_rejected" and auth_hint(base):
        record["hint"] = auth_hint(base)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record.get("code") == "ok" else 3


if __name__ == "__main__":
    sys.exit(main())
