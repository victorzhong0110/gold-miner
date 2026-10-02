#!/usr/bin/env python3
"""Auditable generation -> validation -> A/B/C/M search bridge; no network by default."""
from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path
from e1_batch import build_a_variants, load_queries, run_batch, is_eval_frozen
from query_generation import E1, generate, query_lang, other_lang


def search_variants(task: dict, arm: str, generated: list[dict]) -> list[dict]:
    original = build_a_variants(task)
    source, target = query_lang(task['direction']), other_lang(task['direction'])
    rows, seen = [], {task['query']}
    if not isinstance(generated, list):
        raise ValueError('variants must be an array')
    for row in generated:
        q, lang = row.get('variant_query'), row.get('variant_lang')
        if not isinstance(q, str) or not q.strip() or len(q) > 256 or lang not in ('zh', 'en'):
            raise ValueError('invalid variant')
        q = q.strip()
        if row.get('api_query', q) != q:
            raise ValueError('hidden API query changes are forbidden')
        if re.search(r'\b(?:language|in|stars|repo|user|org):', q, re.I) or re.search(r'\b[\w.-]+/[\w.-]+\b', q):
            raise ValueError('main comparison cannot inject field, star or repo filters')
        if q in seen:
            continue
        seen.add(q)
        rows.append({'variant_query': q, 'variant_lang': lang, 'api_query': q})
    if arm == 'B':
        if len(rows) != 1 or rows[0]['variant_lang'] != target:
            raise ValueError('B requires one target-language translation')
    elif arm == 'M':
        if not 1 <= len(rows) <= 3 or any(r['variant_lang'] != source for r in rows):
            raise ValueError('M requires one to three same-language variants')
    elif arm == 'C':
        targets = [r for r in rows if r['variant_lang'] == target]
        same = [r for r in rows if r['variant_lang'] == source]
        if len(targets) != 2 or len(same) > 2:
            raise ValueError('C requires two distinct target-language variants')
        rows = targets + same[:1]
    else:
        raise ValueError('generated arm must be B, C or M')
    return original + rows


def run_pipeline(tasks, *, run_id, mode='fixture', client=None, http_get=None, token=None,
                 should_cancel=None, allow_network=False):
    if mode not in ('fixture', 'live'):
        raise ValueError('mode must be fixture or live')
    records, mappings = [], {arm: {} for arm in ('B', 'C', 'M')}
    for task in tasks:
        for arm in mappings:
            if should_cancel and should_cancel():
                records.append({'task_id': task['id'], 'arm': arm, 'mode': mode, 'code': 'cancelled', 'variants': []})
                continue
            try:
                row = generate(task, arm, mode, client, allow_network=allow_network)
            except KeyError:
                row = {'task_id': task['id'], 'arm': arm, 'mode': mode, 'code': 'fixture_missing', 'variants': []}
            if row['code'] == 'ok':
                try:
                    mappings[arm][task['id']] = search_variants(task, arm, row['variants'])
                except ValueError as exc:
                    row = dict(row, code='invalid_variants', notes=str(exc))
            records.append(row)
    results = {}
    for arm in ('A', 'B', 'C', 'M'):
        results[arm] = run_batch(tasks=tasks, arm=arm, run_id=run_id + '-' + arm,
                                variants_by_task=mappings.get(arm), http_get=http_get, token=token,
                                should_cancel=should_cancel)
    return {'run_id': run_id, 'mode': mode, 'field': 'default',
            'generation_records': records, 'arms': results,
            'model_usage': 'unknown' if mode == 'live' else 'fixture-no-model-calls',
            'product_effect': 'not-evaluated'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--batch', choices=['dev', 'eval.batch_1'], default='dev')
    parser.add_argument('--out', required=True)
    parser.add_argument('--settings', default=str(E1 / 'run-settings.json'))
    args = parser.parse_args()
    # Formal evaluation must name a configured frozen model before any billable call.
    settings = json.loads(Path(args.settings).read_text())
    if args.batch == 'eval.batch_1':
        model = settings.get('model', {}).get('concrete_model_id')
        if not args.live or not is_eval_frozen(settings) or not model or model != os.environ.get('OPENAI_MODEL'):
            parser.error('formal evaluation requires --live, frozen settings and matching concrete model')
    http_get = None
    if args.live:
        from github_search import _urllib_get
        http_get = _urllib_get
    tasks = load_queries(E1 / 'queries.yaml')[args.batch]
    result = run_pipeline(tasks, run_id='pipeline-dev', mode='live' if args.live else 'fixture',
                          http_get=http_get, allow_network=args.live)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'pipeline.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for kind, rows in [('generation', result['generation_records']),
                       ('candidates', [r for arm in result['arms'].values() for task in arm['task_results'] for r in task['merged_candidates']])]:
        (out / (kind + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    failed = any(r['code'] != 'ok' for r in result['generation_records']) or any(
        arm['totals'].get('failed_requests', 0) or arm['totals'].get('tasks_blocked', 0) for arm in result['arms'].values())
    return 2 if failed else 0

if __name__ == '__main__':
    raise SystemExit(main())
