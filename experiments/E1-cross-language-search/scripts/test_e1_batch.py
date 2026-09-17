"""Unit tests for e1_batch.py. No real network: all HTTP is faked."""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_batch as batch

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / "experiments" / "E1-cross-language-search"
QUERIES = E1 / "queries.yaml"
SETTINGS = E1 / "run-settings.json"

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
)

REQUIRED_CANDIDATE_FIELDS = (
    "run_id",
    "task_id",
    "direction",
    "arm",
    "variant_query",
    "variant_lang",
    "api_query",
    "page",
    "rank",
    "repo",
    "stars",
    "matched_fields",
    "is_seed_target",
    "fetched_at",
)


def noop(_seconds: float) -> None:
    return None


def make_items(*names):
    items = []
    for i, name in enumerate(names, start=1):
        items.append(
            {
                "full_name": name,
                "stargazers_count": i * 10,
                "description": "d",
                "topics": [],
                "text_matches": [{"property": "name"}],
            }
        )
    return {"items": items}


def fake_get_factory(mapping):
    def fake_get(url, headers):
        for key, payload in mapping.items():
            if key in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        return {"items": []}

    return fake_get


class TestLoadQueries(unittest.TestCase):
    def test_dev_and_eval_present(self):
        q = batch.load_queries(QUERIES)
        self.assertGreaterEqual(len(q["dev"]), 1)
        self.assertGreaterEqual(len(q["eval.batch_1"]), 1)
        for task in q["dev"] + q["eval.batch_1"]:
            for f in ("id", "direction", "type", "query", "need", "written_at"):
                self.assertIn(f, task)

    def test_eval_gate_unfrozen(self):
        settings = batch.load_run_settings(SETTINGS)
        self.assertFalse(batch.is_eval_frozen(settings))


class TestBuildAVariants(unittest.TestCase):
    def test_zh2en_maps_zh(self):
        v = batch.build_a_variants(
            {"query": "剪贴板历史 工具", "direction": "zh2en"}
        )
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["variant_lang"], "zh")
        self.assertEqual(v[0]["api_query"], "剪贴板历史 工具")

    def test_en2zh_maps_en(self):
        v = batch.build_a_variants(
            {"query": "clipboard history manager", "direction": "en2zh"}
        )
        self.assertEqual(v[0]["variant_lang"], "en")


