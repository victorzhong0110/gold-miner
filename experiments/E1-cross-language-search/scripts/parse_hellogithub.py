"""HelloGitHub 单期 Markdown 保守解析器。

协议依据：experiments/E1-cross-language-search/protocol.md 第 3 节
步骤 1（取月刊 Markdown，解析每条目的仓库地址与中文介绍）。
输出字段对齐种子集所需子集：repo、zh_description、hellogithub_issue。

保守规则（真实月刊格式未 clone 验证前）：
- 只认 markdown 内联链接 ``[文本](URL)`` 里的 github.com/owner/repo。
- 裸 URL（无 ``[...]()`` 包裹）一律忽略，不计入 entries 也不计入 skipped。
- URL 仅接受 http/https（含 www.）且域名大小写不敏感为 github.com。
- 取路径前两段为 owner/repo，多余路径（/tree/...、/blob/... 等）忽略。
- 末尾 ``.git`` 后缀剥离，query/fragment 剥离，末尾 ``/`` 剥离。
- owner/repo 每段仅允许 ``[A-Za-z0-9_.-]`` 且必须含至少一个字母数字；
  长度 owner<=39、repo<=100；``.``/``..`` 拒绝。不确定一律丢弃并计入 skipped。
- 非 github 域名的 markdown 链接计入 skipped，不产生 entry。
- 同一 repo（大小写不敏感）重复出现只保留首次，后续计入 skipped。
- zh_description 为该链接所在节内、链接行前后窗口的清洗文本：
  节以 ``#{1,6}`` 标题切分；取标题 + 链接行前最多 8 个非空行 +
  链接行本身 + 链接行后最多 2 个非空行（均限本节内），清洗后以 ``\\n``
  连接并截断至 500 字符。清洗指：去图片、链接留文本、去 HTML 标签、
  去行首标题/引用/列表标记、压缩空白。多链接同节时各自窗口可能重叠，
  属保守行为，已在文档中说明。
- 不访问网络，不读环境变量，不写文件。CLI 只向 stdout 写 JSONL。

版本：hellogithub-parse-v1。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Union

VERSION = "hellogithub-parse-v1"

HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$")
LINK_RE = re.compile(
    r"\[([^\]]*)\]"  # link text
    r"\(\s*(<[^>]+>|[^)\s]+)"  # URL (or <URL>)
    r"(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)")

_OWNER_REPO_CHARS_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_HAS_ALNUM_RE = re.compile(r"[A-Za-z0-9]")
_GITHUB_PATH_RE = re.compile(
    r"^https?://(www\.)?github\.com/([^/\s?#]+)/([^/\s?#]+)",
    re.IGNORECASE,
)


def extract_repo(url: str) -> Union[str, None]:
    """从单个 URL 提取 ``owner/repo``，不确定返回 None。"""
    if not isinstance(url, str):
        return None
    u = url.strip()
    if len(u) >= 2 and u.startswith("<") and u.endswith(">"):
        u = u[1:-1].strip()
    if not u:
        return None
    # 防御：若误传入带标题的整体，只取首 token。
    u = u.split()[0].strip()
    # 剥离 fragment/query、末尾斜杠、.git 后缀。
    u = u.split("#", 1)[0].split("?", 1)[0].rstrip("/").strip()
    if u.lower().endswith(".git"):
        u = u[:-4].rstrip("/").strip()
    if not u:
        return None
    m = _GITHUB_PATH_RE.match(u)
    if not m:
        return None
    owner, repo = m.group(2), m.group(3)
    if not _OWNER_REPO_CHARS_RE.fullmatch(owner):
        return None
    if not _OWNER_REPO_CHARS_RE.fullmatch(repo):
        return None
    if owner in (".", "..") or repo in (".", ".."):
        return None
    if len(owner) > 39 or len(repo) > 100:
        return None
    if not _HAS_ALNUM_RE.search(owner):
        return None
    if not _HAS_ALNUM_RE.search(repo):
        return None
    return f"{owner}/{repo}"


def _clean_line(line: str) -> str:
    text = line if isinstance(line, str) else ""
    text = IMAGE_RE.sub("", text)
    text = LINK_RE.sub(lambda m: m.group(1), text)
    text = HTML_TAG_RE.sub("", text)
    text = text.strip()
    # 去行首标题/引用标记。
    text = re.sub(r"^[#>]+\s*", "", text).strip()
    text = LIST_MARKER_RE.sub("", text).strip()
    # 去残留强调符号首尾空白，不动中文内文。
    text = text.strip(" \t`").strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _section_bounds(lines: list, link_line_idx: int) -> tuple:
    start = 0
    for i in range(link_line_idx, -1, -1):
        if HEADING_RE.match(lines[i]):
            start = i
            break
    end = len(lines)
    for i in range(link_line_idx + 1, len(lines)):
        if HEADING_RE.match(lines[i]):
            end = i
            break
    return start, end


def _build_description(
    lines: list, link_line_idx: int, start: int, end: int
) -> str:
    heading_text = ""
    if start < len(lines) and HEADING_RE.match(lines[start]):
        heading_text = _clean_line(HEADING_RE.match(lines[start]).group(1))
    # 链接行前最多 8 个非空行（本节内，不含标题行本身）。
    before: list = []
    i = link_line_idx - 1
    while i > start and len(before) < 8:
        cleaned = _clean_line(lines[i])
        if cleaned:
            before.append(cleaned)
        i -= 1
    before.reverse()
    # 链接行本身。
    self_line = _clean_line(lines[link_line_idx])
    # 链接行后最多 2 个非空行（本节内）。
    after: list = []
    i = link_line_idx + 1
    while i < end and len(after) < 2:
        cleaned = _clean_line(lines[i])
        if cleaned:
            after.append(cleaned)
        i += 1
    parts: list = []
    if heading_text:
        parts.append(heading_text)
    parts.extend(before)
    if self_line:
        parts.append(self_line)
    parts.extend(after)
    # 去重连续重复行（标题与首行重复时常见），保留顺序。
    deduped: list = []
    for p in parts:
        if not deduped or deduped[-1] != p:
            deduped.append(p)
    text = "\n".join(deduped).strip()
    return text[:500]


def parse_issue(markdown_text: str, issue_number: int) -> dict:
    """解析单期 Markdown，返回 entries/skipped/version。

    Args:
        markdown_text: 单期 Markdown 全文。
        issue_number: HelloGitHub 期号（正整数），原样写入每条 entry。

    Returns:
        ``{"entries": [{"repo", "zh_description", "hellogithub_issue"}],
        "skipped": int, "version": str}``。entries 按文档顺序，去重后保留首次。
    """
    if not isinstance(markdown_text, str):
        raise TypeError("markdown_text must be str")
    if (
        not isinstance(issue_number, int)
        or isinstance(issue_number, bool)
        or issue_number < 1
    ):
        raise ValueError("issue_number must be a positive int")
    lines = markdown_text.splitlines()
    entries: list = []
    seen: set = set()
    skipped = 0
    for idx, line in enumerate(lines):
        for m in LINK_RE.finditer(line):
            raw_url = m.group(2).strip()
            repo = extract_repo(raw_url)
            if repo is None:
                skipped += 1
                continue
            key = repo.lower()
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            start, end = _section_bounds(lines, idx)
            desc = _build_description(lines, idx, start, end)
            entries.append(
                {
                    "repo": repo,
                    "zh_description": desc,
                    "hellogithub_issue": issue_number,
                }
            )
    return {"entries": entries, "skipped": skipped, "version": VERSION}


def parse_file(path: Union[str, Path], issue_number: int) -> dict:
    """从 Markdown 文件解析单期，行为同 parse_issue。"""
    text = Path(path).read_text(encoding="utf-8")
    return parse_issue(text, issue_number)


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print(
            "usage: python parse_hellogithub.py <markdown_path> <issue_number>",
            file=sys.stderr,
        )
        return 2
    md_path, issue_raw = args
    try:
        issue_number = int(issue_raw)
    except ValueError:
        print("issue_number must be a positive int", file=sys.stderr)
        return 2
    try:
        result = parse_file(md_path, issue_number)
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for entry in result["entries"]:
        print(
            json.dumps(entry, ensure_ascii=False),
            file=sys.stdout,
        )
    print(
        json.dumps(
            {"skipped": result["skipped"], "version": result["version"]},
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
