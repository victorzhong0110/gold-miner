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

def run(out, tasks, http_post, github_get, **kwargs):
    params = dict(
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
    params.update(kwargs)
    return d.run_d_group(**params)


def simple_github(url, headers, timeout):
    parts = url.rstrip("/").split("/")
    return {"status": 200, "body": github_body(parts[-2] + "/" + parts[-1], 1), "headers": {}}


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class RetryTests(unittest.TestCase):
    def test_timeout_is_not_completed_and_resume_retries(self):
        calls = {"n": 0}
        sleeps = []

        def failing_post(url, headers, payload, timeout):
            calls["n"] += 1
            raise TimeoutError("model request timed out")

        tasks = [task("zh2en-eval-01", "第一题"), task("zh2en-eval-02", "第二题")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)

            def post_first_ok(url, headers, payload, timeout):
                if "第一" in payload["input"]:
                    return model_response("one/repo\n")
                return failing_post(url, headers, payload, timeout)

            first = run(out, tasks, post_first_ok, simple_github, model_attempts=2,
                        retry_backoff_seconds=5, sleep=sleeps.append)
            self.assertEqual(first["status"], "incomplete")
            self.assertEqual(first["failed_task_ids"], ["zh2en-eval-02"])
            self.assertEqual(calls["n"], 2)
            self.assertIn(5, sleeps)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["tasks"]["completed"], 1)
            self.assertEqual(manifest["tasks"]["failed"], 1)
            self.assertEqual(manifest["remaining_task_ids"], ["zh2en-eval-02"])
            self.assertIsNone(manifest["finished_at"])
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("任务完成 1 / 2", report)
            self.assertIn("zh2en-eval-02", report)
            fails = rows(out / "failures.jsonl")
            self.assertEqual([f["code"] for f in fails], ["timeout", "timeout"])

            def post_ok(url, headers, payload, timeout):
                calls["n"] += 1
                self.assertIn("第二", payload["input"])
                return model_response("two/repo\n")

            second = run(out, tasks, post_ok, simple_github)
            self.assertEqual(second["status"], "complete")
            self.assertEqual(calls["n"], 3)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["tasks"]["completed"], 2)
            self.assertEqual(manifest["actual_requests"]["model"], 4)
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("任务完成 2 / 2", report)
            self.assertIn("经过重试才完成", report)

    def test_bad_response_and_empty_list_stay_retryable(self):
        answers = iter(
            [
                {"status": 400, "body": json.dumps({"error": {"message": "bad"}}), "retry_after": None},
                model_response("我找不到合适的仓库。\n"),
                model_response("found/repo\n"),
            ]
        )

        def http_post(url, headers, payload, timeout):
            return next(answers)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = run(out, [task("en2zh-eval-03", "q", "en2zh")], http_post, simple_github,
                        model_attempts=2)
            self.assertEqual(first["status"], "incomplete")
            codes = [r["code"] for r in rows(out / "model_calls.jsonl")]
            self.assertEqual(codes, ["bad_response", "no_parseable_list"])
            self.assertIn("bad", rows(out / "model_calls.jsonl")[0]["attempts"][0]["error_excerpt"])
            self.assertEqual(rows(out / "candidates.jsonl"), [])
            second = run(out, [task("en2zh-eval-03", "q", "en2zh")], http_post, simple_github)
            self.assertEqual(second["status"], "complete")
            self.assertEqual([r["repo"] for r in rows(out / "candidates.jsonl")], ["found/repo"])

    def test_legacy_terminal_timeout_row_is_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            legacy = {
                "run_id": "test-d",
                "task_id": "zh2en-eval-08",
                "input_sha256": d.sha256_text(d.render_prompt(PROMPT, "q")),
                "code": "timeout",
                "model_requests": 1,
                "elapsed_ms": 300000,
                "searches": [],
                "usage": {},
                "parsed_repos": [],
                "terminal": True,
                "recorded_at": "2026-10-04T11:27:23Z",
            }
            (out / "model_calls.jsonl").write_text(json.dumps(legacy) + "\n", encoding="utf-8")
            posts = []

            def http_post(url, headers, payload, timeout):
                posts.append(1)
                return model_response("x/y\n")

            result = run(out, [task("zh2en-eval-08", "q")], http_post, simple_github)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(len(posts), 1)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["actual_requests"]["model"], 2)

    def test_auth_rejected_stops_and_stays_retryable(self):
        def http_post(url, headers, payload, timeout):
            return {"status": 401, "body": json.dumps({"base_resp": {"status_code": 1004}}), "retry_after": None}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = run(out, [task("zh2en-eval-01", "q"), task("zh2en-eval-02", "q2")], http_post, simple_github)
            self.assertEqual(result["code"], "auth_rejected")
            self.assertEqual(result["stopped_before_task_id"], "zh2en-eval-01")
            self.assertEqual(len(rows(out / "model_calls.jsonl")), 1)
            self.assertFalse(rows(out / "model_calls.jsonl")[0]["terminal"])


