#!/usr/bin/env bash
# Package the unpacked extension and a zip for sharing (no secrets).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXT="$ROOT/extension"
DIST="$ROOT/dist/gold-miner-extension"
ZIP="$ROOT/dist/gold-miner-extension-0.1.0.zip"

rm -rf "$DIST"
mkdir -p "$DIST"
cp -R "$EXT/manifest.json" "$EXT/_locales" "$EXT/src" "$DIST/"
# Do not copy tests or local env files.
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("dist/gold-miner-extension/manifest.json")
# allow running from repo root
import os
root = os.environ.get("ROOT")
PY
cd "$ROOT"
python3 -c 'import json,pathlib; json.loads(pathlib.Path("dist/gold-miner-extension/manifest.json").read_text())'
rm -f "$ZIP"
(cd "$ROOT/dist" && zip -qr "gold-miner-extension-0.1.0.zip" gold-miner-extension)
echo "unpacked: $DIST"
echo "zip: $ZIP"
