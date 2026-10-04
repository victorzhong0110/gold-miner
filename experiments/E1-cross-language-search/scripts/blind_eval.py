#!/usr/bin/env python3
"""Prepare masked top-five candidate sheets and analyze completed judgments."""
import argparse
import copy
import hashlib
import json
import os
import re
import datetime
from pathlib import Path

SALT_ENV = "E1_BLIND_SALT"


def resolve_salt(salt_file=None):
    """Return the judge's private salt, or None when running unmasked.

    Deliberately NOT a command-line value: process arguments show up in `ps`
    and shell history, and a salt in either place is a salt in the log. Read it
    from E1_BLIND_SALT or a file the judge keeps outside this repository.

    This script never generates, stores or defaults to a salt. A fixed string in
    a public source file is security theatre, because the repository is public.
    """
    if salt_file:
        return Path(salt_file).read_text(encoding="utf-8").strip() or None
    return (os.environ.get(SALT_ENV) or "").strip() or None


def blind_digest(salt, run_id, task_id, repo):
    """blind_id derivation. The arm is never an input, by design.

    arm-free input is what lets a single judgment cover a repo appearing in
    several arms. It also means the mapping is recomputable from the public run
    records for unsalted IDs. Even salted IDs retain public task/repo identities;
    audit_masking measures both routes.
    """
    prefix = (salt + ':') if salt else ''
    return hashlib.sha256((prefix + run_id + ':' + task_id + ':' + repo).encode()).hexdigest()[:16]



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


def prepare(pipeline, salt=None):
    public, key = {}, {}
    for arm, result in pipeline['arms'].items():
        for task in result['task_results']:
            for rank, row in enumerate(task['merged_candidates'][:5], 1):
                repo = row['repo'].lower()
                blind_id = blind_digest(salt, pipeline['run_id'], task['task_id'], repo)
                public[blind_id] = {'blind_id': blind_id, 'task_id': task['task_id'], 'repo': repo,
                                    'url': 'https://github.com/' + repo}
                key.setdefault(blind_id, []).append({'arm': arm, 'rank': rank, 'task_id': task['task_id'], 'repo': repo})
    # Sort by opaque ID, never source rank or arm. Keep the key away from the judge.
    return [public[k] for k in sorted(public)], {'run_id': pipeline['run_id'], 'mode': pipeline['mode'], 'links': key,
        'arm_task_status': {arm: {t['task_id']: t['status'] for t in a['task_results']} for arm, a in pipeline['arms'].items()},
        'salted': bool(salt)}