class RedirectTests(unittest.TestCase):
    def test_verify_repo_follows_repositories_location(self):
        seen = []

        def github_get(url, headers, timeout):
            seen.append(url)
            if url.endswith("/repos/twwch/Mako"):
                return {
                    "status": 301,
                    "body": json.dumps({"message": "Moved Permanently", "url": "https://api.github.com/repositories/1105761331"}),
                    "headers": {"Location": "https://api.github.com/repositories/1105761331"},
                }
            if url == "https://api.github.com/repositories/1105761331":
                self.assertIn("Accept", headers)
                return {"status": 200, "body": github_body("newowner/Mako", 7), "headers": {}}
            raise AssertionError(url)

        checked = d.verify_repo("twwch/Mako", github_get, "", 5)
        self.assertEqual(checked["code"], "exists")
        self.assertEqual(checked["canonical_repo"], "newowner/Mako")
        self.assertEqual(checked["redirected_from"], "twwch/Mako")
        self.assertEqual(checked["redirect"]["first_http_status"], 301)
        self.assertEqual(checked["github_requests"], 2)
        self.assertEqual(len(seen), 2)

    def test_offhost_redirect_is_unresolved(self):
        def github_get(url, headers, timeout):
            return {"status": 301, "body": "", "headers": {"Location": "https://evil.example/repos/a/b"}}

        checked = d.verify_repo("a/b", github_get, "", 5)
        self.assertEqual(checked["code"], "github_migrated")
        self.assertFalse(checked["exists"])
        self.assertEqual(checked["github_requests"], 1)

    def test_redirect_loop_is_bounded(self):
        def github_get(url, headers, timeout):
            return {"status": 301, "body": "", "headers": {"Location": "/repositories/1"}}

        checked = d.verify_repo("a/b", github_get, "", 5)
        self.assertEqual(checked["code"], "github_migrated")
        self.assertEqual(checked["github_requests"], d.MAX_GITHUB_REDIRECTS + 1)

    def test_resume_reverifies_migrated_without_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            moved = {"n": 0}

            def http_post(url, headers, payload, timeout):
                return model_response("keep/one\nold/name\nghost/none\n")

            def github_get_old(url, headers, timeout):
                if url.endswith("/old/name"):
                    return {"status": 301, "body": "", "headers": {"Location": "https://evil.example/x"}}
                if url.endswith("/ghost/none"):
                    return {"status": 404, "body": "{}", "headers": {}}
                return simple_github(url, headers, timeout)

            first = run(out, [task("zh2en-eval-04", "q")], http_post, github_get_old,
                        historical_a=[{"arm": "A", "task_id": "zh2en-eval-04", "repo": "new/name"},
                                      {"arm": "A", "task_id": "seed-zh2en-01", "repo": "z/z"}])
            self.assertEqual(first["status"], "incomplete")
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["tasks"]["completed"], 1)
            self.assertEqual(manifest["repos"]["unresolved"], 1)

            def no_post(url, headers, payload, timeout):
                raise AssertionError("model must not be called again")

            def github_get_new(url, headers, timeout):
                moved["n"] += 1
                if url.endswith("/repos/old/name"):
                    return {"status": 301, "body": "", "headers": {"Location": "https://api.github.com/repositories/42"}}
                if url.endswith("/repositories/42"):
                    return {"status": 200, "body": github_body("new/name", 9), "headers": {}}
                raise AssertionError("only the unresolved name is re-checked: " + url)

            second = run(out, [task("zh2en-eval-04", "q")], no_post, github_get_new,
                         historical_a=[{"arm": "A", "task_id": "zh2en-eval-04", "repo": "new/name"},
                                       {"arm": "A", "task_id": "seed-zh2en-01", "repo": "z/z"}])
            self.assertEqual(second["status"], "complete")
            self.assertEqual(moved["n"], 2)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["repos"]["proposed"], 3)
            self.assertEqual(manifest["repos"]["exists"], 2)
            self.assertEqual(manifest["repos"]["redirected"], 1)
            self.assertEqual(manifest["repos"]["hallucinated_404"], 1)
            self.assertEqual(manifest["repos"]["unresolved"], 0)
            self.assertEqual(manifest["actual_requests"]["model"], 1)
            verifications = rows(out / "verifications.jsonl")
            self.assertEqual(verifications[-1]["canonical_repo"], "new/name")
            self.assertTrue(verifications[-1]["reverify"])
            self.assertIn("跳转", verifications[-1]["note"])
            cands = [r["repo"] for r in rows(out / "candidates.jsonl")]
            self.assertEqual(cands, ["keep/one", "new/name"])
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("new/name", report)
            self.assertIn("幻觉率（占提名）1/3", report)
            self.assertIn("| zh2en-eval-04 | 完成 | 2 | 1 | 1 | 1 |", report)
            self.assertIn("seed-zh2en-01", report)
            self.assertIn("不能下的结论", report)

    def test_overlap_lists_every_batch_task(self):
        overlap = d.overlap_with_historical_a(
            [{"task_id": "t1", "repo": "a/b"}],
            [{"arm": "A", "task_id": "t1", "repo": "A/B"}, {"arm": "A", "task_id": "seed", "repo": "c/d"}],
            ["t1", "t2"],
        )
        self.assertEqual([r["task_id"] for r in overlap["per_task"]], ["t1", "t2"])
        self.assertEqual(overlap["intersection"], 1)
        self.assertEqual(overlap["a_tasks_outside_batch"], [{"task_id": "seed", "a_candidates": 1}])


