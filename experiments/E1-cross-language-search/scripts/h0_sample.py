"""H0 分区间占比纯函数。

协议依据：experiments/E1-cross-language-search/protocol.md 第 2 节（H0 规模测量）。
本模块不做抽样 HTTP、不访问网络。输入是“已下载的仓库元数据列表”，
输出各 star 区间的语言分类计数与占比（JSON 可序列化 dict）。

输入：list[dict]，每个 dict 已有：
  stars, readme_text, root_files, description, topics,
  full_name, is_fork, archived

规则：
- 排除 fork（is_fork 真值）与 archived（真值）。
- star 区间：100-199、200-499、500-999、1000-4999、>=5000。
  stars < 100 或缺失/非法 → 忽略（不计入任何区间）。
- 语言分类复用 readme_lang.classify（h0-lang-v1），逐字遵循协议第 2 节。
- zh_only 中 description 像英文：description 里拉丁字母数多于 CJK 表意字数。
- zh_only 中 topics 非空：topics 为 list/tuple 且至少含一个非空字符串。

输出（json.dumps 可序列化）：
{
  "version": "h0-sample-v1",
  "classifier_version": "h0-lang-v1",
  "buckets": {
    "<bucket>": {
      "n": int,
      "zh_only": int, "bilingual": int, "en": int, "ja": int, "ko": int,
      "counts": {"zh_only":..,"bilingual":..,"en":..,"ja":..,"ko":..},
      "shares": {"zh_only":..,"bilingual":..,"en":..,"ja":..,"ko":..},
      "zh_only_share": float, "bilingual_share": float, "en_share": float,
      "ja_share": float, "ko_share": float,
      "zh_only_desc_en_like_n": int,
      "zh_only_desc_en_like_ratio": float | None,
      "zh_only_topics_nonempty_n": int,
      "zh_only_topics_nonempty_ratio": float | None,
    }, ...
  }
}
- shares = count / n（n==0 时为 0.0）。
- zh_only_*_ratio = 子集数 / zh_only 数；zh_only==0 时为 None（无定义）。
"""

from __future__ import annotations

try:
    from .readme_lang import VERSION as CLASSIFIER_VERSION
    from .readme_lang import classify
except ImportError:  # 直接 python3 scripts/test_h0_sample.py 运行
    from readme_lang import VERSION as CLASSIFIER_VERSION  # type: ignore
    from readme_lang import classify  # type: ignore

VERSION = "h0-sample-v1"

BUCKET_100_199 = "100-199"
BUCKET_200_499 = "200-499"
BUCKET_500_999 = "500-999"
BUCKET_1000_4999 = "1000-4999"
BUCKET_GE_5000 = ">=5000"

BUCKET_KEYS = (
    BUCKET_100_199,
    BUCKET_200_499,
    BUCKET_500_999,
    BUCKET_1000_4999,
    BUCKET_GE_5000,
)

LABELS = ("zh_only", "bilingual", "en", "ja", "ko")


def _is_cjk_ideograph(ch: str) -> bool:
    o = ord(ch)
    return (
        (0x3400 <= o <= 0x4DBF)
        or (0x4E00 <= o <= 0x9FFF)
        or (0x20000 <= o <= 0x2EBEF)
    )


