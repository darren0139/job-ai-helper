"""Bounded text detector for Stage 2C OFFLINE RESEARCH ONLY.

Nothing in production imports this module. Unsupported language is not proof.
Offsets are half-open Python Unicode character offsets in the unmodified source.
No expected/oracle action labels are accepted by either public function.
"""
from copy import deepcopy
import re

POLICY = 'PREVIEW-ONLY-grounded-coordinated-ownership-v1'
_VERBS = {
    'design': ('design','designs','designed','designing'),
    'develop': ('develop','develops','developed','developing','build','builds','built','building',
                'implement','implements','implemented','implementing'),
    'maintain': ('maintain','maintains','maintained','maintaining'),
    'deploy': ('deploy','deploys','deployed','deploying'),
}
_ACTION = re.compile(r'\b(?:'+ '|'.join(v for words in _VERBS.values() for v in words) +r')\b',re.I)
_AND = re.compile(r'\s*[\u00b7\u2022]?\s*(Design),\s*(develop|build),?\s+and\s+(maintain|deploy)\s+(?P<object>.+?)\.?',re.I)
_OR = re.compile(r'\s*(Design)\s+or\s+(develop|build)\s+(?P<object>.+?)\.?',re.I)
_FAMILIES = (
    ('pipeline',r'(?:scalable\s+)?data pipelines\b'),
    ('embedded',r'embedded software modules\b'),
    ('fullstack',r'(?:scalable\s+)?full-stack applications\b'),
    ('cloud',r'cloud-based applications\b'),
    ('backend',r'(?:scalable\s+)?backend services and API\b'),
)


def normal(value):
    return re.sub(r'\s+',' ',re.sub(r'[,\.]',' ',value.casefold())).strip()


def action_kind(word):
    return next((action for action,words in _VERBS.items() if word.casefold() in words),None)


def extract_obligation(requirement):
    sources=requirement.get('source_provenance') or []
    base={'policy':POLICY,'status':'UNSUPPORTED','reason':'not_admitted_grammar',
          'requirement_id':requirement.get('requirement_id'),'actions':[],
          'conjunction':None,'optional_qualifiers':[], 'source_occurrences':sources}
    if len(sources)!=1 or not sources[0].get('raw_parent_text') or not sources[0].get('grounding'):
        return {**base,'reason':'missing_or_multiple_grounded_parent_occurrences'}
    source=sources[0]; raw=source['raw_parent_text']
    base.update(raw_parent_text=raw,parent_occurrence_id=source['parent_occurrence_id'])
    optional=re.search(r',?\s+preferably using\s+[^.;]+\.?$',raw,re.I)
    mandatory=raw
    if optional:
        base['optional_qualifiers']=[{'text':raw[optional.start():optional.end()],
                                      'span':[optional.start(),optional.end()]}]
        mandatory=raw[:optional.start()].rstrip().rstrip('.')
    m=_AND.fullmatch(mandatory)
    mode='AND'
    if not m:
        m=_OR.fullmatch(mandatory);mode='OR'
    if not m:
        return {**base,'negation_present':bool(re.search(r'\b(?:not|never|no)\b',raw,re.I)),
                'alternatives_present':bool(re.search(r'\bor\b|and/or',raw,re.I))}
    obj=m.group('object')
    family=next((name for name,pattern in _FAMILIES if re.match(pattern,obj,re.I)),None)
    if not family or re.search(r'\bor\b|\b(?:not|never|without|unless|except)\b|and/or|[;\n]',obj,re.I):
        return {**base,'reason':'unsupported_object_scope_or_boolean_modifier'}
    # The finite source objects may contain descriptive verbs (ingest/transform),
    # but never another ownership action or an independent obligation.
    if _ACTION.search(obj):
        return {**base,'reason':'ownership_action_inside_object_scope'}
    groups=range(1,4) if mode=='AND' else range(1,3)
    actions=[{'action':action_kind(m.group(i)),'original_action':m.group(i),
              'span':[m.start(i),m.end(i)]} for i in groups]
    return {**base,'status':'SUPPORTED','reason':'finite_shared_object_grammar',
            'conjunction':mode,'actions':actions,'object':obj,
            'object_span':[m.start('object'),m.end('object')],'object_family':family,
            'negation_present':False,'alternatives_present':mode=='OR',
            'build_develop_equivalence':'bounded affirmative creation of the exact same software artifact; no endpoint-authorship inference'}


