"""Wording-only estimates. Never native evidence, score credit or selector input."""
from functools import lru_cache
import json
import re

VERSION = 'estimated-wording-v1.3'
HARD = {'required', 'core', 'deal_breaker'}
BONUS = {'preferred', 'supporting', 'bonus'}
UNCERTAIN = re.compile(r'\b(?:not|never|without|no|plan(?:ned|ning)?\s+to|intend\w*|will|would|could|aspir\w*|hope\w*|interested|hypothetical)\b', re.I)
ACTION = re.compile(r'\b(?:set\s+up|built|developed|added|implemented|wrote|performed|executed|tested|designed|automated|verified|maintained|deployed|integrated|delivered|created|managed|led|ran|carried|validated|configured|resolved|supported|optimized|analysed|analyzed|collaborated|established)\b', re.I)
STOP = set('a an the and or for to of in on by with using use ensure ensuring experience proficiency knowledge ability responsible requirements skills you will your have has had work working application applications system systems software solution solutions robust comprehensive relevant perform execute design develop build implement create maintain set up configure automated'.split())
STEMS = {'built':'build','developed':'develop','implemented':'implement','designed':'design','created':'create','executed':'execute','performed':'perform','configured':'configure','led':'lead','testing':'test','tests':'test','apis':'api','applications':'application','automated':'automate','automation':'automate','coding':'code','frontend':'frontend','front-end':'frontend','backend':'backend','back-end':'backend','setup':'setup'}
STOP.update('be is are was were being been added advantage advantages advantageous desirable preferred candidate candidates must should possess demonstrate demonstrated strong good excellent one more any either'.split())


def alternative_terms(text):
    """Only explicit one-or-more parenthesized slash lists; no inferred OR semantics."""
    match = re.search(r'\bone or more\b[^()]*\(([^()]+)\)', text, re.I)
    if not match or '/' not in match[1]:
        return set()
    return set().union(*(terms(part) for part in match[1].split('/')))


def action_status(text):
    if re.match(r'^\s*(?:keywords?|tools?|technologies|skills)\s*:',text,re.I):
        return 'keyword_list_only'
    if UNCERTAIN.search(text):
        return 'negated_or_nonperformed'
    return 'performed_claim' if ACTION.search(text) else 'no_completed_action'


def terms(text):
    from taxonomy_discovery.technology_registry import get_default_registry
    text = text.casefold()
    identities = set()
    # Canonicalize only approved aliases with token boundaries, never Java -> JavaScript.
    for entry in get_default_registry().entries:
        aliases = sorted(entry['aliases'], key=len, reverse=True)
        for alias in aliases:
            def consume(match):
                identities.add(entry['technology_id'])
                return ' '
            text = re.sub(r'(?<![\w+#])'+re.escape(alias.casefold())+r'(?![\w+#])', consume, text)
    found = re.findall(r'[a-z0-9_]+(?:\+\+|#)?', text)
    return identities | {STEMS.get(t, t) for t in found if len(t)>1 and t not in STOP}


def term_labels(values):
    """Human-readable projection only; comparisons retain atomic registry IDs."""
    from taxonomy_discovery.technology_registry import get_default_registry
    labels = {entry['technology_id']: entry['label'] for entry in get_default_registry().entries}
    return sorted(labels.get(value, value) for value in values)


def estimate_pair(base, library, requirements, *, selected=()):
    if (len(base)>2000 or len(library)>2000 or len(requirements)>160 or len(selected)>80 or any(len(s)>2000 for s in selected)
            or any(len(q.get('text',''))>4000 for q in requirements)):
        return {'version':VERSION,'outcome':'Indeterminate','reason':'Input bound exceeded.', 'requirements':[], 'native_impact':'unmeasured'}
    return json.loads(_cached(json.dumps([base,library,requirements,list(selected)],sort_keys=True)))


