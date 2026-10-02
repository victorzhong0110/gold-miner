import copy
import json
from pathlib import Path
import unittest
from stage_records import discovery, diary, summarize

ROOT = Path(__file__).resolve().parents[1]
class StageRecordsTests(unittest.TestCase):
    def entry(self):
        return json.loads((ROOT/'experiments/E5-local-reuse/discovery-entries.jsonl').read_text().splitlines()[0])
    def observation(self, day='2026-09-22'):
        return {'participant':'P01','date':day,'reading_lang':'zh','action':'no-opportunity',
                'repo':None,'reason':'Fixture: no usage opportunity','minutes':None,'visible_cost':None}
    def test_source_entry_and_bilingual_fields(self): discovery(self.entry())
    def test_reject_hostile_urls_private_extras_and_sharing(self):
        for patch in [{'url':'https://evil.invalid/x'},{'private_note':'private'},
                      {'apiKey':'fixture'},{'public_contribution':True}]:
            entry = self.entry(); entry.update(patch)
            with self.assertRaises(ValueError): discovery(entry)
    def test_source_commit_and_generated_state_required(self):
        entry = self.entry(); entry['source']['version']='HEAD'
        with self.assertRaises(ValueError): discovery(entry)
        entry = self.entry(); entry['processing_status']='verified-effective'
        with self.assertRaises(ValueError): discovery(entry)
    def test_null_cost_and_no_opportunity_are_not_zero_or_failure(self):
        summary = summarize([self.observation()])['participants']['P01']
        self.assertEqual(summary['unknown_cost_records'],1)
        self.assertFalse(summary['seven_day_coverage'])
        self.assertEqual(summary['actions'],{'no-opportunity':1})
    def test_actions_need_repo_and_reason(self):
        row = self.observation(); row['action']='tried'
        with self.assertRaises(ValueError): diary(row)
        row = self.observation(); row['reason']=''
        with self.assertRaises(ValueError): diary(row)
    def test_duplicate_dates_do_not_make_week(self):
        with self.assertRaises(ValueError): summarize([self.observation(),self.observation()])
        rows = [self.observation('2026-09-'+str(day)) for day in range(22,29)]
        result = summarize(rows)
        self.assertTrue(result['participants']['P01']['seven_day_coverage'])
        self.assertEqual(result['effectiveness_conclusion'],'not-inferred')
    def test_future_and_secrets_rejected(self):
        row = self.observation('2099-01-01')
        with self.assertRaises(ValueError): diary(row)
        row = self.observation(); row['reason']='Bearer fixture-secret'
        with self.assertRaises(ValueError): diary(row)
