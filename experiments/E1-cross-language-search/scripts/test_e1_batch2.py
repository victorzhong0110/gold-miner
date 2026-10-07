"""Correction batch regression: injected fixtures only, never live providers."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import e1_batch
import e1_pipeline
import query_generation as generation

E1 = generation.E1
BATCH2 = E1 / 'batches/eval.batch_2'


class Batch2Tests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((BATCH2 / 'run-settings.draft.json').read_text())
        self.task = e1_batch.load_queries(BATCH2 / 'queries.yaml')['dev'][0]

    def test_legacy_materials_still_match_actual_run_freeze(self):
        frozen = json.loads((E1 / 'run-settings-2026-10-04-bcm-minimax.json').read_text())
        for name, digest in frozen['freeze']['material_sha256'].items():
            self.assertEqual(hashlib.sha256((E1 / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(json.loads((E1 / 'materials-status.json').read_text())['resolution']['status'],
                         'not-fixed-in-this-batch')

    def test_second_batch_has_same_public_tasks_and_no_first_batch_fallback(self):
        old = e1_batch.load_queries(E1 / 'queries.yaml')
        new = e1_batch.load_queries(BATCH2 / 'queries.yaml')
        self.assertEqual(set(old), {'dev', 'eval.batch_1'})
        self.assertEqual(new['eval.batch_1'], [])
        self.assertEqual(new['eval.batch_2'], old['eval.batch_1'])
        self.assertEqual(len(new['eval.batch_2']), 20)
        self.assertFalse(e1_batch.is_eval_frozen(self.settings))
        self.assertEqual(e1_pipeline.check_batch2_materials(self.settings, BATCH2 / 'queries.yaml'), [])

    def test_material_fingerprints_reject_wrong_query_prompt_and_identity(self):
        for field in ['queries_sha256', 'prompts_sha256']:
            settings = copy.deepcopy(self.settings)
            settings['material_fingerprints'][field] = 'wrong' if field == 'queries_sha256' else {}
            self.assertTrue(e1_pipeline.check_batch2_materials(settings, BATCH2 / 'queries.yaml'))
        settings = copy.deepcopy(self.settings)
        settings['prompt_profile'] = 'eval.batch_1'
        self.assertIn('batch/profile identity', e1_pipeline.check_batch2_materials(settings, BATCH2 / 'queries.yaml'))
        self.assertIn('queries digest', e1_pipeline.check_batch2_materials(self.settings, E1 / 'queries.yaml'))

    def test_query_parse_binds_exact_bytes(self):
        with self.assertRaisesRegex(ValueError, 'digest changed'):
            e1_batch.load_queries(E1 / 'queries.yaml', expected_sha256=self.settings['material_fingerprints']['queries_sha256'])

    def test_corrected_profile_is_separate_and_c_generation_passes_search_contract(self):
        old_paths = dict(generation.PROMPTS)
        captured = []
        class Client:
            def generate_variants(_, task, arm, prompt):
                captured.append(prompt)
                return [{'variant_query': q, 'variant_lang': lang, 'api_query': q}
                        for q, lang in [('剪贴板 管理', 'zh'), ('clipboard history', 'en'), ('clipboard manager', 'en')]]
        row = generation.generate(self.task, 'C', 'live', Client(), prompt_profile='eval.batch_2',
                                  expected_prompt_sha256=self.settings['material_fingerprints']['prompts_sha256']['C'])
        self.assertEqual(row['code'], 'ok')
        self.assertEqual(len(e1_pipeline.search_variants(self.task, 'C', row['variants'])), 4)
        self.assertIn('batches/eval.batch_2/prompts/c-rewrite.txt', row['prompt_file'])
        self.assertEqual(row['prompt_sha256_16'], hashlib.sha256(captured[0].encode()).hexdigest()[:16])
        self.assertNotIn('stars 可用', captured[0])
        self.assertEqual(generation.PROMPTS, old_paths)

    def test_wrong_prompt_digest_refuses_before_client(self):
        class Client:
            def generate_variants(_, *args):
                self.fail('no provider dispatch allowed')
        with self.assertRaisesRegex(ValueError, 'before dispatch'):
            generation.generate(self.task, 'B', 'live', Client(), prompt_profile='eval.batch_2',
                                expected_prompt_sha256='wrong')

    def test_record_digest_is_the_prompt_sent_not_a_later_file_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt_path = root / 'b.txt'
            prompt_path.write_text('fixture sent prompt')
            class Client:
                def generate_variants(_, task, arm, prompt):
                    self.assertEqual(prompt, 'fixture sent prompt')
                    prompt_path.write_text('changed after outbound')
                    return []
            with patch.object(generation, 'ROOT', root), patch.object(generation, 'prompt_paths', return_value={'B': prompt_path}):
                row = generation.generate(self.task, 'B', 'live', Client())
            self.assertEqual(row['prompt_sha256_16'], hashlib.sha256(b'fixture sent prompt').hexdigest()[:16])

    def test_all_qualifiers_prohibited_in_every_prompt_and_rejected_at_boundary(self):
        qualifiers = ['in:readme', 'in:name', 'in:description', 'language:', 'stars:', 'repo:', 'user:', 'org:']
        for path in generation.prompt_paths('eval.batch_2').values():
            prohibition = next(line for line in path.read_text().splitlines() if line.startswith('4. '))
            self.assertIn('均禁止', prohibition)
            for qualifier in qualifiers:
                self.assertIn(qualifier, prohibition)
        for qualifier in qualifiers + ['owner/repo']:
            with self.subTest(qualifier=qualifier), self.assertRaises(ValueError):
                q = 'clipboard ' + qualifier + ('fixture' if qualifier.endswith(':') else '')
                e1_pipeline.search_variants(self.task, 'B', [{'variant_query': q, 'variant_lang': 'en', 'api_query': q}])

    def test_incomplete_c_remains_blocked_no_fabricated_completion(self):
        with self.assertRaisesRegex(ValueError, 'two distinct'):
            e1_pipeline.search_variants(self.task, 'C', [{'variant_query': 'clipboard', 'variant_lang': 'en'}])

    def test_fixture_pipeline_uses_batch2_and_no_actual_network(self):
        def fixture_http(url, headers):
            return {'total_count': 1, 'items': [{'full_name': 'fixture/repo', 'stargazers_count': 0}]}
        output = e1_pipeline.run_pipeline([self.task], run_id='fixture-batch2', http_get=fixture_http,
                                         prompt_profile='eval.batch_2', expected_prompts_sha256=self.settings['material_fingerprints']['prompts_sha256'])
        self.assertEqual(output['model_cost'], 'fixture-no-model-calls')
        self.assertTrue(all(row['code'] == 'ok' and 'batches/eval.batch_2' in row['prompt_file'] for row in output['generation_records']))
        self.assertTrue(all(arm['totals']['tasks_ok'] == 1 for arm in output['arms'].values()))

    def test_unfrozen_formal_pipeline_cannot_dispatch_or_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'new-output'
            args = ['e1_pipeline.py', '--batch', 'eval.batch_2', '--queries', str(BATCH2 / 'queries.yaml'),
                    '--settings', str(BATCH2 / 'run-settings.draft.json'), '--out', str(out)]
            with patch.object(sys, 'argv', args), patch.object(e1_pipeline, 'run_pipeline') as dispatch:
                with self.assertRaises(SystemExit):
                    e1_pipeline.main()
                dispatch.assert_not_called()
            self.assertFalse(out.exists())

    def test_batch_cli_rejects_first_batch_settings_before_search(self):
        args = ['--batch', 'eval.batch_2', '--queries', str(BATCH2 / 'queries.yaml'),
                '--run-settings', str(E1 / 'run-settings.json'), '--arm', 'A', '--run-id', 'fixture', '--out-dir', '/tmp/unused-batch2-output']
        with patch.object(e1_batch, 'run_batch') as dispatch:
            self.assertEqual(e1_batch.main(args), 3)
            dispatch.assert_not_called()

    def test_generator_cli_refuses_profile_mix_and_live_freeze_bypass(self):
        base = ['--task-id', self.task['id'], '--arm', 'B', '--prompt-profile', 'eval.batch_2']
        for args in [base, base + ['--queries', str(BATCH2 / 'queries.yaml'), '--mode', 'live']]:
            with patch.object(generation, 'generate') as dispatch:
                with self.assertRaises(SystemExit):
                    generation.main(args)
                dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
