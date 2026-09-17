"""W1 材料完整性检查，可直接运行，不访问网络。

依据：docs/backlog.md W1、docs/plan/v0.4.md W1 与第 10 节、
experiments/E1-cross-language-search/protocol.md 第 2/4/5 节、
experiments/E2-open-ended-discovery/protocol.md 第 2 节。

运行：
  python3 experiments/E1-cross-language-search/scripts/test_w1_materials.py
  python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"

检查只断言“材料已固定且如实标未运行”，不产生任何效果结论。
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / "experiments" / "E1-cross-language-search"
E2 = ROOT / "experiments" / "E2-open-ended-discovery"
QUERIES = E1 / "queries.yaml"
READING = E1 / "reading-baseline.md"
GUIDE = E1 / "judgment-guide.md"
SETTINGS = E1 / "run-settings.json"
SEED_DRAFT = E1 / "seed-tasks.draft.yaml"
SESSION = E2 / "session-setup.md"

REQUIRED_QUERY_FIELDS = ("id", "direction", "type", "query", "need", "written_at")
ALLOWED_DIRECTIONS = {"zh2en", "en2zh"}
ALLOWED_TYPES = {"term", "uncovered", "ambiguous", "negation", "long"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_simple_queries(text: str):
    """极简 YAML 子集解析：只提取 dev/eval.batch_1 条目的标量字段。

    不依赖 pyyaml；严格程度低于完整 YAML 解析，足以检查分离性与必填字段。
    若 queries.yaml 缩进结构被破坏，本函数可能少提条目并导致测试失败，
    属预期行为（失败即提示人工检查）。
    """
    entries = []
    current = None
    section = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped == "dev:":
            section = "dev"
            continue
        if stripped == "eval:":
            section = "eval"
            continue
        if stripped == "batch_1:":
            section = "batch_1"
            continue
        m = re.match(r"^(\s*)-\s+id:\s*(\S+)\s*$", raw)
        if m:
            if current is not None:
                entries.append((section, current))
            current = {"id": m.group(2)}
            continue
        if current is not None:
            fm = re.match(r"^\s+(direction|type|query|need|written_at):\s*(.+?)\s*$", raw)
            if fm:
                current[fm.group(1)] = fm.group(2)
    if current is not None:
        entries.append((section, current))
    dev = [e for s, e in entries if s == "dev"]
    eval_entries = [e for s, e in entries if s == "batch_1"]
    return dev, eval_entries


def scan_secrets(text: str) -> list:
    hits = []
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


class TestW1Queries(unittest.TestCase):
    def test_queries_file_exists(self):
        self.assertTrue(QUERIES.is_file(), "queries.yaml 缺失")

    def test_dev_eval_separated(self):
        dev, eval_entries = parse_simple_queries(read_text(QUERIES))
        self.assertGreaterEqual(len(dev), 1, "dev 题缺失")
        self.assertGreaterEqual(len(eval_entries), 1, "eval.batch_1 缺失")
        dev_ids = {e.get("id") for e in dev}
        eval_ids = {e.get("id") for e in eval_entries}
        self.assertTrue(all(i for i in dev_ids), "dev 存在空 id")
        self.assertTrue(all(i for i in eval_ids), "eval 存在空 id")
        self.assertEqual(len(eval_ids), len(eval_entries), "eval id 重复")
        self.assertFalse(dev_ids & eval_ids, "dev 与 eval id 必须互不重复")

    def test_eval_covers_directions_and_types(self):
        _, eval_entries = parse_simple_queries(read_text(QUERIES))
        for e in eval_entries:
            for f in REQUIRED_QUERY_FIELDS:
                self.assertIn(f, e, f"eval 条目缺少字段 {f}: {e.get('id')}")
            self.assertIn(e["direction"], ALLOWED_DIRECTIONS)
            self.assertIn(e["type"], ALLOWED_TYPES)
        dirs = {e["direction"] for e in eval_entries}
        self.assertEqual(dirs, ALLOWED_DIRECTIONS, "eval 须覆盖 zh2en 与 en2zh")
        types = {e["type"] for e in eval_entries}
        self.assertTrue(
            {"term", "uncovered", "ambiguous", "negation", "long"} <= types,
            f"eval 须覆盖五类，实际 {sorted(types)}",
        )

    def test_eval_not_frozen_yet(self):
        text = read_text(QUERIES)
        self.assertIn("eval_frozen_commit: null", text)


class TestW1ReadingAndGuide(unittest.TestCase):
    def test_reading_baseline_fixed_but_not_run(self):
        self.assertTrue(READING.is_file())
        text = read_text(READING)
        self.assertIn("未运行", text)
        self.assertIn("沉浸式翻译", text)
        self.assertIn("回查原文", text)
        self.assertFalse(scan_secrets(text), "阅读基线不得含密钥")

    def test_judgment_guide_fields(self):
        self.assertTrue(GUIDE.is_file())
        text = read_text(GUIDE)
        for field in (
            "purpose_fit",
            "hard_conditions",
            "kind",
            "novel_to_judge",
            "judge",
            "judged_at",
        ):
            self.assertIn(field, text, f"判定口径缺少字段 {field}")
        self.assertIn("未运行", text)


class TestW1RunSettings(unittest.TestCase):
    def test_valid_json_and_budgets(self):
        self.assertTrue(SETTINGS.is_file())
        data = json.loads(read_text(SETTINGS))
        self.assertEqual(data.get("protocol_version"), "v0.4")
        budget = data["budget"]
        self.assertEqual(budget["A"]["max_github_requests"], 1)
        self.assertEqual(budget["B"]["max_github_requests"], 2)
        self.assertEqual(budget["C"]["max_github_requests"], 4)
        self.assertEqual(budget["M"]["max_github_requests"], 4)
        # 模型预算与 prompts/README 必须一致：A 0、B/C/M 各最多 1 次。
        self.assertEqual(budget["A"]["max_model_requests"], 0)
        self.assertEqual(budget["B"]["max_model_requests"], 1)
        self.assertEqual(budget["C"]["max_model_requests"], 1)
        self.assertEqual(budget["M"]["max_model_requests"], 1)
        self.assertEqual(data["candidate_merge"]["per_query_top_n"], 30)
        self.assertEqual(data["candidate_merge"]["truncate_merged_top_n"], 30)
        self.assertEqual(data["judgment_window"]["human_check_top_k_per_group"], 5)
        self.assertEqual(data["freeze"]["status"], "unfrozen-no-run")
        self.assertIn("recorded-not-used", data.get("reading_setup_status", ""))
        self.assertFalse(scan_secrets(read_text(SETTINGS)))

    def test_no_real_model_configured(self):
        data = json.loads(read_text(SETTINGS))
        self.assertIsNone(data["model"].get("concrete_model_id"))

    def test_all_freeze_markers_unfrozen(self):
        text = read_text(QUERIES)
        for key in (
            "eval_frozen_commit: null",
            "prompts_frozen_commit: null",
            "seed_set_frozen_commit: null",
            "run_settings_commit: null",
        ):
            self.assertIn(key, text, f"queries.yaml 缺少未冻结标记 {key}")
        data = json.loads(read_text(SETTINGS))
        for key in (
            "eval_frozen_commit",
            "prompts_frozen_commit",
            "seed_set_frozen_commit",
            "run_settings_commit",
        ):
            self.assertIsNone(
                data["freeze"].get(key), f"run-settings {key} 应为 null（未冻结）"
            )


class TestW1SeedDraft(unittest.TestCase):
    def test_draft_separate_and_unverified(self):
        self.assertTrue(SEED_DRAFT.is_file())
        text = read_text(SEED_DRAFT)
        self.assertIn("draft-unfrozen", text)
        self.assertIn("未运行", text)
        self.assertIn("entries: []", text)
        # 草案不得以字段赋值形式声称冻结时间戳（正文提及字段名允许）。
        field_lines = [
            ln for ln in text.splitlines() if re.match(r"^\s*frozen_at\s*:", ln)
        ]
        self.assertFalse(field_lines, f"草案不得含 frozen_at 字段赋值: {field_lines}")
        self.assertIn("repo: null", text)


class TestW1E2Session(unittest.TestCase):
    def test_session_setup_not_run(self):
        self.assertTrue(SESSION.is_file())
        text = read_text(SESSION)
        self.assertIn("未运行", text)
        self.assertIn("10–15 分钟", text)
        self.assertIn("人工准备时间单独记录", text)


class TestW1NoSecrets(unittest.TestCase):
    def test_w1_files_have_no_keys(self):
        for path in (READING, GUIDE, SETTINGS, SEED_DRAFT, SESSION, QUERIES):
            hits = scan_secrets(read_text(path))
            self.assertFalse(hits, f"{path.name} 疑似含密钥模式: {hits}")


class TestW1Consistency(unittest.TestCase):
    """跨文件一致性：预算、节号、schema 与证据路径必须对齐。"""

    def test_candidates_schema_arms(self):
        schema_path = E1 / "schemas" / "candidates.schema.json"
        schema = json.loads(read_text(schema_path))
        self.assertEqual(
            set(schema["properties"]["arm"]["enum"]), {"A", "B", "C", "M"}
        )
        self.assertIn("第 5 节", schema["description"])
        self.assertNotIn("第 7 节", schema["description"])

    def test_judgments_schema_fields(self):
        schema_path = E1 / "schemas" / "judgments.schema.json"
        schema = json.loads(read_text(schema_path))
        for field in ("worth_following", "reason"):
            self.assertIn(
                field, schema["properties"], f"judgments 缺少协议第 5 节字段 {field}"
            )
            self.assertIn(
                field, schema["required"], f"judgments required 缺少 {field}"
            )
        self.assertIn("第 5 节", schema["description"])
        self.assertNotIn("第 7 节", schema["description"])

    def test_prompts_readme_budgets_and_sections(self):
        text = read_text(E1 / "prompts" / "README.md")
        self.assertIn("第 3 节", text)
        self.assertIn("最多 2 次 Search API 调用、最多 1 次模型调用", text)
        self.assertIn("最多 4 次 Search API 调用、最多 1 次模型调用", text)
        self.assertNotIn("最多 5 次", text)
        self.assertNotIn("最多 2 次模型调用", text)

    def test_runs_readme_sections(self):
        text = read_text(E1 / "runs" / "README.md")
        self.assertIn("第 5 节", text)
        self.assertNotIn("依据 protocol.md 第 11 节", text)
        self.assertNotIn("第 7 节），一行一条", text)

    def test_backlog_evidence_paths(self):
        text = read_text(ROOT / "docs" / "backlog.md")
        for path in (
            "experiments/E1-cross-language-search/w2-source-check-2026-09-17.md",
            "experiments/E1-cross-language-search/scripts/e1_minimal_runner.py",
            "experiments/E1-cross-language-search/w4-first-round-status-2026-09-17.md",
            "experiments/E2-open-ended-discovery/session-setup.md",
        ):
            self.assertIn(path, text, f"backlog 证据路径缺失或非全路径: {path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