def export_judgments(key, judgments, judge_kind):
    """Turn blind judgments into records that satisfy judgments.schema.json.

    The blind step and the repo's only judgments schema describe different
    shapes, and they were incompatible: a blind row carries `blind_id`, which
    the schema forbids, and omits `run_id`/`task_id`/`repo`, which it requires.
    So the records the pending judgment would produce could never be validated
    against the schema that judgment-guide.md calls authoritative.

    The three identity fields are not invented here -- they come from
    blind-key.json, which already maps every blind_id to its task and repo.
    Nothing about the arm is written: the exported row is per (run, task, repo),
    exactly like the non-blind records, so the arm stays out of the record.
    """
    if judge_kind not in ('human', 'technical'):
        raise ValueError('judge kind must be explicit')
    # Reuse duplicate/unknown-ID, categorical and technical-novelty validation.
    analyze(key, judgments, judge_kind)
    run_id = key.get('run_id') or ''
    rows = []
    for row in judgments:
        blind = row['blind_id']
        refs = key['links'].get(blind)
        if not refs:
            raise ValueError('unknown blind judgment: ' + str(blind))
        ref = refs[0]
        # kind/notes are required by the schema and are not read by analyze;
        # they must come from the judge rather than be defaulted here.
        for field in ('kind', 'notes'):
            if field not in row:
                raise ValueError(
                    field + ' is required to export a schema-valid judgment; '
                    'blind-sheet.md asks for it and judgments.schema.json requires it'
                )
        if row['kind'] not in ('tool', 'library', 'tutorial', 'list', 'mirror', 'other') or not isinstance(row['notes'], str):
            raise ValueError('invalid kind or notes')
        for field in ('reason', 'judge'):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError('invalid ' + field)
        stamp = row['judged_at']
        if not isinstance(stamp, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', stamp):
            raise ValueError('judged_at must be RFC 3339 with timezone')
        datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        rows.append({
            'run_id': run_id,
            'task_id': ref['task_id'],
            'repo': ref['repo'],
            'purpose_fit': row['purpose_fit'],
            'hard_conditions': row['hard_conditions'],
            'kind': row['kind'],
            'novel_to_judge': row['novel_to_judge'],
            'worth_following': row['worth_following'],
            'reason': row['reason'],
            'judge': row['judge'],
            'judged_at': row['judged_at'],
            'notes': row['notes'],
        })
    return rows


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
    # Status records include successful zero-hit groups, which have no links.
    # Initialize them before counting judgments; blocked zero-hit groups remain
    # unavailable through the per-comparison status gate below.
    groups = {task + ':' + arm: {'checked': 0, 'missing': 0, 'suitable': [],
                                'conditions_unknown': [], 'human_new_discoveries': []}
              for arm, tasks in key['arm_task_status'].items() for task in tasks}
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
    # Protocol section 6 names three comparisons, not two:
    #   A->C  measures overall assistance
    #   M->C  is the closer read on language extension at equal budget
    #   B->C  decides whether the extra complexity is worth it
    # c_minus_b was missing, and the old single completeness gate ignored B
    # entirely, so a task with every B judgment absent still reported as
    # complete. Each difference now carries its own completeness: a task with a
    # partial B run loses B->C but keeps A->C and M->C, which are valid on their
    # own terms.
    REQUIRED = (('c_minus_a', 'A'), ('c_minus_m', 'M'), ('c_minus_b', 'B'))

    def _arm_ok(arm, task, group):
        return (group is not None and group['missing'] == 0
                and key['arm_task_status'].get(arm, {}).get(task) == 'ok')

    differences = {}
    for task in {name.split(':')[0] for name in groups}:
        entry = {}
        for field, other in REQUIRED:
            c_group, o_group = groups.get(task + ':C'), groups.get(task + ':' + other)
            if _arm_ok('C', task, c_group) and _arm_ok(other, task, o_group):
                entry[field] = sorted(set(c_group['suitable']) - set(o_group['suitable']))
            else:
                entry[field] = {'status': 'incomplete-no-comparison', 'needs': [other, 'C']}
        entry['protocol_basis'] = 'E1 protocol section 6'
        differences[task] = entry
    # D is deliberately not differenced. It ran through a different mechanism
    # (a web-enabled assistant) on a different request budget, and the protocol
    # requires the mechanisms and budgets to be disclosed. This D run covered
    # all 20 tasks, but a D-C set
    # difference would read as like-for-like when it is not. Its per-task
    # suitable sets stay visible under groups for a human to read.
    return {'mode': key['mode'], 'judge_kind': judge_kind, 'groups': groups, 'differences': differences,
            'd_not_differenced': 'D uses a different mechanism and request budget; see E1 protocol sections 6-7',
            'product_effect': 'not-concluded', 'missing_judgments': len(key['links']) - len(indexed)}


def audit_masking(public, pipeline, salt=None):
    """Measure source recovery using hashes and public task/repo identities.

    Salted hashes cannot be recomputed without the salt, but the public sheet
    still names each repository and task. That identity matches the published
    source runs without any key. Salt alone cannot establish blinding.
    """
    run_id = pipeline['run_id']
    recoverable, identities = {}, {}
    for arm, result in pipeline['arms'].items():
        for task in result['task_results']:
            for row in task['merged_candidates'][:5]:
                # Deliberately unsalted: this models the attacker, who has the
                # public run records but NOT the judge's salt. Recomputing with
                # the salt here would measure the judge's own view and always
                # report full exposure, hiding the very thing being audited.
                recoverable.setdefault(
                    blind_digest(None, run_id, task['task_id'], row['repo'].lower()), set()
                ).add(arm)
                identities.setdefault((task['task_id'], row['repo'].lower()), set()).add(arm)
    # Public sheets disclose task_id and repo. Identity matching recovers the
    # source even when the ID hash is salted and the private key is unavailable.
    exposed = [row for row in public if (row['task_id'], row['repo'].lower()) in identities]
    single = [row for row in exposed if len(identities[(row['task_id'], row['repo'].lower())]) == 1]
    per_arm = {}
    for row in single:
        (arm,) = tuple(identities[(row['task_id'], row['repo'].lower())])
        per_arm[arm] = per_arm.get(arm, 0) + 1
    return {
        'run_id': run_id,
        'blind_ids': len(public),
        'arm_group_recoverable': len(exposed),
        'single_arm_attributable': len(single),
        'single_arm_by_group': dict(sorted(per_arm.items())),
        'salted': bool(salt),
        'hash_ids_recoverable': sum(row['blind_id'] in recoverable for row in public),
        'identity_match_recoverable': len(exposed),
        # Describe the measured material, not the flag: a supplied salt does
        # not make unsalted material safe, and this is the only honest label.
        'masking_strength': ('none-mechanical-reversal-possible' if exposed
                             else 'not-derivable-from-public-records'),
        'note': 'Public task_id and repo match the published run records directly, '
                'even with a private salt. Salt changes IDs, not this disclosure. '
                'Material is source-masked, not blind; keep source records away '
                'from judges during a controlled assessment and disclose prior exposure.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pipeline'); p.add_argument('--d-run', help='optional completed same-batch D run directory'); p.add_argument('--key'); p.add_argument('--judgments'); p.add_argument('--judge-kind', choices=['human', 'technical']); p.add_argument('--out', required=True); p.add_argument('--audit-masking', action='store_true', help='report de-anonymizability only, without writing judge material'); p.add_argument('--salt-file', help='file holding the judge\'s private salt; must live outside this repository'); p.add_argument('--key-out', help='write blind-key.json here instead of into --out, so the mapping stays out of the repository')
    args = p.parse_args(); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.pipeline:
        pipeline = json.loads(Path(args.pipeline).read_text())
        if args.d_run:
            d = Path(args.d_run)
            pipeline = include_d(pipeline, [json.loads(l) for l in (d / 'candidates.jsonl').read_text().splitlines() if l.strip()],
                                 json.loads((d / 'manifest.json').read_text()))
        salt = resolve_salt(args.salt_file)
        public, key = prepare(pipeline, salt)
        if args.d_run:
            key['source_runs'] = {'ABCM_pipeline': args.pipeline, 'D_run': args.d_run}
        if args.audit_masking:
            report = audit_masking(public, pipeline, salt)
            (out / 'masking-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        (out / 'blind-candidates.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in public))
        key_dest = Path(args.key_out) if args.key_out else out / 'blind-key.json'
        key_dest.parent.mkdir(parents=True, exist_ok=True)
        key_dest.write_text(json.dumps(key, ensure_ascii=False, indent=2) + '\n')
    elif args.key and args.judgments and args.judge_kind:
        key = json.loads(Path(args.key).read_text())
        judgments = [json.loads(l) for l in Path(args.judgments).read_text().splitlines() if l.strip()]
        result = analyze(key, judgments, args.judge_kind)
        exported = export_judgments(key, judgments, args.judge_kind)
        (out / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        (out / 'judgments.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in exported))
    else: p.error('provide --pipeline, or --key --judgments --judge-kind')

if __name__ == '__main__': main()
