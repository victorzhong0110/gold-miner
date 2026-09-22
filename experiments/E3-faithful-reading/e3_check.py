"""E3 现成翻译检查：解析、对照记录与一致性校验。

本模块默认不访问网络。实时翻译由调用方传入 ``http_get``。
个人模型 API 不在这里调用。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import urllib.parse
from typing import Callable

TOOL_NAME = "google-translate-gtx"
ENDPOINT_HOST = "translate.googleapis.com"
KEPT_ENUM = ("yes", "no", "不适用", "未运行")
SEVERE_ENUM = ("yes", "no", "未运行")
RUN_KEPT = ("yes", "no", "不适用")
CATEGORIES = ("术语", "否定", "限制", "代码", "讨论关系")

HttpGet = Callable[[str, float], tuple[int, bytes]]


def utcnow() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_gtx_body(body: bytes) -> str:
    """把 Google Translate ``client=gtx`` 的 JSON 拼成译文。失败则抛出 ValueError。"""
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("响应不是 UTF-8 JSON") from exc
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("响应缺少译文分段")
    chunks: list[str] = []
    for part in data[0]:
        if not isinstance(part, list) or not part or not isinstance(part[0], str):
            continue
        chunks.append(part[0])
    if not chunks:
        raise ValueError("响应没有译文文本")
    return "".join(chunks)


def translate_url(text: str, source: str, target: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text,
        }
    )
    return "https://%s/translate_a/single?%s" % (ENDPOINT_HOST, query)


def translate_one(
    fragment: dict,
    http_get: HttpGet,
    timeout: float = 30,
) -> dict:
    """翻译一条已冻结片段。不写忠实度判定。"""
    text = fragment["source_text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("source_text 为空")
    url = translate_url(text, fragment["source_lang"], fragment["target_lang"])
    started = datetime.datetime.now(datetime.timezone.utc)
    try:
        status, body = http_get(url, timeout)
    except Exception as exc:
        elapsed = _elapsed_ms(started)
        return _translation_row(
            fragment,
            http_status=None,
            elapsed_ms=elapsed,
            error_class="网络",
            translation_output="未运行",
            error_detail=type(exc).__name__,
        )
    elapsed = _elapsed_ms(started)
    if status != 200:
        return _translation_row(
            fragment,
            http_status=status,
            elapsed_ms=elapsed,
            error_class="网络",
            translation_output="未运行",
            error_detail="HTTP %s" % status,
        )
    try:
        output = parse_gtx_body(body)
    except ValueError as exc:
        return _translation_row(
            fragment,
            http_status=status,
            elapsed_ms=elapsed,
            error_class="响应格式",
            translation_output="未运行",
            error_detail=str(exc),
        )
    return _translation_row(
        fragment,
        http_status=status,
        elapsed_ms=elapsed,
        error_class="无",
        translation_output=output,
        error_detail="",
    )


def _elapsed_ms(started: datetime.datetime) -> int:
    delta = datetime.datetime.now(datetime.timezone.utc) - started
    return int(delta.total_seconds() * 1000)


def _translation_row(
    fragment: dict,
    *,
    http_status: int | None,
    elapsed_ms: int,
    error_class: str,
    translation_output: str,
    error_detail: str,
) -> dict:
    return {
        "frag_id": fragment["frag_id"],
        "source_text": fragment["source_text"],
        "source_sha256": sha256_text(fragment["source_text"]),
        "tool": TOOL_NAME,
        "tool_version": "未知",
        "endpoint_host": ENDPOINT_HOST,
        "client": "gtx",
        "lang_pair": fragment["lang_pair"],
        "http_status": http_status,
        "elapsed_ms": elapsed_ms,
        "error_class": error_class,
        "translation_output": translation_output,
        "error_detail": error_detail,
        "fetched_at": utcnow(),
        "attempted": True,
    }


def load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("%s:%d 不是 JSON" % (path, line_no)) from exc
            if not isinstance(row, dict):
                raise ValueError("%s:%d 不是对象" % (path, line_no))
            rows.append(row)
    return rows


def write_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def join_records(
    fragments: list[dict],
    translations: list[dict],
    judgments: list[dict],
) -> list[dict]:
    by_frag = {row["frag_id"]: row for row in fragments}
    by_tr = {row["frag_id"]: row for row in translations}
    by_j = {row["frag_id"]: row for row in judgments}
    if set(by_frag) != set(by_tr) or set(by_frag) != set(by_j):
        raise ValueError("片段、译文与判定的 frag_id 不一致")
    observations = []
    for frag_id in sorted(by_frag):
        fragment = by_frag[frag_id]
        translation = by_tr[frag_id]
        judgment = by_j[frag_id]
        if translation["source_text"] != fragment["source_text"]:
            raise ValueError("%s 的译文记录原文与冻结片段不一致" % frag_id)
        if translation["source_sha256"] != sha256_text(fragment["source_text"]):
            raise ValueError("%s 的 source_sha256 不一致" % frag_id)
        observation = {}
        observation.update(fragment)
        observation.update(translation)
        observation.update(judgment)
        observation["frag_id"] = frag_id
        validate_observation(observation)
        observations.append(observation)
    return observations


def validate_observation(row: dict) -> None:
    output = row["translation_output"]
    kept_fields = (
        "terminology_kept",
        "polarity_kept",
        "limit_kept",
        "code_intact",
        "discussion_kept",
    )
    for field in kept_fields:
        if row[field] not in KEPT_ENUM:
            raise ValueError("%s %s 非法" % (row["frag_id"], field))
    if row["severe_mistranslation"] not in SEVERE_ENUM:
        raise ValueError("%s severe_mistranslation 非法" % row["frag_id"])
    if row["changes_understanding"] not in SEVERE_ENUM:
        raise ValueError("%s changes_understanding 非法" % row["frag_id"])
    if output == "未运行":
        for field in kept_fields:
            if row[field] != "未运行":
                raise ValueError("%s 无译文时不能写缺口判定" % row["frag_id"])
        if row["severe_mistranslation"] != "未运行" or row["changes_understanding"] != "未运行":
            raise ValueError("%s 无译文时严重误译必须为未运行" % row["frag_id"])
        if row["error_location"] != "未运行":
            raise ValueError("%s 无译文时 error_location 必须为未运行" % row["frag_id"])
        return
    for field in kept_fields:
        if row[field] not in RUN_KEPT:
            raise ValueError("%s 已有译文时 %s 不能是未运行" % (row["frag_id"], field))
    if row["severe_mistranslation"] == "未运行" or row["changes_understanding"] == "未运行":
        raise ValueError("%s 已有译文时不能把严重性留成未运行" % row["frag_id"])
    negatives = [field for field in kept_fields if row[field] == "no"]
    if row["severe_mistranslation"] == "yes" or negatives:
        if row["error_location"] in ("", "无", "未运行"):
            raise ValueError("%s 有缺口时必须写 error_location" % row["frag_id"])
    else:
        if row["error_location"] != "无":
            raise ValueError("%s 无缺口时 error_location 应为无" % row["frag_id"])
    if row["code_intact"] == "yes":
        missing = [token for token in row.get("must_keep", []) if token not in output]
        if missing:
            raise ValueError("%s 声称代码完好，但译文缺少 %s" % (row["frag_id"], missing))
    if "代码" in row.get("categories", []) and not row.get("must_keep"):
        raise ValueError("%s 代码类片段缺少 must_keep" % row["frag_id"])
    if row["severe_mistranslation"] == "yes" and row["changes_understanding"] != "yes":
        raise ValueError("%s 严重误译必须同时改变理解" % row["frag_id"])
    if row["changes_understanding"] == "yes" and row["severe_mistranslation"] != "yes":
        raise ValueError("%s 改变理解时应标为严重误译" % row["frag_id"])


def validate_fragment_set(rows: list[dict]) -> None:
    if len(rows) != 6:
        raise ValueError("本批片段数量固定为 6")
    ids = [row["frag_id"] for row in rows]
    if ids != ["P-%02d" % i for i in range(1, 7)]:
        raise ValueError("frag_id 必须是 P-01 到 P-06 且按序")
    directions = {row["lang_pair"] for row in rows}
    if directions != {"zh→en", "en→zh"}:
        raise ValueError("必须同时有 zh→en 与 en→zh")
    for direction in ("zh→en", "en→zh"):
        covered = set()
        for row in rows:
            if row["lang_pair"] == direction:
                covered.update(row["categories"])
        missing = [cat for cat in CATEGORIES if cat not in covered]
        if missing:
            raise ValueError("%s 缺少类别 %s" % (direction, missing))
    for row in rows:
        if "代码" in row["categories"] and not row.get("must_keep"):
            raise ValueError("%s 代码类缺少 must_keep" % row["frag_id"])
        for field in ("source_text", "source_url", "source_repo", "frozen_at"):
            if not row.get(field):
                raise ValueError("%s 缺少 %s" % (row["frag_id"], field))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="E3 片段翻译与记录合并")
    sub = parser.add_subparsers(dest="cmd", required=True)
    translate = sub.add_parser("translate")
    translate.add_argument("--fragments", required=True)
    translate.add_argument("--out", required=True)
    join = sub.add_parser("join")
    join.add_argument("--fragments", required=True)
    join.add_argument("--translations", required=True)
    join.add_argument("--judgments", required=True)
    join.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.cmd == "translate":
        import urllib.error
        import urllib.request

        def http_get(url: str, timeout: float) -> tuple[int, bytes]:
            request = urllib.request.Request(url, headers={"User-Agent": "gold-miner-w6"})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read()

        fragments = load_jsonl(args.fragments)
        validate_fragment_set(fragments)
        rows = [translate_one(fragment, http_get) for fragment in fragments]
        write_jsonl(args.out, rows)
        return
    fragments = load_jsonl(args.fragments)
    translations = load_jsonl(args.translations)
    judgments = load_jsonl(args.judgments)
    validate_fragment_set(fragments)
    observations = join_records(fragments, translations, judgments)
    write_jsonl(args.out, observations)


if __name__ == "__main__":
    main()
