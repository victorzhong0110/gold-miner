#!/usr/bin/env python3
"""Build a reproducible, source-matched unpacked extension and ZIP. No network."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
ROOT = Path(__file__).resolve().parents[1]

def build(source=ROOT / 'extension', output=ROOT / 'dist', source_sha=None):
    source, output = Path(source), Path(output)
    version = json.loads((source / 'manifest.json').read_text())['version']
    if source_sha is None:
        source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    files = sorted(p for p in source.rglob('*') if p.is_file() and p.relative_to(source).parts[0] in ('src', '_locales', 'manifest.json'))
    unpacked = output / 'gold-miner-extension'
    if unpacked.exists(): shutil.rmtree(unpacked)
    unpacked.mkdir(parents=True)
    hashes = {}
    license_files = {name: (ROOT / name).read_bytes() for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md')}
    archive = output / f'gold-miner-extension-{version}.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
        for path in files:
            rel = path.relative_to(source)
            data = path.read_bytes()
            hashes[str(rel)] = hashlib.sha256(data).hexdigest()
            dest = unpacked / rel; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
            info = ZipInfo('gold-miner-extension/' + rel.as_posix(), (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
        for name, data in license_files.items():
            (unpacked / name).write_bytes(data)
            info = ZipInfo('gold-miner-extension/' + name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    manifest = {'version': version, 'source_sha': source_sha, 'source_files_sha256': hashes,
                'license': 'MIT', 'license_files_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in license_files.items()},
                'archive': archive.name, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'browser_installation': 'not-run', 'release_status': 'experimental-not-beta'}
    (output / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = p.parse_args()
    print(json.dumps(build(output=args.output), indent=2))
