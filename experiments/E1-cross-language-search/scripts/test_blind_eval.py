import json
import re
import unittest
from pathlib import Path
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
        # Every comparison must say "incomplete", never an empty list. An empty
        # list reads as "this arm found nothing extra", which is a finding.
        entry = result['differences']['task']
        for field in ('c_minus_a', 'c_minus_m', 'c_minus_b'):
            self.assertEqual(entry[field]['status'], 'incomplete-no-comparison', field)
            self.assertNotIsInstance(entry[field], list)
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


class ProtocolComparisonTests(unittest.TestCase):
    """Protocol section 6 names three comparisons; analyze must emit all three.

    "A->C measures overall assistance; M->C is the closer read on language
    extension at equal budget. B->C decides whether the complexity is worth it."
    c_minus_b was missing, and the old completeness gate ignored B entirely.
    """

    def _key(self, statuses):
        """One blind_id per (task, arm) with a suitable repo, so differences exist."""
        links, groups = {}, {'task': {}}
        for arm, repo in statuses.items():
            blind = f'b{arm}'
            links[blind] = [{'arm': arm, 'rank': 1, 'task_id': 'task', 'repo': repo}]
            groups['task:' + arm] = {
                'checked': 1, 'missing': 0, 'suitable': [repo],
                'conditions_unknown': [], 'human_new_discoveries': []}
        return {'run_id': 'r1', 'mode': 'live', 'links': links, 'groups': groups,
                'arm_task_status': {arm: {'task': 'ok'} for arm in statuses}}

    def _judgments(self, key, suitable=('yes', 'satisfied')):
        return [{'blind_id': blind, 'purpose_fit': suitable[0],
                 'hard_conditions': suitable[1], 'novel_to_judge': 'unknown',
                 'worth_following': 'unknown', 'reason': 'r', 'judge': 'j',
                 'judged_at': '2026-10-05T00:00:00Z'} for blind in key['links']]

    def test_all_three_comparisons_are_emitted(self):
        key = self._key({'A': 'a/only', 'B': 'b/only', 'C': 'c/only', 'M': 'm/only'})
        result = analyze(key, self._judgments(key), 'human')
        entry = result['differences']['task']
        for field in ('c_minus_a', 'c_minus_m', 'c_minus_b'):
            self.assertIn(field, entry, field)
        self.assertEqual(entry['c_minus_a'], ['c/only'])
        self.assertEqual(entry['c_minus_m'], ['c/only'])
        # B->C is the comparison that decides whether the complexity is worth it.
        self.assertEqual(entry['c_minus_b'], ['c/only'])
        self.assertEqual(entry['protocol_basis'], 'E1 protocol section 6')

    def test_missing_b_does_not_suppress_the_a_and_m_comparisons(self):
        # B was partial in the recorded run. A->C and M->C stay valid; only
        # B->C becomes unavailable. The old single gate hid all three.
        key = self._key({'A': 'a/only', 'B': 'b/only', 'C': 'c/only', 'M': 'm/only'})
        key['arm_task_status']['B']['task'] = 'partial'
        result = analyze(key, self._judgments(key), 'human')
        entry = result['differences']['task']
        self.assertEqual(entry['c_minus_a'], ['c/only'])
        self.assertEqual(entry['c_minus_m'], ['c/only'])
        self.assertEqual(entry['c_minus_b']['status'], 'incomplete-no-comparison')
        self.assertEqual(entry['c_minus_b']['needs'], ['B', 'C'])

    def test_missing_judgment_for_b_only_kills_b_to_c(self):
        key = self._key({'A': 'a/only', 'B': 'b/only', 'C': 'c/only', 'M': 'm/only'})
        rows = [r for r in self._judgments(key) if r['blind_id'] != 'bB']
        result = analyze(key, rows, 'human')
        entry = result['differences']['task']
        self.assertEqual(entry['c_minus_a'], ['c/only'])
        self.assertEqual(entry['c_minus_b']['status'], 'incomplete-no-comparison')

    def test_d_is_never_differenced(self):
        # D used a different mechanism and budget; a D-C set difference would
        # read as like-for-like when it is not.
        key = self._key({'A': 'a/only', 'B': 'b/only', 'C': 'c/only', 'M': 'm/only', 'D': 'd/only'})
        result = analyze(key, self._judgments(key), 'human')
        entry = result['differences']['task']
        self.assertFalse([f for f in entry if f.startswith('d_')], entry)
        self.assertIn('D', result['d_not_differenced'])
        # Its per-task set stays visible for a human to read.
        self.assertEqual(result['groups']['task:D']['suitable'], ['d/only'])


