import json
import unittest
from blind_eval import prepare, analyze
class BlindTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = {'run_id': 'fixture', 'mode': 'fixture', 'arms': {arm: {'task_results': [{'task_id': 'task', 'status': 'ok', 'merged_candidates': [{'repo': 'safe/repo', 'arm': arm, 'rank': 1, 'sources': ['secret-lane']}]}]} for arm in ('A', 'C', 'M')}}
        self.public, self.key = prepare(self.pipeline)
        self.row = {'blind_id': self.public[0]['blind_id'], 'purpose_fit': 'yes', 'hard_conditions': 'unknown', 'novel_to_judge': 'unknown', 'worth_following': 'unknown', 'reason': 'fixture reason', 'judge': 'fixture-technical', 'judged_at': '2026-10-02T00:00:00Z'}
    def test_union_is_masked_and_key_preserves_all_arms(self):
        self.assertEqual(len(self.public), 1)
        self.assertNotIn('sources', json.dumps(self.public))
        self.assertNotIn('rank', json.dumps(self.public))
        self.assertEqual(len(next(iter(self.key['links'].values()))), 3)
    def test_unknown_conditions_cannot_be_counted_suitable(self):
        result = analyze(self.key, [self.row], 'technical')
        self.assertTrue(all(not g['suitable'] for g in result['groups'].values()))
        self.assertTrue(all(not g['human_new_discoveries'] for g in result['groups'].values()))
    def test_missing_judgments_do_not_become_zero_effect(self):
        result = analyze(self.key, [], 'human')
        self.assertEqual(result['missing_judgments'], 1)
        self.assertEqual(result['differences']['task']['status'], 'incomplete-no-comparison')
    def test_duplicate_unknown_and_false_user_novelty_rejected(self):
        for rows in [[self.row, self.row], [dict(self.row, blind_id='unknown')], [dict(self.row, novel_to_judge='yes')]]:
            with self.assertRaises(ValueError): analyze(self.key, rows, 'technical')
