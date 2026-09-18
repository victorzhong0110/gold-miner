"""E3 公开片段清单的可运行检查，不访问网络，不用凭据，不调模型。

运行（仓库根）：
  python3 -m unittest discover -s experiments/E3-faithful-reading -p "test_*.py"
或：
  python3 experiments/E3-faithful-reading/test_fragments.py
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

E3_DIR = Path(__file__).resolve().parent
CHECKLIST = E3_DIR / "fragments-2026-09-17.md"
REPO_ROOT = E3_DIR.parents[1]

FRAG_HEAD_RE = re.compile(r"^###\s+(F-\d{2})\b")
FILE_RE = re.compile(r"^-\s+文件：`([^`]+)`\s*$")
LINES_RE = re.compile(r"^-\s+行：(\d+)(?:\s*[-–—]\s*(\d+))?\s*$")
LANG_RE = re.compile(r"^-\s+语言：(\S+)")
CATS_RE = re.compile(r"^-\s+类别：(.+)$")
QUOTE_RE = re.compile(r"^ {2}-\s+(.+?)\s*$")
SECRET_RES = (re.compile(r"sk-[A-Za-z0-9]{8,}"), re.compile(r"ghp_[A-Za-z0-9]+"),
              re.compile(r"github_pat_[A-Za-z0-9_]+"))
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def parse_checklist(text):
    """解析 8 个片段块，返回 {frag_id: {file, start, end, lang, cats, quotes}}。"""
    frags = {}
    current = None
    in_quotes = False
    for raw in text.splitlines():
        m = FRAG_HEAD_RE.match(raw)
        if m:
            current = m.group(1)
            if current in frags:
                raise ValueError("duplicate fragment %s" % current)
            frags[current] = {"quotes": []}
            in_quotes = False
            continue
        if current is None:
            continue
        m = FILE_RE.match(raw)
        if m:
            frags[current]["file"] = m.group(1)
            in_quotes = False
            continue
        m = LINES_RE.match(raw)
        if m:
            frags[current]["start"] = int(m.group(1))
            frags[current]["end"] = int(m.group(2)) if m.group(2) else int(m.group(1))
            in_quotes = False
            continue
        m = LANG_RE.match(raw)
        if m:
            frags[current]["lang"] = m.group(1)
            in_quotes = False
            continue
        m = CATS_RE.match(raw)
        if m:
            frags[current]["cats"] = [c.strip() for c in re.split(r"[、，,]", m.group(1)) if c.strip()]
            in_quotes = False
            continue
        if raw.strip() == "- 引用：":
            in_quotes = True
            continue
        if raw.strip().startswith("- ") and not raw.startswith("  -"):
            in_quotes = False
            continue
        if in_quotes:
            m = QUOTE_RE.match(raw)
            if m:
                q = m.group(1).strip()
                # 去除包围用的整段反引号（一段或两段），保留行内代码自身的反引号。
                # `` `x` `` -> `x`；`x` -> x。每层之间顺手去空白。
                while True:
                    q = q.strip()
                    if len(q) >= 2 and q.startswith("`") and q.endswith("`"):
                        inner = q.strip("`").strip()
                        if not inner:
                            break
                        q = inner
                    else:
                        break
                if q:
                    frags[current]["quotes"].append(q)
    return frags


def git_commit_exists(sha: str) -> bool:
    out = subprocess.run(["git", "cat-file", "-e", sha + "^{commit}"],
                         cwd=str(REPO_ROOT),
                         capture_output=True, text=True, timeout=15)
    return out.returncode == 0


def git_show_blob(sha: str, relpath: str) -> str:
    out = subprocess.run(["git", "show", "%s:%s" % (sha, relpath)],
                         cwd=str(REPO_ROOT),
                         capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        raise AssertionError("missing blob %s at %s: %s"
                             % (relpath, sha, (out.stderr or "").strip()[:200]))
    return out.stdout or ""


class TestChecklistExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(CHECKLIST.is_file(), "missing %s" % CHECKLIST)

    def test_eight_fragments(self):
        frags = parse_checklist(CHECKLIST.read_text(encoding="utf-8"))
        self.assertEqual(sorted(frags), ["F-%02d" % i for i in range(1, 9)])

    def test_fields_complete(self):
        frags = parse_checklist(CHECKLIST.read_text(encoding="utf-8"))
        for fid, f in frags.items():
            for key in ("file", "start", "end", "lang", "cats", "quotes"):
                self.assertIn(key, f, "%s missing %s" % (fid, key))
            self.assertLessEqual(f["start"], f["end"])
            self.assertTrue(f["quotes"], "%s has no quotes" % fid)
            self.assertTrue(f["lang"].startswith(("zh", "en")), fid)


class TestQuotesMatchSource(unittest.TestCase):
    def test_quotes_are_substrings_of_cited_line_ranges(self):
        frags = parse_checklist(CHECKLIST.read_text(encoding="utf-8"))
        for fid, f in sorted(frags.items()):
            src = REPO_ROOT / f["file"]
            self.assertTrue(src.is_file(), "%s cites missing file %s" % (fid, f["file"]))
            lines = src.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(f["end"], len(lines),
                                 "%s line range exceeds %s (%d lines)" % (fid, f["file"], len(lines)))
            window = "\n".join(lines[f["start"] - 1:f["end"]])
            for q in f["quotes"]:
                self.assertIn(q, window, "%s quote not in %s L%d-%d: %r"
                              % (fid, f["file"], f["start"], f["end"], q[:60]))


class TestCoverage(unittest.TestCase):
    REQUIRED_CATS = ("术语", "否定", "限制", "代码", "讨论关系")

    def test_both_directions_and_all_categories(self):
        frags = parse_checklist(CHECKLIST.read_text(encoding="utf-8"))
        langs = {f["lang"][:2] for f in frags.values()}
        self.assertIn("zh", langs)
        self.assertIn("en", langs)
        for cat in self.REQUIRED_CATS:
            holders = [fid for fid, f in frags.items() if cat in f["cats"]]
            self.assertTrue(holders, "category %s uncovered" % cat)
        zh_cats = {c for f in frags.values() if f["lang"].startswith("zh") for c in f["cats"]}
        en_cats = {c for f in frags.values() if f["lang"].startswith("en") for c in f["cats"]}
        for cat in self.REQUIRED_CATS:
            self.assertIn(cat, zh_cats, "zh missing %s" % cat)
            self.assertIn(cat, en_cats, "en missing %s" % cat)


class TestHonestyMarkers(unittest.TestCase):
    def test_translation_comparison_marked_not_run(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        self.assertIn("未运行", text)
        self.assertIn("翻译对照", text)

    def test_zero_paid_calls_declared(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        self.assertTrue(("付费调用计数：0" in text) or ("零付费调用" in text))

    def test_no_secrets(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        for rx in SECRET_RES:
            self.assertIsNone(rx.search(text), "secret pattern in checklist")

    def test_materials_commit_is_real_frozen_commit(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        m = re.search(r"materials_commit:\s*([0-9a-f]{40})", text)
        self.assertIsNotNone(m, "materials_commit SHA missing")
        sha = m.group(1)
        # Frozen source commit: must exist as a real commit, but is
        # intentionally NOT required to equal current HEAD. Bumping the
        # SHA without re-verifying quotes would fabricate provenance,
        # and forcing HEAD equality turns every later commit red.
        self.assertTrue(SHA_RE.fullmatch(sha), "materials_commit shape invalid")
        self.assertTrue(git_commit_exists(sha),
                        "materials_commit is not a real commit: %s" % sha)

    def test_quotes_match_frozen_commit_blobs(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        m = re.search(r"materials_commit:\s*([0-9a-f]{40})", text)
        self.assertIsNotNone(m, "materials_commit SHA missing")
        sha = m.group(1)
        self.assertTrue(SHA_RE.fullmatch(sha))
        self.assertTrue(git_commit_exists(sha))
        frags = parse_checklist(text)
        for fid, f in sorted(frags.items()):
            blob = git_show_blob(sha, f["file"])
            lines = blob.splitlines()
            self.assertLessEqual(f["end"], len(lines),
                                 "%s line range exceeds %s@%s (%d lines)"
                                 % (fid, f["file"], sha[:7], len(lines)))
            window = "\n".join(lines[f["start"] - 1:f["end"]])
            for q in f["quotes"]:
                self.assertIn(q, window,
                              "%s quote not in %s@%s L%d-%d: %r"
                              % (fid, f["file"], sha[:7],
                                 f["start"], f["end"], q[:60]))

    def test_eval_freeze_not_claimed(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        self.assertIn("保持 `null`", text)

    def test_blocked_items_recorded_without_fabrication(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        for marker in ("remaining 0/60", "W4", "W5", "E8"):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
