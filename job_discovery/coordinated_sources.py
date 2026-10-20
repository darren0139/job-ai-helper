"""Pure, replay-verified library projection for the developer comparison only.

The ordinary Job Match adapter is unchanged. Raw aliases are linked by the
adapter's original emission receipts, never inferred by searching résumé text.
"""
from copy import deepcopy
import hashlib
import json

from job_discovery.matching import build_profile_evidence_context, _clean

PROJECTION_VERSION = 'job-match-source-projection-v1'
ALIAS_POLICY_VERSION = 'coordinated-verified-raw-alias-scope-v1'
PROJECTED_SCORER_VERSION = 'stable-evidence-v1.21-phase6d25'
LIBRARY_AUTHORITY = 'EXPLICIT_LIBRARY_INPUT'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


def build_library_projection(evidence_items, *, raw_only_text=''):
    """Retain every original field/line, including deduplicated emissions."""
    if not isinstance(evidence_items, list) or not all(isinstance(r, dict) for r in evidence_items):
        raise ValueError('Explicit library records are required; no document/profile substitution')
    ids = [r.get('id') for r in evidence_items]
    if any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Original library item IDs must be unique positive integers')
    if not isinstance(raw_only_text, str):
        raise ValueError('Raw-only coverage must be original text')
    context = build_profile_evidence_context(deepcopy(evidence_items))
    supplied = {r['id']: r for r in evidence_items}
    originals, emissions, unindexed = [], [], []
    counters = {'projects': 0, 'experience': 0, 'certifications': 0}

    def original(item, field, text, projected, container, target=None):
        source = f'evidence_library[id={item["id"]}].{field}'
        record = {'library_item_id': item['id'], 'source': source, 'original_text': text,
                  'projected_text': projected, 'container': container, 'structured_source': target,
                  'library_container_id': f'library-item:{item["id"]}',
                  'occurrence_id': 'libocc_'+fingerprint([item['id'], source, text])[:20]}
        originals.append(record)
        return record

    for item in context['evidence_items']:
        category = _clean(item.get('category')).casefold()
        section = {'project': 'projects', 'internship': 'experience'}.get(category)
        container = f'resume_profile.{section}[{counters[section]}]' if section else None
        if section:
            counters[section] += 1
        # Store each field occurrence, even where the existing adapter dedups it.
        descriptions, impacts = [], []
        line_origins = []
        for field in ('description', 'canonical_bullets', 'bullets', 'impact'):
            values = item.get(field, []) if field in ('canonical_bullets', 'bullets') else [item.get(field, '')]
            if values is None:
                values = []
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError('Unavailable library field coverage: '+field)
            for index, value in enumerate(values):
                path = f'{field}[{index}]' if field in ('canonical_bullets', 'bullets') else field
                for line_index, raw in enumerate(value.splitlines()):
                    line = raw.strip().lstrip('•-* ').strip()
                    if not line:
                        continue
                    collection = impacts if field == 'impact' else descriptions
                    if line not in collection:
                        collection.append(line)
                    line_origins.append((path+f'.lines[{line_index}]', raw, line, field == 'impact'))
        bullets = descriptions+[line for line in impacts if line not in descriptions]
        heading = ' — '.join(_clean(item.get(k)) for k in ('title', 'subtitle', 'period') if _clean(item.get(k)))
        if heading:
            record = original(item, 'heading', heading, _clean(heading), container, container)
            record['heading_fields'] = {k: deepcopy(item.get(k)) for k in ('title', 'subtitle', 'period')}
            emissions.append(record)
        for field, raw, line, is_impact in line_origins:
            target = f'{container}.bullets[{bullets.index(line)}]' if container else None
            record = original(item, field, raw, _clean(line), container, target)
            # Repeated impact/description emissions are all retained as aliases.
            emissions.append(record)
        for field in ('skills', 'tools'):
            values = item.get(field, []) or []
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError('Unavailable library field coverage: '+field)
            for index, raw in enumerate(values):
                if _clean(raw):
                    record = original(item, f'{field}[{index}]', raw, _clean(raw), None,
                                      f'resume_profile.skills.evidence_{item["id"]}_{field}[{index}]')
                    emissions.append(record)
        # Unsupported metadata remains visible, never promoted to ownership.
        def retain(value, path):
            if isinstance(value, str) and value.strip():
                unindexed.append(original(item, path, value, _clean(value), container))
            elif isinstance(value, dict):
                for key in sorted(value):
                    retain(value[key], path+'.'+str(key))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    retain(child, path+f'[{index}]')
        for field in ('scope', 'resume_header_context', 'resume_header_tools', 'source_metadata', 'provenance'):
            retain(item.get(field), field)
        used = {'id', 'evidence_id', 'project_id', 'category', 'title', 'display_title', 'subtitle', 'period',
                'description', 'canonical_bullets', 'bullets', 'impact', 'skills', 'tools', 'source_type', 'source',
                'created_at', 'updated_at', 'scope', 'resume_header_context', 'resume_header_tools', 'source_metadata', 'provenance'}
        for field in sorted(supplied[item['id']].keys()-used):
            retain(supplied[item['id']][field], field)

    raw_lines = context['raw_resume_text'].splitlines()
    aliases = []
    for index, text in enumerate(raw_lines):
        origins = [deepcopy(r) for r in emissions if r['projected_text'].casefold() == text.casefold()]
        aliases.append({'source': f'raw_resume_text[{index}]', 'text': text, 'origins': origins})
    # Explicit extra raw text is not an adapter emission, even when text matches.
    combined = context['raw_resume_text']
    if raw_only_text:
        combined = combined+'\n'+raw_only_text if combined else raw_only_text
    return {'authority': LIBRARY_AUTHORITY, 'version': PROJECTION_VERSION,
            'evidence_items': deepcopy(evidence_items), 'raw_only_text': raw_only_text,
            'context': {**context, 'raw_resume_text': combined}, 'originals': originals,
            'raw_aliases': aliases, 'unindexed': unindexed}


