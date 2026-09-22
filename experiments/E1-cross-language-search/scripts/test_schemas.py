"""Schema sample validation for candidates/judgments. No network.

Tries ``jsonschema`` if installed; otherwise falls back to lightweight
required/enum/additionalProperties checks. Validates:
- candidates.schema.json allows arms A/B/C/D/M, documents ``sources``
  with additionalProperties false preserved.
- judgments.schema.json requires ``worth_following`` and ``reason``
  per judgment-guide.md L19, preserving additionalProperties false.
- Sample rows (per-query without sources, merged with sources, judgment)
  pass validation; negative cases (missing required, extra prop) fail.
"""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import jsonschema  # type: ignore

    HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover - fallback path
    HAS_JSONSCHEMA = False

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / "experiments" / "E1-cross-language-search"
CAND_SCHEMA_PATH = E1 / "schemas" / "candidates.schema.json"
JUDG_SCHEMA_PATH = E1 / "schemas" / "judgments.schema.json"

REPO_PAT = re.compile(r"^[^/\s]+/[^/\s]+$")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def lightweight_validate(row: dict, schema: dict) -> list:
    """Return list of error strings; empty means valid (subset of JSON Schema)."""
    errs = []
    if not isinstance(row, dict):
        return ["row must be object"]
    props = schema.get("properties", {})
    required = schema.get("required", [])
    for f in required:
        if f not in row:
            errs.append(f"missing required: {f}")
    if schema.get("additionalProperties") is False:
        for k in row:
            if k not in props:
                errs.append(f"additional property not allowed: {k}")
    # enum / type spot checks for known fields
    for key, spec in props.items():
        if key not in row:
            continue
        val = row[key]
        enum = spec.get("enum")
        if enum is not None and val not in enum:
            errs.append(f"{key}={val!r} not in enum {enum}")
        typ = spec.get("type")
        if typ == "string" and not isinstance(val, str):
            errs.append(f"{key} must be string")
        if typ == "integer" and not isinstance(val, int):
            errs.append(f"{key} must be integer")
        if typ == "boolean" and not isinstance(val, bool):
            errs.append(f"{key} must be boolean")
        if typ == "array" and not isinstance(val, list):
            errs.append(f"{key} must be array")
        if key == "repo" and isinstance(val, str) and not REPO_PAT.match(val):
            errs.append(f"repo pattern mismatch: {val!r}")
        if key in ("page", "rank") and isinstance(val, int) and val < 1:
            errs.append(f"{key} must be >=1")
        if key == "stars" and isinstance(val, int) and val < 0:
            errs.append(f"{key} must be >=0")
        if key == "matched_fields" and isinstance(val, list):
            allowed = {"name", "description", "readme", "unknown"}
            if not val or any(v not in allowed for v in val):
                errs.append(f"matched_fields invalid: {val!r}")
        if key == "sources" and isinstance(val, list):
            item_schema = spec.get("items", {})
            item_props = item_schema.get("properties", {})
            item_req = item_schema.get("required", [])
            for i, src in enumerate(val):
                if not isinstance(src, dict):
                    errs.append(f"sources[{i}] must be object")
                    continue
                for f in item_req:
                    if f not in src:
                        errs.append(f"sources[{i}] missing {f}")
                if item_schema.get("additionalProperties") is False:
                    for k in src:
                        if k not in item_props:
                            errs.append(f"sources[{i}] extra prop: {k}")
    return errs


def validate_row(row: dict, schema: dict) -> list:
    if HAS_JSONSCHEMA:
        try:
            jsonschema.validate(row, schema)
            return []
        except Exception as exc:  # jsonschema.ValidationError
            return [str(exc).splitlines()[0] if str(exc) else "schema invalid"]
    return lightweight_validate(row, schema)


def sample_candidate_per_query() -> dict:
    return {
        "run_id": "r-sample",
        "task_id": "zh2en-eval-01",
        "direction": "zh2en",
        "arm": "M",
        "variant_query": "局域网文件互传",
        "variant_lang": "zh",
        "api_query": "局域网文件互传",
        "page": 1,
        "rank": 2,
        "repo": "Owner/Example",
        "stars": 42,
        "matched_fields": ["description"],
        "is_seed_target": False,
        "fetched_at": "2026-09-17T20:00:00Z",
    }


def sample_candidate_merged() -> dict:
    row = sample_candidate_per_query()
    row["sources"] = [
        {
            "variant_query": "局域网文件互传",
            "api_query": "局域网文件互传",
            "variant_lang": "zh",
            "rank": 2,
            "page": 1,
        },
        {
            "variant_query": "lan file transfer",
            "api_query": "lan file transfer",
            "variant_lang": "en",
            "rank": 5,
            "page": 1,
        },
    ]
    return row


