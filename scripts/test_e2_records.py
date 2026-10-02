"""Invented fixtures only: no participant sessions are run by these tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from e2_records import session, candidate, session_summary

ROOT = Path(__file__).resolve().parents[1]

def fixture_session(condition='A'):
    return {'session_id':'fixture-'+condition,'pair':'P1','condition':condition,'participant':'P01',
            'reading_lang':'zh','status':'recorded','evidence_kind':'fixture','order':'A_then_B',
            'start':'2026-09-22T09:00:00+08:00' if condition=='A' else '2026-09-22T10:00:00+08:00',
            'end':'2026-09-22T09:10:00+08:00' if condition=='A' else '2026-09-22T10:10:00+08:00',
            'start_url':'https://github.com/fixture/start','interests':['clipboard'],
            'translation':{'tool':'fixture translator','settings':'fixed fixture settings','target_lang':'zh'},
            'method_version':'fixture-method-v1','opened_repos':[], 'worth_follow':None,'reason_quote':None,
            'abandon_reason':None,'prep_minutes':None,'github_requests':None,'model_requests':None,
            'visible_cost':None,'observer_notes':None}

def fixture_candidate():
    return {'session_id':'fixture-A','repo':'fixture/utility','source_url':'https://github.com/fixture/utility',
            'query':None,'method_version':'fixture-method-v1','rank':1,'shown':True,
            'already_known':None,'known_assessed_when':'unknown','opened':None,'worth_follow':None,
            'reason_quote':None,'expected_use':None,'conditions':[],'unknowns':['Fixture unknown requirement'],
            'observer_observation':None,'generated_reason':'Fixture generated rationale, not a human answer'}

class E2RecordsTests(unittest.TestCase):
    def test_full_record_and_schema_can_represent_every_protocol_field(self):
        row=fixture_session();session(row);candidate(fixture_candidate())
        schema=json.loads((ROOT/'experiments/E2-open-ended-discovery/schemas/e2-session.schema.json').read_text())
        self.assertTrue(set(row)<=set(schema['properties']))
        self.assertIn('translation',schema['allOf'][0]['then']['required'])
    def test_recorded_requires_fields_but_unrun_core_is_valid(self):
        row=fixture_session();core={k:row[k] for k in ['session_id','pair','condition','participant','reading_lang','status']}
        with self.assertRaises(ValueError):session(core)
        core['status']='owner-blocked';session(core)
        core['model_requests']=0
        with self.assertRaises(ValueError):session(core)
    def test_unknown_counts_remain_null_and_bool_counts_are_rejected(self):
        row=fixture_session();session(row);self.assertIsNone(row['model_requests'])
        for count in [True,-1,1.5,float('inf')]:
            row=fixture_session();row['github_requests']=count
            with self.assertRaises(ValueError):session(row)
    def test_positive_judgment_cannot_use_model_reason_in_place_of_human_quote(self):
        row=fixture_candidate();row['worth_follow']=True
        with self.assertRaises(ValueError):candidate(row)
        row['reason_quote']='Fixture human quote, not an actual session';candidate(row)
    def test_recall_and_presentation_state_are_explicit(self):
        for patch in [{'shown':False,'rank':1},{'shown':True,'rank':None},
                      {'already_known':False,'known_assessed_when':'unknown'}]:
            row=fixture_candidate();row.update(patch)
            with self.assertRaises(ValueError):candidate(row)
        row=fixture_candidate();row.update(already_known=False,known_assessed_when='after-recall');candidate(row)
    def test_future_naive_and_reversed_timestamps_are_rejected(self):
        for start,end in [('2099-01-01T01:00:00Z','2099-01-01T02:00:00Z'),
                          ('2026-09-22T01:00:00','2026-09-22T02:00:00'),
                          ('2026-09-22T02:00:00Z','2026-09-22T01:00:00Z')]:
            row=fixture_session();row.update(start=start,end=end)
            with self.assertRaises(ValueError):session(row)
    def test_fixtures_never_count_as_human_sessions(self):
        result=session_summary([fixture_session('A'),fixture_session('B')])
        self.assertEqual(result['human_sessions'],0);self.assertEqual(result['fixture_sessions'],2)
        self.assertEqual(result['pair_checks'],[])
        self.assertEqual(result['effectiveness_conclusion'],'not-inferred')
    def test_pair_checker_flags_missing_condition_translation_and_order_without_imputing_results(self):
        a,b=fixture_session('A'),fixture_session('B')
        # These are still invented fixtures; relabeling tests the validator's accounting only.
        a['evidence_kind']=b['evidence_kind']='human-record'
        self.assertFalse(session_summary([a])['pair_checks'][0]['comparable_structure'])
        self.assertTrue(session_summary([a,b])['pair_checks'][0]['comparable_structure'])
        b['translation']['settings']='different fixture baseline'
        self.assertIn('translation baseline differs',session_summary([a,b])['pair_checks'][0]['issues'])
        b['start']=a['start'];b['end']=a['end']
        self.assertIn('order violated or sessions overlap',session_summary([a,b])['pair_checks'][0]['issues'])
        with self.assertRaises(ValueError):session_summary([a,a])
    def test_invalid_date_cli_does_not_echo_input_and_missing_file_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.jsonl';row=fixture_session();row['start']='Bearer fixture-secret-value';p.write_text(json.dumps(row)+'\n')
            run=subprocess.run([sys.executable,str(ROOT/'scripts/stage_records.py'),'session',str(p)],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0);self.assertNotIn('fixture-secret-value',run.stderr)
            missing=subprocess.run([sys.executable,str(ROOT/'scripts/stage_records.py'),'session',str(Path(d)/'missing.jsonl')],capture_output=True,text=True)
            self.assertNotEqual(missing.returncode,0);self.assertNotIn('Traceback',missing.stderr)
