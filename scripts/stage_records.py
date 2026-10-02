#!/usr/bin/env python3
"""Validate local discovery entries or E7 diary JSONL; never invent observations."""
import argparse
from datetime import date, datetime
import json
import re
from pathlib import Path

REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')
ACTIONS = {'seen', 'saved', 'tried', 'learned', 'revisited', 'no-opportunity', 'not-used'}


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name}: nonempty text required')
    if re.search(r'sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+', value):
        raise ValueError(f'{name}: possible credential; do not store it')
    return value


def shape(row, allowed, required):
    if not isinstance(row, dict):
        raise ValueError('record must be an object')
    if set(row) - allowed or required - set(row):
        raise ValueError('unexpected or missing fields')


def discovery(row):
    required = {'repo', 'url', 'purpose', 'aliases', 'kind', 'conditions', 'source',
                'processing_status', 'unknowns', 'public_contribution'}
    shape(row, required, required)
    if not isinstance(row['repo'], str) or not REPO.fullmatch(row['repo']):
        raise ValueError('invalid repository')
    if row['url'] != 'https://github.com/' + row['repo']:
        raise ValueError('canonical GitHub URL required')
    shape(row['purpose'], {'zh','en'}, {'zh','en'})
    for lang, value in row['purpose'].items(): text(value, 'purpose.' + lang)
    for field in ('aliases','conditions','unknowns'):
        if not isinstance(row[field], list): raise ValueError(field + ': array required')
        for value in row[field]: text(value, field)
    text(row['kind'], 'kind')
    if row['processing_status'] not in {'generated-unreviewed','human-reviewed'}:
        raise ValueError('explicit processing status required')
    if row['public_contribution'] is not False:
        raise ValueError('public contribution is disabled in this phase')
    source = row['source']
    shape(source, {'url','version','checked_at','license'}, {'url','version','checked_at','license'})
    if not isinstance(source['version'], str) or not SHA.fullmatch(source['version']):
        raise ValueError('source version must name an existing full commit SHA; existence checked by operator')
    prefix = row['url'] + '/blob/' + source['version'] + '/'
    if not isinstance(source['url'], str) or not source['url'].startswith(prefix):
        raise ValueError('source must locate a file at the recorded repository commit')
    if any(x in source['url'] for x in ['?', '#', '..', '\\']):
        raise ValueError('ambiguous source path')
    datetime.fromisoformat(source['checked_at'].replace('Z','+00:00'))
    text(source['license'],'source.license')
    return row


def diary(row):
    required = {'participant','date','reading_lang','action','repo','reason','minutes','visible_cost'}
    shape(row, required, required)
    if not re.fullmatch(r'P[0-9]{2,4}', row['participant']):
        raise ValueError('use pseudonymous participant ID such as P01')
    day = date.fromisoformat(row['date'])
    if day > date.today(): raise ValueError('cannot record a future observation')
    if row['reading_lang'] not in {'zh','en'} or row['action'] not in ACTIONS:
        raise ValueError('unsupported language or action')
    if row['repo'] is not None and not REPO.fullmatch(row['repo']):
        raise ValueError('canonical repository or null required')
    if row['action'] not in {'no-opportunity','not-used'} and row['repo'] is None:
        raise ValueError('repository required for observed project action')
    text(row['reason'], 'reason')
    minutes = row['minutes']
    if minutes is not None and (type(minutes) not in {int,float} or not 0 <= minutes <= 1440):
        raise ValueError('minutes: nonnegative number or null for unknown')
    if row['visible_cost'] is not None: text(row['visible_cost'], 'visible_cost')
    return row


def summarize(rows):
    participants = {}
    seen = set()
    for row in rows:
        diary(row)
        key = (row['participant'],row['date'],row['repo'],row['action'])
        if key in seen: raise ValueError('duplicate observation; do not inflate counts')
        seen.add(key)
        p = participants.setdefault(row['participant'], {'dates':set(), 'actions':{}, 'unknown_cost_records':0})
        p['dates'].add(row['date'])
        p['actions'][row['action']] = p['actions'].get(row['action'],0)+1
        p['unknown_cost_records'] += row['visible_cost'] is None
    for p in participants.values():
        days = sorted(p.pop('dates'))
        p['recorded_dates'] = days
        p['calendar_span_days'] = (date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days+1
        p['seven_day_coverage'] = len(days) >= 7 and p['calendar_span_days'] >= 7
    return {'participants':participants, 'records':len(rows),
            'effectiveness_conclusion':'not-inferred', 'human_followup':'required'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['discovery','diary'])
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    rows = []
    try:
        for number, line in enumerate(args.input.read_text().splitlines(),1):
            if not line.strip(): continue
            row = json.loads(line)
            (discovery if args.kind == 'discovery' else diary)(row)
            rows.append(row)
        output = {'valid_entries':len(rows), 'public_contribution':False} if args.kind == 'discovery' else summarize(rows)
        print(json.dumps(output,ensure_ascii=False,indent=2))
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        parser.exit(1, f'invalid record at or before line {locals().get("number", 0)}: {error}\n')

if __name__ == '__main__': main()