def verified_projection_ledger(projection, profile, raw_resume):
    """Replay the explicit originals before trusting any supplied alias receipt."""
    from analysis_stability import coordinated_conflicts as conflicts
    from analysis_stability import stable_evidence_scoring as native
    if not isinstance(projection, dict) or projection.get('authority') != LIBRARY_AUTHORITY:
        raise ValueError('Library projection authority required; document authority is separate')
    replay = build_library_projection(projection['evidence_items'], raw_only_text=projection['raw_only_text'])
    if (replay != projection or profile != replay['context']['resume_profile']
            or raw_resume != replay['context']['raw_resume_text']):
        raise ValueError('Source projection/original alias verification failed')
    ledger = conflicts.build_ledger(profile, raw_resume)
    ledger['source_projection_version'] = PROJECTION_VERSION
    ledger['source_projection_fingerprint'] = fingerprint(replay)
    ledger['library_originals'] = deepcopy(replay['originals'])
    by_source = {r['source']: r for r in ledger['occurrences']}
    for record in ledger['occurrences']:
        origins = [r for r in replay['originals'] if r['structured_source'] == record['source']
                   and r['projected_text'] == record['text']]
        if origins:
            record['library_origins'] = deepcopy(origins)
    for alias in replay['raw_aliases']:
        record = by_source.get(alias['source'])
        if not record or record['text'] != alias['text']:
            raise ValueError('Raw occurrence does not match the verified projection')
        scoped = []
        for origin in alias['origins']:
            target = by_source.get(origin['structured_source'])
            if (target and target['container'] and target['text'] == origin['projected_text']
                    and target['container'] == origin['container']):
                scoped.append(target['occurrence_id'])
        record['library_origins'] = deepcopy(alias['origins'])
        record['verified_alias_occurrences'] = sorted(set(scoped))
        record['raw_alias_status'] = ('VERIFIED_SCOPED_ORIGINALS' if scoped and len(scoped) == len(alias['origins'])
                                      else 'UNSCOPED_OR_PARTIAL_COVERAGE')
    # Preserve metadata omitted by normal projection as unindexed coverage.
    for original in replay['unindexed']:
        text = original['projected_text']
        ledger['occurrences'].append({'source': original['source'], 'section': 'unindexed',
            'text': text, 'original_text': original['original_text'], 'kind': 'UNINDEXED_FIELD',
            'container': original['container'], 'container_id': original['library_container_id'],
            'occurrence_id': original['occurrence_id'], 'library_origins': [deepcopy(original)],
            'evidence_id': native._stable_id('ev', 'unindexed|'+native._normalise_basic(text))})
    return ledger