@lru_cache(maxsize=256)
def _cached(payload):
    from tailoring.capability_taxonomy import evaluate_evidence
    base,library,requirements,selected = json.loads(payload)
    from taxonomy_discovery.technology_registry import get_default_registry
    entries = get_default_registry().entries
    technology_ids = {entry['technology_id'] for entry in entries}
    languages = {entry['technology_id'] for entry in entries if entry['entry_kind'] == 'language'}
    seen={}; rows=[]; conflicts=[]
    for q in requirements:
        rid=q.get('id') or q.get('requirement_id')
        identity=(q.get('text'),q.get('importance'))
        if not rid or not q.get('text'): continue
        if rid in seen:
            if seen[rid]!=identity:conflicts.append(rid)
            continue
        seen[rid]=identity
        if (q.get('score_eligible') is False or q.get('evidence_eligible') is False
                or q.get('importance') not in HARD|BONUS): continue
        required=terms(q['text'])
        alternatives=alternative_terms(q['text'])
        candidates=[]
        for text in (base,library):
            matched=required & terms(text)
            alternative_match=matched & alternatives
            optional=alternatives-matched if alternative_match else set()
            applicable=required-optional
            status=action_status(text)
            requested_technologies = required & technology_ids
            # Generic language prose is not evidence for a named language.
            language_identity_present = not (requested_technologies and requested_technologies <= languages
                                             and not (matched & requested_technologies))
            support=bool(applicable and status=='performed_claim' and language_identity_present and
                         (alternative_match or len(matched)>=min(2,len(applicable)))
                         and len(matched)/len(applicable)>=.25)
            # Parent requirements are single identities; facets explain partial support, not extra points.
            grade='full_wording_overlap' if support and matched==required else 'partial_wording_support' if support else 'lexical_only' if matched else 'none'
            capability=evaluate_evidence({'text':q['text'],'importance':q['importance']},text)
            candidates.append({'coverage':grade,'supported_facets':sorted(matched) if support else [],
                'lexical_terms':sorted(matched),'missing_terms':sorted(applicable-matched),
                'optional_alternatives':sorted(optional),'alternative_satisfied':bool(alternative_match),'action_status':status,
                'capability_id':capability.get('capability_id'),'taxonomy_label':capability.get('label'),
                'capability_reason':capability.get('reason'), 'verified':False})
        elsewhere=any(action_status(s)=='performed_claim' and required and len(required & terms(s))/len(required)>=.75 for s in selected)
        rows.append({'id':rid,'text':q['text'],'importance':q['importance'],
            'parent':q.get('scoring_parent_occurrence_id') or q.get('parent_occurrence_id') or rid,
            'base':candidates[0],'library':candidates[1], 'already_supported_elsewhere_estimate':bool(elsewhere)})
    outcome='Indeterminate';reason='No reliable performed wording support from the supplied requirement context.'
    if conflicts:
        rows=[];reason='Conflicting requirement identities; comparison withheld.'
    elif base==library:
        outcome='Equivalent';reason='Identical wording; shared provenance, no source winner.'
    else:
        any_support=any(r[role]['supported_facets'] for r in rows for role in ('base','library'))
        if any_support:
            outcome='Equivalent';reason='Comparable estimated facets; repetition or shorter wording alone is not extra coverage.'
            for importance in (HARD,BONUS):
                a=b=False
                for row in rows:
                    if row['importance'] not in importance or row['already_supported_elsewhere_estimate']:continue
                    aa=set(row['base']['supported_facets']);bb=set(row['library']['supported_facets'])
                    a |= bool(aa-bb);b |= bool(bb-aa)
                if a and b:outcome='Complementary';reason='Each wording adds estimated relevant facets the other lacks; replacement may lose useful information.';break
                if a or b:
                    outcome='Base stronger' if a else 'Library stronger'
                    reason=('Base' if a else 'Library')+' adds explicit performed '+('Required/Core' if importance==HARD else 'Preferred/Supporting')+' wording support; this is an estimate, not verified experience or native credit.'
                    break
    return json.dumps({'version':VERSION,'outcome':outcome,'reason':reason,'requirements':rows,
        'word_counts':{'base':len(base.split()),'library':len(library.split())},
        'native_impact':'unmeasured','verified_evidence':'not assessed by this wording-only mode',
        'limits':'Token/facet and action heuristics plus governed taxonomy hints. Full wording overlap is not proof of full compound satisfaction. Negation is conservatively scoped to the entire bullet. No official weights or native scores. Parent identities are deduplicated; no parent weights are added.'},ensure_ascii=False)
