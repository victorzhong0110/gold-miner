import json
import tempfile
import unittest
from pathlib import Path

import e1_bcm_report as rep


def task(tid, repos, status='ok', errors=None):
    return {'task_id': tid, 'status': status, 'errors': errors or [],
            'merged_candidates': [{'repo': r} for r in repos]}


def arm(tasks, **tot):
    totals = {'tasks': len(tasks), 'tasks_ok': 0, 'tasks_partial': 0, 'tasks_blocked': 0, 'tasks_error': 0,
              'attempted_requests': 0, 'failed_requests': 0, 'per_query_records': 0, 'merged_candidates': 0}
    totals.update(tot)
    return {'task_results': tasks, 'totals': totals}


PIPELINE = {
    'run_id': 'r', 'batch': 'eval.batch_1', 'mode': 'live', 'field': 'default', 'source_sha': 'a' * 40,
    'settings_sha256': 'b' * 64, 'started_at': 's', 'finished_at': 'f', 'github_sleep_seconds': 3.0,
    'generation_records': [
        {'task_id': 't1', 'arm': 'B', 'code': 'ok', 'prompt_file': 'b', 'prompt_sha256_16': '1', 'elapsed_seconds': 1.0,
         'request_parameters': {'model': 'MiniMax-M3', 'base_url_host': 'api.minimax.cn', 'max_tokens': 2048, 'timeout_seconds': 300}},
        {'task_id': 't1', 'arm': 'C', 'code': 'bad_response', 'notes': 'parse', 'prompt_file': 'c', 'prompt_sha256_16': '2',
         'elapsed_seconds': 2.0, 'request_parameters': {}},
        {'task_id': 't1', 'arm': 'M', 'code': 'ok', 'prompt_file': 'm', 'prompt_sha256_16': '3', 'elapsed_seconds': 1.0,
         'request_parameters': {}}],
    'model_usage': {k: {'model_requests': 1, 'prompt_tokens': 5, 'completion_tokens': 6, 'reasoning_tokens': 1,
                        'cached_prompt_tokens': 0, 'requests_without_usage': 0} for k in 'BCM'},
    'arms': {
        'A': arm([task('t1', ['X/one'])], attempted_requests=1, tasks_ok=1, merged_candidates=1),
        'B': arm([task('t1', ['x/one', 'd/hit'], errors=[{'error': 'HTTPError 422', 'api_query': 'long'}])],
                 attempted_requests=2, failed_requests=1, tasks_partial=1, merged_candidates=2),
        'C': arm([task('t1', [], status='blocked')], tasks_blocked=1),
        'M': arm([task('t1', ['m/only'])], attempted_requests=2, tasks_ok=1, merged_candidates=1)},
}


class ReportTests(unittest.TestCase):
    def test_counts_failures_and_d_overlap_from_records_only(self):
        s = rep.summarize(PIPELINE, [{'task_id': 't1', 'repo': 'D/Hit'}], [{'task_id': 't1', 'repo': 'x/one'}])
        self.assertEqual(s['arms']['B']['overlap_with_d_task_level'], 1)
        self.assertEqual(s['arms']['A']['overlap_with_d_task_level'], 0)
        self.assertEqual([f['stage'] for f in s['arms']['B']['failures']], ['github_search'])
        self.assertEqual(s['arms']['C']['failures'][0]['code'], 'bad_response')
        self.assertIsNone(s['arms']['A']['visible_tokens'])
        self.assertEqual(s['historical_a_overlap']['overlap'], 1)
        self.assertEqual(s['pairwise']['M-C'], 1)

    def test_cli_writes_report_without_gain_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, d = root / 'run', root / 'd'
            run.mkdir(); d.mkdir()
            (run / 'pipeline.json').write_text(json.dumps(PIPELINE))
            (d / 'candidates.jsonl').write_text(json.dumps({'task_id': 't1', 'repo': 'd/hit'}) + '\n')
            (root / 's.json').write_text('{"freeze": {}, "budget": {}}')
            rep.main(['--run', str(run), '--settings', str(root / 's.json'), '--d-run', str(d),
                      '--record', str(root / 'rec.json')])
            text = (run / 'report.md').read_text()
            self.assertIn('人工用途判断', text)
            self.assertIn('不能宣称跨语言增益', text)
            self.assertIn('C `t1`', text)
            self.assertEqual((run / 'judgments.jsonl').read_text(), '')
            record = json.loads((root / 'rec.json').read_text())
            self.assertEqual(record['cost'], 'unknown')
            self.assertEqual(record['human_judgment'], '未运行')


if __name__ == '__main__':
    unittest.main()
