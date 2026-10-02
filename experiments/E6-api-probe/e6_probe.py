"""E6 个人模型最小请求记录。

没有 OPENAI_BASE_URL、OPENAI_MODEL、OPENAI_API_KEY 时不发起请求，
用量、延迟和模型输出记为未运行或未知。密钥不写入记录。
"""

from __future__ import annotations

import datetime
import json
import urllib.parse
from typing import Any, Callable

PUBLIC_PROMPT = "Reply with the single word pong."
STATUS_ENUM = ("未运行", "已运行", "取消", "失败")
ERROR_ENUM = ("无", "未配置", "预算", "取消", "地址", "协议", "权限或凭据", "额度", "限流", "网络", "响应格式")
ENV_KEYS = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")

HttpPost = Callable[[str, dict, dict, float], tuple[int, bytes]]


def utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def public_base_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    host = parts.hostname or ""
    if parts.port:
        host = "%s:%s" % (host, parts.port)
    return urllib.parse.urlunsplit((parts.scheme, host, parts.path.rstrip("/"), "", ""))


def probe(
    *,
    http_post: HttpPost | None = None,
    env: dict | None = None,
    should_cancel: Callable[[], bool] | None = None,
    request_budget: int = 1,
    max_output_tokens: int = 16,
    timeout: float = 30,
    run_id: str = "2026-09-22-w6-e6",
) -> dict:
    """做至多一次最小聊天补全，或在不能发送时写未运行记录。"""
    import os

    if request_budget not in (0, 1):
        raise ValueError("本探测 request_budget 只能是 0 或 1")
    if max_output_tokens < 1 or max_output_tokens > 32:
        raise ValueError("max_output_tokens 必须在 1 到 32")
    source = os.environ if env is None else env
    key = source.get("OPENAI_API_KEY") or ""
    base = source.get("OPENAI_BASE_URL") or ""
    model = source.get("OPENAI_MODEL") or ""
    started = utcnow()
    record = _blank(run_id, started, request_budget, max_output_tokens, source)
    missing = [name for name in ENV_KEYS if not source.get(name)]
    if missing:
        record["status"] = "未运行"
        record["error_class"] = "未配置"
        record["error_detail"] = "缺少 " + ",".join(missing)
        record["finished_at"] = utcnow()
        record["billing_note"] = "未发送请求，本次零费用"
        _ensure_no_secret(record, key)
        return record
    record["model"] = model
    record["base_url"] = public_base_url(base)
    if request_budget == 0:
        record["status"] = "未运行"
        record["error_class"] = "预算"
        record["error_detail"] = "request_budget 为 0"
        record["finished_at"] = utcnow()
        record["billing_note"] = "未发送请求，本次零费用"
        _ensure_no_secret(record, key)
        return record
    if should_cancel and should_cancel():
        record["status"] = "取消"
        record["error_class"] = "取消"
        record["cancelled_before_send"] = True
        record["error_detail"] = "发送前取消"
        record["finished_at"] = utcnow()
        record["billing_note"] = "未发送请求，本次零费用"
        _ensure_no_secret(record, key)
        return record
    if http_post is None:
        raise ValueError("已配置时必须传入 http_post，禁止在本函数内隐式开口")
    url = record["base_url"] + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PUBLIC_PROMPT}],
        "max_tokens": max_output_tokens,
    }
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }
    clock = datetime.datetime.now(datetime.timezone.utc)
    try:
        status, body = http_post(url, headers, payload, timeout)
    except Exception as exc:
        record["sent_requests"] = 1
        record["actual_requests"] = 1
        record["elapsed_ms"] = _elapsed_ms(clock)
        record["status"] = "失败"
        record["error_class"] = "网络"
        record["error_detail"] = type(exc).__name__
        record["finished_at"] = utcnow()
        record["billing_note"] = "已发送请求可能已计费"
        _ensure_no_secret(record, key)
        return record
    record["sent_requests"] = 1
    record["actual_requests"] = 1
    record["elapsed_ms"] = _elapsed_ms(clock)
    record["http_status"] = status
    record["finished_at"] = utcnow()
    record["billing_note"] = "已发送请求可能已计费"
    _fill_from_response(record, status, body, key)
    _ensure_no_secret(record, key)
    return record


def _blank(run_id: str, started: str, request_budget: int, max_output_tokens: int, source: dict) -> dict:
    return {
        "run_id": run_id,
        "started_at": started,
        "finished_at": "",
        "elapsed_ms": "未知",
        "status": "未运行",
        "model": "未知",
        "base_url": "未知",
        "protocol": "openai-chat-completions",
        "request_budget": request_budget,
        "max_output_tokens": max_output_tokens,
        "actual_requests": 0,
        "sent_requests": 0,
        "retries": 0,
        "cancelled_before_send": False,
        "cache_hits": 0,
        "usage_prompt_tokens": "未知",
        "usage_completion_tokens": "未知",
        "usage_total_tokens": "未知",
        "visible_response_id": "未知",
        "response_format": "未知",
        "model_output": "未运行",
        "http_status": None,
        "error_class": "未配置",
        "error_detail": "",
        "billing_note": "",
        "prompt": PUBLIC_PROMPT,
        "env_openai_api_key_set": bool(source.get("OPENAI_API_KEY")),
        "env_openai_base_url_set": bool(source.get("OPENAI_BASE_URL")),
        "env_openai_model_set": bool(source.get("OPENAI_MODEL")),
        "env_github_token_set": bool(source.get("GITHUB_TOKEN")),
    }


