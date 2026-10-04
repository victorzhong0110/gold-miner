import unittest
from e1_pipeline import search_variants, run_pipeline, failure_rows
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


class FailureLedgerTests(unittest.TestCase):
    """The A/B/C/M runner must write the ledger schemas/failures.schema.json
    defines. It used to detect failures, signal them through the exit code, and
    persist nothing -- while the D runner did write failures.jsonl, so the two
    record shapes differed for the same experiment."""

    def _result(self, generation=None, tasks=None):
        arms = {}
        for arm, results in (tasks or {}).items():
            arms[arm] = {'task_results': results}
        return {'run_id': 'r1', 'generation_records': generation or [], 'arms': arms}

    def test_generation_failure_becomes_a_ledger_row(self):
        rows = failure_rows(self._result(generation=[
            {'task_id': 't1', 'arm': 'C', 'code': 'bad_response', 'notes': 'parse failed'},
            {'task_id': 't2', 'arm': 'B', 'code': 'ok', 'notes': 'live model client'},
        ]))
        self.assertEqual(len(rows), 1, 'a successful generation must not appear')
        self.assertEqual(rows[0], {'run_id': 'r1', 'task_id': 't1', 'arm': 'C',
                                   'code': 'bad_response', 'message': 'parse failed'})

    def test_partial_task_records_the_error(self):
        rows = failure_rows(self._result(tasks={'B': [
            {'task_id': 't9', 'status': 'partial',
             'errors': [{'api_query': 'x', 'error': 'HTTPError: HTTP Error 422: Unprocessable Entity'}]}]}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['code'], 'partial')
        self.assertIn('422', rows[0]['message'])
        # additionalProperties is false, so the query must not leak into the row.
        self.assertNotIn('api_query', rows[0])
        self.assertEqual(set(rows[0]), {'run_id', 'task_id', 'arm', 'code', 'message'})

    def test_blocked_task_records_its_reason(self):
        rows = failure_rows(self._result(tasks={'C': [
            {'task_id': 't3', 'status': 'blocked', 'errors': [], 'reason': 'coverage miss'}]}))
        self.assertEqual(rows[0]['code'], 'blocked')
        self.assertEqual(rows[0]['message'], 'coverage miss')

    def test_ok_tasks_are_absent(self):
        rows = failure_rows(self._result(tasks={'A': [
            {'task_id': 't1', 'status': 'ok', 'errors': []},
            {'task_id': 't2', 'status': 'ok', 'errors': []}]}))
        self.assertEqual(rows, [])

    def test_one_cause_can_produce_two_layers(self):
        # Generation failed AND the task ended blocked: two facts, two rows.
        rows = failure_rows(self._result(
            generation=[{'task_id': 't1', 'arm': 'C', 'code': 'bad_response', 'notes': 'x'}],
            tasks={'C': [{'task_id': 't1', 'status': 'blocked', 'errors': [], 'reason': 'y'}]}))
        self.assertEqual({r['code'] for r in rows}, {'bad_response', 'blocked'})
        self.assertEqual(len({r['task_id'] for r in rows}), 1, 'same task, not two tasks')

    def test_rows_validate_against_the_failures_schema(self):
        import json
        from pathlib import Path
        schema = json.loads(
            (Path(__file__).resolve().parents[1] / 'schemas' / 'failures.schema.json')
            .read_text(encoding='utf-8'))
        try:
            import jsonschema
            validate = lambda row: jsonschema.validate(row, schema)
        except Exception:
            required = set(schema['required'])
            allowed = set(schema['properties'])
            arms = set(schema['properties']['arm']['enum'])
            def validate(row):
                self.assertTrue(required <= set(row), f'missing {required - set(row)}')
                self.assertTrue(set(row) <= allowed, f'extra {set(row) - allowed}')
                self.assertIn(row['arm'], arms)
                for field in ('run_id', 'task_id', 'code'):
                    self.assertTrue(isinstance(row[field], str) and row[field])
        result = self._result(
            generation=[{'task_id': 't1', 'arm': 'C', 'code': 'bad_response', 'notes': 'x'}],
            tasks={'B': [{'task_id': 't2', 'status': 'partial', 'errors': [{'error': 'boom'}]}]})
        rows = failure_rows(result)
        self.assertEqual(len(rows), 2)
        for row in rows:
            validate(row)

    def test_run_writes_failures_jsonl_even_when_empty(self):
        import json, sys, tempfile
        from pathlib import Path
        from unittest.mock import patch
        from e1_pipeline import main
        stub = {'run_id': 'r1', 'generation_records': [
            {'task_id': 't1', 'arm': 'A', 'code': 'ok', 'notes': 'ok'}],
            'arms': {'A': {'task_results': [{'task_id': 't1', 'status': 'ok', 'errors': [],
                                             'merged_candidates': []}], 'totals': {}}}}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('e1_pipeline.run_pipeline', return_value=stub), \
                 patch.object(sys, 'argv', ['e1_pipeline.py', '--out', tmp]):
                main()
            ledger = Path(tmp) / 'failures.jsonl'
            # A missing file is indistinguishable from a run that never checked.
            self.assertTrue(ledger.exists(), 'failures.jsonl must always be written')
            self.assertEqual(ledger.read_text(encoding='utf-8'), '')


class LatencyCostTests(unittest.TestCase):
    """Protocol section 6 lists 成本与等待 (actual requests, elapsed, failures,
    human effort, visible cost) as a required observation, and
    schemas/latency-cost.schema.json defines the record. The A/B/C/M runner
    could not produce it: neither half of a cell was ever timed."""

    def test_run_batch_times_ok_error_and_cancelled_paths(self):
        import time
        from e1_batch import run_batch

        def slow(url, headers):
            time.sleep(0.01)
            return {'total_count': 1, 'items': [{'full_name': 'a/b', 'description': 'd',
                                                 'stargazers_count': 1}]}
        task = {'id': 't1', 'direction': 'zh2en', 'query': 'x y'}

        ok = run_batch(tasks=[task], arm='A', run_id='r', http_get=slow)['task_results'][0]
        self.assertIsInstance(ok['elapsed_ms'], int)
        self.assertGreater(ok['elapsed_ms'], 0, 'real work must produce real elapsed time')

        err = run_batch(tasks=[task], arm='A', run_id='r')['task_results'][0]
        self.assertIsInstance(err['elapsed_ms'], int)

        cancelled = run_batch(tasks=[task], arm='A', run_id='r', http_get=slow,
                              should_cancel=lambda: True)['task_results'][0]
        self.assertEqual(cancelled['elapsed_ms'], 0, 'a cancelled task did no work')

    def test_one_row_per_task_and_arm(self):
        from e1_pipeline import run_pipeline, latency_cost_rows
        tasks = [{'id': 't1', 'direction': 'zh2en', 'query': 'x y'},
                 {'id': 't2', 'direction': 'zh2en', 'query': 'a b'}]
        result = run_pipeline(tasks, run_id='r1', mode='fixture')
        rows = result['latency_cost']
        self.assertEqual(len(rows), 8, '2 tasks x 4 arms')
        self.assertEqual({r['arm'] for r in rows}, {'A', 'B', 'C', 'M'})
        self.assertEqual(len({(r['task_id'], r['arm']) for r in rows}), 8)

    def test_rows_validate_against_the_schema(self):
        import json
        from pathlib import Path
        from e1_pipeline import run_pipeline
        schema = json.loads((Path(__file__).resolve().parents[1] /
                             'schemas' / 'latency-cost.schema.json').read_text(encoding='utf-8'))
        try:
            import jsonschema
            validate = lambda row: jsonschema.validate(row, schema)
        except Exception:
            required = set(schema['required'])
            allowed = set(schema['properties'])
            arms = set(schema['properties']['arm']['enum'])
            def validate(row):
                self.assertTrue(required <= set(row))
                self.assertTrue(set(row) <= allowed)
                self.assertIn(row['arm'], arms)
                self.assertIsInstance(row['elapsed_ms'], int)
                self.assertGreaterEqual(row['elapsed_ms'], 0)
        for row in run_pipeline([{'id': 't1', 'direction': 'zh2en', 'query': 'x y'}],
                                run_id='r1', mode='fixture')['latency_cost']:
            validate(row)

    def test_visible_cost_is_never_invented(self):
        from e1_pipeline import latency_cost_rows
        live = latency_cost_rows('r', [], {'A': {'task_results': [{'task_id': 't', 'attempted_requests': 1}]}},
                                 {}, 'live')
        fixture = latency_cost_rows('r', [], {'A': {'task_results': [{'task_id': 't', 'attempted_requests': 1}]}},
                                   {}, 'fixture')
        self.assertEqual(live[0]['visible_cost'], 'unknown')
        self.assertEqual(fixture[0]['visible_cost'], 'fixture-no-model-calls')
        for row in live + fixture:
            self.assertIsInstance(row['visible_cost'], str)
            # A cost is not something this tool can know; never a number.
            self.assertNotIsInstance(row['visible_cost'], (int, float))

    def test_model_requests_uses_the_same_signal_as_summarize_usage(self):
        from e1_pipeline import latency_cost_rows
        records = [{'task_id': 't1', 'arm': 'C', 'request_parameters': {'model': 'm'}},
                   {'task_id': 't1', 'arm': 'A'}]
        rows = latency_cost_rows('r', records,
                                 {'C': {'task_results': [{'task_id': 't1', 'attempted_requests': 4}]},
                                  'A': {'task_results': [{'task_id': 't1', 'attempted_requests': 1}]}},
                                 {}, 'live')
        by_arm = {r['arm']: r for r in rows}
        self.assertEqual(by_arm['C']['model_requests'], 1)
        self.assertEqual(by_arm['A']['model_requests'], 0, 'A makes no model request')
        self.assertEqual(by_arm['C']['github_requests'], 4)
        self.assertEqual(by_arm['A']['github_requests'], 1)

    def test_generation_time_is_added_to_the_cell(self):
        from e1_pipeline import latency_cost_rows
        rows = latency_cost_rows('r', [], {'A': {'task_results': [
            {'task_id': 't1', 'attempted_requests': 1, 'elapsed_ms': 900}]}},
            {('t1', 'A'): 100}, 'live')
        self.assertEqual(rows[0]['elapsed_ms'], 1000)

    def test_run_writes_latency_cost_jsonl(self):
        import json, sys, tempfile
        from pathlib import Path
        from unittest.mock import patch
        from e1_pipeline import main
        stub = {'run_id': 'r1', 'generation_records': [
            {'task_id': 't1', 'arm': 'A', 'code': 'ok', 'notes': 'ok'}],
            'arms': {'A': {'task_results': [{'task_id': 't1', 'status': 'ok', 'errors': [],
                                             'merged_candidates': [], 'elapsed_ms': 5,
                                             'attempted_requests': 1}], 'totals': {}}},
            'latency_cost': [{'run_id': 'r1', 'task_id': 't1', 'arm': 'A', 'elapsed_ms': 5,
                              'github_requests': 1, 'model_requests': 0, 'visible_cost': 'unknown'}]}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('e1_pipeline.run_pipeline', return_value=stub), \
                 patch.object(sys, 'argv', ['e1_pipeline.py', '--out', tmp]):
                main()
            path = Path(tmp) / 'latency_cost.jsonl'
            self.assertTrue(path.exists(), 'latency_cost.jsonl must always be written')
            rows = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['elapsed_ms'], 5)
