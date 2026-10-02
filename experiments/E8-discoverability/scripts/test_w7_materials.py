"""W7 材料完整性检查。不访问网络，不产生 E8 排名。

运行：
  python3 experiments/E8-discoverability/scripts/test_w7_materials.py
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E8 = ROOT / "experiments" / "E8-discoverability"
SCRIPTS = E8 / "scripts"
sys.path.insert(0, str(SCRIPTS))

import e8_materials  # noqa: E402


class W7MaterialsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = e8_materials.load_metadata()
        cls.queries = e8_materials.load_queries()
        cls.errors = e8_materials.validate(cls.metadata, cls.queries)

    def test_materials_validate(self):
        self.assertEqual(self.errors, [])

    def test_description_is_bilingual_draft_under_limit(self):
        description = self.metadata["description"]
        self.assertEqual(description["char_count"], 166)
        self.assertLessEqual(description["char_count"], description["max_chars"])
        self.assertIn("Chrome extension planned", description["text"])
        self.assertNotIn("可安装扩展已发布", description["text"])

    def test_topics_match_name_decision_draft(self):
        self.assertEqual(
            self.metadata["topics"],
            [
                "chrome-extension",
                "browser-extension",
                "github",
                "cross-language",
                "cross-lingual-search",
                "project-discovery",
                "readme-translation",
                "chinese",
                "english",
                "bring-your-own-key",
            ],
        )

    def test_license_page_keeps_options_undecided(self):
        text = (E8 / "license-options.md").read_text(encoding="utf-8")
        self.assertIn("待决策", text)
        self.assertIn("没有在仓库根目录添加 `LICENSE`", text)
        self.assertIn("建议不是决定", text)
        self.assertNotIn("已决定采用", text)
        self.assertNotIn("本轮决定采用", text)
        self.assertFalse((ROOT / "LICENSE").exists())
        self.assertFalse((ROOT / "NOTICE").exists())

    def test_retest_record_says_not_run(self):
        text = (E8 / "2026-09-22-retest-prepared.md").read_text(encoding="utf-8")
        self.assertIn("未运行", text)
        self.assertIn("applied_to_github", text)
        self.assertIn("不是零结果", text)
        self.assertNotIn("total_count", text)
        probe = (E8 / "2026-09-17-probe.md").read_text(encoding="utf-8")
        earlier = (E8 / "2026-09-18-retest.md").read_text(encoding="utf-8")
        self.assertIn("简介为空", probe)
        self.assertIn("HTTP 403", earlier)

    def test_plan_prints_without_network_or_secrets(self):
        source = (SCRIPTS / "e8_materials.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertFalse(any(name.split(".")[0] in {"requests", "httpx", "urllib3"} for name in imported))
        self.assertNotIn("urlopen", source)
        self.assertNotIn("GITHUB_TOKEN", source)
        self.assertNotIn("OPENAI_API_KEY", source)

        plan = e8_materials.build_plan(self.metadata, self.queries)
        self.assertEqual(plan["mode"], "plan-only")
        self.assertEqual(plan["live_requests"], 0)
        self.assertFalse(plan["metadata_applied"])
        self.assertEqual(len(plan["items"]), len(self.queries))
        self.assertTrue(all(item["executed"] is False and item["status"] == "未运行" for item in plan["items"]))
        rest = next(item for item in plan["items"] if item["query_id"] == "gh-api-zh-name-purpose")
        self.assertEqual(
            rest["url"],
            "https://api.github.com/search/repositories?q=%E9%BB%84%E9%87%91%E7%9F%BF%E5%B7%A5%20%E8%B7%A8%E8%AF%AD%E8%A8%80&per_page=20",
        )
        web = next(item for item in plan["items"] if item["query_id"] == "web-zh-purpose")
        self.assertIsNone(web["url"])
        self.assertEqual(web["method"], "manual")

        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "e8_materials.py"), "--live"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("未运行", completed.stderr)

        printed = subprocess.run(
            [sys.executable, str(SCRIPTS / "e8_materials.py")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(printed.returncode, 0, printed.stderr)
        payload = json.loads(printed.stdout)
        self.assertEqual(payload["live_requests"], 0)
        self.assertEqual(len(payload["items"]), 23)


if __name__ == "__main__":
    unittest.main()