def sample_judgment() -> dict:
    return {
        "run_id": "r-sample",
        "task_id": "zh2en-eval-01",
        "repo": "Owner/Example",
        "purpose_fit": "yes",
        "hard_conditions": "unknown",
        "kind": "tool",
        "novel_to_judge": "yes",
        "worth_following": "yes",
        "reason": "README 说明支持局域网直连，与任务 need 相符；待核对离线可用性。",
        "judge": "reviewer-1",
        "judged_at": "2026-09-17T21:00:00Z",
        "notes": "",
    }


class TestCandidatesSchema(unittest.TestCase):
    def test_arms_allow_m_and_retain_abcd(self):
        schema = load_json(CAND_SCHEMA_PATH)
        self.assertEqual(
            set(schema["properties"]["arm"]["enum"]),
            {"A", "B", "C", "D", "M"},
        )
        self.assertFalse(schema.get("additionalProperties", True))

    def test_sources_documented(self):
        schema = load_json(CAND_SCHEMA_PATH)
        self.assertIn("sources", schema["properties"])
        src = schema["properties"]["sources"]
        self.assertEqual(src.get("type"), "array")
        self.assertEqual(
            set(src["items"]["required"]),
            {"variant_query", "api_query", "variant_lang", "rank", "page"},
        )
        self.assertFalse(src["items"].get("additionalProperties", True))
        # sources is optional (per-query rows omit it), others required.
        self.assertNotIn("sources", schema.get("required", []))

    def test_per_query_sample_valid(self):
        schema = load_json(CAND_SCHEMA_PATH)
        errs = validate_row(sample_candidate_per_query(), schema)
        self.assertEqual(errs, [], f"per-query sample should validate: {errs}")

    def test_merged_sample_with_sources_valid(self):
        schema = load_json(CAND_SCHEMA_PATH)
        errs = validate_row(sample_candidate_merged(), schema)
        self.assertEqual(errs, [], f"merged sample should validate: {errs}")

    def test_missing_required_fails(self):
        schema = load_json(CAND_SCHEMA_PATH)
        bad = sample_candidate_per_query()
        del bad["repo"]
        self.assertTrue(validate_row(bad, schema))

    def test_extra_property_fails(self):
        schema = load_json(CAND_SCHEMA_PATH)
        bad = sample_candidate_per_query()
        bad["__extra"] = 1
        self.assertTrue(validate_row(bad, schema))


class TestJudgmentsSchema(unittest.TestCase):
    def test_requires_worth_following_and_reason(self):
        schema = load_json(JUDG_SCHEMA_PATH)
        self.assertIn("worth_following", schema["properties"])
        self.assertIn("reason", schema["properties"])
        self.assertIn("worth_following", schema["required"])
        self.assertIn("reason", schema["required"])
        self.assertIn("unknown", schema["properties"]["novel_to_judge"]["enum"])
        self.assertFalse(schema.get("additionalProperties", True))

    def test_sample_valid(self):
        schema = load_json(JUDG_SCHEMA_PATH)
        errs = validate_row(sample_judgment(), schema)
        self.assertEqual(errs, [], f"judgment sample should validate: {errs}")

    def test_missing_reason_fails(self):
        schema = load_json(JUDG_SCHEMA_PATH)
        bad = sample_judgment()
        del bad["reason"]
        self.assertTrue(validate_row(bad, schema))

    def test_missing_worth_following_fails(self):
        schema = load_json(JUDG_SCHEMA_PATH)
        bad = sample_judgment()
        del bad["worth_following"]
        self.assertTrue(validate_row(bad, schema))


class TestRunnerOutputConforms(unittest.TestCase):
    def test_runner_rows_validate(self):
        import e1_minimal_runner as runner

        def fake_get(url, headers):
            from test_e1_minimal_runner import make_items

            if "second" in url:
                # duplicate canonical to exercise sources length 2
                return make_items("Owner/Repo", "other/two")
            return make_items("Owner/Repo", "other/one")

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="B",
            variants=[
                {"variant_query": "first", "variant_lang": "zh", "api_query": "first"},
                {"variant_query": "second", "variant_lang": "en", "api_query": "second"},
            ],
            http_get=fake_get,
            sleep_func=lambda s: None,
            sleep_seconds=0,
        )
        cand_schema = load_json(CAND_SCHEMA_PATH)
        for row in out["per_query_records"]:
            self.assertEqual(validate_row(row, cand_schema), [])
            self.assertNotIn("sources", row)
        for row in out["merged_candidates"]:
            self.assertEqual(
                validate_row(row, cand_schema), [], f"merged row invalid: {row}"
            )
            self.assertIn("sources", row)
            self.assertGreaterEqual(len(row["sources"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
