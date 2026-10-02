"""Offline provenance/coverage checks for actual-source material; no evaluation."""
import hashlib
import json
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parent
class ContextPackTests(unittest.TestCase):
    def rows(self):return [json.loads(x) for x in (ROOT/'context-pack-2026-10-03.jsonl').read_text().splitlines()]
    def test_bidirectional_sources_and_no_fabricated_evaluation(self):
        rows=self.rows();self.assertEqual({(r['source_language'],r['target_language']) for r in rows},{('en','zh'),('zh','en')})
        for row in rows:
            self.assertEqual(row['translation_status'],'not-run');self.assertEqual(row['human_judgment'],'not-run')
            self.assertIs(row['public_contribution'],False)
    def test_thread_all_turns_and_uncertain_reply_metadata(self):
        row=self.rows()[0];self.assertEqual(row['declared_comments'],row['fetched_comments'])
        self.assertEqual(len(row['turns']),1+row['fetched_comments'])
        self.assertEqual([x['turn'] for x in row['turns']],[1,2,3])
        self.assertEqual([x['author'] for x in row['turns']],['alivault','p0deje','alivault'])
        for turn in row['turns']:
            self.assertIsNone(turn['direct_reply_id']);self.assertRegex(turn['source_body_sha256'],r'^[0-9a-f]{64}$')
            self.assertLessEqual(len(turn['quote'].split()),25)
    def test_conditional_advice_and_specific_type_not_generic_application_id(self):
        turns=self.rows()[0]['turns']
        self.assertIn('If there are any custom types',turns[1]['quote'])
        self.assertIn('com.adobe.indesign-interchange',turns[2]['quote'])
        self.assertIn('not a full-text or image archive',self.rows()[0]['context_scope'])
    def test_code_version_negation_and_original_license_retained(self):
        row=self.rows()[1];self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
        self.assertIn(row['source_commit'],row['source_url'])
        self.assertIn('!types.isDisjoint(with: ignoredTypes)',row['sections'][1]['text'])
        self.assertIn('not present on the NSPasteboardItem',row['sections'][0]['text'])
        notice=(ROOT/row['license_notice']).read_text()
        self.assertIn('Alex Rodionov',notice);self.assertIn('permission notice',notice)
    def test_existing_chinese_snapshot_hashes_and_capture_date(self):
        for row in self.rows()[2:]:
            self.assertEqual(hashlib.sha256((ROOT/row['material_path']).read_bytes()).hexdigest(),row['material_sha256'])
            self.assertEqual(row['source_capture_date'],'2026-09-19')
            self.assertIn('not re-fetched',row['scope'])