class TestRunBatchAArm(unittest.TestCase):
    def test_dev_a_dry_run_two_tasks(self):
        q = batch.load_queries(QUERIES)
        tasks = q["dev"][:2]
        out = batch.run_batch(
            tasks=tasks,
            arm="A",
            run_id="test-batch-1",
            http_get=lambda u, h: make_items("a/one"),
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["totals"]["tasks"], 2)
        self.assertEqual(out["totals"]["tasks_ok"], 2)
        self.assertEqual(out["totals"]["attempted_requests"], 2)
        self.assertEqual(out["totals"]["successful_requests"], 2)
        self.assertEqual(out["totals"]["failed_requests"], 0)
        for tr in out["task_results"]:
            self.assertEqual(tr["status"], "ok")
            self.assertEqual(len(tr["merged_candidates"]), 1)
            for row in tr["merged_candidates"]:
                for f in REQUIRED_CANDIDATE_FIELDS:
                    self.assertIn(f, row)
                self.assertIn("sources", row)

    def test_b_without_variants_blocked_no_network(self):
        calls = {"n": 0}

        def counting_get(url, headers):
            calls["n"] += 1
            return {"items": []}

        q = batch.load_queries(QUERIES)
        out = batch.run_batch(
            tasks=q["dev"][:1],
            arm="B",
            run_id="test-batch-2",
            http_get=counting_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["totals"]["tasks_blocked"], 1)
        self.assertEqual(calls["n"], 0)
        self.assertEqual(
            out["task_results"][0]["status"], "blocked"
        )

    def test_d_always_refused(self):
        q = batch.load_queries(QUERIES)
        with self.assertRaises(ValueError):
            batch.run_batch(
                tasks=q["dev"][:1],
                arm="D",
                run_id="x",
                http_get=lambda u, h: {"items": []},
                sleep_func=noop,
                sleep_seconds=0,
            )

    def test_cancel_marks_remaining(self):
        q = batch.load_queries(QUERIES)
        state = {"cancel": True}
        out = batch.run_batch(
            tasks=q["dev"][:3],
            arm="A",
            run_id="test-batch-3",
            http_get=lambda u, h: make_items("a/one"),
            should_cancel=lambda: state["cancel"],
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["totals"]["tasks"], 3)
        self.assertEqual(out["totals"]["tasks_cancelled"], 3)
        self.assertEqual(out["totals"]["attempted_requests"], 0)

    def test_manifest_materials_commit_shape(self):
        settings = batch.load_run_settings(SETTINGS)
        m = batch.build_manifest(
            run_id="r",
            batch="dev",
            arm="A",
            repo_root=ROOT,
            settings=settings,
            totals={"tasks": 0},
            started_at="2026-09-17T00:00:00Z",
            finished_at="2026-09-17T00:00:01Z",
            http_mode="dry-run",
        )
        self.assertIn("materials_commit", m)
        self.assertTrue(
            m["materials_commit"] == "unknown"
            or re.fullmatch(r"[0-9a-f]{40}", m["materials_commit"])
        )

    def test_jsonl_roundtrip(self):
        import tempfile

        q = batch.load_queries(QUERIES)
        out = batch.run_batch(
            tasks=q["dev"][:1],
            arm="A",
            run_id="test-batch-4",
            http_get=lambda u, h: make_items("Owner/Repo"),
            sleep_func=noop,
            sleep_seconds=0,
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "candidates.jsonl"
            n = batch.write_candidates_jsonl(p, out["task_results"])
            self.assertEqual(n, 1)
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            for f in REQUIRED_CANDIDATE_FIELDS:
                self.assertIn(f, row)


class TestCliGates(unittest.TestCase):
    def _run_main(self, *argv):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = batch.main(list(argv))
        return code, buf.getvalue()

    def test_eval_unfrozen_refused(self):
        code, out = self._run_main(
            "--queries", str(QUERIES),
            "--run-settings", str(SETTINGS),
            "--batch", "eval.batch_1",
            "--arm", "A",
            "--run-id", "dry",
            "--out-dir", "/tmp/e1-dry",
        )
        self.assertEqual(code, 3)
        self.assertIn("未冻结", out)

    def test_b_without_variants_refused(self):
        code, out = self._run_main(
            "--queries", str(QUERIES),
            "--run-settings", str(SETTINGS),
            "--batch", "dev",
            "--arm", "B",
            "--run-id", "dry",
            "--out-dir", "/tmp/e1-dry",
        )
        self.assertEqual(code, 4)
        self.assertIn("refusing to fabricate", out)

    def test_dry_run_refuses_network(self):
        code, out = self._run_main(
            "--queries", str(QUERIES),
            "--run-settings", str(SETTINGS),
            "--batch", "dev",
            "--arm", "A",
            "--run-id", "dry",
            "--out-dir", "/tmp/e1-dry",
        )
        self.assertEqual(code, 5)
        self.assertIn("refuses network", out)


class TestNoPlaceholdersOrSecrets(unittest.TestCase):
    def test_no_todo_in_new_module(self):
        text = (Path(__file__).resolve().parent / "e1_batch.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("TODO", text)

    def test_no_secrets_in_new_files(self):
        for name in ("e1_batch.py", "test_e1_batch.py"):
            text = (Path(__file__).resolve().parent / name).read_text(
                encoding="utf-8"
            )
            for pat in SECRET_PATTERNS:
                self.assertIsNone(
                    pat.search(text), f"{name} looks like a key: {pat.pattern}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