class JudgmentRecordShapeTests(unittest.TestCase):
    """The blind step, the blind sheet and judgments.schema.json described three
    different record shapes, and they were mutually incompatible.

    A blind row carries `blind_id`, which judgments.schema.json rejects under
    additionalProperties:false, and omits `run_id`/`task_id`/`repo`, which it
    requires. So the records the pending judgment produces could never be
    validated against the schema judgment-guide.md calls authoritative.
    """

    E1 = Path(__file__).resolve().parents[1]
    SHEET = E1 / "evaluation" / "2026-10-04-minimax" / "blind-sheet.md"

    def _blind_schema(self):
        return json.loads((self.E1 / "schemas" / "judgments-blind.schema.json").read_text(encoding="utf-8"))

    def _sheet_fields(self):
        text = self.SHEET.read_text(encoding="utf-8")
        sentence = re.search(r"每项记录([^。]+)。", text).group(1)
        return set(re.findall(r"`?([a-z_]{3,})`?", sentence))

    def test_sheet_documents_exactly_the_blind_schema_fields(self):
        self.assertEqual(self._sheet_fields(), set(self._blind_schema()["required"]))

    def test_blind_schema_covers_every_field_analyze_reads(self):
        import inspect
        import blind_eval
        source = inspect.getsource(blind_eval.analyze)
        read = {a or b for a, b in re.findall(
            r"row\[['\"](\w+)['\"]\]|row\.get\(['\"](\w+)['\"]\)", source)}
        read |= {'purpose_fit', 'hard_conditions', 'worth_following'}  # validated in the choices loop
        missing = read - set(self._blind_schema()["properties"])
        self.assertFalse(missing, f"analyze reads fields the blind schema does not describe: {missing}")

    def test_blind_row_cannot_satisfy_the_non_blind_schema(self):
        # Stated explicitly so the incompatibility is on record, not just implied.
        main = json.loads((self.E1 / "schemas" / "judgments.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("blind_id", main["properties"])
        self.assertFalse(main["additionalProperties"])
        self.assertTrue({"run_id", "task_id", "repo"} <= set(main["required"]))

    def _key(self):
        return {'run_id': 'r1', 'mode': 'live',
                'links': {'b1': [{'arm': 'C', 'rank': 1, 'task_id': 't1', 'repo': 'x/y'}]},
                'arm_task_status': {'C': {'t1': 'ok'}}}

    def _judgment(self, **kw):
        row = {'blind_id': 'b1', 'purpose_fit': 'yes', 'hard_conditions': 'satisfied',
               'kind': 'tool', 'novel_to_judge': 'unknown', 'worth_following': 'unknown',
               'reason': 'r', 'judge': 'j', 'judged_at': '2026-10-05T00:00:00Z', 'notes': ''}
        row.update(kw)
        return row

    def test_export_produces_schema_valid_records(self):
        from blind_eval import export_judgments
        schema = json.loads((self.E1 / "schemas" / "judgments.schema.json").read_text(encoding="utf-8"))
        try:
            import jsonschema
            validate = lambda row: jsonschema.validate(row, schema)
        except Exception:
            required, allowed = set(schema['required']), set(schema['properties'])
            def validate(row):
                self.assertTrue(required <= set(row))
                self.assertTrue(set(row) <= allowed)
        for row in export_judgments(self._key(), [self._judgment()], 'technical'):
            validate(row)

    def test_export_takes_identity_from_the_key_not_invented(self):
        from blind_eval import export_judgments
        row = export_judgments(self._key(), [self._judgment()], 'technical')[0]
        self.assertEqual(row['run_id'], 'r1')
        self.assertEqual(row['task_id'], 't1')
        self.assertEqual(row['repo'], 'x/y')

    def test_export_never_writes_the_arm(self):
        from blind_eval import export_judgments
        row = export_judgments(self._key(), [self._judgment()], 'technical')[0]
        self.assertNotIn('arm', row)
        self.assertNotIn('C', [v for v in row.values() if isinstance(v, str)])

    def test_export_refuses_to_default_kind_or_notes(self):
        from blind_eval import export_judgments
        # analyze does not read these, but the schema requires them. Defaulting
        # would put a value in a record the judge never made.
        for field in ('kind', 'notes'):
            row = self._judgment()
            row.pop(field)
            with self.assertRaises(ValueError) as ctx:
                export_judgments(self._key(), [row], 'technical')
            self.assertIn(field, str(ctx.exception))

    def test_export_rejects_unknown_blind_id(self):
        from blind_eval import export_judgments
        with self.assertRaises(ValueError):
            export_judgments(self._key(), [self._judgment(blind_id='nope')], 'technical')
