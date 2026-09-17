"""h0_sample 纯函数测试：12 条人造仓库测 star 边界与分区间占比。

不访问网络，可直接运行：
  python3 experiments/E1-cross-language-search/scripts/test_h0_sample.py

12 条覆盖：
  99（<100 忽略）、100（100-199 下界）、199（100-199 上界）、
  200（200-499 下界）、499（200-499 上界）、500（500-999 下界）、
  999（500-999 上界）、1000（1000-4999 下界）、4999（1000-4999 上界）、
  5000（>=5000 下界）、fork 排除、archived 排除。
语言覆盖 zh_only / bilingual / en / ja / ko；
zh_only 内同时覆盖 description 像英文 True/False 与 topics 非空/空。
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import h0_sample
from h0_sample import (
    bucket_for_stars,
    has_topics,
    is_english_like_description,
    summarize_repos,
)

ZH_TEXT = "这是一个中文项目的简介，用于测试分类功能，包含项目目标与用法说明。"
EN_TEXT = "This is an English README for testing classification logic."
BILINGUAL_TEXT = "中文介绍abcdef"
JA_TEXT = "これはテストです。This is a test README."
KO_TEXT = "이것은 테스트입니다. This is a test README."

DESC_EN = "Awesome toolkit for data processing"
DESC_ZH = "这是一个中文简介没有英文"


def make_repo(stars, readme_text, root_files, description, topics,
              full_name, is_fork=False, archived=False):
    return {
        "stars": stars,
        "readme_text": readme_text,
        "root_files": root_files,
        "description": description,
        "topics": topics,
        "full_name": full_name,
        "is_fork": is_fork,
        "archived": archived,
    }


def twelve_repos():
    return [
        # R1: <100，应被忽略
        make_repo(99, EN_TEXT, ["README.md"], DESC_EN, [],
                  "org/r-below-100"),
        # R2: 100-199 下界，zh_only，desc 像英文 True，topics 非空
        make_repo(100, ZH_TEXT, ["README.md"], DESC_EN, ["python"],
                  "org/r-100-zh"),
        # R3: 100-199 上界，en
        make_repo(199, EN_TEXT, ["README.md"], DESC_EN, [],
                  "org/r-199-en"),
        # R4: 200-499 下界，bilingual（0.4）
        make_repo(200, BILINGUAL_TEXT, ["README.md"], DESC_EN, [],
                  "org/r-200-bi"),
        # R5: 200-499 上界，ja
        make_repo(499, JA_TEXT, ["README.md"], DESC_EN, [],
                  "org/r-499-ja"),
        # R6: 500-999 下界，ko
        make_repo(500, KO_TEXT, ["README.md"], DESC_EN, [],
                  "org/r-500-ko"),
        # R7: 500-999 上界，zh_only，desc 像英文 False，topics 空
        make_repo(999, ZH_TEXT, ["README.md"], DESC_ZH, [],
                  "org/r-999-zh"),
        # R8: 1000-4999 下界，en
        make_repo(1000, EN_TEXT, ["README.md"], DESC_EN, [],
                  "org/r-1000-en"),
        # R9: 1000-4999 上界，双语（中文正文 + 英文副本）
        make_repo(4999, ZH_TEXT, ["README.md", "README.en.md"], DESC_EN,
                  ["demo"], "org/r-4999-bi-copy"),
        # R10: >=5000 下界，zh_only，desc 像英文 True，topics 非空
        make_repo(5000, ZH_TEXT, ["README.md"], DESC_EN, ["tool", "zh"],
                  "org/r-5000-zh"),
        # R11: fork，应被排除（stars 落在 100-199 也不计）
        make_repo(150, ZH_TEXT, ["README.md"], DESC_EN, ["x"],
                  "org/r-fork", is_fork=True),
        # R12: archived，应被排除（stars 落在 500-999 也不计）
        make_repo(600, ZH_TEXT, ["README.md"], DESC_EN, ["x"],
                  "org/r-archived", archived=True),
    ]


class TestBucketBoundaries(unittest.TestCase):
    def test_edges(self):
        self.assertIsNone(bucket_for_stars(99))
        self.assertEqual(bucket_for_stars(100), "100-199")
        self.assertEqual(bucket_for_stars(199), "100-199")
        self.assertEqual(bucket_for_stars(200), "200-499")
        self.assertEqual(bucket_for_stars(499), "200-499")
        self.assertEqual(bucket_for_stars(500), "500-999")
        self.assertEqual(bucket_for_stars(999), "500-999")
        self.assertEqual(bucket_for_stars(1000), "1000-4999")
        self.assertEqual(bucket_for_stars(4999), "1000-4999")
        self.assertEqual(bucket_for_stars(5000), ">=5000")
        self.assertEqual(bucket_for_stars(10000), ">=5000")

    def test_invalid_stars_ignored(self):
        self.assertIsNone(bucket_for_stars(None))
        self.assertIsNone(bucket_for_stars("abc"))
        self.assertIsNone(bucket_for_stars(True))


class TestDescTopicsHelpers(unittest.TestCase):
    def test_desc_en_like(self):
        self.assertTrue(is_english_like_description(DESC_EN))
        self.assertFalse(is_english_like_description(DESC_ZH))
        self.assertFalse(is_english_like_description(""))
        self.assertFalse(is_english_like_description(None))

    def test_topics(self):
        self.assertTrue(has_topics(["python"]))
        self.assertFalse(has_topics([]))
        self.assertFalse(has_topics(None))
        self.assertFalse(has_topics(["  "]))


class TestSummarizeTwelve(unittest.TestCase):
    def test_counts_and_exclusions(self):
        out = summarize_repos(twelve_repos())
        buckets = out["buckets"]
        self.assertEqual(buckets["100-199"]["n"], 2)
        self.assertEqual(buckets["200-499"]["n"], 2)
        self.assertEqual(buckets["500-999"]["n"], 2)
        self.assertEqual(buckets["1000-4999"]["n"], 2)
        self.assertEqual(buckets[">=5000"]["n"], 1)
        total = sum(b["n"] for b in buckets.values())
        self.assertEqual(total, 9)  # 12 - 99越界 - fork - archived

    def test_labels_per_bucket(self):
        buckets = summarize_repos(twelve_repos())["buckets"]
        self.assertEqual(buckets["100-199"]["counts"]["zh_only"], 1)
        self.assertEqual(buckets["100-199"]["counts"]["en"], 1)
        self.assertEqual(buckets["200-499"]["counts"]["bilingual"], 1)
        self.assertEqual(buckets["200-499"]["counts"]["ja"], 1)
        self.assertEqual(buckets["500-999"]["counts"]["ko"], 1)
        self.assertEqual(buckets["500-999"]["counts"]["zh_only"], 1)
        self.assertEqual(buckets["1000-4999"]["counts"]["en"], 1)
        self.assertEqual(buckets["1000-4999"]["counts"]["bilingual"], 1)
        self.assertEqual(buckets[">=5000"]["counts"]["zh_only"], 1)

    def test_shares(self):
        buckets = summarize_repos(twelve_repos())["buckets"]
        b = buckets["100-199"]
        self.assertAlmostEqual(b["shares"]["zh_only"], 0.5)
        self.assertAlmostEqual(b["shares"]["en"], 0.5)
        self.assertAlmostEqual(b["zh_only_share"], 0.5)
        b5 = buckets[">=5000"]
        self.assertAlmostEqual(b5["shares"]["zh_only"], 1.0)

    def test_zh_only_ratios(self):
        buckets = summarize_repos(twelve_repos())["buckets"]
        # 100-199：唯一 zh_only 的 desc 像英文、topics 非空 → 1.0
        self.assertEqual(buckets["100-199"]["zh_only_desc_en_like_n"], 1)
        self.assertAlmostEqual(
            buckets["100-199"]["zh_only_desc_en_like_ratio"], 1.0)
        self.assertAlmostEqual(
            buckets["100-199"]["zh_only_topics_nonempty_ratio"], 1.0)
        # 500-999：唯一 zh_only 的 desc 中文、topics 空 → 0.0
        self.assertAlmostEqual(
            buckets["500-999"]["zh_only_desc_en_like_ratio"], 0.0)
        self.assertAlmostEqual(
            buckets["500-999"]["zh_only_topics_nonempty_ratio"], 0.0)
        # 200-499：无 zh_only → ratio 为 None
        self.assertIsNone(
            buckets["200-499"]["zh_only_desc_en_like_ratio"])
        self.assertIsNone(
            buckets["200-499"]["zh_only_topics_nonempty_ratio"])

    def test_json_serializable_and_versions(self):
        out = summarize_repos(twelve_repos())
        self.assertEqual(out["version"], h0_sample.VERSION)
        self.assertEqual(out["classifier_version"], "h0-lang-v1")
        s = json.dumps(out, ensure_ascii=False)
        back = json.loads(s)
        self.assertEqual(back["buckets"]["100-199"]["n"], 2)

    def test_pure_no_mutation_no_network(self):
        repos = twelve_repos()
        snapshot = json.dumps(repos, ensure_ascii=False)
        summarize_repos(repos)
        self.assertEqual(json.dumps(repos, ensure_ascii=False), snapshot)
        src = Path(__file__).resolve().parent.joinpath("h0_sample.py").read_text(
            encoding="utf-8")
        self.assertNotIn("api.github.com", src)
        self.assertNotIn("urlopen", src)
        self.assertNotIn("http_get", src)

    def test_empty_input(self):
        out = summarize_repos([])
        for key in ("100-199", "200-499", "500-999", "1000-4999", ">=5000"):
            self.assertEqual(out["buckets"][key]["n"], 0)
            self.assertIsNone(
                out["buckets"][key]["zh_only_desc_en_like_ratio"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
