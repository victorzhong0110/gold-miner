#!/usr/bin/env python3
"""Shared secret scrubbing for E1 run records.

Run records are committed to the repository, so any model output written into
them must be scrubbed first. `e1_d_assistant.py` has carried its own copy of
this logic since the D run; it is left untouched on purpose, because its
output is already recorded and changing it risks the run staying
self-consistent. New and future record writers should import from here.
"""

from __future__ import annotations

import hashlib
import os
import re

SECRET_RES = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"ghs_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.I),
)


def redact(text: str, extra: str = "") -> str:
    """Remove API keys and bearer tokens from text bound for a committed file."""
    out = text or ""
    if extra:
        out = out.replace(extra, "[redacted]")
    for var in ("OPENAI_API_KEY", "GITHUB_TOKEN", "MINIMAX_API_KEY"):
        secret = os.environ.get(var) or ""
        if secret:
            out = out.replace(secret, "[redacted]")
    for pat in SECRET_RES:
        out = pat.sub("[redacted]", out)
    return out


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