def ground_to_raw_jd(obligation,raw_jd_text):
    """Add document offsets only when the exact raw parent occurs unambiguously."""
    result=deepcopy(obligation)
    raw=result.get('raw_parent_text','')
    starts=[m.start() for m in re.finditer(re.escape(raw),raw_jd_text)] if raw else []
    if result['status']!='SUPPORTED' or len(starts)!=1:
        return {**result,'status':'UNSUPPORTED','reason':'missing_or_ambiguous_exact_raw_document_span'}
    start=starts[0]
    result['raw_jd_parent_span']=[start,start+len(raw)]
    result['raw_jd_object_span']=[start+x for x in result['object_span']]
    for action in result['actions']:
        action['raw_jd_span']=[start+x for x in action['span']]
    for optional in result['optional_qualifiers']:
        optional['raw_jd_span']=[start+x for x in optional['span']]
    result['document_grounding']='EXACT_UNIQUE_SUBSTRING_IN_ORIGINAL_RAW_JD'
    return result


def _subject(prefix,verb):
    cleaned=prefix.strip(' ,:').casefold()
    if re.search(r'\b(?:not|never|no|without|didn.t)\b',cleaned):
        return 'NEGATED'
    if re.search(r'\b(?:will|would|could|can|may|might|plan|planned|learn|learned|intend|intended|if|should|must)\b',cleaned):
        return 'AMBIGUOUS_MODALITY'
    if re.search(r'\b(?:team|we|vendor|colleague|they|partner|supplier|others|someone)\b',cleaned):
        return 'NON_CANDIDATE_OR_TEAM'
    if cleaned not in ('','i','i personally','personally','i have','i am','i was'):
        return 'AMBIGUOUS_SUBJECT'
    word=verb.casefold()
    if word in ('designed','developed','built','implemented','maintained','deployed'):
        if cleaned in ('i am','i was'):
            return 'AMBIGUOUS_VOICE'
        return 'CANDIDATE'
    if cleaned in ('i','i personally','personally','i am') and not word.endswith('s'):
        return 'CANDIDATE'
    return 'AMBIGUOUS_TENSE'