def _is_latin(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z")


def bucket_for_stars(stars) -> str | None:
    """stars → 区间 key；<100/非法 → None（忽略）。bool 视为非法。"""
    if isinstance(stars, bool):
        return None
    if isinstance(stars, float):
        if stars != stars or stars == float("inf") or stars == float("-inf"):
            return None
        stars = int(stars)
    if not isinstance(stars, int):
        return None
    if stars < 100:
        return None
    if 100 <= stars <= 199:
        return BUCKET_100_199
    if 200 <= stars <= 499:
        return BUCKET_200_499
    if 500 <= stars <= 999:
        return BUCKET_500_999
    if 1000 <= stars <= 4999:
        return BUCKET_1000_4999
    return BUCKET_GE_5000


def is_english_like_description(description) -> bool:
    """description 像英文 ⟺ 拉丁字母数多于 CJK 表意字数。

    非字符串（None 等）、空串、无字母 → False。
    """
    if not isinstance(description, str) or not description:
        return False
    cjk = sum(1 for ch in description if _is_cjk_ideograph(ch))
    latin = sum(1 for ch in description if _is_latin(ch))
    return latin > cjk


def has_topics(topics) -> bool:
    """topics 非空 ⟺ list/tuple 里至少有一个非空字符串。"""
    if not isinstance(topics, (list, tuple)):
        return False
    for t in topics:
        if isinstance(t, str) and t.strip():
            return True
    return False


def _empty_bucket() -> dict:
    counts = {label: 0 for label in LABELS}
    shares = {label: 0.0 for label in LABELS}
    bucket: dict = {
        "n": 0,
        "counts": dict(counts),
        "shares": dict(shares),
        "zh_only_desc_en_like_n": 0,
        "zh_only_desc_en_like_ratio": None,
        "zh_only_topics_nonempty_n": 0,
        "zh_only_topics_nonempty_ratio": None,
    }
    for label in LABELS:
        bucket[label] = 0
        bucket[f"{label}_share"] = 0.0
    return bucket


def summarize_repos(repos: list[dict]) -> dict:
    """给定已下载仓库元数据列表，输出分区间占比（纯函数，不触网）。

    排除 fork/archived；stars <100 忽略；语言经 readme_lang.classify 判定。
    不修改输入。
    """
    items = list(repos) if isinstance(repos, (list, tuple)) else []
    acc: dict[str, dict] = {key: _empty_bucket() for key in BUCKET_KEYS}
    # 暂存 zh_only 子集计数，最后再算比例
    desc_n: dict[str, int] = {key: 0 for key in BUCKET_KEYS}
    topics_n: dict[str, int] = {key: 0 for key in BUCKET_KEYS}

    for repo in items:
        if not isinstance(repo, dict):
            continue
        if repo.get("is_fork"):
            continue
        if repo.get("archived"):
            continue
        bucket = bucket_for_stars(repo.get("stars"))
        if bucket is None:
            continue
        readme_text = repo.get("readme_text")
        if not isinstance(readme_text, str):
            readme_text = ""
        root_files = repo.get("root_files")
        if not isinstance(root_files, (list, tuple)):
            root_files = []
        else:
            root_files = list(root_files)
        label = classify(readme_text, root_files).get("label")
        if label not in LABELS:
            label = "en"
        b = acc[bucket]
        b["n"] += 1
        b[label] += 1  # type: ignore[literal-required]
        b["counts"][label] += 1
        if label == "zh_only":
            if is_english_like_description(repo.get("description")):
                desc_n[bucket] += 1
            if has_topics(repo.get("topics")):
                topics_n[bucket] += 1

    for key in BUCKET_KEYS:
        b = acc[key]
        n = b["n"]
        for label in LABELS:
            b["shares"][label] = (b["counts"][label] / n) if n else 0.0
            b[f"{label}_share"] = b["shares"][label]
        zh_n = b["counts"]["zh_only"]
        b["zh_only_desc_en_like_n"] = desc_n[key]
        b["zh_only_topics_nonempty_n"] = topics_n[key]
        b["zh_only_desc_en_like_ratio"] = (
            (desc_n[key] / zh_n) if zh_n else None
        )
        b["zh_only_topics_nonempty_ratio"] = (
            (topics_n[key] / zh_n) if zh_n else None
        )

    return {
        "version": VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "buckets": acc,
    }


# 别名：评测/调用方若用不同函数名仍可命中同一纯函数。
summarize = summarize_repos
h0_summary = summarize_repos
summarize_h0 = summarize_repos

__all__ = [
    "VERSION",
    "BUCKET_KEYS",
    "LABELS",
    "bucket_for_stars",
    "is_english_like_description",
    "has_topics",
    "summarize_repos",
    "summarize",
    "h0_summary",
    "summarize_h0",
]
