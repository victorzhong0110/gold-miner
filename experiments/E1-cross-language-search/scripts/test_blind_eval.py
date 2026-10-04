import json
import unittest
from blind_eval import prepare, analyze, include_d, audit_masking
class BlindTests(unittest.TestCase):
    def test_combined_d_uses_recorded_rank_and_masks_source(self):
        p = {'run_id': 'bcm', 'mode': 'live', 'batch': 'eval', 'arms': {'A': {'task_results': [
            {'task_id': 't', 'status': 'ok', 'merged_candidates': [{'repo': 'same/repo'}]}]}}}
        m = {'run_id': 'd', 'arm': 'D', 'status': 'complete', 'batch': 'eval', 'tasks': {'completed': 1}}
        rows = [{'run_id': 'd', 'arm': 'D', 'task_id': 't', 'repo': 'same/repo', 'rank': 1}]
        combined = include_d(p, rows, m)
        public, key = prepare(combined)
        self.assertNotIn('D', p['arms'])
        self.assertEqual(len(public), 1)
        self.assertEqual({r['arm'] for r in next(iter(key['links'].values()))}, {'A', 'D'})
        for invalid in [dict(m, batch='other'), dict(m, status='partial')]:
            with self.assertRaises(ValueError): include_d(p, rows, invalid)
        with self.assertRaises(ValueError): include_d(p, rows + rows, m)

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


class MaskingAuditTests(unittest.TestCase):
    """The blind set must not be advertised as stronger than it is.

    blind_id is sha256(run_id + ':' + task_id + ':' + repo)[:16] — the arm is not
    in the hash input, so the published run records are enough to rebuild the
    grouping without opening blind-key.json. Measured on the 2026-10-04
    materials: 196 of 233 blind_ids are attributable to exactly one arm.

    These tests pin that measurement so the tool cannot quietly be trusted as
    "blind". Fixing it needs a salt that is NOT stored in this repository, which
    is the judge's decision; the audit exists to make the gap visible first.
    """

    def _pipeline(self):
        return {'run_id': 'r1', 'mode': 'live', 'arms': {
            arm: {'task_results': [{'task_id': 't1', 'status': 'ok', 'merged_candidates': [
                {'repo': 'only/%s' % arm.lower()}, {'repo': 'shared/repo'}]}]}
            for arm in ('A', 'C', 'M')}}

    def test_single_arm_repos_are_reported_as_attributable(self):
        p = self._pipeline()
        public, _ = prepare(p)
        report = audit_masking(public, p)
        self.assertEqual(report['blind_ids'], 4)
        self.assertEqual(report['arm_group_recoverable'], 4)
        # three repos are single-arm; shared/repo belongs to all three
        self.assertEqual(report['single_arm_attributable'], 3)
        self.assertEqual(report['single_arm_by_group'], {'A': 1, 'C': 1, 'M': 1})
        self.assertEqual(report['masking_strength'], 'none-mechanical-reversal-possible')

    def test_shared_repos_are_not_counted_as_single_arm(self):
        p = self._pipeline()
        public, key = prepare(p)
        report = audit_masking(public, p)
        shared = [r for r in public
                  if {e['arm'] for e in key['links'][r['blind_id']]} == {'A', 'C', 'M'}]
        self.assertEqual(len(shared), 1)
        self.assertNotIn(shared[0]['blind_id'],
                         [r['blind_id'] for r in public
                          if report['single_arm_by_group'] and
                          len({e['arm'] for e in key['links'][r['blind_id']]}) == 1
                          and r['blind_id'] not in {s['blind_id'] for s in shared}])

    def test_audit_needs_no_key_and_agrees_with_it(self):
        p = self._pipeline()
        public, key = prepare(p)
        from_audit = audit_masking(public, p)
        from_key = {}
        for blind, entries in key['links'].items():
            arms = {e['arm'] for e in entries}
            if len(arms) == 1:
                from_key[next(iter(arms))] = from_key.get(next(iter(arms)), 0) + 1
        self.assertEqual(from_audit['single_arm_by_group'], from_key)

    def test_audit_states_the_arms_is_recoverable_not_just_the_key(self):
        p = self._pipeline()
        public, _ = prepare(p)
        report = audit_masking(public, p)
        self.assertIn('source-masked, not blind', report['note'])
        self.assertIn('salt', report['note'])

    def test_arm_is_absent_from_the_hash_input(self):
        # The root cause, stated as a test: same task+repo in two arms must
        # produce the same blind_id, which is what makes the reversal possible.
        p = {'run_id': 'r1', 'mode': 'live', 'arms': {
            arm: {'task_results': [{'task_id': 't1', 'status': 'ok', 'merged_candidates': [
                {'repo': 'same/repo'}]}]} for arm in ('A', 'C')}}
        public, key = prepare(p)
        self.assertEqual(len(public), 1)
        self.assertEqual({e['arm'] for e in next(iter(key['links'].values()))}, {'A', 'C'})