def detect_ownership(obligation, record, verified_index):
    """Read ONE verified original record. Index must come from original current inputs."""
    result={'policy':POLICY,'status':'UNSUPPORTED','complete':False,
            'supported_actions':[],'missing_actions':[r['action'] for r in obligation['actions']],
            'denied_actions':[],'receipts':[], 'ambiguities':[],
            'evidence_id':record.get('evidence_id'), 'source':record.get('source'),
            'evidence_text':record.get('text','')}
    if obligation['status']!='SUPPORTED':
        return {**result,'reason':obligation['reason']}
    original=next((r for r in verified_index if record.get('source') and record.get('evidence_id')
        and r.get('source')==record['source'] and r.get('evidence_id')==record['evidence_id']
        and r.get('text')==record.get('text') and r.get('section')==record.get('section')),None)
    if original is None or record.get('section') not in ('projects','experience'):
        return {**result,'status':'UNVERIFIED_SOURCE','reason':'no_exact_current_project_or_experience_receipt'}
    text=record['text']; supported=set();denied=set()
    if '?' in text or re.search(r'\b(?:not me|not my work|hypothetical|example only|the vendor did this)\b',text,re.I):
        return {**result,'status':'AMBIGUOUS','reason':'question_or_explicit_global_qualification',
                'ambiguities':['record_level_modality_or_attribution']}
    # Clauses are parts of this one original record, never merged independent bullets.
    for clause_match in re.finditer(r'[^;.\n!?]+',text):
        chunk=clause_match.group(); offset=clause_match.start()
        # Contrast is a new local attribution/negation boundary.
        contrasts=list(re.finditer(r'\bbut\b',chunk,re.I))
        starts=[0]+[m.end() for m in contrasts]
        ends=[m.start() for m in contrasts]+[len(chunk)]
        for begin,finish in zip(starts,ends):
            clause=chunk[begin:finish]; origin=offset+begin
            matches=list(_ACTION.finditer(clause)); contexts=[]
            for i,match in enumerate(matches):
                prefix=clause[:match.start()] if i==0 else clause[matches[i-1].end():match.start()]
                connector=bool(re.fullmatch(r'[\s,]*(?:and\s+)?',prefix,re.I))
                if i and connector:
                    subject=contexts[-1]
                elif i and re.search(r'(?:\band|,)\s*$',prefix,re.I):
                    subject=contexts[-1]
                else:
                    subject=_subject(prefix,match.group())
                if i and subject=='CANDIDATE':
                    first_prefix=clause[:matches[0].start()].strip().casefold()
                    past={'designed','developed','built','implemented','maintained','deployed'}
                    if match.group().casefold() not in past and first_prefix not in ('i','i personally','i am'):
                        subject='AMBIGUOUS_TENSE'
                contexts.append(subject)
                end_index=i
                while end_index+1<len(matches) and re.fullmatch(r'[\s,]*(?:and\s+)?',
                    clause[matches[end_index].end():matches[end_index+1].start()],re.I):
                    end_index+=1
                start=matches[end_index].end()
                end=matches[end_index+1].start() if end_index+1<len(matches) else len(clause)
                rhs=clause[start:end]
                # Denial tails are not positive object modifiers. Their unsupported
                # noun-form ownership mentions cannot manufacture positive actions.
                tail=re.search(r'\s+(?:without|but)\b',rhs,re.I)
                if tail:end=start+tail.start();rhs=clause[start:end]
                trailing=re.search(r'\s+and\s*$',rhs,re.I)
                if trailing:end=start+trailing.start();rhs=clause[start:end]
                leading=len(rhs)-len(rhs.lstrip(' ,:'));start+=leading
                rhs=rhs.strip(' ,:');end=start+len(rhs)
                normalized=normal(re.sub(r'^(?:the|a|an)\s+','',rhs,flags=re.I))
                object_ok=normalized==normal(obligation['object'])
                kind=action_kind(match.group())
                state=('AFFIRMATIVE' if subject=='CANDIDATE' and object_ok else
                       'DENIED' if subject=='NEGATED' and object_ok else
                       'WRONG_OR_INCOMPLETE_OBJECT' if not object_ok else subject)
                receipt={'action':kind,'verb':match.group(),'action_span':[origin+match.start(),origin+match.end()],
                         'object_text':text[origin+start:origin+end],
                         'object_span':[origin+start,origin+end],'subject':subject,
                         'object_matches_exact_modifier_scope':object_ok,'status':state,
                         'source':record['source'],'evidence_id':record['evidence_id']}
                result['receipts'].append(receipt)
                if state=='AFFIRMATIVE':supported.add(kind)
                elif state=='DENIED':denied.add(kind)
                elif state!='WRONG_OR_INCOMPLETE_OBJECT':result['ambiguities'].append(state)
    # Conservatively cancel affirmative ownership when the same artifact record
    # explicitly denies ownership via a pronoun tail; no unrelated-object borrowing.
    if normal(obligation['object']) in normal(text):
        for match in re.finditer(r'without (?:owning|responsibility for) (?:its |their )?([^.;]+)',text,re.I):
            for action in ('design','development','maintenance','deployment'):
                if re.search(r'\b'+action+r'\b',match.group(1),re.I):
                    kind={'development':'develop','maintenance':'maintain','deployment':'deploy'}.get(action,action)
                    denied.add(kind)
                    result['receipts'].append({'action':kind,'status':'DENIED_OWNERSHIP_TAIL',
                        'action_span':[match.start(),match.end()],'source':record['source'],'evidence_id':record['evidence_id']})
    supported-=denied
    required=set(r['action'] for r in obligation['actions'])
    complete=(required<=supported if obligation['conjunction']=='AND' else bool(required & supported))
    return {**result,'status':'COMPLETE' if complete else 'INCOMPLETE',
            'reason':'all_boolean_obligations_proven' if complete else 'missing_denied_or_ambiguous_ownership',
            'complete':complete,'supported_actions':sorted(supported & required),
            'missing_actions':sorted(required-supported),'denied_actions':sorted(denied & required)}
