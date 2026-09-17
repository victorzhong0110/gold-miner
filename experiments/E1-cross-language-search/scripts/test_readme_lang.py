"""h0-lang-v1 分类器测试，不访问网络，可直接运行。

运行：
  python3 experiments/E1-cross-language-search/scripts/test_readme_lang.py
"""

import unittest

try:
    from .readme_lang import classify
except ImportError:
    from readme_lang import classify


class TestReadmeLang(unittest.TestCase):
    def test_pure_chinese(self):
        text = "这是一个中文项目的简介，用于测试分类功能，包含项目目标与用法说明。"
        r = classify(text, ["README.md"])
        self.assertEqual(r["version"], "h0-lang-v1")
        self.assertEqual(r["label"], "zh_only")
        self.assertGreaterEqual(r["cjk_ratio"], 0.6)
        self.assertFalse(r["has_en_readme_copy"])

    def test_pure_english(self):
        text = "This is an English README for testing classification logic."
        r = classify(text, ["README.md"])
        self.assertEqual(r["label"], "en")
        self.assertLess(r["cjk_ratio"], 0.2)
        self.assertFalse(r["has_en_readme_copy"])

    def test_mixed_bilingual(self):
        # 4 个表意字 + 6 个拉丁字母 = 0.4，落入 0.2-0.6 双语区间。
        text = "中文介绍abcdef"
        r = classify(text, ["README.md"])
        self.assertEqual(r["label"], "bilingual")
        self.assertGreaterEqual(r["cjk_ratio"], 0.2)
        self.assertLess(r["cjk_ratio"], 0.6)

    def test_japanese_kana(self):
        text = "これはテストです。This is a test README."
        r = classify(text, ["README.md"])
        self.assertEqual(r["label"], "ja")

    def test_korean(self):
        text = "이것은 테스트입니다. This is a test README."
        r = classify(text, ["README.md"])
        self.assertEqual(r["label"], "ko")

    def test_has_en_readme_copy(self):
        text = "这是一个中文项目的简介，用于测试分类功能，包含项目目标与用法说明。"
        for copy in ("README.en.md", "README_EN.md", "README-en.md"):
            with self.subTest(copy=copy):
                r = classify(text, ["README.md", copy])
                self.assertTrue(r["has_en_readme_copy"])
                self.assertEqual(r["label"], "bilingual")

    def test_only_code_and_badges(self):
        text = (
            "```python\n"
            "print('你好世界 hello')\n"
            "```\n"
            "[![Build](https://img.shields.io/badge/build-passing-brightgreen)]"
            "(https://example.com)\n"
        )
        r = classify(text, ["README.md"])
        self.assertEqual(r["label"], "en")
        self.assertEqual(r["cjk_ratio"], 0.0)

    def test_empty_string(self):
        r = classify("", ["README.md"])
        self.assertEqual(r["label"], "en")
        self.assertEqual(r["cjk_ratio"], 0.0)
        self.assertFalse(r["has_en_readme_copy"])

    def test_boundary_06_goes_zh_only(self):
        # 3 个表意字 + 2 个拉丁字母 = 0.6，边界走仅中文支。
        text = "中文测ab"
        r = classify(text, ["README.md"])
        self.assertAlmostEqual(r["cjk_ratio"], 0.6)
        self.assertEqual(r["label"], "zh_only")

    def test_preprocess_strips_url_html_and_code(self):
        text = (
            "<div>hello</div> https://example.com/x "
            "```js\nvar x = '你好';\n```\n"
            "中文介绍abcdef"
        )
        r = classify(text, ["README.md"])
        self.assertEqual(r["label"], "bilingual")


if __name__ == "__main__":
    unittest.main()
