"""E3 检查的离线测试。不访问网络。"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e3_check

E3_DIR = Path(__file__).resolve().parent
RUN_DIR = E3_DIR / "runs" / "2026-09-22-w6"
PING = (
    b'[[["connection detection","\xe8\xbf\x9e\xe6\x8e\xa5\xe6\x8e\xa2\xe6\xb5\x8b",'
    b"null,null,3]],null,\"zh-CN\"]"
)


def fragment(**overrides):
    row = {
        "frag_id": "P-01",
        "source_repo": "example/repo",
        "source_sha": "a" * 40,
        "source_path": "README.md",
        "source_kind": "readme",
        "line_start": 1,
        "line_end": 1,
        "source_url": "https://example.test/readme",
        "lang_pair": "zh→en",
        "source_lang": "zh-CN",
        "target_lang": "en",
        "categories": ["术语", "否定"],
        "source_text": "不要同时安装",
        "must_keep": [],
        "risk_note": "否定在不要",
        "frozen_at": "2026-09-22T00:00:00Z",
    }
    row.update(overrides)
    return row


def judgment(**overrides):
    row = {
        "frag_id": "P-01",
        "terminology_kept": "yes",
        "polarity_kept": "yes",
        "limit_kept": "不适用",
        "code_intact": "不适用",
        "discussion_kept": "不适用",
        "severe_mistranslation": "no",
        "changes_understanding": "no",
        "error_location": "无",
        "judge": "test",
        "judged_at": "2026-09-22T00:00:02Z",
        "notes": "",
    }
    row.update(overrides)
    return row


class ParseGtxTest(unittest.TestCase):
    def test_ping_fixture_joins_first_segment(self):
        self.assertEqual(e3_check.parse_gtx_body(PING), "connection detection")

    def test_multiple_segments_are_concatenated(self):
        body = json.dumps([[["Hello ", "你"], ["world", "好"]]]).encode()
        self.assertEqual(e3_check.parse_gtx_body(body), "Hello world")

    def test_bad_json_raises(self):
        with self.assertRaises(ValueError):
            e3_check.parse_gtx_body(b"not-json")


class TranslateOneTest(unittest.TestCase):
    def test_http_get_is_used_and_output_recorded(self):
        calls = []

        def http_get(url, timeout):
            calls.append((url, timeout))
            body = json.dumps([[["do not install both", "不要同时安装"]]]).encode()
            return 200, body

        row = e3_check.translate_one(fragment(), http_get, timeout=3)
        self.assertEqual(len(calls), 1)
        self.assertIn("client=gtx", calls[0][0])
        self.assertEqual(row["translation_output"], "do not install both")
        self.assertEqual(row["error_class"], "无")
        self.assertIsInstance(row["elapsed_ms"], int)
        self.assertGreaterEqual(row["fetched_at"], "2026-09-22T00:00:00Z")

    def test_http_error_does_not_invent_translation(self):
        def http_get(url, timeout):
            return 429, b"no"

        row = e3_check.translate_one(fragment(), http_get)
        self.assertEqual(row["translation_output"], "未运行")
        self.assertEqual(row["error_class"], "网络")
        self.assertEqual(row["http_status"], 429)

    def test_exception_is_network_and_not_a_translation(self):
        def http_get(url, timeout):
            raise TimeoutError("slow")

        row = e3_check.translate_one(fragment(), http_get)
        self.assertEqual(row["translation_output"], "未运行")
        self.assertEqual(row["error_class"], "网络")
        self.assertIsNone(row["http_status"])


class JudgmentRuleTest(unittest.TestCase):
    def test_missing_translation_cannot_claim_a_gap(self):
        frag = fragment()
        translation = e3_check.translate_one(frag, lambda url, timeout: (500, b""))
        bad = judgment(
            terminology_kept="未运行",
            polarity_kept="未运行",
            severe_mistranslation="yes",
            changes_understanding="yes",
            error_location="臆造",
        )
        with self.assertRaises(ValueError):
            e3_check.join_records([frag], [translation], [bad])

    def test_code_intact_yes_requires_must_keep(self):
        frag = fragment(categories=["代码"], must_keep=["requests.get"], source_text="requests.get")
        translation = {
            "frag_id": "P-01",
            "source_text": frag["source_text"],
            "source_sha256": e3_check.sha256_text(frag["source_text"]),
            "tool": e3_check.TOOL_NAME,
            "tool_version": "未知",
            "endpoint_host": e3_check.ENDPOINT_HOST,
            "client": "gtx",
            "lang_pair": "zh→en",
            "http_status": 200,
            "elapsed_ms": 5,
            "error_class": "无",
            "translation_output": "请求获取",
            "error_detail": "",
            "fetched_at": "2026-09-22T00:00:01Z",
            "attempted": True,
        }
        bad = judgment(code_intact="yes", error_location="无")
        with self.assertRaises(ValueError):
            e3_check.join_records([frag], [translation], [bad])

    def test_gap_requires_location(self):
        frag = fragment()
        translation = e3_check.translate_one(
            frag, lambda url, timeout: (200, json.dumps([[["install both"]]]).encode())
        )
        bad = judgment(polarity_kept="no", error_location="无", severe_mistranslation="yes", changes_understanding="yes")
        with self.assertRaises(ValueError):
            e3_check.join_records([frag], [translation], [bad])


class CommittedRunTest(unittest.TestCase):
    def test_frozen_run_joins_and_has_no_secrets(self):
        fragments = e3_check.load_jsonl(str(RUN_DIR / "fragments.jsonl"))
        translations = e3_check.load_jsonl(str(RUN_DIR / "translations.jsonl"))
        judgments = e3_check.load_jsonl(str(RUN_DIR / "judgments.jsonl"))
        observations = e3_check.load_jsonl(str(RUN_DIR / "observations.jsonl"))
        e3_check.validate_fragment_set(fragments)
        joined = e3_check.join_records(fragments, translations, judgments)
        self.assertEqual(joined, observations)
        translated_by_id = {row["frag_id"]: row for row in translations}
        for frag in fragments:
            translated = translated_by_id[frag["frag_id"]]
            self.assertGreaterEqual(translated["fetched_at"], frag["frozen_at"])
            self.assertEqual(translated["tool"], "google-translate-gtx")
            for token in frag["must_keep"]:
                self.assertIn(token, frag["source_text"])
        blob = (RUN_DIR / "observations.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("sk-", blob)
        self.assertNotIn("ghp_", blob)
        self.assertNotIn("github_pat_", blob)
        manifest = json.loads((RUN_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["baseline_tool_status"], "未运行")
        self.assertEqual(manifest["chrome_ui_status"], "未运行")
        self.assertEqual(manifest["paid_model_requests"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
