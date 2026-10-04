#!/usr/bin/env python3
"""Summarize an A/B/C/M pipeline run into manifest.json, report.md and a machine record.

Reads only recorded files: <run>/pipeline.json, the D run's candidates.jsonl and an
optional historical A run. No network, no model calls. Set overlap is repository-name
overlap per task, not usefulness; human judgment stays "未运行".
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ARMS = ('A', 'B', 'C', 'M')


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def repo_sets(rows: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in rows:
        out.setdefault(row['task_id'], set()).add(str(row['repo']).strip().lower())
    return out


def summarize(pipeline: dict, d_rows: list[dict], hist_a_rows: list[dict] | None = None) -> dict:
    task_ids = [t['task_id'] for t in pipeline['arms']['A']['task_results']]
    gen = {(r['task_id'], r['arm']): r for r in pipeline['generation_records']}
    sets = {arm: {t['task_id']: {c['repo'].strip().lower() for c in t['merged_candidates']}
                  for t in pipeline['arms'][arm]['task_results']} for arm in ARMS}
    d_sets = repo_sets(d_rows)
    hist = repo_sets(hist_a_rows or [])
    arms = {}
    for arm in ARMS:
        res = pipeline['arms'][arm]
        tot = res['totals']
        failures = []
        for t in res['task_results']:
            g = gen.get((t['task_id'], arm))
            if g and g['code'] != 'ok':
                failures.append({'task_id': t['task_id'], 'stage': 'query_generation', 'code': g['code'],
                                 'notes': g.get('notes', '')})
            for e in t.get('errors') or []:
                failures.append({'task_id': t['task_id'], 'stage': 'github_search', 'code': e['error'],
                                 'api_query': e.get('api_query', '')})
        union = set().union(*[s for s in sets[arm].values()]) if sets[arm] else set()
        d_overlap = sum(len(sets[arm].get(t, set()) & d_sets.get(t, set())) for t in task_ids)
        usage = pipeline.get('model_usage', {}).get(arm) if isinstance(pipeline.get('model_usage'), dict) else None
        arms[arm] = {
            'tasks': tot['tasks'], 'tasks_ok': tot['tasks_ok'], 'tasks_partial': tot['tasks_partial'],
            'tasks_blocked': tot['tasks_blocked'], 'tasks_error': tot['tasks_error'],
            'github_requests_attempted': tot['attempted_requests'],
            'github_requests_failed': tot['failed_requests'],
            'per_query_hits': tot['per_query_records'],
            'merged_candidates_task_level': tot['merged_candidates'],
            'distinct_repos_all_tasks': len(union),
            'overlap_with_d_task_level': d_overlap,
            'model_requests': (usage or {}).get('model_requests', 0),
            'visible_tokens': None if arm == 'A' else {k: (usage or {}).get(k) for k in (
                'prompt_tokens', 'completion_tokens', 'reasoning_tokens', 'cached_prompt_tokens',
                'requests_without_usage')},
            'generation_elapsed_seconds': round(sum(gen[(t, arm)].get('elapsed_seconds') or 0 for t in task_ids
                                                    if (t, arm) in gen), 1) if arm != 'A' else 0,
            'failures': failures,
        }
    per_task = []
    for t in task_ids:
        row = {'task_id': t, 'D': len(d_sets.get(t, set()))}
        for arm in ARMS:
            row[arm] = len(sets[arm].get(t, set()))
            row[arm + '∩D'] = len(sets[arm].get(t, set()) & d_sets.get(t, set()))
        row['C-M'] = len(sets['C'].get(t, set()) - sets['M'].get(t, set()))
        row['M-C'] = len(sets['M'].get(t, set()) - sets['C'].get(t, set()))
        row['C-B'] = len(sets['C'].get(t, set()) - sets['B'].get(t, set()))
        per_task.append(row)
    def total(key):
        return sum(r[key] for r in per_task)
    any_bcm = {t: sets['A'].get(t, set()) | sets['B'].get(t, set()) | sets['C'].get(t, set()) | sets['M'].get(t, set())
               for t in task_ids}
    pair = {k: total(k) for k in ('C-M', 'M-C', 'C-B')}
    pair['ABCM_union_task_level'] = sum(len(s) for s in any_bcm.values())
    pair['ABCM_union_overlap_with_D'] = sum(len(any_bcm[t] & d_sets.get(t, set())) for t in task_ids)
    pair['D_task_level'] = sum(len(d_sets.get(t, set())) for t in task_ids)
    hist_overlap = None
    if hist:
        hist_overlap = {'historical_A_task_level': sum(len(hist.get(t, set())) for t in task_ids),
                        'today_A_task_level': total('A'),
                        'overlap': sum(len(sets['A'].get(t, set()) & hist.get(t, set())) for t in task_ids)}
    return {'task_ids': task_ids, 'arms': arms, 'per_task': per_task, 'pairwise': pair,
            'historical_a_overlap': hist_overlap}


def render_report(pipeline: dict, s: dict, *, settings_path: str, d_run: str, hist_run: str | None) -> str:
    gp = next((r.get('request_parameters') for r in pipeline['generation_records'] if r.get('request_parameters')), {})
    L = [f"# E1 A/B/C/M 运行 {pipeline['run_id']}", '',
         f"- 批次：`{pipeline['batch']}`（{len(s['task_ids'])} 题）。模式：`{pipeline['mode']}`。字段：默认（主比较）。",
         f"- 模型：`{gp.get('model')}`，主机 `{gp.get('base_url_host')}`，`POST /v1/chat/completions`；输出上限 {gp.get('max_tokens')}（含推理），单次超时 {gp.get('timeout_seconds')} 秒，每题每组 1 次请求、不自动重试。",
         f"- 冻结设置：`{settings_path}`（sha256 `{pipeline['settings_sha256']}`）。运行时源码 SHA `{pipeline['source_sha']}`。",
         f"- GitHub：仓库搜索默认字段，每条取前 30，合并后截断 30；串行，每次请求后间隔 {pipeline.get('github_sleep_seconds')} 秒；不自动重试。",
         f"- 开始 {pipeline['started_at']}，结束 {pipeline['finished_at']}（UTC）。",
         '- 可见费用：未知。人工用途判断：未运行。README 字段配对诊断：未运行。', '',
         '## 各组', '',
         '| 组 | 完成/部分/阻断 | 模型请求 | 输入 token（缓存） | 输出 token（其中推理） | GitHub 请求（失败） | 题级合并候选 | 跨题去重仓库 | 与 D 交集（题级） |',
         '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        a = s['arms'][arm]
        tok = a['visible_tokens']
        tin = '—' if tok is None else f"{tok['prompt_tokens']}（{tok['cached_prompt_tokens']}）"
        tout = '—' if tok is None else f"{tok['completion_tokens']}（{tok['reasoning_tokens']}）"
        L.append(f"| {arm} | {a['tasks_ok']}/{a['tasks_partial']}/{a['tasks_blocked'] + a['tasks_error']} | {a['model_requests']} | {tin} | {tout} | {a['github_requests_attempted']}（{a['github_requests_failed']}） | {a['merged_candidates_task_level']} | {a['distinct_repos_all_tasks']} | {a['overlap_with_d_task_level']} |")
    L += ['', 'token 为接口响应里可见的计数；缺计数的请求单列，不按 0 计（本次各组缺计数请求数：' +
          '，'.join(f"{arm} {s['arms'][arm]['visible_tokens']['requests_without_usage']}" for arm in ('B', 'C', 'M')) + '）。', '',
          '## 失败（照实保留，不重跑）', '']
    fails = [(arm, f) for arm in ARMS for f in s['arms'][arm]['failures']]
    if not fails:
        L.append('无。')
    for arm, f in fails:
        extra = f"，查询 `{f['api_query']}`" if f.get('api_query') else ''
        L.append(f"- {arm} `{f['task_id']}` {f['stage']}：`{f['code']}`{extra}。")
    L += ['', '失败按 pipeline 规则不在同一目录续跑或覆盖；查询生成失败的题该组记为阻断（不编造查询），GitHub 单条失败的题记为部分完成。', '',
          '## 与 D 组及组间的仓库集合关系', '',
          f"D 组来自 `{d_run}`（同日、同模型，联网 web_search，GitHub 核对存在的仓库）。下表是仓库全名集合的题级交集与差集，不是用途适合度，也不说明哪一组更好用。", '',
          '| 任务 | A | B | C | M | D | A∩D | B∩D | C∩D | M∩D | C−M | M−C | C−B |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in s['per_task']:
        L.append(f"| {r['task_id']} | {r['A']} | {r['B']} | {r['C']} | {r['M']} | {r['D']} | {r['A∩D']} | {r['B∩D']} | {r['C∩D']} | {r['M∩D']} | {r['C-M']} | {r['M-C']} | {r['C-B']} |")
    blocked = [f"{arm} `{t['task_id']}`" for arm in ARMS for t in pipeline['arms'][arm]['task_results']
               if t['status'] in ('blocked', 'error', 'cancelled')]
    if blocked:
        L += ['', '表中阻断/错误题记 0，不代表搜索无结果：' + '，'.join(blocked) + '。']
    p = s['pairwise']
    L += ['', f"合计：A/B/C/M 题级并集 {p['ABCM_union_task_level']}，其中也在 D 中 {p['ABCM_union_overlap_with_D']}；D 题级 {p['D_task_level']}。C 有而 M 没有 {p['C-M']}，M 有而 C 没有 {p['M-C']}，C 有而 B 没有 {p['C-B']}。"]
    h = s.get('historical_a_overlap')
    if h:
        L += ['', f"今日 A 与历史 A（`{hist_run}`）：今日 {h['today_A_task_level']}，历史 {h['historical_A_task_level']}（仅本批 20 题），题级交集 {h['overlap']}。差异原因未逐条诊断（可能包括 GitHub 索引随时间变化）。"]
    L += ['', '## 不能下的结论', '',
          '- 查询生成失败时记录只保存错误码与说明，不保存模型原文，无法事后复核具体输出。',
          '- 人工用途判断（盲判前 5）未运行，所以没有「合适候选」「独有合适候选」「有价值新发现」数字；候选多或与 D 交集多都不等于更好用。',
          '- 不能宣称跨语言增益：C−M、C−B 只是集合差，未判断用途；按协议第 6–7 节须等盲判后比较 M→C、B→C。',
          '- 已知目标命中@30 不适用：eval.batch_1 是开放任务，种子题不在本批。',
          '- 费用未知；token 是可见计数。单次运行，未估计波动；模型输出每次可能不同。',
          '- C 组提示词允许 `in:description`/`stars`，而主比较拒绝任何字段/stars 语法；本次未触发该冲突，但它对 C 有额外失败风险，后续批次应统一。',
          '- B 组长句整句直译可能超出 GitHub 搜索接受范围（本次 1 条 HTTP 422）。', '']
    return '\n'.join(L)


def build_manifest(pipeline: dict, s: dict, settings: dict, settings_path: str) -> dict:
    gp = next((r.get('request_parameters') for r in pipeline['generation_records'] if r.get('request_parameters')), {})
    return {
        'run_id': pipeline['run_id'], 'batch': pipeline['batch'], 'materials_commit': pipeline['source_sha'],
        'frozen_settings': settings_path, 'settings_sha256': pipeline['settings_sha256'],
        'freeze': settings.get('freeze', {}),
        'prompt_version': {r['arm']: r['prompt_file'] + ' sha256_16:' + r['prompt_sha256_16']
                           for r in pipeline['generation_records']},
        'model': gp.get('model'), 'base_url_host': gp.get('base_url_host'),
        'request_parameters': gp, 'reading_setup': 'reading-baseline.md v1', 'reading_applied': False,
        'method': list(ARMS), 'field_config': pipeline.get('field', 'default'),
        'requested_budget': settings.get('budget', {}),
        'github_sleep_seconds': pipeline.get('github_sleep_seconds'),
        'actual_requests': {arm: {'github': s['arms'][arm]['github_requests_attempted'],
                                  'model': s['arms'][arm]['model_requests']} for arm in ARMS},
        'visible_tokens': {arm: s['arms'][arm]['visible_tokens'] for arm in ('B', 'C', 'M')},
        'cost': 'unknown',
        'started_at': pipeline['started_at'], 'finished_at': pipeline['finished_at'],
        'errors': [dict(f, arm=arm) for arm in ARMS for f in s['arms'][arm]['failures']],
        'human_judgment': '未运行', 'product_effect': 'not-evaluated',
        'artifacts': ['pipeline.json', 'generation.jsonl', 'candidates.jsonl', 'judgments.jsonl', 'report.md'],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', required=True)
    ap.add_argument('--settings', required=True)
    ap.add_argument('--d-run', required=True)
    ap.add_argument('--historical-a', default=None)
    ap.add_argument('--record', required=True, help='machine-readable summary JSON path')
    args = ap.parse_args(argv)
    run = Path(args.run)
    pipeline = json.loads((run / 'pipeline.json').read_text(encoding='utf-8'))
    settings = json.loads(Path(args.settings).read_text(encoding='utf-8'))
    hist_rows = load_jsonl(Path(args.historical_a) / 'candidates.jsonl') if args.historical_a else None
    s = summarize(pipeline, load_jsonl(Path(args.d_run) / 'candidates.jsonl'), hist_rows)
    (run / 'report.md').write_text(render_report(pipeline, s, settings_path=args.settings, d_run=args.d_run,
                                                 hist_run=args.historical_a), encoding='utf-8')
    manifest = build_manifest(pipeline, s, settings, args.settings)
    (run / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    judgments = run / 'judgments.jsonl'
    if not judgments.exists():
        judgments.write_text('', encoding='utf-8')
    record = {'experiment': 'E1', 'arms': list(ARMS), 'batch': pipeline['batch'], 'status': '已运行',
              'run_id': pipeline['run_id'], 'run_directory': str(run), 'report': str(run / 'report.md'),
              'model': manifest['model'], 'base_url_host': manifest['base_url_host'],
              'source_sha': pipeline['source_sha'], 'settings': args.settings,
              'settings_sha256': pipeline['settings_sha256'],
              'started_at': pipeline['started_at'], 'finished_at': pipeline['finished_at'],
              'per_arm': {arm: {k: v for k, v in s['arms'][arm].items()} for arm in ARMS},
              'set_relations': s['pairwise'], 'historical_a_overlap': s['historical_a_overlap'],
              'd_run': args.d_run, 'cost': 'unknown', 'human_judgment': '未运行',
              'cross_language_gain': '未下结论（无人工用途判断）'}
    Path(args.record).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
