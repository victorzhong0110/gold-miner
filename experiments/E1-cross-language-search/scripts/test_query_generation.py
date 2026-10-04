"""Offline tests for B/C/M query generation."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

E1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(E1 / "scripts"))
import query_generation as qg  # noqa: E402


class FakeClient:
    def generate_variants(self, task, arm, prompt):
        assert "用户原话" in prompt or "改写" in prompt
        return [
            {
                "variant_query": "injected clipboard manager",
                "variant_lang": "en",
                "api_query": "injected clipboard manager",
            }
        ]


class TestQueryGeneration(unittest.TestCase):
    def test_prompts_exist(self):
        for arm, path in qg.PROMPTS.items():
            self.assertTrue(path.is_file(), arm)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("TODO", text)

    def test_fixture_b_for_dev01(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "B", "fixture")
        self.assertEqual(row["code"], "ok")
        self.assertEqual(row["mode"], "fixture")
        self.assertGreaterEqual(len(row["variants"]), 1)
        self.assertTrue(row["prompt_sha256_16"])
        self.assertTrue(row["input_sha256_16"])

    def test_live_without_key_is_blocked(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "C", "live")
        self.assertEqual(row["code"], "owner_blocked")
        self.assertIn("未运行", row["notes"])
        self.assertEqual(row["variants"], [])

    def test_m_fixture_same_language(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "M", "fixture")
        langs = {v["variant_lang"] for v in row["variants"]}
        self.assertEqual(langs, {"zh"})

    def test_cli_fixture(self):
        code = qg.main(
            ["--task-id", "zh2en-dev-01", "--arm", "B", "--mode", "fixture"]
        )
        self.assertEqual(code, 0)

    def test_live_with_injected_client_uses_model(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "C", "live", client=FakeClient())
        self.assertEqual(row["code"], "ok")
        self.assertEqual(row["mode"], "live")
        self.assertEqual(row["variants"][0]["variant_query"], "injected clipboard manager")
        self.assertIn("live model client", row["notes"])
        blob = json.dumps(row, ensure_ascii=False)
        self.assertNotIn("sk-", blob)

    def test_live_with_key_still_blocked_without_allow_network(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        env = {
            "OPENAI_API_KEY": "mock-key-not-real",
            "OPENAI_BASE_URL": "https://example.test/v1",
            "OPENAI_MODEL": "mock-model",
        }
        with patch.dict(os.environ, env, clear=False):
            row = qg.generate(tasks["zh2en-dev-01"], "C", "live")
        self.assertEqual(row["code"], "owner_blocked")
        self.assertIn("allow_network", row["notes"])

    def test_allow_network_uses_injected_http_post(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        payload_seen = {}

        def fake_post(url, headers, payload, timeout):
            payload_seen["url"] = url
            payload_seen["headers"] = headers
            payload_seen["payload"] = payload
            content = json.dumps(
                {
                    "zh": ["剪贴板 历史"],
                    "en": ["clipboard history"],
                    "notes": "",
                },
                ensure_ascii=False,
            )
            return {
                "status": 200,
                "body": json.dumps({"choices": [{"message": {"content": content}}]}),
            }

        env = {
            "OPENAI_API_KEY": "mock-key-not-real",
            "OPENAI_BASE_URL": "https://example.test/v1",
            "OPENAI_MODEL": "mock-model",
        }
        with patch.dict(os.environ, env, clear=False):
            row = qg.generate(
                tasks["zh2en-dev-01"],
                "C",
                "live",
                allow_network=True,
                http_post=fake_post,
            )
        self.assertEqual(row["code"], "ok")
        self.assertEqual(row["variants"][0]["variant_query"], "剪贴板 历史")
        self.assertIn("example.test", payload_seen["url"])
        self.assertNotIn("mock-key-not-real", json.dumps(row, ensure_ascii=False))

    def test_parse_model_variants_b_c_m(self):
        b = qg.parse_model_variants(
            "B", "zh2en", '{"other_lang":"en","query":"clipboard history tool"}'
        )
        self.assertEqual(b[0]["variant_lang"], "en")
        c = qg.parse_model_variants(
            "C",
            "zh2en",
            '{"zh":["剪贴板"],"en":["clipboard"],"notes":""}',
        )
        self.assertEqual({v["variant_lang"] for v in c}, {"zh", "en"})
        m = qg.parse_model_variants(
            "M",
            "zh2en",
            '{"same_lang":"zh","queries":["剪贴板 历史"],"notes":""}',
        )
        self.assertEqual(m[0]["variant_lang"], "zh")


if __name__ == "__main__":
    unittest.main()


class ReasoningClientTests(unittest.TestCase):
    def test_thinking_json_and_shared_budget(self):
        task={"id":"test", "query":"剪贴板", "direction":"zh2en"}
        outputs={"B":'{"query":"clipboard","other_lang":"en"}',"C":'{"zh":["剪贴板"],"en":["clipboard"]}',"M":'{"queries":["剪贴板历史"],"same_lang":"zh"}'}
        for arm, output in outputs.items():
            def post(url,headers,payload,timeout):
                self.assertEqual(payload["max_tokens"],2048);self.assertEqual(timeout,60)
                return {"status":200,"body":json.dumps({"choices":[{"finish_reason":"stop","message":{"content":"<think>{irrelevant}</think>"+output}}]})}
            client=qg.HttpQueryClient(post,base_url="https://fixture.example/v1",model="MiniMax-M3",api_key="fixture-key")
            row=qg.generate(task,arm,"live",client)
            self.assertEqual(row["code"],"ok");self.assertEqual(row["request_parameters"]["max_tokens"],2048)
            self.assertNotIn("fixture-key",json.dumps(row))

    def test_truncated_and_malformed_outputs_fail_without_retry(self):
        task={"id":"test","query":"q","direction":"zh2en"}
        for body, code in [({"choices":[{"finish_reason":"length","message":{"content":'{"query":"looks-valid"}'}}]},"model_output_truncated"),({"choices":[None]},"bad_response"),({"choices":{}},"bad_response"),({"base_resp":{"status_code":1004}},"auth_rejected"),({"choices":[{"message":{"content":None}}]},"empty_model_output")]:
            calls=[]
            def post(*args):calls.append(1);return {"status":200,"body":json.dumps(body)}
            client=qg.HttpQueryClient(post,base_url="https://fixture.example/v1",model="MiniMax-M3",api_key="fixture")
            row=qg.generate(task,"B","live",client);self.assertEqual(row["code"],code);self.assertEqual(len(calls),1)
            self.assertEqual(row["variants"],[])


class VisibleUsageTests(unittest.TestCase):
    def test_usage_and_elapsed_recorded_even_when_truncated(self):
        task = {"id": "test", "query": "q", "direction": "zh2en"}
        usage = {"prompt_tokens": 10, "completion_tokens": 2048, "total_tokens": 2058,
                 "completion_tokens_details": {"reasoning_tokens": 2000},
                 "prompt_tokens_details": {"cached_tokens": 4}}
        def post(*args):
            return {"status": 200, "body": json.dumps({"usage": usage, "choices": [
                {"finish_reason": "length", "message": {"content": "<think>..."}}]})}
        client = qg.HttpQueryClient(post, base_url="https://fixture.example/v1", model="MiniMax-M3", api_key="k")
        row = qg.generate(task, "B", "live", client)
        self.assertEqual(row["code"], "model_output_truncated")
        self.assertEqual(row["usage"], {"prompt_tokens": 10, "completion_tokens": 2048,
                                        "reasoning_tokens": 2000, "cached_prompt_tokens": 4,
                                        "total_tokens": 2058})
        self.assertIsInstance(row["elapsed_seconds"], float)

    def test_missing_usage_stays_none_not_zero(self):
        task = {"id": "test", "query": "q", "direction": "zh2en"}
        def post(*args):
            raise qg.QueryClientError("timeout", "model request timed out")
        client = qg.HttpQueryClient(post, base_url="https://fixture.example/v1", model="MiniMax-M3", api_key="k")
        row = qg.generate(task, "B", "live", client)
        self.assertEqual(row["code"], "timeout")
        self.assertIsNone(row["usage"])


class FailureEvidenceTests(unittest.TestCase):
    """A failed model call must leave enough evidence to diagnose it.

    On 2026-10-04 the C arm failed at en2zh-eval-03 with "model output JSON
    parse failed" and no stored output, so the reply was unrecoverable: the
    protocol forbids re-driving a failed item into the same batch, and nothing
    recorded whether it was prose-wrapped JSON, a schema mismatch or a refusal.
    These tests pin the fix.
    """

    def _client(self, content, finish="stop"):
        def post(*args):
            return {"status": 200, "body": json.dumps({"choices": [
                {"finish_reason": finish, "message": {"content": content}}]})}
        return qg.HttpQueryClient(post, base_url="https://fixture.example/v1",
                                  model="MiniMax-M3", api_key="k")

    def _row(self, content, arm="C", finish="stop"):
        task = {"id": "en2zh-eval-03", "query": "weekly report generator", "direction": "en2zh"}
        return qg.generate(task, arm, "live", self._client(content, finish))

    def test_parse_failure_records_the_model_reply(self):
        row = self._row("<think>let me think about {} braces</think>Sorry, I cannot help.")
        self.assertEqual(row["code"], "bad_response")
        self.assertEqual(row["variants"], [])
        # The evidence that was previously thrown away.
        self.assertIn("cannot help", row["answer_text"])
        self.assertIn("raw_output_chars", row)
        self.assertTrue(row["think_present"])
        self.assertEqual(len(row["raw_output_sha256"]), 64)

    def test_truncated_output_keeps_how_far_the_model_got(self):
        row = self._row('<think>reasoning</think>{"zh": ["a', finish="length")
        self.assertEqual(row["code"], "model_output_truncated")
        self.assertIn('"zh": ["a', row["raw_output"])
        self.assertEqual(row["answer_text"], '{"zh": ["a')

    def test_empty_answer_is_recorded_without_inventing_text(self):
        row = self._row("")
        self.assertEqual(row["code"], "empty_model_output")
        self.assertEqual(row["variants"], [])

    def test_model_output_that_parsed_keeps_no_raw_copy(self):
        row = self._row('<think>t</think>{"zh":["报表生成器"],"en":["weekly report generator"]}')
        self.assertEqual(row["code"], "ok")
        self.assertEqual(len(row["variants"]), 2)
        # A successful row stays small; the raw copy exists only to debug failures.
        for key in ("raw_output", "answer_text", "raw_output_sha256"):
            self.assertNotIn(key, row)

    def test_recorded_output_is_scrubbed_and_bounded(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-abcdefghijklmnop"}):
            row = self._row("<think>t</think>here is sk-abcdefghijklmnop and Bearer abc.def-123")
        self.assertNotIn("sk-abcdefghijklmnop", json.dumps(row, ensure_ascii=False))
        self.assertNotIn("abc.def-123", json.dumps(row, ensure_ascii=False))
        self.assertIn("[redacted]", row["answer_text"])

    def test_oversized_output_records_a_hash_but_not_the_body(self):
        row = self._row("x" * (qg.RAW_CAPTURE_LIMIT + 10))
        self.assertNotIn("raw_output", row)
        self.assertEqual(row["raw_output_chars"], qg.RAW_CAPTURE_LIMIT + 10)
        self.assertEqual(len(row["raw_output_sha256"]), 64)

    def test_strip_think_matches_the_parser_rule(self):
        self.assertEqual(qg._strip_think('<think>a{}b</think>{"zh":["x"]}'), '{"zh":["x"]}')
        self.assertEqual(qg._strip_think("<think>never closed"), "")


class StrictParserTests(unittest.TestCase):
    """The prompts forbid prose around the JSON, so the parser stays strict.

    Recorded here because a strict parser plus a lost raw output made the
    2026-10-04 failure uninvestigable. Now that the reply is stored, a stray
    brace is diagnosable rather than mysterious.
    """

    def test_prose_example_object_is_refused_not_recorded_as_a_query(self):
        # find("{")/rfind("}") spans from the first "{" to the last "}", so a
        # reply with an example object plus a real one could put either into
        # the candidate set with no trace of which was intended.
        reply = 'Example: {"zh":["demo"]} and my answer: {"zh":["报表生成器"]}'
        with self.assertRaises(qg.QueryClientError) as ctx:
            qg.parse_model_variants("C", "en2zh", reply)
        self.assertEqual(ctx.exception.code, "ambiguous_model_output")
        self.assertIn("2 JSON objects", ctx.exception.notes)

    def test_single_example_object_inside_prose_is_refused(self):
        with self.assertRaises(qg.QueryClientError) as ctx:
            qg.parse_model_variants("C", "en2zh", 'Example: {"zh":["demo"]} but I cannot answer')
        self.assertEqual(ctx.exception.code, 'ambiguous_model_output')

    def test_brace_counting_ignores_braces_inside_strings(self):
        self.assertEqual(
            len(qg._top_level_brace_groups('{"zh":["a } b"],"en":[]}')), 1
        )
        self.assertEqual(
            len(qg._top_level_brace_groups('{"a":"\\""} {"b":"x"}')), 2
        )
        self.assertEqual(qg._top_level_brace_groups('{"unclosed": "x"'), [])

    def test_only_json_or_json_fence_is_accepted(self):
        rows = qg.parse_model_variants("C", "en2zh", '```json\n{"zh":["报表"],"en":["report"]}\n```')
        self.assertEqual([r["variant_query"] for r in rows], ["报表", "report"])
        for text in ['Here: {"zh":["报表"]} done', '[{"zh":["报表"]}]', '{"zh":["报表"]} {']:
            with self.assertRaises(qg.QueryClientError): qg.parse_model_variants('C', 'en2zh', text)

    def test_client_credential_not_in_environment_is_redacted_before_excerpt(self):
        secret = 'fixture-private-credential-with-no-prefix'
        def post(*args):
            return {'status': 200, 'body': json.dumps({'choices': [{'finish_reason': 'stop',
                'message': {'content': 'rejected ' + secret}}]})}
        client = qg.HttpQueryClient(post, base_url='https://fixture.test/v1', model='fixture', api_key=secret)
        row = qg.generate({'id': 'fixture', 'query': 'report', 'direction': 'en2zh'}, 'C', 'live', client)
        self.assertNotIn(secret, json.dumps(row))
        self.assertIn('[redacted]', row['raw_output'])

    def test_length_with_no_content_is_still_truncated(self):
        def post(*args):
            return {'status': 200, 'body': json.dumps({'choices': [{'finish_reason': 'length', 'message': {'content': ''}}]})}
        client = qg.HttpQueryClient(post, base_url='https://fixture.test/v1', model='fixture', api_key='fixture')
        row = qg.generate({'id': 'fixture', 'query': 'report', 'direction': 'en2zh'}, 'C', 'live', client)
        self.assertEqual(row['code'], 'model_output_truncated')
