#!/usr/bin/env python3
"""Run every offline unittest + Node extension tests. No network intended."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STEPS = [
    [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(ROOT / "experiments/E1-cross-language-search/scripts"),
        "-p",
        "test_*.py",
    ],
    [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(ROOT / "experiments/E1-cross-language-search/harness"),
        "-p",
        "test_*.py",
    ],
    [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(ROOT / "experiments/E3-faithful-reading"),
        "-p",
        "test_*.py",
    ],
    [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(ROOT / "experiments/E2-open-ended-discovery"),
        "-p",
        "test_*.py",
    ],
    [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "scripts"), "-p", "test_*.py"],
    [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(ROOT / "experiments/E5-local-reuse"),
        "-p",
        "test_*.py",
    ],
    ["node", "--test", str(ROOT / "extension/tests/test_shared.mjs")],
    ["node", "--test", str(ROOT / "extension/tests/test_background.mjs")],
]


def main() -> int:
    for cmd in STEPS:
        print("+", " ".join(cmd), flush=True)
        proc = subprocess.run(cmd, cwd=str(ROOT))
        if proc.returncode != 0:
            return proc.returncode
    print("offline suite ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
