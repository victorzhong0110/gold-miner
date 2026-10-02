import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from build_extension import build, ROOT
class BuildTests(unittest.TestCase):
    def test_deterministic_and_source_matched(self):
        with tempfile.TemporaryDirectory() as d:
            first = build(output=d, source_sha='test-source')
            second = build(output=d, source_sha='test-source')
            self.assertEqual(first['archive_sha256'], second['archive_sha256'])
            with ZipFile(Path(d) / first['archive']) as z:
                self.assertIsNone(z.testzip())
                for name, digest in first['source_files_sha256'].items():
                    self.assertEqual(z.read('gold-miner-extension/' + name), (ROOT / 'extension' / name).read_bytes())
                    self.assertEqual(hashlib.sha256(z.read('gold-miner-extension/' + name)).hexdigest(), digest)
                self.assertFalse(any('/tests/' in name for name in z.namelist()))
    def test_checked_in_dist_matches_source(self):
        manifest = json.loads((ROOT / 'dist/build-manifest.json').read_text())
        with ZipFile(ROOT / 'dist' / manifest['archive']) as z:
            for name, digest in manifest['source_files_sha256'].items():
                data = (ROOT / 'extension' / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest, name)
                self.assertEqual(data, (ROOT / 'dist/gold-miner-extension' / name).read_bytes())
                self.assertEqual(data, z.read('gold-miner-extension/' + name))
