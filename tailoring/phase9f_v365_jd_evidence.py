"""Read-only JD evidence explanations and conservative JD-fragment quality audit.

Never awards scoring credit, changes source evidence, or certifies a per-bullet
native winner. Exact lexical observations are NOT semantic proof.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import re
from typing import Any
import unicodedata

VERSION = 'phase9f-v3.6.5-read-only-jd-evidence-v1'
REQUIRED = frozenset({'required', 'core', 'deal_breaker'})
PREFERRED = frozenset({'preferred', 'bonus'})
_WORD = re.compile(r"ci/cd|\.?[a-z][a-z0-9+#.]*", re.IGNORECASE)
STOP = frozenset(('the a an and or to of in on for with from through using use used ' 
    'will should would can could one more at by is are be been being as this that ' 
    'added advantage preferred experience proficiency good strong have has had ' 
    'ability knowledge skill skills relevant related meet requirements requirement ' 
    'software application applications working work candidate team').split())
# Important: only literal JD/bullet overlaps are shown. Synonyms below help label
# an action-family overlap, without granting scorer evidence or JD identity credit.
ACTIONS = {
 'test': ('test', 'tests', 'testing', 'qa', 'regression', 'unit', 'integration', 'uat'),
 'build': ('build', 'built', 'compile', 'compilation', 'automation', 'automated'),
 'deploy': ('deploy', 'deployment', 'deployed', 'release', 'shipping'),
 'configure': ('configur', 'configuration', 'setup', 'set-up'),
 'develop': ('develop', 'development', 'developed', 'implement', 'implemented', 'engineering'),
 'maintain': ('maintain', 'maintenance', 'maintained'),
 'integrate': ('integrat', 'integration', 'integrated', 'connect', 'connected'),
 'analyze': ('analyz', 'analyse', 'analyzed', 'analysed', 'analysis'),
 'collaborate': ('stakeholder', 'stakeholders', 'collaborat', 'partner', 'business'),
 'improve': ('improv', 'improvement', 'optimiz', 'optimization'),
}
TECH = frozenset(('python java kotlin react angular html5 typescript javascript postgresql ' 
    'postgres supabase sqlite postgrest docker kubernetes linux windows ubuntu ' 
    'github gitlab aws azure gcp ci/cd cicd sql .net dotnet php mongodb ' 
    'streamlit c++ c# github-actions').split())


def tokens(text: Any) -> set[str]:
    return {x.lower().rstrip('.') for x in _WORD.findall(str(text or ''))}


def meaningful_terms(text: Any) -> set[str]:
    return {x for x in tokens(text) if len(x)>2 and x not in STOP}


def _has_action(text: str, family: str) -> bool:
    t=tokens(text)
    return any(any(word.startswith(stem) for stem in ACTIONS[family]) for word in t)


def _normalized(text: Any) -> str:
    return ' '.join(unicodedata.normalize('NFC', str(text or '')).split()).casefold()


def _jd_digest(text: str) -> str:
    return sha256(text.replace('\r\n', '\n').strip().encode('utf-8')).hexdigest()


def audit_fragment(fragment: Any, *, parent_sentence: Any = None, raw_jd_text: Any = None,
                   source_provenance: Any = None, expected_jd_text: str = '') -> dict:
    """Conservative parser-warning only. Missing original source -> unverified.

    A clipped fragment may be a valid child if the original activity scope is
    separately inherited. Never auto-infer it without the preserved source.
    """
    value = str(fragment or '').strip()
    raw = str(raw_jd_text or '')
    sources = [s for s in source_provenance or [] if isinstance(s, dict)]
    parents = [str(parent_sentence or '').strip()]
    for source in sources:
        grounding = source.get('grounding') or {}
        parents.extend(str(text or '').strip() for text in (
            source.get('raw_parent_text'), source.get('parent_text'), grounding.get('sentence_text')))
    parents = [parent for parent in dict.fromkeys(parents) if parent]
    words = _normalized(value).strip(' .;').split()
    clipped = not words or words[0] in {'and', 'or', 'but', 'with', 'to', 'for', 'of'} or (
        words[-1] in {'and', 'or', 'with', 'to', 'for', 'of', 'a', 'an', 'the'})
    normalized_raw = _normalized(raw)
    normalized_value = _normalized(value)
    # A coordinate run of bare verbs can be clipped before their shared object.
    # Keep this advisory separate from the independent source trace.
    verb = r'(?:design|build|develop|deploy|maintain|identify|analy[sz]e|resolve|review|update)'
    coordinated_verbs = re.fullmatch(rf'[^\w]*{verb}(?:,\s*{verb})+', normalized_value)
    if coordinated_verbs:
        clipped |= any(re.search(re.escape(normalized_value) + r',?\s+and\s+\w+\s+\w+',
                                 _normalized(parent)) for parent in parents)
    anchored = next((parent for parent in parents
                     if normalized_value and _contains_text(_normalized(parent), normalized_value)
                     and _contains_text(normalized_raw, _normalized(parent))), None)
    exact = next((parent for parent in parents if _contains_text(parent, value)
                  and _contains_text(raw, parent)), None)
    if not normalized_raw or not parents:
        source_status = 'missing_source'
        source_reason = 'Original JD text or saved parent is missing.'
    elif expected_jd_text and _normalized(expected_jd_text) != normalized_raw:
        source_status = 'source_identity_mismatch'
        source_reason = 'The supplied JD differs from the JD frozen with this analysis.'
    elif exact:
        source_status = 'exact_span'
        source_reason = 'The wording is present in the saved parent and original JD.'
    elif anchored:
        source_status = 'text_normalization_difference'
        source_reason = 'The saved wording matches the original JD after whitespace, case, or Unicode normalization.'
    else:
        source_status = 'source_span_mismatch'
        source_reason = 'The saved fragment and parent could not both be traced to the supplied JD.'
    traceable = source_status in {'exact_span', 'text_normalization_difference'}
    status = 'suspect' if clipped else 'source_span_present' if traceable else 'unverified'
    return {
        'status': status, 'source_status': source_status,
        'grammar_status': 'clipped_boundary' if clipped else 'no_boundary_warning',
        'reason': 'Empty or potentially clipped JD fragment.' if clipped else source_reason,
        'source_reason': source_reason,
        'parent': exact or anchored or (parents[0] if parents else ''),
        'source_provenance': sources,
        'eligible_for_bonus_explanation': traceable and not clipped,
    }


def _contains_text(haystack: str, needle: str) -> bool:
    return bool(needle and re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', haystack))


def requirement_catalog(baseline_report: Any, projects: Any) -> dict[str,dict]:
    """Use stable canonical requirement metadata, with ranking-only fallback."""
    records=[]
    expected_jd_text = ''
    if isinstance(baseline_report,dict):
        stable=baseline_report.get('stable_analysis') or {}
        if isinstance(stable,dict):records=stable.get('canonical_requirements') or []
        expected_jd_text = baseline_report.get('raw_jd_text') or ''
    if not records and isinstance(projects,dict):
        for project in projects.get('candidate_project_ranking') or []:
            if isinstance(project,dict):records.extend(project.get('requirement_matches') or [])
    catalog={}
    for r in records:
        if not isinstance(r,dict):continue
        rid=str(r.get('requirement_id') or '').strip()
        title=str(r.get('text') or r.get('requirement_text') or '').strip()
        if not rid or not title:continue
        parent=str(r.get('parent_text') or '')
        source=r.get('source_provenance') or []
        if not parent and isinstance(source,list):
            for s in source:
                if isinstance(s,dict):
                    grounding=s.get('grounding') or {}
                    if isinstance(grounding,dict) and grounding.get('sentence_text'):
                        parent=str(grounding['sentence_text']);break
        catalog.setdefault(rid,{'id':rid,'text':title,
            'importance':str(r.get('importance') or 'unknown').lower(),
            'parent':parent,
            'source_provenance':source,
            'parent_occurrence_id':r.get('scoring_parent_occurrence_id'),
            'group_weight_fraction':r.get('group_weight_fraction'),
            'score_eligible':r.get('score_eligible'),
            'evidence_eligible':r.get('evidence_eligible'),
            'frozen_jd_sha256':_jd_digest(expected_jd_text) if expected_jd_text else None,
            })
    return catalog


def requirement_fragment(req: dict, raw_jd_text: str, *, expected_jd_text: str = '') -> dict:
    return audit_fragment(req['text'], parent_sentence=req.get('parent'), raw_jd_text=raw_jd_text,
                          source_provenance=req.get('source_provenance'),
                          expected_jd_text=expected_jd_text)


def explain_bullet(row: dict, catalog: dict, *, raw_jd_text: str = '',
                   selected_rows: list[dict] | None = None,
                   fragments: dict | None = None) -> dict:
    """Explain visible term overlap plus saved link cardinality, not causal merit."""
    ids=list(dict.fromkeys(row.get('saved_jd_ids') or []))
    text=str(row.get('bullet') or '')
    bullet_terms=meaningful_terms(text)
    if fragments is None:
        fragments = {rid: requirement_fragment(req, raw_jd_text) for rid, req in catalog.items()}
    linked=[]; suspect=[]; bonus=[]; missing=[]
    terms=set(); tech=set(); activity=set()
    for rid in ids:
        req=catalog.get(rid)
        if not req:
            missing.append(rid);continue
        jd=str(req['text']); jd_terms=meaningful_terms(jd)
        common=bullet_terms & jd_terms
        meaningful=sorted(common)
        # For each recorded JD link, label explicit literal cues; keep keywords
        # separate from semantic proof. An unrelated link can appear here.
        family_hits=sorted(f for f in ACTIONS if _has_action(text,f) and _has_action(jd,f))
        technical=sorted(common & TECH)
        fragment=fragments[rid]
        fragment_status=fragment['status']
        link={'id':rid,'text':jd,'importance':req['importance'],
              'keyword_overlap':meaningful,'technology_overlap':technical,
              'activity_overlap':family_hits,'fragment_status':fragment_status,
              'fragment_warning':fragment['reason'], 'fragment':fragment,
              'literal_corroboration': bool(meaningful or family_hits),
              'independent_evidence_verified':False}
        if not link['literal_corroboration'] or not fragment['eligible_for_bonus_explanation']:
            suspect.append(rid)
        if (req['importance'] in ('preferred','bonus') and link['literal_corroboration']
                and fragment['eligible_for_bonus_explanation']):
            bonus.append(rid) # observed link only, NEVER native points
        terms.update(meaningful);tech.update(technical);activity.update(family_hits)
        linked.append(link)
    global_jd_terms=set().union(*(meaningful_terms(r['text']) for r in catalog.values())) if catalog else set()
    overall=sorted(bullet_terms & global_jd_terms)
    unlinked=sorted(set(overall)-terms)
    jd_wide_technical=sorted(set(overall) & TECH)
    bonus_cues=[]
    for item in catalog.values():
        if item['importance'] not in ('preferred','bonus') or item['id'] in ids:continue
        overlap=bullet_terms & meaningful_terms(item['text'])
        if overlap and fragments[item['id']]['eligible_for_bonus_explanation']:
            bonus_cues.append({'text':item['text'],'terms':sorted(overlap),'status':'unlinked_lexical_cue_only'})
    selected=selected_rows if selected_rows is not None else []
    support=Counter(rid for x in selected if x.get('in_proposed_b') for rid in set(x.get('saved_jd_ids') or []))
    unique=[rid for rid in ids if row.get('in_proposed_b') and support[rid]==1]
    shared=[rid for rid in ids if row.get('in_proposed_b') and support[rid]>1]
    return {'bullet':text,'project':row.get('project'),
        'jd_links':linked,'unresolved_jd_ids':missing,
        'matched_terms':sorted(terms),'jd_wide_term_cues':overall,'jd_wide_technology_cues':jd_wide_technical,
        'unlinked_jd_term_cues':unlinked,
        'possible_unlinked_bonus_cues':bonus_cues,'matched_technologies':sorted(tech),
        'matched_action_families':sorted(activity),
        'suspect_link_ids':suspect,
        'preferred_link_ids':bonus,
        'unique_saved_links':unique,'shared_saved_links':shared,
        'words':row.get('words'),
        'claim_limit':'Term overlap is not independent evidence proof; link identity is not native Job Match points.'}


def compare_source_pair(pair: dict, catalog: dict, *, raw_jd_text: str = '') -> dict:
    """Use linked JD text as a fixed comparison context, report deltas without awarding points."""
    ids=pair.get('shared_saved_jd_ids') or []
    base={'bullet':pair.get('base_bullet') or '', 'saved_jd_ids':ids,'words':pair.get('base_words')}
    lib={'bullet':pair.get('library_bullet') or '', 'saved_jd_ids':ids,'words':pair.get('library_words')}
    a=explain_bullet(base,catalog,raw_jd_text=raw_jd_text)
    b=explain_bullet(lib,catalog,raw_jd_text=raw_jd_text)
    only_a=sorted(set(a['jd_wide_term_cues'])-set(b['jd_wide_term_cues']))
    only_b=sorted(set(b['jd_wide_term_cues'])-set(a['jd_wide_term_cues']))
    wa,wb=a['words'],b['words']
    return {'base':a,'library':b,'only_base_terms':only_a,'only_library_terms':only_b,
       'base_words':wa,'library_words':wb,
       'library_words_saved':wa-wb if isinstance(wa,int) and isinstance(wb,int) else None,
       'verdict':'No native head-to-head winner measured',
       'limit':'Same saved JD links do not imply equal strength; keyword differences are only cues.'}


def source_wording_label(source_labels: Any) -> str:
    sources = set(source_labels or ())
    if {'Selected Base', 'Evidence Library'} <= sources:
        return 'Base bullet and Library bullet (identical wording)'
    if 'Selected Base' in sources:
        return 'Base bullet'
    if 'Evidence Library' in sources:
        return 'Library bullet'
    if 'Current final' in sources:
        return 'Existing fitted résumé wording (source unconfirmed)'
    return 'Source unconfirmed'


def rank_bullets(rows: list[dict], catalog: dict, *, raw_jd_text: str, result: dict,
                 expected_jd_text: str = '', selection_recorded: bool = True) -> list[dict]:
    """Rank display evidence and describe coverage in the eligible project pool."""
    fragments = {rid: requirement_fragment(req, raw_jd_text, expected_jd_text=expected_jd_text)
                 for rid, req in catalog.items()}
    safe_ids = {rid for rid, fragment in fragments.items()
                if fragment['eligible_for_bonus_explanation']
                and catalog[rid].get('evidence_eligible') is not False}
    snapshots = result.get('native_document_evidence') or {}
    evidence = {}
    verified_roles = set()
    for role, field, hash_key in (
        ('existing', 'in_actual_a', 'a_docx_sha256'),
        ('alternative', 'in_proposed_b', 'b_docx_sha256'),
    ):
        snapshot = snapshots.get(role) or {}
        if (result.get('status') != 'verified' or not result.get(hash_key)
                or snapshot.get('docx_sha256') != result[hash_key]):
            continue
        verified_roles.add(role)
        owners = Counter(_normalized(row['bullet']) for row in rows if row.get(field))
        for req in snapshot.get('requirements') or []:
            rid = req.get('requirement_id')
            if rid not in safe_ids or req.get('match_label') not in {'weak', 'transferable', 'direct'}:
                continue
            for excerpt in req.get('evidence') or []:
                wording = _normalized(excerpt.get('text'))
                if excerpt.get('section') == 'projects' and wording and owners[wording] == 1:
                    evidence.setdefault((role, wording), {})[rid] = {
                        'match_label': req['match_label'],
                        'strength': req.get('evidence_strength'),
                        'excerpt': excerpt['text'],
                    }

    ranked = []
    for row in rows:
        explanation = explain_bullet(row, catalog, raw_jd_text=raw_jd_text, fragments=fragments)
        wording = _normalized(row['bullet'])
        selected = bool(row.get('in_proposed_b'))
        existing = bool(row.get('in_actual_a'))
        native = {role: evidence.get((role, wording), {}) if member else {}
                  for role, member in (('existing', existing), ('alternative', selected))}
        native_ids = native['existing'].keys() | native['alternative'].keys()
        linked = {link['id']: link for link in explanation['jd_links']}
        lexical_ids = {rid for rid, link in linked.items()
                       if rid in safe_ids and (link['keyword_overlap'] or link['technology_overlap'])}
        observed_ids = sorted(linked.keys() | native_ids)
        links = []
        for rid in observed_ids:
            req = catalog[rid]
            link = linked.get(rid) or explain_bullet(
                {**row, 'saved_jd_ids': [rid]}, catalog, raw_jd_text=raw_jd_text,
                fragments=fragments)['jd_links'][0]
            links.append({**link, 'saved_link': rid in linked,
                          'status': ('Native document evidence' if rid in native_ids else
                                     'Saved link with lexical cues' if rid in lexical_ids else
                                     'Questionable saved link'),
                          'native_evidence': {role: values[rid] for role, values in native.items()
                                              if rid in values}})
        # Counts order the display. The production objective uses different rules.
        def count(ids: set, importance: frozenset) -> int:
            return len({catalog[rid].get('parent_occurrence_id') or rid for rid in ids
                        if catalog[rid]['importance'] in importance})

        ranked.append({
            **row, **explanation, 'source_label': source_wording_label(row.get('sources')),
            'jd_links': links, 'native_impact_status': 'unknown',
            'native_requirement_ids': sorted(native_ids),
            'native_existing_requirement_ids': sorted(native['existing']),
            'native_alternative_requirement_ids': sorted(native['alternative']),
            'traceable_lexical_link_ids': sorted(lexical_ids),
            'relevance_order': (
                count(native_ids, REQUIRED),
                count(lexical_ids, REQUIRED),
                count(native_ids, PREFERRED),
                count(lexical_ids, PREFERRED),
                len(explanation['jd_wide_technology_cues']),
            ),
        })
    native_support = Counter(rid for row in ranked for rid in row['native_alternative_requirement_ids'])
    lexical_support = Counter(rid for row in ranked if row.get('in_proposed_b')
                              for rid in row['traceable_lexical_link_ids'])
    for row in ranked:
        row['coverage'] = {}
        for label, ids, support in (
            ('Native excerpts', row['native_requirement_ids'], native_support),
            ('Saved links with lexical cues', row['traceable_lexical_link_ids'], lexical_support),
        ):
            buckets = {'Unique in alternative': [], 'Shared in alternative': [], 'Absent from alternative': []}
            if selection_recorded and (label != 'Native excerpts' or 'alternative' in verified_roles):
                for rid in ids:
                    member = bool(row.get('in_proposed_b')) if label == 'Saved links with lexical cues' else (
                        rid in row['native_alternative_requirement_ids'])
                    other = support[rid] - int(member)
                    bucket = ('Shared in alternative' if other else
                              'Unique in alternative' if member else 'Absent from alternative')
                    buckets[bucket].append(catalog[rid])
            row['coverage'][label] = buckets
    return sorted(ranked, key=lambda row: (
        tuple(-value for value in row['relevance_order']), row['project'].casefold(),
        row['bullet'].casefold(), row['bullet']))
