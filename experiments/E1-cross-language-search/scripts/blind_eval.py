#!/usr/bin/env python3
"""Prepare masked top-five candidate sheets and analyze completed judgments."""
import argparse
import hashlib
import json
import copy
from pathlib import Path


def include_d(pipeline, d_rows, manifest):
    """Add a completed, same-batch live D run without changing either raw run."""
    if pipeline['mode'] != 'live' or manifest.get('status') != 'complete' or manifest.get('arm') != 'D':
        raise ValueError('combined D preparation requires completed live D evidence')
    if manifest.get('batch') != pipeline.get('batch'):
        raise ValueError('D and A/B/C/M batch must match')
    task_ids = [t['task_id'] for t in pipeline['arms']['A']['task_results']]
    grouped = {t: [] for t in task_ids}
    for row in d_rows:
        if row.get('run_id') != manifest['run_id'] or row.get('arm') != 'D' or row['task_id'] not in grouped:
            raise ValueError('D candidate provenance or task does not match')
        grouped[row['task_id']].append(row)
    if manifest.get('tasks', {}).get('completed') != len(task_ids) or any(not rows for rows in grouped.values()):
        raise ValueError('D evidence must cover every task; incomplete runs need separate preparation')
    for rows in grouped.values():
        rows.sort(key=lambda row: row['rank'])
        if len({row['rank'] for row in rows}) != len(rows) or len({row['repo'].lower() for row in rows}) != len(rows):
            raise ValueError('duplicate D ranks or repositories')
    combined = copy.deepcopy(pipeline)
    combined['arms']['D'] = {'task_results': [{'task_id': t, 'status': 'ok', 'merged_candidates': grouped[t]} for t in task_ids]}
    return combined


def prepare(pipeline):
    public, key = {}, {}
    for arm, result in pipeline['arms'].items():
        for task in result['task_results']:
            for rank, row in enumerate(task['merged_candidates'][:5], 1):
                repo = row['repo'].lower()
                identity = task['task_id'] + ':' + repo
                blind_id = hashlib.sha256((pipeline['run_id'] + ':' + identity).encode()).hexdigest()[:16]
                public[blind_id] = {'blind_id': blind_id, 'task_id': task['task_id'], 'repo': repo,
                                    'url': 'https://github.com/' + repo}
                key.setdefault(blind_id, []).append({'arm': arm, 'rank': rank, 'task_id': task['task_id'], 'repo': repo})
    # Sort by opaque ID, never source rank or arm. Keep the key away from the judge.
    return [public[k] for k in sorted(public)], {'run_id': pipeline['run_id'], 'mode': pipeline['mode'], 'links': key,
        'arm_task_status': {arm: {t['task_id']: t['status'] for t in a['task_results']} for arm, a in pipeline['arms'].items()}}


def analyze(key, judgments, judge_kind):
    if judge_kind not in ('human', 'technical'):
        raise ValueError('judge kind must be explicit')
    indexed = {}
    for row in judgments:
        blind = row['blind_id']
        if blind not in key['links'] or blind in indexed:
            raise ValueError('unknown or duplicate blind judgment')
        for field, choices in [('purpose_fit', ('yes', 'partial', 'no')), ('hard_conditions', ('satisfied', 'conflict', 'unknown')),
                               ('novel_to_judge', ('yes', 'no', 'unknown')), ('worth_following', ('yes', 'no', 'unknown'))]:
            if row.get(field) not in choices:
                raise ValueError('invalid ' + field)
        if not row.get('reason') or not row.get('judge') or not row.get('judged_at'):
            raise ValueError('reason, judge and judged_at required')
        if judge_kind == 'technical' and row['novel_to_judge'] != 'unknown':
            raise ValueError('technical checks cannot claim user novelty')
        indexed[blind] = row
    groups = {}
    for blind, refs in key['links'].items():
        judgment = indexed.get(blind)
        for ref in refs:
            name = ref['task_id'] + ':' + ref['arm']
            group = groups.setdefault(name, {'checked': 0, 'missing': 0, 'suitable': [], 'conditions_unknown': [], 'human_new_discoveries': []})
            if judgment is None: group['missing'] += 1; continue
            group['checked'] += 1
            if judgment['purpose_fit'] == 'yes':
                if judgment['hard_conditions'] == 'satisfied': group['suitable'].append(ref['repo'])
                elif judgment['hard_conditions'] == 'unknown': group['conditions_unknown'].append(ref['repo'])
            if judge_kind == 'human' and judgment['novel_to_judge'] == 'yes' and judgment['worth_following'] == 'yes':
                group['human_new_discoveries'].append(ref['repo'])
    differences = {}
    for task in {name.split(':')[0] for name in groups}:
        task_groups = {arm: groups.get(task + ':' + arm) for arm in ('A', 'C', 'M')}
        complete = all(g is not None and g['missing'] == 0 and key['arm_task_status'].get(arm, {}).get(task) == 'ok' for arm, g in task_groups.items())
        differences[task] = ({'c_minus_a': sorted(set(task_groups['C']['suitable']) - set(task_groups['A']['suitable'])),
                              'c_minus_m': sorted(set(task_groups['C']['suitable']) - set(task_groups['M']['suitable']))} if complete else {'status': 'incomplete-no-comparison'})
    return {'mode': key['mode'], 'judge_kind': judge_kind, 'groups': groups, 'differences': differences,
            'product_effect': 'not-concluded', 'missing_judgments': len(key['links']) - len(indexed)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pipeline'); p.add_argument('--d-run', help='optional completed same-batch D run directory'); p.add_argument('--key'); p.add_argument('--judgments'); p.add_argument('--judge-kind', choices=['human', 'technical']); p.add_argument('--out', required=True)
    args = p.parse_args(); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.pipeline:
        pipeline = json.loads(Path(args.pipeline).read_text())
        if args.d_run:
            d = Path(args.d_run)
            pipeline = include_d(pipeline, [json.loads(l) for l in (d / 'candidates.jsonl').read_text().splitlines() if l.strip()],
                                 json.loads((d / 'manifest.json').read_text()))
        public, key = prepare(pipeline)
        if args.d_run:
            key['source_runs'] = {'ABCM_pipeline': args.pipeline, 'D_run': args.d_run}
        (out / 'blind-candidates.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in public))
        (out / 'blind-key.json').write_text(json.dumps(key, ensure_ascii=False, indent=2) + '\n')
    elif args.key and args.judgments and args.judge_kind:
        result = analyze(json.loads(Path(args.key).read_text()), [json.loads(l) for l in Path(args.judgments).read_text().splitlines() if l.strip()], args.judge_kind)
        (out / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    else: p.error('provide --pipeline, or --key --judgments --judge-kind')

if __name__ == '__main__': main()