class SaltTests(unittest.TestCase):
    """The judge-held salt is the only thing standing between public data and
    the arm mapping. The script must support it without ever inventing one."""

    def _pipeline(self):
        return {'run_id': 'r1', 'mode': 'live', 'arms': {
            arm: {'task_results': [{'task_id': 't1', 'status': 'ok', 'merged_candidates': [
                {'repo': 'only/%s' % arm.lower()}]}]} for arm in ('A', 'C', 'M')}}

    def test_salt_changes_every_blind_id(self):
        p = self._pipeline()
        plain, _ = prepare(p)
        salted, key = prepare(p, 'judge-private-salt')
        self.assertNotEqual([r['blind_id'] for r in plain], [r['blind_id'] for r in salted])
        self.assertTrue(key['salted'])

    def test_salted_material_is_not_recoverable_from_public_records(self):
        p = self._pipeline()
        salted, _ = prepare(p, 'judge-private-salt')
        report = audit_masking(salted, p, 'judge-private-salt')
        # The attacker only has the public run records, so nothing is derivable.
        self.assertEqual(report['arm_group_recoverable'], 0)
        self.assertEqual(report['single_arm_attributable'], 0)
        self.assertEqual(report['masking_strength'], 'not-derivable-from-public-records')

    def test_audit_never_uses_the_salt_to_measure_exposure(self):
        # Regression: measuring with the salt in hand would always report full
        # exposure and hide exactly what the audit exists to reveal.
        p = self._pipeline()
        plain, _ = prepare(p)
        report = audit_masking(plain, p, 'judge-private-salt')
        self.assertGreater(report['single_arm_attributable'], 0)
        self.assertEqual(report['masking_strength'], 'none-mechanical-reversal-possible')

    def test_unsalted_key_records_that_it_is_unsalted(self):
        _, key = prepare(self._pipeline())
        self.assertFalse(key['salted'])

    def test_resolve_salt_reads_env_and_file_but_never_invents_one(self):
        import os as _os
        import tempfile
        from blind_eval import resolve_salt, SALT_ENV
        previous = _os.environ.pop(SALT_ENV, None)
        try:
            self.assertIsNone(resolve_salt())
            _os.environ[SALT_ENV] = '  from-env  '
            self.assertEqual(resolve_salt(), 'from-env')
            _os.environ[SALT_ENV] = '   '
            self.assertIsNone(resolve_salt(), 'blank env must not become a salt')
            with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as fh:
                fh.write('from-file' + chr(10))
                name = fh.name
            self.assertEqual(resolve_salt(name), 'from-file')
            with open(name, 'w') as fh:
                fh.write('   ' + chr(10))
            self.assertIsNone(resolve_salt(name), 'blank file must not become a salt')
        finally:
            _os.environ.pop(SALT_ENV, None)
            if previous is not None:
                _os.environ[SALT_ENV] = previous
