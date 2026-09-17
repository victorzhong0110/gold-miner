"""parse_hellogithub 保守解析器测试，不访问网络，可直接运行。

运行：
  python3 experiments/E1-cross-language-search/scripts/test_parse_hellogithub.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parse_hellogithub

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "hellogithub_issue_snippet.md"
)


def parse_fixture(issue=99):
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    return parse_hellogithub.parse_issue(text, issue)


class TestFixture(unittest.TestCase):
    def test_fixture_file_exists_and_has_four_links(self):
        self.assertTrue(FIXTURE_PATH.is_file())
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("fake-owner-a/fake-repo-a", text)
        self.assertIn("example.com", text)

    def test_fixture_yields_three_entries_and_one_skipped(self):
        result = parse_fixture()
        self.assertEqual(len(result["entries"]), 3)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["version"], "hellogithub-parse-v1")

    def test_fixture_repos_exact(self):
        result = parse_fixture()
        repos = [e["repo"] for e in result["entries"]]
        self.assertEqual(
            repos,
            [
                "fake-owner-a/fake-repo-a",
                "fake-owner-b/fake-repo-b",
                "fake-owner-c/fake-repo-c",
            ],
        )

    def test_extra_path_normalized(self):
        result = parse_fixture()
        self.assertIn("fake-owner-c/fake-repo-c", [e["repo"] for e in result["entries"]])
        for e in result["entries"]:
            self.assertNotIn("/tree/main", e["repo"])

    def test_non_github_link_skipped(self):
        result = parse_fixture()
        repos = [e["repo"] for e in result["entries"]]
        self.assertNotIn("example.com", " ".join(repos))
        for e in result["entries"]:
            self.assertNotIn("example.com", e["repo"])

    def test_issue_number_propagated(self):
        result = parse_fixture(issue=123)
        for e in result["entries"]:
            self.assertEqual(e["hellogithub_issue"], 123)

    def test_zh_description_contains_chinese_intro(self):
        result = parse_fixture()
        by_repo = {e["repo"]: e["zh_description"] for e in result["entries"]}
        self.assertIn(
            "中文介绍 Alpha", by_repo["fake-owner-a/fake-repo-a"]
        )
        self.assertIn("中文介绍 Beta", by_repo["fake-owner-b/fake-repo-b"])
        self.assertIn("中文介绍 Gamma", by_repo["fake-owner-c/fake-repo-c"])
        for e in result["entries"]:
            self.assertTrue(e["zh_description"].strip())

    def test_parse_file_matches_parse_issue(self):
        from_file = parse_hellogithub.parse_file(FIXTURE_PATH, 99)
        from_text = parse_fixture(99)
        self.assertEqual(from_file, from_text)


class TestConservativeRules(unittest.TestCase):
    def test_bare_url_ignored_not_counted(self):
        text = "裸链接 https://github.com/bare-owner/bare-repo 应被忽略\n"
        result = parse_hellogithub.parse_issue(text, 1)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["skipped"], 0)

    def test_malformed_github_link_skipped(self):
        text = "坏链接 [坏](https://github.com/only-one-segment)\n"
        result = parse_hellogithub.parse_issue(text, 1)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["skipped"], 1)

    def test_duplicate_repo_keeps_first_and_counts_skipped(self):
        text = (
            "[a](https://github.com/dup-owner/dup-repo)\n\n"
            "[a2](https://github.com/dup-owner/dup-repo)\n"
        )
        result = parse_hellogithub.parse_issue(text, 1)
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["repo"], "dup-owner/dup-repo")
        self.assertEqual(result["skipped"], 1)

    def test_duplicate_case_insensitive(self):
        text = (
            "[a](https://github.com/Dup-Owner/Dup-Repo)\n\n"
            "[b](https://github.com/dup-owner/dup-repo)\n"
        )
        result = parse_hellogithub.parse_issue(text, 1)
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["repo"], "Dup-Owner/Dup-Repo")
        self.assertEqual(result["skipped"], 1)

    def test_git_suffix_and_query_stripped(self):
        text = "[x](https://github.com/some-owner/some-repo.git)\n"
        result = parse_hellogithub.parse_issue(text, 1)
        self.assertEqual(result["entries"][0]["repo"], "some-owner/some-repo")
        text2 = "[y](https://github.com/q-owner/q-repo?tab=readme#readme)\n"
        result2 = parse_hellogithub.parse_issue(text2, 1)
        self.assertEqual(result2["entries"][0]["repo"], "q-owner/q-repo")

    def test_non_github_domain_skipped(self):
        text = "[站](https://gitee.com/someone/somerepo)\n"
        result = parse_hellogithub.parse_issue(text, 1)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["skipped"], 1)

    def test_invalid_issue_number_rejected(self):
        with self.assertRaises(ValueError):
            parse_hellogithub.parse_issue("[a](https://github.com/o/r)", 0)
        with self.assertRaises(ValueError):
            parse_hellogithub.parse_issue("[a](https://github.com/o/r)", "99")

    def test_no_network_imports(self):
        src = Path(parse_hellogithub.__file__).read_text(encoding="utf-8")
        for banned in (
            "urllib",
            "requests",
            "httpx",
            "socket",
            "urlopen",
            "GITHUB_TOKEN",
            "OPENAI_API_KEY",
        ):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