if __name__ == "__main__":
    unittest.main()


class ReviewRegressionTests(unittest.TestCase):
    def test_incomplete_answer_is_not_success(self):
        body = json.dumps({"status": "incomplete", "output_text": "real/repo"})
        self.assertEqual(d.classify_model_response(200, body)["code"], "model_output_truncated")
        self.assertEqual(d.classify_model_response(200, '{"choices":[null]}')["code"], "empty_model_output")

    def test_budget_rejection_never_resends_uncapped(self):
        posts=[]
        def post(url, headers, payload, timeout):
            posts.append(payload)
            return {"status":400,"body":json.dumps({"base_resp":{"status_code":2013,"status_msg":"unknown parameter max_output_tokens"}})}
        result=d.call_model(base_url="https://api.minimax.cn/v1",model="MiniMax-M3",api_key="fixture",prompt="q",http_post=post,timeout=1)
        self.assertEqual(result["code"],"bad_response")
        self.assertEqual(len(posts),1)
        self.assertEqual(posts[0]["max_output_tokens"],8192)

    def test_resume_mismatch_refuses_before_requests_or_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);tasks=[task("t1","original")]
            run(out,tasks,lambda *args:model_response("real/repo"),simple_github)
            snapshot={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
            def forbidden(*args):raise AssertionError("must not request")
            for change in [{"model":"other"},{"base_url":"https://other.example/v1"},{"run_id":"other"},{"prompt_template":PROMPT+" changed"}]:
                with self.assertRaisesRegex(ValueError,"resume configuration mismatch"):
                    run(out,tasks,forbidden,forbidden,**change)
            with self.assertRaisesRegex(ValueError,"resume task set mismatch"):
                run(out,[task("t1","changed")],forbidden,forbidden)
            self.assertEqual(snapshot,{p.name:p.read_bytes() for p in out.iterdir() if p.is_file()})
