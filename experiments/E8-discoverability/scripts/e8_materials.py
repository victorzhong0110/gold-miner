"""Load and check W7 metadata and E8 query materials. No network.

Run:
  python3 experiments/E8-discoverability/scripts/e8_materials.py

Prints a plan-only JSON object. It does not read API keys and does not
send HTTP requests. Passing --live exits with an error.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E8 = ROOT / "experiments" / "E8-discoverability"
METADATA_PATH = E8 / "metadata-draft.json"
QUERIES_PATH = E8 / "entry-queries.jsonl"

SURFACES = {"github_rest_search", "github_web", "web_search_engine"}
ROLES = {"entry", "diagnostic", "baseline_variant"}
GROUPS = {"name_plus_purpose", "purpose_only", "name_only"}
LANGUAGES = {"zh", "en"}
REQUIRED_QUERY_FIELDS = (
    "query_id",
    "surface",
    "role",
    "group",
    "language",
    "query",
    "contains_github_term",
    "window",
    "rank_first_required",
    "source_ref",
    "natural_user_phrasing",
    "compare_to",
    "status",
    "result",
)
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
GITHUB_TERM_RE = re.compile(r"github", re.IGNORECASE)
SECRET_RES = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
)


def load_metadata(path: Path = METADATA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_queries(path: Path = QUERIES_PATH) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} 不是 JSON") from exc
    return rows


def _has_github_term(query: str) -> bool:
    return GITHUB_TERM_RE.search(query) is not None


def validate(metadata: dict, queries: list[dict]) -> list[str]:
    errors: list[str] = []
    if metadata.get("applied_to_github") is not False:
        errors.append("applied_to_github 必须为 false")
    if metadata.get("status") != "draft-not-applied":
        errors.append("元数据状态必须是 draft-not-applied")
    if metadata.get("e8_retest") != "未运行":
        errors.append("e8_retest 必须写明未运行")
    if metadata.get("remote_metadata_read") != "未运行":
        errors.append("远程元数据读取必须写明未运行")

    repo = metadata.get("repo") or {}
    if repo.get("full_name") != "victorzhong0110/gold-miner" or repo.get("rename") is not False:
        errors.append("仓库名必须保持 victorzhong0110/gold-miner，且 rename 为 false")

    decisions = metadata.get("decisions") or {}
    if decisions.get("0001") != "待决策" or decisions.get("0003") != "待决策":
        errors.append("决策 0001 和 0003 必须仍是待决策")

    license_info = metadata.get("license") or {}
    if license_info.get("decision") != "待决策" or license_info.get("file_added") is not False:
        errors.append("许可证必须仍是待决策，且 file_added 为 false")

    description = metadata.get("description") or {}
    text = description.get("text") or ""
    zh = description.get("zh") or ""
    en = description.get("en") or ""
    if zh + en != text:
        errors.append("双语两段拼接后必须等于唯一的 description 草案")
    if description.get("char_count") != len(text):
        errors.append("char_count 与草案字数不一致")
    max_chars = description.get("max_chars")
    if not isinstance(max_chars, int) or len(text) > max_chars:
        errors.append("简介草案超过记录的字符上限")
    if "planned" not in text or description.get("claims_installable_extension") is not False:
        errors.append("简介必须标明扩展仍是 planned，不能写成已可安装")
    if "黄金矿工" not in text or "Gold Miner" not in text:
        errors.append("简介草案须同时包含中英文工作名")

    topics = metadata.get("topics")
    limits = metadata.get("topic_limits") or {}
    if not isinstance(topics, list) or not topics:
        errors.append("topics 草案不能为空")
    else:
        max_count = limits.get("max_count", 20)
        max_length = limits.get("max_length", 50)
        if len(topics) > max_count:
            errors.append("topics 数量超过上限")
        if len(topics) != len(set(topics)):
            errors.append("topics 不能重复")
        for topic in topics:
            if not isinstance(topic, str) or not TOPIC_RE.fullmatch(topic) or len(topic) > max_length:
                errors.append(f"topic 不符合小写、数字、连字符约束：{topic!r}")

    seen_ids = set()
    for row in queries:
        missing = [key for key in REQUIRED_QUERY_FIELDS if key not in row]
        if missing:
            errors.append(f"查询缺少字段 {missing}")
            continue
        query_id = row["query_id"]
        if query_id in seen_ids:
            errors.append(f"query_id 重复：{query_id}")
        seen_ids.add(query_id)
        if row["surface"] not in SURFACES:
            errors.append(f"{query_id} 入口无效")
        if row["role"] not in ROLES:
            errors.append(f"{query_id} 角色无效")
        if row["group"] not in GROUPS:
            errors.append(f"{query_id} 分组无效")
        if row["language"] not in LANGUAGES:
            errors.append(f"{query_id} 语言无效")
        if row["status"] != "未运行" or row["result"] is not None:
            errors.append(f"{query_id} 必须是未运行且 result 为 null")
        if row["rank_first_required"] is not False:
            errors.append(f"{query_id} 不能要求排名第一")
        if row["window"] != 20:
            errors.append(f"{query_id} 拟定窗口应为 20")
        if row["natural_user_phrasing"] is not False:
            errors.append(f"{query_id} 不能把模板例句写成用户原话")
        actual_github = _has_github_term(row["query"])
        if row["contains_github_term"] is not actual_github:
            errors.append(f"{query_id} 的 contains_github_term 与查询原文不一致")
        if row["role"] == "entry" and row["surface"] in {"github_rest_search", "github_web"}:
            if actual_github:
                errors.append(f"{query_id} 是站内入口查询，不应含 GitHub 一词")
        if row["role"] == "entry" and row["surface"] == "web_search_engine" and not actual_github:
            errors.append(f"{query_id} 是普通搜索入口，应保留 GitHub 一词")
        if row["role"] == "baseline_variant":
            if row["surface"] != "github_rest_search" or not actual_github:
                errors.append(f"{query_id} 基线变体应是带 GitHub 一词的站内 API 查询")
        if not isinstance(row["query"], str) or not row["query"].strip():
            errors.append(f"{query_id} 查询原文为空")

    entry = [row for row in queries if row.get("role") == "entry"]
    for surface in SURFACES:
        for language in LANGUAGES:
            for group in ("name_plus_purpose", "purpose_only"):
                matched = [
                    row
                    for row in entry
                    if row.get("surface") == surface
                    and row.get("language") == language
                    and row.get("group") == group
                ]
                if len(matched) != 1:
                    errors.append(f"入口查询应各有一条 {surface}/{language}/{group}")

    api_entry = {
        row["query"]
        for row in entry
        if row.get("surface") == "github_rest_search"
    }
    web_entry = {row["query"] for row in entry if row.get("surface") == "github_web"}
    if api_entry != web_entry:
        errors.append("GitHub 网页入口查询应与 REST 入口查询使用同一组站内原文")

    name_only = [row for row in queries if row.get("group") == "name_only"]
    if not name_only or any(row.get("role") == "entry" for row in name_only):
        errors.append("单独名称只作诊断，不作为必须排第一的入口查询")

    blob = json.dumps(metadata, ensure_ascii=False) + "\n" + "\n".join(
        json.dumps(row, ensure_ascii=False) for row in queries
    )
    for pattern in SECRET_RES:
        if pattern.search(blob):
            errors.append("材料中出现疑似密钥")
    return errors


def rest_search_url(query: str, window: int) -> str:
    encoded = urllib.parse.quote(query, safe="")
    return f"https://api.github.com/search/repositories?q={encoded}&per_page={window}"


def github_web_url(query: str) -> str:
    encoded = urllib.parse.quote(query, safe="")
    return f"https://github.com/search?q={encoded}&type=repositories"


def build_plan(metadata: dict, queries: list[dict]) -> dict:
    items = []
    for row in queries:
        item = {
            "query_id": row["query_id"],
            "surface": row["surface"],
            "query": row["query"],
            "executed": False,
            "status": "未运行",
        }
        if row["surface"] == "github_rest_search":
            item["method"] = "GET"
            item["url"] = rest_search_url(row["query"], row["window"])
        elif row["surface"] == "github_web":
            item["method"] = "manual"
            item["url"] = github_web_url(row["query"])
        else:
            item["method"] = "manual"
            item["url"] = None
        items.append(item)
    return {
        "mode": "plan-only",
        "live_requests": 0,
        "metadata_applied": metadata.get("applied_to_github"),
        "repo": (metadata.get("repo") or {}).get("full_name"),
        "items": items,
    }


def main(argv: list[str]) -> int:
    if "--live" in argv:
        print("本材料包不发起网络请求。E8 复测未运行。", file=sys.stderr)
        return 2
    metadata = load_metadata()
    queries = load_queries()
    errors = validate(metadata, queries)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    json.dump(build_plan(metadata, queries), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
