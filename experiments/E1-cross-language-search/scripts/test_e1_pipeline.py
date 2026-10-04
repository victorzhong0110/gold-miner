import unittest
from e1_pipeline import search_variants, run_pipeline
TASK = {'id': 'zh2en-dev-01', 'direction': 'zh2en', 'query': '剪贴板历史 工具'}
def row(q, lang): return {'variant_query': q, 'variant_lang': lang, 'api_query': q}
class PipelineTests(unittest.TestCase):
    def test_c_original_and_two_target_queries_under_four_request_limit(self):
        rows = search_variants(TASK, 'C', [row('剪贴板', 'zh'), row('剪贴板 管理', 'zh'), row('clipboard', 'en'), row('clipboard history', 'en')])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['variant_query'], TASK['query'])
        self.assertEqual(sum(r['variant_lang'] == 'en' for r in rows), 2)
    def test_incomplete_or_changed_language_is_rejected(self):
        for arm, rows in [('B', [row('剪贴板', 'zh')]), ('M', [row('clipboard', 'en')]), ('C', [row('clipboard', 'en')])]:
            with self.assertRaises(ValueError): search_variants(TASK, arm, rows)
    def test_field_star_repo_and_hidden_api_changes_rejected(self):
        for query in ['clipboard language:Chinese', 'clipboard stars:>50', 'clipboard in:readme', 'owner/repo']:
            with self.assertRaises(ValueError): search_variants(TASK, 'B', [row(query, 'en')])
        changed = row('clipboard', 'en'); changed['api_query'] = 'another query'
        with self.assertRaises(ValueError): search_variants(TASK, 'B', [changed])
    def test_fixture_generation_reaches_all_search_arms(self):
        calls = []
        def http(url, headers):
            calls.append(url)
            return {'total_count': 1, 'items': [{'full_name': 'fixture/repo', 'stargazers_count': 0}]}
        output = run_pipeline([TASK], run_id='fixture', http_get=http)
        self.assertEqual(output['mode'], 'fixture')
        self.assertTrue(all(r['code'] == 'ok' for r in output['generation_records']))
        self.assertTrue(all(a['totals']['tasks_ok'] == 1 for a in output['arms'].values()))
        self.assertLessEqual(len(calls), 11)
    def test_missing_live_credentials_does_not_fabricate_variants(self):
        output = run_pipeline([TASK], run_id='blocked', mode='live')
        self.assertTrue(all(r['code'] == 'owner_blocked' for r in output['generation_records']))
        self.assertEqual(output['arms']['C']['totals']['tasks_blocked'], 1)
    def test_cancel_before_generation_sends_no_requests(self):
        output = run_pipeline([TASK], run_id='cancel', should_cancel=lambda: True,
                              http_get=lambda *args: self.fail('network must not run'))
        self.assertTrue(all(r['code'] == 'cancelled' for r in output['generation_records']))

    def test_cli_rejects_existing_output_and_missing_id_before_network(self):
        import tempfile, sys
        from pathlib import Path
        from unittest.mock import patch
        from e1_pipeline import main
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'pipeline.json').write_text('preserve')
            with patch('e1_pipeline.run_pipeline') as run, patch.object(sys,'argv',['e1_pipeline.py','--live','--run-id','new','--out',tmp]):
                with self.assertRaises(SystemExit):main()
                run.assert_not_called()
            self.assertEqual((out/'pipeline.json').read_text(),'preserve')
            (out/'pipeline.json').unlink()
            with patch('e1_pipeline.run_pipeline') as run, patch.object(sys,'argv',['e1_pipeline.py','--live','--out',tmp]):
                with self.assertRaises(SystemExit):main()
                run.assert_not_called()


class FrozenRunGuardTests(unittest.TestCase):
    def _client(self, **kw):
        from query_generation import HttpQueryClient
        args = dict(base_url='https://api.minimax.cn/v1', model='MiniMax-M3', api_key='k', timeout=300.0)
        args.update(kw)
        return HttpQueryClient(lambda *a: None, **args)

    def test_settings_must_match_client_parameters(self):
        from e1_pipeline import check_frozen_settings
        settings = {'model': {'concrete_model_id': 'MiniMax-M3', 'base_url': 'https://api.minimax.cn/v1/',
                              'bcm_max_output_tokens': 2048, 'bcm_timeout_seconds': 300}}
        self.assertEqual(check_frozen_settings(settings, self._client()), [])
        self.assertIn('base_url', check_frozen_settings(settings, self._client(base_url='https://api.minimaxi.com/v1')))
        self.assertTrue(check_frozen_settings(settings, self._client(timeout=60.0)))
        bad = {'model': dict(settings['model'], bcm_max_output_tokens=8192)}
        self.assertIn('bcm_max_output_tokens', check_frozen_settings(bad, self._client()))

    def test_non_empty_output_directory_rejected_before_network(self):
        import tempfile, sys
        from pathlib import Path
        from unittest.mock import patch
        from e1_pipeline import main
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'manifest.json').write_text('d-run')
            with patch('e1_pipeline.run_pipeline') as run, patch('e1_pipeline.default_client_from_env') as mk, \
                    patch.object(sys, 'argv', ['e1_pipeline.py', '--live', '--run-id', 'new', '--out', tmp]):
                with self.assertRaises(SystemExit):
                    main()
                run.assert_not_called()
                mk.assert_not_called()
            self.assertEqual((Path(tmp) / 'manifest.json').read_text(), 'd-run')

    def test_github_spacing_and_usage_summary(self):
        from unittest.mock import patch
        import e1_pipeline
        seen = []
        def fake_batch(**kw):
            seen.append(kw['sleep_seconds'])
            return {'task_results': [], 'totals': {}, 'coverage': None}
        class Client:
            def generate_variants(self, task, arm, prompt):
                return []
        with patch('e1_pipeline.run_batch', fake_batch):
            out = e1_pipeline.run_pipeline([TASK], run_id='x', mode='live', client=Client(), sleep_seconds=3.0)
        self.assertEqual(seen, [3.0] * 4)
        self.assertEqual(out['github_sleep_seconds'], 3.0)
        self.assertEqual(out['model_cost'], 'unknown')
        rows = [{'arm': 'B', 'request_parameters': {}, 'usage': {'prompt_tokens': 5, 'completion_tokens': 7,
                 'reasoning_tokens': 3, 'cached_prompt_tokens': None}},
                {'arm': 'B', 'request_parameters': {}, 'usage': None},
                {'arm': 'C', 'code': 'owner_blocked'}]
        summary = e1_pipeline.summarize_usage(rows)
        self.assertEqual(summary['B']['model_requests'], 2)
        self.assertEqual(summary['B']['requests_without_usage'], 1)
        self.assertEqual(summary['B']['completion_tokens'], 7)
        self.assertEqual(summary['C']['model_requests'], 0)
