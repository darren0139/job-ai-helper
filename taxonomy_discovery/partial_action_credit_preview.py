"""Stage 2D research only: separate family ownership, exact scope, and credit ceilings.

No production module imports this file. P1-P4 are proposals, never approved labels.
Expected outcomes are not accepted as detector or policy inputs.
"""
from copy import deepcopy
import re

from taxonomy_discovery import coordinated_ownership_preview as prior
from tailoring.capability_taxonomy import evaluate_capability_evidence

LANGUAGE_VERSION='RESEARCH-coordinated-ownership-language-v2d1'
PARTIAL_VERSION='RESEARCH-coordinated-partial-action-credit-v1'
HEADS={
    'pipeline':r'(?:scalable\s+)?data pipelines',
    'embedded':r'embedded software(?: modules)?',
    'fullstack':r'(?:scalable\s+)?full-stack applications',
    'cloud':r'cloud(?:-based)? applications',
    'backend':r'(?:scalable\s+)?backend services(?: and API)?',
}
PAST=r'(?:designed|developed|built|implemented|maintained|deployed)'
VERB_LIST=PAST+r'(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)'+PAST+r')*'


def technical_object(obligation,text):
    value=re.sub(r'^(?:the|a|an)\s+','',text.strip(' ,:. '),flags=re.I)
    head=re.match(HEADS.get(obligation.get('object_family'),'(?!)')+r'\b',value,re.I)
    return {'artifact_family_proven':bool(head),
            'exact_required_scope_proven':prior.normal(value)==prior.normal(obligation.get('object','')),
            'observed_object':text,'head':head.group() if head else None}


def detect(obligation,record,verified_index):
    old=prior.detect_ownership(obligation,record,verified_index)
    result={**deepcopy(old),'language_version':LANGUAGE_VERSION,'ownership_complete':False,
            'technical_scope':'UNPROVEN','technical_supported_actions':[],
            'required_object':obligation.get('object'),'extended_receipts':[]}
    if old['status'] in ('UNSUPPORTED','UNVERIFIED_SOURCE','AMBIGUOUS'):
        return result
    required={a['action'] for a in obligation['actions']}
    owned=set();full=set();denied=set(old.get('denied_actions',[]))
    def add(action,verb_span,obj_span,obj,subject,kind):
        scope=technical_object(obligation,obj)
        receipt={'action':action,'action_span':verb_span,'object_span':obj_span,
            'object_text':obj,'source':record['source'],'evidence_id':record['evidence_id'],
            'subject':subject,'binding':kind,**scope}
        result['extended_receipts'].append(receipt)
        if not scope['artifact_family_proven']:return
        if subject=='NEGATED':denied.add(action)
        if subject!='CANDIDATE':return
        owned.add(action)
        if scope['exact_required_scope_proven']:full.add(action)
    for receipt in old['receipts']:
        if 'object_span' in receipt:
            add(receipt['action'],receipt['action_span'],receipt['object_span'],receipt['object_text'],
                receipt.get('subject'),'reviewed_active_binding')
    text=record['text'];resolved_clause_spans=[]
    for clause in re.finditer(r'[^;.\n!?]+',text):
        raw=clause.group();offset=clause.start()
        passive=re.fullmatch(r'\s*(?P<object>.+?)\s+(?:was|were)\s+(?P<negative>not\s+|never\s+)?(?P<verbs>'+VERB_LIST+r')\s+by\s+(?P<agent>me|myself|the vendor|our team|them|us)\s*',raw,re.I)
        relative=re.fullmatch(r'\s*(?:Used|Using)\s+(?P<object>.+?)\s+(?:which|that)\s+(?P<agent>I|we|the vendor|our team)\s+(?P<negative>never\s+|did not\s+)?(?P<verbs>'+VERB_LIST+r')\s*',raw,re.I)
        m=passive or relative
        if not m:continue
        resolved_clause_spans.append((offset,offset+len(raw)))
        candidate=m.group('agent').casefold() in ('me','myself','i')
        subject=('NEGATED' if m.group('negative') else 'CANDIDATE') if candidate else 'NON_CANDIDATE_OR_TEAM'
        for verb in re.finditer(PAST,m.group('verbs'),re.I):
            action=prior.action_kind(verb.group())
            add(action,[offset+m.start('verbs')+verb.start(),offset+m.start('verbs')+verb.end()],
                [offset+m.start('object'),offset+m.end('object')],m.group('object'),subject,
                'explicit_first_person_passive' if passive else 'explicit_first_person_relative')
    # An explicit single-artifact "... but did not maintain it" denial is not
    # ignored just because its pronoun is not a repeated literal object.
    pronoun=re.fullmatch(r'\s*(?:I\s+)?'+PAST+r'\s+(?P<object>.+?)\s+but\s+(?:I\s+)?(?:did not|never)\s+(?P<action>design|develop|build|implement|maintain|deploy)\s+it\s*\.?',text,re.I)
    if pronoun and technical_object(obligation,pronoun.group('object'))['artifact_family_proven']:
        denied.add(prior.action_kind(pronoun.group('action')))
        result['extended_receipts'].append({'action':prior.action_kind(pronoun.group('action')),
            'action_span':[pronoun.start('action'),pronoun.end('action')],
            'binding':'single_explicit_artifact_pronoun_denial','source':record['source'],'evidence_id':record['evidence_id']})
    owned=(owned-denied)&required;full=(full-denied)&required
    ownership_complete=(required<=owned if obligation['conjunction']=='AND' else bool(required&owned))
    complete=(required<=full if obligation['conjunction']=='AND' else bool(required&full))
    ambiguities=[r.get('subject') for r in old['receipts'] if r.get('subject','').startswith(('AMBIGUOUS','NON_CANDIDATE'))
        and not any(start<=r['action_span'][0]<end for start,end in resolved_clause_spans)]
    return {**result,'status':'COMPLETE' if complete else 'INCOMPLETE','complete':complete,
            'ambiguities':sorted(set(ambiguities)),
            'ownership_complete':ownership_complete,'supported_actions':sorted(owned),
            'missing_actions':sorted(required-owned),'denied_actions':sorted(denied&required),
            'technical_supported_actions':sorted(full),
            'independent_api_guard':(evaluate_capability_evidence('backend.api_development',
                {'text':obligation['raw_parent_text']},text) if obligation.get('object_family')=='backend' else None),
            'technical_scope':'FULL' if owned and owned<=full else 'UNPROVEN',
            'reason':'literal_scope_and_ownership_complete' if complete else 'ownership_and_technical_scope_are_separate'}


