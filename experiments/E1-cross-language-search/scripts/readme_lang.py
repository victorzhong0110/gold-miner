"""H0 README 语言启发式分类器。

协议依据：experiments/E1-cross-language-search/protocol.md 第 2 节
「分类（启发式，记录版本号）」，版本号 h0-lang-v1。

规则（逐字实现）：
- 预处理：去掉围栏代码块、URL、HTML 标签、徽章行；取前 3000 字符。
- CJK 占比 = 中日韩表意字符数 /（表意字符数 + 拉丁字母数）。
  分母为 0 时 label="en"，cjk_ratio=0.0。
- 含日文假名 -> ja（不计入 zh）。含韩文 -> ko（不计入 zh）。
  先判 ja/ko，再判 zh。
- 仅中文：占比 >= 0.6 且 root_files 中不存在英文副本。
- 双语：0.2-0.6，或存在英文副本。
- 英文：< 0.2。
- 0.6 边界：>= 0.6 走仅中文支。

英文副本指精确文件名（大小写敏感）：
README.en.md / README_EN.md / README-en.md。
"""

from __future__ import annotations

import re

VERSION = "h0-lang-v1"

EN_README_COPIES = ("README.en.md", "README_EN.md", "README-en.md")

_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

_HIRAGANA_RE = re.compile(r"[\u3040-\u309F]")
_KATAKANA_RE = re.compile(r"[\u30A0-\u30FF\u31F0-\u31FF]")
_HANGUL_RE = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]")


def _is_cjk_ideograph(ch: str) -> bool:
    o = ord(ch)
    return (
        (0x3400 <= o <= 0x4DBF)
        or (0x4E00 <= o <= 0x9FFF)
        or (0x20000 <= o <= 0x2EBEF)
    )


def _is_latin(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z")


def _is_badge_line(line: str) -> bool:
    low = line.lower()
    return (
        "[![" in line
        or "shields.io" in line
        or "badge.svg" in low
        or ("![" in line and "badge" in low)
    )


def _preprocess(readme_text: str) -> str:
    text = readme_text if isinstance(readme_text, str) else ""
    # 1. 去围栏代码块（``` ... ```，含换行）。
    text = _FENCED_CODE_RE.sub("", text)
    # 2. 去徽章行（按行判定，在去 URL 之前判定，保留 "[![" 这类标记）。
    lines = text.splitlines()
    lines = [ln for ln in lines if not _is_badge_line(ln)]
    text = "\n".join(lines)
    # 3. 去 URL。
    text = _URL_RE.sub("", text)
    # 4. 去 HTML 标签。
    text = _HTML_TAG_RE.sub("", text)
    # 5. 去徽章行残留（去 URL/HTML 后可能仍剩 "[![" 空壳，再扫一遍）。
    lines = text.splitlines()
    lines = [ln for ln in lines if not _is_badge_line(ln)]
    text = "\n".join(lines)
    # 6. 取前 3000 字符。
    return text[:3000]


def classify(readme_text: str, root_files: list[str]) -> dict:
    """按 h0-lang-v1 启发式给 README 分类。"""
    files = list(root_files) if isinstance(root_files, (list, tuple)) else []
    has_en_readme_copy = any(f in EN_README_COPIES for f in files)

    text = _preprocess(readme_text)

    # 先判 ja/ko，再判 zh。
    if _HIRAGANA_RE.search(text) or _KATAKANA_RE.search(text):
        cjk_count = sum(1 for ch in text if _is_cjk_ideograph(ch))
        latin_count = sum(1 for ch in text if _is_latin(ch))
        denom = cjk_count + latin_count
        ratio = (cjk_count / denom) if denom else 0.0
        return {
            "version": VERSION,
            "cjk_ratio": float(ratio),
            "label": "ja",
            "has_en_readme_copy": bool(has_en_readme_copy),
        }
    if _HANGUL_RE.search(text):
        cjk_count = sum(1 for ch in text if _is_cjk_ideograph(ch))
        latin_count = sum(1 for ch in text if _is_latin(ch))
        denom = cjk_count + latin_count
        ratio = (cjk_count / denom) if denom else 0.0
        return {
            "version": VERSION,
            "cjk_ratio": float(ratio),
            "label": "ko",
            "has_en_readme_copy": bool(has_en_readme_copy),
        }

    cjk_count = sum(1 for ch in text if _is_cjk_ideograph(ch))
    latin_count = sum(1 for ch in text if _is_latin(ch))
    denom = cjk_count + latin_count
    if denom == 0:
        return {
            "version": VERSION,
            "cjk_ratio": 0.0,
            "label": "en",
            "has_en_readme_copy": bool(has_en_readme_copy),
        }
    ratio = cjk_count / denom

    # 存在英文副本 -> 双语（ja/ko 已提前返回，不受此支影响）。
    if has_en_readme_copy:
        return {
            "version": VERSION,
            "cjk_ratio": float(ratio),
            "label": "bilingual",
            "has_en_readme_copy": True,
        }
    # 0.6 边界：>= 0.6 走仅中文支。
    if ratio >= 0.6:
        label = "zh_only"
    elif ratio >= 0.2:
        label = "bilingual"
    else:
        label = "en"
    return {
        "version": VERSION,
        "cjk_ratio": float(ratio),
        "label": label,
        "has_en_readme_copy": False,
    }
