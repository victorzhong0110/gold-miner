#!/usr/bin/env python3
"""Auditable generation -> validation -> A/B/C/M search bridge; no network by default."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from e1_batch import build_a_variants, load_queries, run_batch, is_eval_frozen, materials_commit
from query_generation import E1, MAX_OUTPUT_TOKENS, generate, query_lang, other_lang, default_client_from_env

# GitHub search allows 30 authenticated requests/minute; space serial calls (not a guarantee).
DEFAULT_GITHUB_SLEEP_SECONDS = 3.0


# Qualifiers the main comparison forbids in a variant query.
#
# The comparison is A (plain default search) against B/C/M. If any arm may use
# field, star or repo qualifiers, it searches a different space than A and the
# difference stops measuring cross-language rewriting. So the prompts and this
# rule must agree; e1_materials_check.py exists to catch them disagreeing.
FORBIDDEN_QUERY_SYNTAX = re.compile(r'\b(?:language|in|stars|repo|user|org):', re.I)
FORBIDDEN_REPO_TOKEN = re.compile(r'\b[\w.-]+/[\w.-]+\b')


def forbidden_query_syntax(q: str) -> bool:
    """True when a variant query would break the main comparison."""
    return bool(FORBIDDEN_QUERY_SYNTAX.search(q) or FORBIDDEN_REPO_TOKEN.search(q))


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
        if forbidden_query_syntax(q):
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


def summarize_usage(records):
    """Per-arm visible token totals; requests without counters are counted, not zero-filled."""
    out = {}
    for row in records:
        arm = out.setdefault(row['arm'], {'model_requests': 0, 'requests_with_usage': 0,
                                          'requests_without_usage': 0, 'prompt_tokens': 0,
                                          'completion_tokens': 0, 'reasoning_tokens': 0,
                                          'cached_prompt_tokens': 0})
        if 'request_parameters' not in row:
            continue
        arm['model_requests'] += 1
        usage = row.get('usage')
        if not isinstance(usage, dict):
            arm['requests_without_usage'] += 1
            continue
        arm['requests_with_usage'] += 1
        for key in ('prompt_tokens', 'completion_tokens', 'reasoning_tokens', 'cached_prompt_tokens'):
            if isinstance(usage.get(key), int):
                arm[key] += usage[key]
    return out


def check_frozen_settings(settings, client):
    """Pinned model parameters must match the configured client before any request."""
    model = settings.get('model', {}) if isinstance(settings, dict) else {}
    problems = []
    if not client or model.get('concrete_model_id') != client.model:
        problems.append('concrete model')
    base = model.get('base_url')
    if base is not None and (not client or base.rstrip('/') != client.base_url):
        problems.append('base_url')
    tokens = model.get('bcm_max_output_tokens')
    if tokens is not None and tokens != MAX_OUTPUT_TOKENS:
        problems.append('bcm_max_output_tokens')
    timeout = model.get('bcm_timeout_seconds')
    if timeout is not None and (not client or float(timeout) != float(client.timeout)):
        problems.append('bcm_timeout_seconds (BYOK_TIMEOUT_SECONDS)')
    return problems


def run_pipeline(tasks, *, run_id, mode='fixture', client=None, http_get=None, token=None,
                 should_cancel=None, allow_network=False, sleep_seconds=0):
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
                                should_cancel=should_cancel, sleep_seconds=sleep_seconds)
    return {'run_id': run_id, 'mode': mode, 'field': 'default',
            'generation_records': records, 'arms': results,
            'model_usage': summarize_usage(records) if mode == 'live' else 'fixture-no-model-calls',
            'model_cost': 'unknown' if mode == 'live' else 'fixture-no-model-calls',
            'github_sleep_seconds': sleep_seconds,
            'product_effect': 'not-evaluated'}


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--batch', choices=['dev', 'eval.batch_1'], default='dev')
    parser.add_argument('--out', required=True)
    parser.add_argument('--run-id', help='required for live runs; use a new ID and output directory')
    parser.add_argument('--settings', default=str(E1 / 'run-settings.json'))
    args = parser.parse_args()
    out = Path(args.out)
    if (out / 'pipeline.json').exists():
        parser.error('output already exists; use a new directory (no overwrite or automatic retry)')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error('output directory is not empty (e.g. an existing D run); use a new directory')
    if args.live and not args.run_id:
        parser.error('live runs require an explicit --run-id')
    client = default_client_from_env() if args.live else None
    if args.live and client is None:
        parser.error('owner-blocked: live A/B/C/M run requires valid OPENAI_* configuration before any requests')
    # Formal evaluation must name a configured frozen model before any billable call.
    settings = json.loads(Path(args.settings).read_text())
    if args.batch == 'eval.batch_1':
        model = settings.get('model', {}).get('concrete_model_id')
        if not args.live or not is_eval_frozen(settings) or not model or model != os.environ.get('OPENAI_MODEL'):
            parser.error('formal evaluation requires --live, frozen settings and matching concrete model')
        problems = check_frozen_settings(settings, client)
        if problems:
            parser.error('frozen settings do not match the configured client: ' + ', '.join(problems))
    sleep_seconds = float(settings.get('github', {}).get('sleep_seconds_between_search_requests',
                                                         DEFAULT_GITHUB_SLEEP_SECONDS)) if args.live else 0
    http_get = None
    if args.live:
        from github_search import _urllib_get
        http_get = _urllib_get
    tasks = load_queries(E1 / 'queries.yaml')[args.batch]
    started_at = _utcnow()
    result = run_pipeline(tasks, run_id=args.run_id or 'fixture-dev', mode='live' if args.live else 'fixture',
                          client=client, http_get=http_get, allow_network=args.live,
                          sleep_seconds=sleep_seconds)
    result['started_at'], result['finished_at'] = started_at, _utcnow()
    result['source_sha'] = materials_commit()
    result['settings_sha256'] = hashlib.sha256(Path(args.settings).read_bytes()).hexdigest()
    result['batch'] = args.batch
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
