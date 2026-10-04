"""D-group assistant runner tests. No network."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_d_assistant as d

PROMPT = d.PROMPT_PATH.read_text(encoding="utf-8")


def task(task_id: str, query: str, direction: str = "zh2en") -> dict:
    return {
        "id": task_id,
        "direction": direction,
        "type": "term",
        "query": query,
        "need": "test",
        "written_at": "2026-09-18",
    }


def model_response(text: str, *, searches=None, status=200, business=0, usage=None) -> dict:
    body = {
        "status": "completed",
        "model": "MiniMax-M3",
        "output_text": text,
        "output": [
            {
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": q},
            }
            for q in (searches or [])
        ]
        + [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": usage
        or {"input_tokens": 20, "output_tokens": 30, "total_tokens": 50},
        "base_resp": {"status_code": business, "status_msg": ""},
    }
    return {"status": status, "body": json.dumps(body, ensure_ascii=False), "retry_after": None}


def github_body(full_name: str, stars: int) -> str:
    return json.dumps(
        {
            "full_name": full_name,
            "stargazers_count": stars,
            "private": False,
            "description": "public",
        }
    )


class ParseTests(unittest.TestCase):
    def test_render_replaces_placeholder_once(self):
        rendered = d.render_prompt(PROMPT, "局域网文件互传 工具")
        self.assertNotIn(d.PLACEHOLDER, rendered)
        self.assertIn("局域网文件互传 工具", rendered)
        self.assertEqual(rendered.count("局域网文件互传 工具"), 1)

    def test_strip_think_and_parse_list(self):
        text = "<think>looking up repos</think>\npreamble\nfoo/bar\n- baz/qux\n\nexplanation mentions no more\n"
        parsed = d.parse_assistant_repos(text)
        self.assertEqual(parsed["repos"], ["foo/bar", "baz/qux"])

    def test_cap_and_github_url(self):
        lines = [f"https://github.com/o{i}/r{i}" for i in range(12)]
        parsed = d.parse_assistant_repos("\n".join(lines))
        self.assertEqual(len(parsed["repos"]), 10)
        self.assertEqual(parsed["ignored_over_cap"], 2)
        self.assertEqual(parsed["repos"][0], "o0/r0")

    def test_explanation_stops_list(self):
        parsed = d.parse_assistant_repos("a/b\nthis is an explanation\nc/d\n")
        self.assertEqual(parsed["repos"], ["a/b"])


class ClassifyTests(unittest.TestCase):
    def test_quota_business_code(self):
        body = json.dumps({"base_resp": {"status_code": 2056, "status_msg": "超出M Plan资源限制"}})
        self.assertEqual(d.classify_model_response(200, body)["code"], "quota_limited")

    def test_auth(self):
        body = json.dumps({"base_resp": {"status_code": 1004, "status_msg": "auth"}})
        self.assertEqual(d.classify_model_response(401, body)["code"], "auth_rejected")

    def test_ok_extracts_search(self):
        packed = model_response("<think>secret-thought</think>\nowner/repo\n", searches=["lan file transfer"])
        classified = d.classify_model_response(packed["status"], packed["body"])
        self.assertEqual(classified["code"], "ok")
        answer = d.strip_think(d.extract_answer(classified["parsed"]))
        self.assertNotIn("secret-thought", answer)
        self.assertEqual(d.extract_search_calls(classified["parsed"])[0]["query"], "lan file transfer")

    def test_unknown_max_tokens_is_bad_response_not_tool(self):
        body = json.dumps(
            {
                "base_resp": {
                    "status_code": 2013,
                    "status_msg": "unknown parameter max_output_tokens",
                }
            }
        )
        self.assertEqual(d.classify_model_response(400, body)["code"], "bad_response")


class RunTests(unittest.TestCase):
    def test_live_without_key_does_not_call(self):
        import os
        saved = {k: os.environ.get(k) for k in ("OPENAI_API_KEY", "MINIMAX_API_KEY", "OPENAI_MODEL")}
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("MINIMAX_API_KEY", None)
            os.environ["OPENAI_MODEL"] = "MiniMax-M3"
            code = d.main(["--live", "--out", "/tmp/e1-d-should-not", "--run-id", "t"])
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.assertEqual(code, 2)

    def test_without_live_is_not_a_run(self):
        code = d.main(["--out", "/tmp/e1-d-should-not"])
        self.assertEqual(code, 2)

    def test_existing_and_hallucination(self):
        posts = []

        def http_post(url, headers, payload, timeout):
            posts.append(url)
            self.assertNotIn("api_key", json.dumps(payload))
            self.assertIn("/responses", url)
            self.assertEqual(payload["tools"], [{"type": "web_search"}])
            self.assertEqual(payload["max_output_tokens"], d.MAX_OUTPUT_TOKENS)
            self.assertNotIn(headers["Authorization"], json.dumps(payload))
            return model_response(
                "<think>hidden</think>\nreal/repo\nghost/none\n",
                searches=["clipboard"],
            )

        def github_get(url, headers, timeout):
            if url.endswith("/real/repo"):
                return {"status": 200, "body": github_body("Real/Repo", 3), "headers": {}}
            if url.endswith("/ghost/none"):
                return {"status": 404, "body": "{}", "headers": {}}
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = d.run_d_group(
                out_dir=out,
                tasks=[task("zh2en-eval-01", "局域网文件互传 工具")],
                run_id="test-d",
                base_url="https://api.minimax.cn/v1",
                model="MiniMax-M3",
                api_key="sk-testkeyvalue",
                github_token="ghp_testtokenvalue",
                prompt_template=PROMPT,
                http_post=http_post,
                github_get=github_get,
                sleep=lambda _s: None,
                github_sleep_seconds=0,
                materials="abc",
                seeds={"real/repo"},
                historical_a=[
                    {
                        "arm": "A",
                        "task_id": "zh2en-eval-01",
                        "repo": "real/repo",
                    }
                ],
            )
            self.assertEqual(result["code"], "ok")
            text = (out / "candidates.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("sk-testkeyvalue", text)
            call_text = (out / "model_calls.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("ghp_testtokenvalue", call_text)
            self.assertNotIn("sk-testkeyvalue", call_text)
            answer = json.loads(call_text.splitlines()[-1])
            self.assertNotIn("hidden", answer["answer_text"])
            self.assertTrue(answer["think_present"])
            rows = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["repo"], "Real/Repo")
            self.assertEqual(rows[0]["arm"], "D")
            self.assertTrue(rows[0]["is_seed_target"])
            self.assertEqual(rows[0]["matched_fields"], ["unknown"])
            fails = [
                json.loads(line)
                for line in (out / "failures.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(fails[0]["code"], "github_not_found")
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["human_judgment"], "未运行")
            self.assertEqual(manifest["visible_cost"], "未知")
            self.assertIn("未运行", (out / "report.md").read_text(encoding="utf-8"))
            self.assertEqual(len(posts), 1)

    def test_quota_stops_before_next_task_and_resume_continues(self):
        calls = {"n": 0}

        def http_post(url, headers, payload, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                return {
                    "status": 200,
                    "body": json.dumps({"base_resp": {"status_code": 2056, "status_msg": "超出M Plan资源限制"}}),
                    "retry_after": None,
                }
            query = payload["input"]
            if "第一" in query:
                return model_response("one/repo\n")
            return model_response("two/repo\n")

        def github_get(url, headers, timeout):
            name = url.rstrip("/").split("/")[-2] + "/" + url.rstrip("/").split("/")[-1]
            return {"status": 200, "body": github_body(name, 1), "headers": {}}

        tasks = [
            task("zh2en-eval-01", "第一题"),
            task("zh2en-eval-02", "第二题"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = d.run_d_group(
                out_dir=out,
                tasks=tasks,
                run_id="test-d",
                base_url="https://api.minimax.cn/v1",
                model="MiniMax-M3",
                api_key="sk-testkeyvalue",
                github_token="",
                prompt_template=PROMPT,
                http_post=http_post,
                github_get=github_get,
                sleep=lambda _s: None,
                github_sleep_seconds=0,
                seeds=set(),
                historical_a=[],
                wait_for_quota=False,
            )
            self.assertEqual(first["stopped_before_task_id"], "zh2en-eval-01")
            self.assertEqual((out / "candidates.jsonl").read_text(encoding="utf-8"), "")
            checkpoint = json.loads((out / "checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["remaining_task_ids"], ["zh2en-eval-01", "zh2en-eval-02"])
            self.assertEqual(checkpoint["sent_but_incomplete"][0]["model_requests"], 1)
            second = d.run_d_group(
                out_dir=out,
                tasks=tasks,
                run_id="test-d",
                base_url="https://api.minimax.cn/v1",
                model="MiniMax-M3",
                api_key="sk-testkeyvalue",
                github_token="",
                prompt_template=PROMPT,
                http_post=http_post,
                github_get=github_get,
                sleep=lambda _s: None,
                github_sleep_seconds=0,
                seeds=set(),
                historical_a=[],
            )
            self.assertEqual(second["status"], "complete")
            repos = [
                json.loads(line)["repo"]
                for line in (out / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(repos, ["one/repo", "two/repo"])
            self.assertEqual(calls["n"], 3)

    def test_redact_removes_key(self):
        self.assertNotIn("sk-abcdefghij", d.redact("token sk-abcdefghij tail", extra="sk-abcdefghij"))


if __name__ == "__main__":
    unittest.main()
