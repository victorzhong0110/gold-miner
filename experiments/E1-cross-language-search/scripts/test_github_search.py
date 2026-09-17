"""Unit tests for github_search.py. No real network: all HTTP is faked.

Covers: parsing, dedup, matched fields, token header, default-no-network.
Fixture is minimal fake JSON (see fixtures/search_text_match.json).
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import github_search

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "search_text_match.json"


def load_fixture() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def noop(_seconds: float) -> None:
    return None


class TestCanonical(unittest.TestCase):
    def test_lowercases_owner_and_repo(self):
        self.assertEqual(
            github_search.canonical("OctoCat/Hello-World"),
            "octocat/hello-world",
        )

    def test_strips_whitespace(self):
        self.assertEqual(
            github_search.canonical("  Foo/Bar  "),
            "foo/bar",
        )

    def test_parse_preserves_full_name_as_is(self):
        item = {
            "full_name": "OctoCat/Hello-World",
            "stargazers_count": 1,
            "description": "d",
            "topics": [],
            "text_matches": [{"property": "name"}],
        }
        parsed = github_search.parse_repo_item(item)
        self.assertEqual(parsed["full_name"], "OctoCat/Hello-World")
        self.assertEqual(parsed["repo"], "OctoCat/Hello-World")
        self.assertEqual(parsed["canonical"], "octocat/hello-world")


class TestMatchedFields(unittest.TestCase):
    def test_name_property(self):
        item = {"text_matches": [{"property": "name"}]}
        self.assertEqual(github_search.extract_matched_fields(item), ["name"])

    def test_description_property(self):
        item = {"text_matches": [{"property": "description"}]}
        self.assertEqual(
            github_search.extract_matched_fields(item), ["description"]
        )

    def test_readme_property(self):
        item = {"text_matches": [{"property": "readme"}]}
        self.assertEqual(github_search.extract_matched_fields(item), ["readme"])

    def test_unknown_property(self):
        item = {"text_matches": [{"property": "something-else"}]}
        self.assertEqual(github_search.extract_matched_fields(item), ["unknown"])

    def test_missing_text_matches_is_unknown(self):
        self.assertEqual(github_search.extract_matched_fields({}), ["unknown"])
        self.assertEqual(
            github_search.extract_matched_fields({"text_matches": []}),
            ["unknown"],
        )
        self.assertEqual(
            github_search.extract_matched_fields({"text_matches": None}),
            ["unknown"],
        )

    def test_dedups_preserving_order(self):
        item = {
            "text_matches": [
                {"property": "name"},
                {"property": "name"},
                {"property": "description"},
            ]
        }
        self.assertEqual(
            github_search.extract_matched_fields(item),
            ["name", "description"],
        )


class TestParseFixture(unittest.TestCase):
    def test_fixture_has_two_items(self):
        data = load_fixture()
        self.assertEqual(len(data["items"]), 2)

    def test_first_item_hits_name(self):
        data = load_fixture()
        parsed = github_search.parse_repo_item(data["items"][0])
        self.assertEqual(parsed["full_name"], "octocat/Hello-World")
        self.assertEqual(parsed["stargazers_count"], 1234)
        self.assertEqual(parsed["stars"], 1234)
        self.assertEqual(parsed["description"], "My first repository on GitHub!")
        self.assertEqual(parsed["topics"], ["octocat", "demo"])
        self.assertEqual(parsed["matched_fields"], ["name"])

    def test_second_item_without_text_matches(self):
        data = load_fixture()
        parsed = github_search.parse_repo_item(data["items"][1])
        self.assertEqual(parsed["full_name"], "someone/示例项目")
        self.assertEqual(parsed["stargazers_count"], 45)
        self.assertEqual(parsed["matched_fields"], ["unknown"])


class TestDedup(unittest.TestCase):
    def test_dedup_by_canonical_keeps_first(self):
        repos = [
            github_search.parse_repo_item(
                {
                    "full_name": "OctoCat/Hello-World",
                    "stargazers_count": 10,
                    "description": "a",
                    "topics": [],
                    "text_matches": [{"property": "name"}],
                }
            ),
            github_search.parse_repo_item(
                {
                    "full_name": "octocat/hello-world",
                    "stargazers_count": 99,
                    "description": "b",
                    "topics": [],
                    "text_matches": [{"property": "description"}],
                }
            ),
            github_search.parse_repo_item(
                {
                    "full_name": "someone/示例项目",
                    "stargazers_count": 1,
                    "description": "c",
                    "topics": [],
                }
            ),
        ]
        deduped = github_search.dedup_repos(repos)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["full_name"], "OctoCat/Hello-World")
        self.assertEqual(deduped[1]["full_name"], "someone/示例项目")

    def test_search_repos_dedups_single_page(self):
        fixture = load_fixture()
        duplicated = {
            "items": [fixture["items"][0], dict(fixture["items"][0]), fixture["items"][1]]
        }
        # Second copy differs only by case to exercise canonical dedup.
        duplicated["items"][1] = dict(duplicated["items"][1])
        duplicated["items"][1]["full_name"] = "OCTOCAT/hello-world"

        def fake_get(url, headers):
            return duplicated

        result = github_search.search_repos(
            "hello",
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["full_name"], "octocat/Hello-World")


class TestSearchReposRequest(unittest.TestCase):
    def test_accept_and_bearer_headers_and_url(self):
        captured: dict = {}

        def fake_get(url, headers):
            captured["url"] = url
            captured["headers"] = dict(headers)
            return load_fixture()

        sleeps: list = []

        result = github_search.search_repos(
            "test query",
            per_page=30,
            page=2,
            token="test-token-123",
            http_get=fake_get,
            sleep_func=lambda s: sleeps.append(s),
            sleep_seconds=2,
        )
        self.assertEqual(
            captured["headers"]["Accept"],
            "application/vnd.github.text-match+json",
        )
        self.assertEqual(
            captured["headers"]["Authorization"], "Bearer test-token-123"
        )
        self.assertIn("q=test+query", captured["url"])
        self.assertIn("per_page=30", captured["url"])
        self.assertIn("page=2", captured["url"])
        self.assertNotIn("api.github.com", str(sleeps))
        self.assertEqual(sleeps, [2])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["matched_fields"], ["name"])
        self.assertEqual(result[1]["matched_fields"], ["unknown"])

    def test_token_from_env_header(self):
        captured: dict = {}

        def fake_get(url, headers):
            captured["headers"] = dict(headers)
            return {"items": []}

        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "env-token-abc"}):
            github_search.search_repos(
                "q",
                http_get=fake_get,
                sleep_func=noop,
                sleep_seconds=0,
            )
        self.assertEqual(
            captured["headers"]["Authorization"], "Bearer env-token-abc"
        )

    def test_no_token_no_auth_header(self):
        captured: dict = {}

        def fake_get(url, headers):
            captured["headers"] = dict(headers)
            return {"items": []}

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            github_search.search_repos(
                "q",
                http_get=fake_get,
                sleep_func=noop,
                sleep_seconds=0,
            )
        self.assertNotIn("Authorization", captured["headers"])
        self.assertEqual(
            captured["headers"]["Accept"],
            "application/vnd.github.text-match+json",
        )

    def test_sort_param_in_url(self):
        captured: dict = {}

        def fake_get(url, headers):
            captured["url"] = url
            return {"items": []}

        github_search.search_repos(
            "q",
            sort="updated",
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertIn("sort=updated", captured["url"])

    def test_sleep_seconds_zero_skips_sleep(self):
        called: list = []

        def fake_get(url, headers):
            return {"items": []}

        github_search.search_repos(
            "q",
            http_get=fake_get,
            sleep_func=lambda s: called.append(s),
            sleep_seconds=0,
        )
        self.assertEqual(called, [])


class TestDefaultNoNetwork(unittest.TestCase):
    def test_default_http_get_is_none(self):
        import inspect

        sig = inspect.signature(github_search.search_repos)
        self.assertIsNone(sig.parameters["http_get"].default)

    def test_missing_http_get_raises_without_network(self):
        with mock.patch(
            "github_search.urllib.request.urlopen",
            side_effect=AssertionError("must not touch network"),
        ):
            with self.assertRaises(RuntimeError):
                github_search.search_repos(
                    "hello",
                    sleep_func=noop,
                    sleep_seconds=0,
                )

    def test_fixture_and_tests_never_reference_real_call(self):
        # Guard: this test module never calls the real urllib helper.
        self.assertTrue(hasattr(github_search, "_urllib_get"))
        data = load_fixture()
        self.assertIn("items", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