def _elapsed_ms(started: datetime.datetime) -> int:
    delta = datetime.datetime.now(datetime.timezone.utc) - started
    return int(delta.total_seconds() * 1000)


def _fill_from_response(record: dict, status: int, body: bytes, key: str) -> None:
    if status in (401, 403):
        record["status"] = "失败"
        record["error_class"] = "权限或凭据"
        record["error_detail"] = "HTTP %s" % status
        return
    if status == 402:
        record["status"] = "失败"
        record["error_class"] = "额度"
        record["error_detail"] = "HTTP 402"
        return
    if status == 404:
        record["status"] = "失败"
        record["error_class"] = "地址"
        record["error_detail"] = "HTTP 404"
        return
    if status in (400, 405, 415):
        record["status"] = "失败"
        record["error_class"] = "协议"
        record["error_detail"] = "HTTP %s" % status
        return
    if status == 429:
        record["status"] = "失败"
        text = _safe_text(body, key)
        if any(word in text.lower() for word in ("insufficient_quota", "quota", "billing", "exceeded your current")):
            record["error_class"] = "额度"
        else:
            record["error_class"] = "限流"
        record["error_detail"] = "HTTP 429"
        return
    if status != 200:
        record["status"] = "失败"
        record["error_class"] = "网络"
        record["error_detail"] = "HTTP %s" % status
        return
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        record["status"] = "失败"
        record["error_class"] = "响应格式"
        record["error_detail"] = "响应不是 JSON"
        return
    if not isinstance(data, dict):
        record["status"] = "失败"
        record["error_class"] = "响应格式"
        record["error_detail"] = "响应不是对象"
        return
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        record["status"] = "失败"
        record["error_class"] = "响应格式"
        record["error_detail"] = "缺少 choices"
        record["visible_response_id"] = data.get("id") or "未知"
        _copy_usage(record, data.get("usage"))
        return
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        record["status"] = "失败"
        record["error_class"] = "响应格式"
        record["error_detail"] = "缺少 message.content"
        record["visible_response_id"] = data.get("id") or "未知"
        _copy_usage(record, data.get("usage"))
        return
    record["status"] = "已运行"
    record["error_class"] = "无"
    record["error_detail"] = ""
    record["response_format"] = "openai.chat.completion"
    record["visible_response_id"] = data.get("id") or "未知"
    record["model_output"] = content.replace(key, "[redacted]") if key else content
    _copy_usage(record, data.get("usage"))


def _copy_usage(record: dict, usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    for src, dest in (
        ("prompt_tokens", "usage_prompt_tokens"),
        ("completion_tokens", "usage_completion_tokens"),
        ("total_tokens", "usage_total_tokens"),
    ):
        value = usage.get(src)
        if isinstance(value, int) and not isinstance(value, bool):
            record[dest] = value


def _safe_text(body: bytes, key: str) -> str:
    text = body.decode("utf-8", errors="replace")
    if key:
        text = text.replace(key, "[redacted]")
    return text[:500]


def _ensure_no_secret(record: dict, key: str) -> None:
    if not key:
        return
    blob = json.dumps(record, ensure_ascii=False)
    if key in blob:
        raise RuntimeError("记录含有密钥，已拒绝写出")


def validate_record(record: dict) -> None:
    if record["status"] not in STATUS_ENUM:
        raise ValueError("status 非法")
    if record["error_class"] not in ERROR_ENUM:
        raise ValueError("error_class 非法")
    if record["retries"] != 0:
        raise ValueError("本探测不自动重试")
    if record["request_budget"] not in (0, 1):
        raise ValueError("预算非法")
    if record["sent_requests"] != record["actual_requests"]:
        raise ValueError("sent_requests 与 actual_requests 不一致")
    if record["status"] == "未运行":
        if record["actual_requests"] != 0 or record["model_output"] != "未运行":
            raise ValueError("未运行却有请求或输出")
        if record["elapsed_ms"] != "未知":
            raise ValueError("未运行的延迟必须是未知")
        for field in ("usage_prompt_tokens", "usage_completion_tokens", "usage_total_tokens"):
            if record[field] != "未知":
                raise ValueError("未运行的用量必须是未知")
    if record["status"] == "取消":
        if record["actual_requests"] != 0 or not record["cancelled_before_send"]:
            raise ValueError("取消记录与发送计数不一致")
        if record["model_output"] != "未运行" or record["elapsed_ms"] != "未知":
            raise ValueError("发送前取消不能写延迟或输出")
    if record["actual_requests"] == 1 and not isinstance(record["elapsed_ms"], int):
        raise ValueError("已发送请求必须有整数等待")
    if record["status"] == "已运行":
        if not isinstance(record["model_output"], str) or record["model_output"] in ("", "未运行"):
            raise ValueError("已运行缺少模型输出")
    if "Bearer " in json.dumps(record, ensure_ascii=False):
        raise ValueError("记录含认证头")


def urllib_post(url: str, headers: dict, payload: dict, timeout: float) -> tuple[int, bytes]:
    import urllib.error
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="E6 配置检查；无配置时不请求")
    parser.add_argument("--out", required=True)
    parser.add_argument("--run-id", default="2026-09-22-w6-e6")
    args = parser.parse_args()
    record = probe(http_post=urllib_post, run_id=args.run_id)
    validate_record(record)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


if __name__ == "__main__":
    main()
