"""E2 structural validation. Human observations are supplied only by the operator."""
from datetime import datetime, timezone
from urllib.parse import urlsplit
import re
from stage_records import shape, text, REPO

CORE = {'session_id','pair','condition','participant','reading_lang','status'}
DETAIL = {'evidence_kind','order','start','end','start_url','interests','translation',
          'method_version','opened_repos','worth_follow','reason_quote','abandon_reason',
          'prep_minutes','github_requests','model_requests','visible_cost','observer_notes'}
CANDIDATE = {'session_id','repo','source_url','query','method_version','rank','shown',
             'already_known','known_assessed_when','opened','worth_follow','reason_quote',
             'expected_use','conditions','unknowns','observer_observation','generated_reason'}


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None or result.utcoffset() is None: raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('timestamp: timezone-aware ISO date required') from None
    if result > datetime.now(timezone.utc): raise ValueError('future observation is not allowed')
    return result


def github_url(value):
    text(value,'source URL')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or parsed.netloc != 'github.com' or not parsed.path.startswith('/'):
        raise ValueError('public canonical GitHub source URL required')
    return value


def optional_text(value, field):
    if value is not None: text(value,field)


def tri_state(value):
    if value is not None and type(value) is not bool: raise ValueError('boolean or null for unknown required')


def strings(value, field, repos=False):
    if not isinstance(value,list): raise ValueError(field+': array required')
    for item in value:
        text(item,field)
        if repos and not REPO.fullmatch(item): raise ValueError('canonical owner/repo required')


def count(value, field, integer=False):
    if value is not None and (type(value) not in ({int} if integer else {int,float}) or not 0 <= value < float('inf')):
        raise ValueError(field+': nonnegative count or null for unknown required')


def session(row):
    shape(row,CORE|DETAIL,CORE)
    for field in ('session_id','participant'): text(row[field],field)
    if row['pair'] not in {'P1','P2'} or row['condition'] not in {'A','B'} or row['reading_lang'] not in {'zh','en'}:
        raise ValueError('invalid pair, condition or reading language')
    if row['status'] not in {'未运行','owner-blocked','recorded'}: raise ValueError('invalid session status')
    if 'interests' in row: strings(row['interests'],'interests')
    if 'start_url' in row: github_url(row['start_url'])
    for field in ('reason_quote','visible_cost'): 
        if field in row: optional_text(row[field],field)
    if 'prep_minutes' in row: count(row['prep_minutes'],'prep_minutes')
    if row['status'] != 'recorded':
        # An unrun planning row cannot also contain observed outcomes/costs.
        observed = DETAIL-{'start_url','interests','prep_minutes','reason_quote','visible_cost'}
        if any(field in row for field in observed) or any(row.get(f) is not None for f in ('prep_minutes','reason_quote','visible_cost')):
            raise ValueError('unrun row cannot contain observed outcomes')
        return row
    if not DETAIL <= set(row): raise ValueError('recorded session requires complete fields; use null for unknown outcomes/counts')
    if row['evidence_kind'] not in {'fixture','human-record'}: raise ValueError('explicit evidence kind required')
    if not re.fullmatch(r'P[0-9]{2,4}',row['participant']): raise ValueError('recorded participant must be pseudonymous P01 etc.')
    if row['order'] not in {'A_then_B','B_then_A'}: raise ValueError('explicit pair order required')
    if timestamp(row['end']) < timestamp(row['start']): raise ValueError('end must not precede start')
    strings(row['opened_repos'],'opened_repos',repos=True)
    text(row['method_version'],'method_version')
    shape(row['translation'],{'tool','settings','target_lang'},{'tool','settings','target_lang'})
    for field in ('tool','settings'): text(row['translation'][field],'translation.'+field)
    if row['translation']['target_lang'] != row['reading_lang']: raise ValueError('translation target must match reading language')
    tri_state(row['worth_follow'])
    for field in ('reason_quote','abandon_reason','visible_cost','observer_notes'):optional_text(row[field],field)
    if row['worth_follow'] is True and row['reason_quote'] is None: raise ValueError('positive human judgment requires an actual reason')
    count(row['prep_minutes'],'prep_minutes')
    for field in ('github_requests','model_requests'):count(row[field],field,integer=True)
    return row


def candidate(row):
    shape(row,CANDIDATE,CANDIDATE)
    text(row['session_id'],'session_id')
    if not isinstance(row['repo'],str) or not REPO.fullmatch(row['repo']): raise ValueError('canonical repository required')
    github_url(row['source_url'])
    text(row['method_version'],'method_version')
    optional_text(row['query'],'query')
    if type(row['shown']) is not bool: raise ValueError('shown must reflect actual presentation')
    if row['rank'] is not None and (type(row['rank']) is not int or row['rank']<1):raise ValueError('positive rank or null required')
    if row['shown'] and row['rank'] is None:raise ValueError('shown candidate requires actual presentation rank')
    if not row['shown'] and row['rank'] is not None:raise ValueError('unshown candidate cannot have a presentation rank')
    for field in ('already_known','opened','worth_follow'):tri_state(row[field])
    if row['known_assessed_when'] not in {'before','after-recall','unknown'}:raise ValueError('knowledge assessment timing required')
    if (row['already_known'] is None) != (row['known_assessed_when']=='unknown'):raise ValueError('unknown knowledge cannot be asserted as assessed')
    for field in ('reason_quote','expected_use','observer_observation','generated_reason'):optional_text(row[field],field)
    if row['worth_follow'] is True and row['reason_quote'] is None:raise ValueError('model/observer rationale cannot substitute for human reason')
    for field in ('conditions','unknowns'):strings(row[field],field)
    return row


def session_summary(rows):
    ids=set();pairs={};fixtures=0;unrun=0;humans=0
    for row in rows:
        session(row)
        if row['session_id'] in ids:raise ValueError('duplicate session ID')
        ids.add(row['session_id'])
        if row['status']!='recorded':unrun+=1;continue
        if row['evidence_kind']=='fixture':fixtures+=1;continue
        humans+=1
        key=(row['participant'],row['pair'])
        pair=pairs.setdefault(key,{})
        if row['condition'] in pair:raise ValueError('duplicate human condition within pair')
        pair[row['condition']]=row
    comparison=[]
    for (participant,pair_id),pair in sorted(pairs.items()):
        reasons=[]
        if set(pair)!={'A','B'}:reasons.append('missing condition')
        else:
            a,b=pair['A'],pair['B']
            if a['translation']!=b['translation']:reasons.append('translation baseline differs')
            if a['reading_lang']!=b['reading_lang']:reasons.append('reading language differs')
            if a['order']!=b['order']:reasons.append('recorded order differs')
            first,second=(a,b) if a['order']=='A_then_B' else (b,a)
            if timestamp(first['end'])>timestamp(second['start']):reasons.append('order violated or sessions overlap')
        comparison.append({'participant':participant,'pair':pair_id,'comparable_structure':not reasons,'issues':reasons})
    return {'human_sessions':humans,'fixture_sessions':fixtures,'unrun_sessions':unrun,
            'pair_checks':comparison,'effectiveness_conclusion':'not-inferred'}