def eligibility(obligation,proof,policy):
    if policy not in ('P1','P2','P3','P4'):raise ValueError(policy)
    if obligation['status']!='SUPPORTED' or proof['status'] in ('UNSUPPORTED','UNVERIFIED_SOURCE','AMBIGUOUS'):
        return 'REVIEW_REQUIRED'
    if proof.get('denied_actions') or proof.get('ambiguities'):return 'REVIEW_REQUIRED'
    if obligation.get('object_family')=='backend' and (proof.get('independent_api_guard') or {}).get('label') not in ('weak','direct'):
        return 'REVIEW_REQUIRED'
    if proof['complete']:return 'COMPLETE'
    if proof.get('technical_scope')!='FULL' or obligation['conjunction']!='AND':return 'REVIEW_REQUIRED'
    actions=set(proof['supported_actions'])
    if policy=='P1' and actions:return 'ELIGIBLE_PARTIAL'
    # P2: explicit creation plus upstream design OR required downstream lifecycle.
    # This is a delivery-phase contract, not "two arbitrary actions".
    if policy=='P2' and 'develop' in actions and actions&{'design','maintain','deploy'}:
        return 'ELIGIBLE_PARTIAL'
    # P3: the upstream design AND creation pair is critical for partial credit.
    if policy=='P3' and {'design','develop'}<=actions:return 'ELIGIBLE_PARTIAL'
    return 'REVIEW_REQUIRED'


def cap_label(native_label,admission):
    """A proposal of ceilings only; never a number-of-actions credit formula."""
    if native_label=='none':return 'none'
    if admission=='COMPLETE':return native_label
    if admission=='ELIGIBLE_PARTIAL':return 'weak'
    return None  # REVIEW_REQUIRED is a receipt disposition, not a scoring label.
