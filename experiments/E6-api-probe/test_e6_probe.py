"""E6 探测记录测试。不访问真实模型。"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e6_probe

RUN_PATH = Path(__file__).resolve().parent / "runs" / "2026-09-22-w6" / "probe.jsonl"
SECRET = "sk-test-secret-value"


def env_ready():
    return {
        "OPENAI_API_KEY": SECRET,
        "OPENAI_BASE_URL": "https://user:pw@example.test/v1",
        "OPENAI_MODEL": "demo-model",
        "GITHUB_TOKEN": "ghp_should_not_be_written",
    }


def chat_body(content="pong", usage=None, echo_key=False):
    if echo_key:
        content = "key " + SECRET
    payload = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": content}}],
    }
    if usage is not None:
        payload["usage"] = usage
    return 200, json.dumps(payload).encode()


class NotSentTest(unittest.TestCase):
    def test_missing_config_does_not_call(self):
        calls = []

        def http_post(*args):
            calls.append(args)
            return chat_body()

        record = e6_probe.probe(http_post=http_post, env={}, run_id="t")
        e6_probe.validate_record(record)
        self.assertEqual(calls, [])
        self.assertEqual(record["status"], "未运行")
        self.assertEqual(record["error_class"], "未配置")
        self.assertEqual(record["elapsed_ms"], "未知")
        self.assertEqual(record["usage_total_tokens"], "未知")
        self.assertEqual(record["model_output"], "未运行")
        self.assertEqual(record["actual_requests"], 0)

    def test_partial_config_does_not_call(self):
        calls = []
        record = e6_probe.probe(
            http_post=lambda *a: calls.append(a),
            env={"OPENAI_API_KEY": SECRET},
            run_id="t",
        )
        self.assertEqual(calls, [])
        self.assertEqual(record["error_class"], "未配置")
        self.assertNotIn(SECRET, json.dumps(record))

    def test_cancel_before_send(self):
        calls = []
        record = e6_probe.probe(
            http_post=lambda *a: calls.append(a) or chat_body(),
            env=env_ready(),
            should_cancel=lambda: True,
            run_id="t",
        )
        e6_probe.validate_record(record)
        self.assertEqual(calls, [])
        self.assertEqual(record["status"], "取消")
        self.assertEqual(record["billing_note"], "未发送请求，本次零费用")
        self.assertNotIn("pw@", record["base_url"])
        self.assertNotIn(SECRET, json.dumps(record))

    def test_zero_budget_does_not_call(self):
        calls = []
        record = e6_probe.probe(
            http_post=lambda *a: calls.append(a),
            env=env_ready(),
            request_budget=0,
            run_id="t",
        )
        self.assertEqual(calls, [])
        self.assertEqual(record["error_class"], "预算")


class SentTest(unittest.TestCase):
    def test_success_records_usage_and_strips_secret(self):
        def http_post(url, headers, payload, timeout):
            self.assertNotIn(SECRET, url)
            self.assertEqual(payload["max_tokens"], 16)
            self.assertEqual(headers["Authorization"], "Bearer " + SECRET)
            return chat_body(
                usage={"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
                echo_key=True,
            )

        record = e6_probe.probe(http_post=http_post, env=env_ready(), run_id="t")
        e6_probe.validate_record(record)
        self.assertEqual(record["status"], "已运行")
        self.assertEqual(record["usage_total_tokens"], 4)
        self.assertEqual(record["elapsed_ms"] >= 0, True)
        self.assertIsInstance(record["elapsed_ms"], int)
        self.assertEqual(record["visible_response_id"], "chatcmpl-test")
        self.assertIn("[redacted]", record["model_output"])
        self.assertNotIn(SECRET, json.dumps(record))
        self.assertNotIn("ghp_should_not_be_written", json.dumps(record))
        self.assertEqual(record["base_url"], "https://example.test/v1")
        self.assertEqual(record["retries"], 0)
        self.assertIn("已发送请求可能已计费", record["billing_note"])

    def test_missing_usage_stays_unknown(self):
        record = e6_probe.probe(
            http_post=lambda *a: chat_body(usage=None),
            env=env_ready(),
            run_id="t",
        )
        self.assertEqual(record["status"], "已运行")
        self.assertEqual(record["usage_prompt_tokens"], "未知")
        self.assertEqual(record["usage_completion_tokens"], "未知")
        self.assertEqual(record["usage_total_tokens"], "未知")

    def test_401_is_credentials(self):
        record = e6_probe.probe(
            http_post=lambda *a: (401, b"{}"),
            env=env_ready(),
            run_id="t",
        )
        self.assertEqual(record["error_class"], "权限或凭据")
        self.assertEqual(record["model_output"], "未运行")
        self.assertEqual(record["sent_requests"], 1)

    def test_402_is_quota(self):
        record = e6_probe.probe(
            http_post=lambda *a: (402, b"{}"),
            env=env_ready(),
            run_id="t",
        )
        self.assertEqual(record["error_class"], "额度")

    def test_429_without_quota_word_is_rate_limit(self):
        record = e6_probe.probe(
            http_post=lambda *a: (429, b"slow down"),
            env=env_ready(),
            run_id="t",
        )
        self.assertEqual(record["error_class"], "限流")

    def test_429_quota_word_is_quota(self):
        record = e6_probe.probe(
            http_post=lambda *a: (429, b'{"error":"insufficient_quota"}'),
            env=env_ready(),
            run_id="t",
        )
        self.assertEqual(record["error_class"], "额度")

    def test_bad_json_is_format(self):
        record = e6_probe.probe(
            http_post=lambda *a: (200, b"<html>"),
            env=env_ready(),
            run_id="t",
        )
        self.assertEqual(record["error_class"], "响应格式")
        self.assertEqual(record["usage_total_tokens"], "未知")

    def test_timeout_counts_as_sent(self):
        def http_post(*args):
            raise TimeoutError("slow")

        record = e6_probe.probe(http_post=http_post, env=env_ready(), run_id="t")
        e6_probe.validate_record(record)
        self.assertEqual(record["error_class"], "网络")
        self.assertEqual(record["sent_requests"], 1)
        self.assertIsInstance(record["elapsed_ms"], int)

    def test_budget_above_one_rejected(self):
        with self.assertRaises(ValueError):
            e6_probe.probe(env=env_ready(), request_budget=2, run_id="t")


class CommittedProbeTest(unittest.TestCase):
    def test_this_run_is_unrun(self):
        text = RUN_PATH.read_text(encoding="utf-8")
        record = json.loads(text)
        e6_probe.validate_record(record)
        self.assertEqual(record["status"], "未运行")
        self.assertEqual(record["error_class"], "未配置")
        self.assertEqual(record["actual_requests"], 0)
        self.assertEqual(record["model_output"], "未运行")
        self.assertEqual(record["elapsed_ms"], "未知")
        self.assertFalse(record["env_openai_api_key_set"])
        self.assertFalse(record["env_openai_base_url_set"])
        self.assertFalse(record["env_openai_model_set"])
        self.assertNotIn("sk-", text)
        manifest = json.loads((RUN_PATH.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["personal_model_request"], "未运行")
        schema = json.loads(
            (Path(__file__).resolve().parent / "schemas" / "probe-record.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(record), set(schema["required"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
