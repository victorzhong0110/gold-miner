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
