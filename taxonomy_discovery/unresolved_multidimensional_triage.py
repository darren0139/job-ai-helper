"""Additive diagnostics only: no parser children, evidence credit or knowledge writes."""
from copy import deepcopy
import math
import re

from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery.technology_registry import get_default_registry
from taxonomy_discovery.contextual_relationship_validation import context
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from tailoring.phase6d6_structured_matching import technology_requirement_structure

SCHEMA = 'unresolved-multidimensional-triage-v1'
SEMANTICS = ('SINGLE_COHERENT','ANY_OF','ONE_OR_MORE_OPEN_EXAMPLES','ALL_OF','MIXED','EXAMPLES','SHARED_PARENT_WITH_CONTEXT_LOSS','UNKNOWN')
TAGS = ('TECHNOLOGIES_RECOGNIZED','ACTIVITY_PRESENT','PARENT_ACTIVITY_ONLY','NATIVE_STRUCTURE_UNAVAILABLE',
        'SOURCE_CONTEXT_MISSING','ALTERNATIVES_NOT_MANDATORY','CONTEXT_LOSS','NO_APPROVED_RELATIONSHIP','REGISTRY_MENTION_UNRESOLVED')
DEFERRED_CHILD = (31,'req_8d47527c8f34')
ACTIVITY = re.compile(r'web-based applications development|managing data persistence and search layers|'
    r'programming/scripting languages|responsive user interfaces|'
    r'(?:building|build|design|maintain|implement|deploy|develop|write|monitor|ingest|transform|serve)\b[^.;\n]{0,100}',re.I)


def predicate_observations(text, candidates, taxonomy):
    """Requirement-side plural observations, not a production matcher or credit.

    Use whole existing terms plus an optional final plural s. No stemming,
    synonyms, evidence scoring or technology-to-capability equivalence. All
    conjunctive constraints still need to be explicitly present.
    """
    def span(term):
        parts=term.split()
        if not parts:return None
        pattern=r'(?<![\w+#])'+r'\s+'.join(re.escape(p) for p in parts)+r's?(?![\w+#])'
        return re.search(pattern,text,re.I)
    observations=[]
    for candidate in candidates:
        record=taxonomy[candidate['capability_id']];matcher=record['requirement']
        # Custom policies (notably bare C/C++ versus C#) have additional native
        # contracts. A lexical diagnostic must not stand in for those policies.
        if record.get('evidence_policy'):continue
        hits=[m for term in matcher.get('any_terms',[]) if (m:=span(term))]
        if not hits or not all(span(term) for term in matcher.get('all_terms',[])):
            continue
        if not all(any(span(term) for term in group) for group in matcher.get('all_groups',[])):
            continue
        # Negated requirements/explicit exclusions cannot become positive fits.
        if re.search(r'\b(?:not required|not expected|no experience|without|do not)\b',text,re.I):
            continue
        observations.append({'capability_id':record['capability_id'],
            'source':'CURRENT_REQUIREMENT','exact_spans':list(dict.fromkeys(m.group() for m in hits)),
            'status':'EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION',
            'negative_boundaries':deepcopy(record.get('does_not_prove',[])),
            'boundary_status':'HUMAN_REVIEW_REQUIRED_NO_EVIDENCE_CREDIT'})
    return observations


def familiarity_observation(text, technologies):
    """Bounded diagnostic exposure wording; no production identity resolution."""
    for t in technologies:
        if t['technology_id'] and t['source']=='CURRENT_REQUIREMENT' and re.fullmatch(
            r'(?:Exposure to|Familiarity with)\s+'+re.escape(t['matched_text_span'])+
            r'(?:\s+(?:cloud\s+)?services)?(?:\s+is preferred)?\.?',text,re.I):
            return {'technology_id':t['technology_id'],'exact_scope':text,
                    'status':'BOUNDED_FAMILIARITY_NOT_NATIVE_RESOLUTION'}
    return None


def activity(text, source):
    match = ACTIVITY.search(text)
    return {'exact_text_span':match.group(0) if match else '', 'bounded_activity_kind':'NAMED_ACTIVITY' if match else 'UNKNOWN',
            'source':source, 'status':'OBSERVED' if match else 'NOT_ESTABLISHED'}


def build(occurrence, recovered=None, inherited_routes=(), mentioned_unverified=()):
    case = a.build_input(occurrence)
    if case is None: raise ValueError('Already production-resolved; no unresolved diagnostic')
    recovered = recovered or {'status':'UNAVAILABLE'}
    req = occurrence['requirement']; text = case['requirement_text']; key=(case['job_id'],case['requirement_id'])
    native = recovered.get('native_requirement') if recovered.get('status')=='RECOVERED_AND_VERIFIED' else None
    if native and (native['requirement_id'] != key[1] or native['text'] != text): raise ValueError('Recovered source identity mismatch')
    parents = [p for p in recovered.get('parent_provenance',[]) if p.get('raw_parent_verified_in_jd')] if native else []
    parent_texts = list(dict.fromkeys(p['raw_parent_text'] for p in parents))
    if len(parents)>8 or any(not isinstance(p,str) or len(p)>1800 for p in parent_texts):
        raise ValueError('Parent diagnostic context exceeds bounded schema')
    surfaces = {'CURRENT_REQUIREMENT':text, **{f'VERIFIED_PARENT_{i}':p for i,p in enumerate(parent_texts)}}
    act=activity(text,'CURRENT_REQUIREMENT')
    if act['status']=='NOT_ESTABLISHED':
        for name,value in surfaces.items():
            found=activity(value,name)
            if found['status']=='OBSERVED':act=found;break
    act['missing_context'] = not bool(native)
    registry=get_default_registry(); technologies=[]
    for entry in registry.entries:
        for name,value in surfaces.items():
            hits=[m for alias in entry['aliases'] for m in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',value,re.I)]
            if hits:
                hit=sorted(hits,key=lambda m:(m.start(),-len(m.group())))[0]
                technologies.append({'technology_id':entry['technology_id'],'matched_text_span':hit.group(),
                    'registry_candidate_status':'candidate','source':name})
                break
    for span in mentioned_unverified:
        if span not in text:raise ValueError('Unverified mention is not grounded')
        technologies.append({'technology_id':None,'matched_text_span':span,'registry_candidate_status':'unresolved','source':'CURRENT_REQUIREMENT'})
    full=resolve_requirement_with_production_knowledge(native or req)
    for t in technologies:
        if t['technology_id'] and full['status']=='resolved' and full.get('technology_id')==t['technology_id']:
            t['registry_candidate_status']='verified-native'
    structure=technology_requirement_structure(native or req)
    loss=bool(parents and native.get('parent_text') and native['parent_text']!=text and act['source']!='CURRENT_REQUIREMENT')
    if loss:semantic='SHARED_PARENT_WITH_CONTEXT_LOSS'
    elif re.search(r'\bone or more\b',text,re.I):semantic='ONE_OR_MORE_OPEN_EXAMPLES'
    elif structure['mode']=='any':semantic='ANY_OF'
    elif structure['mode']=='all':semantic='ALL_OF'
    elif structure['source']=='native_coherent_example_or_alternative_parent':semantic='SINGLE_COHERENT'
    elif re.search(r'\bsuch as\b|\bor comparable\b',text,re.I):semantic='EXAMPLES'
    elif re.search(r'\bor\b',text,re.I):semantic='ANY_OF'
    elif parents and native.get('parent_text')==text:semantic='SINGLE_COHERENT'
    else:semantic='UNKNOWN'
    tags=[]
    known=any(t['technology_id'] for t in technologies)
    if known:tags.append('TECHNOLOGIES_RECOGNIZED')
    if act['status']=='OBSERVED':tags.append('ACTIVITY_PRESENT')
    if act['source']!='CURRENT_REQUIREMENT':tags.append('PARENT_ACTIVITY_ONLY')
    if loss:tags.append('CONTEXT_LOSS')
    if not native:tags.append('SOURCE_CONTEXT_MISSING')
    if structure['source']=='native_structure_unavailable':tags.append('NATIVE_STRUCTURE_UNAVAILABLE')
    if semantic in ('ANY_OF','ONE_OR_MORE_OPEN_EXAMPLES','EXAMPLES'):tags.append('ALTERNATIVES_NOT_MANDATORY')
    relationships=[{'technology_id':t['technology_id'],'diagnostic':list(context(native or req,t['technology_id']))} for t in technologies if t['technology_id']]
    if any(r['diagnostic'][2]=='NO_RELATIONSHIP_JUSTIFIED' for r in relationships):tags.append('NO_APPROVED_RELATIONSHIP')
    if mentioned_unverified:tags.append('REGISTRY_MENTION_UNRESOLVED')
    taxonomy=get_default_taxonomy().by_id()
    fits=predicate_observations(text,case['taxonomy_candidates'],taxonomy)
    familiarity=familiarity_observation(text,technologies) if native and native.get('parent_text')==text else None
    # Parent mentions remain visible as dimensions, but cannot justify a
    # relationship for an unrelated current sentence. OR is an observation,
    # not proof that native scope is defective.
    known_current=any(t['technology_id'] and t['source']=='CURRENT_REQUIREMENT' for t in technologies)
    open_language_scope=bool(semantic=='ONE_OR_MORE_OPEN_EXAMPLES' and known_current and
        re.search(r'\b(?:programming|scripting|languages)\b',text,re.I) and not structure['components'])
    route='undetermined';status='NEEDS_REVIEW';reason='No primary blocker established by bounded diagnostics'
    if inherited_routes:
        if key not in a.NAC or list(inherited_routes)!=['TRUE_GAP_CANDIDATE']:raise ValueError('Only inherited NAC expectations supported')
        route='TRUE_GAP_CANDIDATE';status='INHERITED_CONTROL'
        reason='Original inherited NAC expectation, not a new human label'
    elif not native:pass
    elif loss or open_language_scope:
        route='STRUCTURAL';status='PROPOSED';reason='Recorded parent activity lost, or open language examples lack native alternative scope'
    elif len(fits)==1 and act['status']=='OBSERVED' and act['source']=='CURRENT_REQUIREMENT':
        route='CAPABILITY';status='PROPOSED';reason='One bounded existing predicate observation; native selection and exclusions still require review'
    elif fits:reason='Predicate terms alone do not establish a unique bounded current activity/scope'
    elif familiarity:
        route='TECH_ID';status='PROPOSED';reason='Complete grounded familiarity sentence; native identity remains independently unresolved'
    elif known_current and act['status']=='OBSERVED' and act['source']=='CURRENT_REQUIREMENT' and semantic not in ('ANY_OF','ONE_OR_MORE_OPEN_EXAMPLES'):
        route='RELATIONSHIP';status='PROPOSED';reason='Same current requirement contains technology and activity; governed equivalence remains unproven'
    candidates=[{'capability_id':c['capability_id'],'predicate':deepcopy(taxonomy[c['capability_id']]['requirement']),
        'negative_boundaries':deepcopy(taxonomy[c['capability_id']].get('does_not_prove',[])),
        'basis':'TOKEN_OVERLAP_ONLY_NOT_EQUIVALENCE'} for c in case['taxonomy_candidates']]
    first=parents[0] if parents else {}
    result={'schema_version':SCHEMA,'job_id':key[0],'requirement_id':key[1],'requirement_text':text,
        'primary_route':{'route':route,'status':status,'origin':'INHERITED_FROZEN_CONTROL' if inherited_routes else 'DETERMINISTIC_DIAGNOSTIC_PROPOSAL','reason':reason},
        'technology_candidates':technologies,'activity':act,
        'structure':{'type':semantic,'interpretation_status':'PROPOSED_SOURCE_OBSERVATION','parent_occurrence_id':first.get('parent_occurrence_id'),
            'atomic_group_id':(native or req).get('atomic_group_id'), 'source_group_fraction':first.get('source_group_fraction'),
            'group_weight_fraction':(native or req).get('group_weight_fraction'), 'source':'NATIVE_PROVENANCE_AND_NONCONSUMING_TEXT_CUES',
            'parent_scope_verified':bool(parents),'is_atomic':(native or req).get('is_atomic'),'parent_allocations':
            [{k:deepcopy(p.get(k)) for k in ('parent_occurrence_id','source_group_fraction','contributes_scoring_allocation')} for p in parents],
            'native_structure':deepcopy(structure),'scoring_children_created':False},
        'capability_candidates':candidates,'capability_predicate_observations':fits,
        'familiarity_observation':familiarity,'secondary_diagnostic_tags':sorted(tags),
        'native_resolution':{k:deepcopy(full.get(k)) for k in ('status','knowledge_status','technology_id','resolution_source')},
        'relationship_diagnostics':relationships,
        'human_review':{'status':'DEFERRED_FOR_CURRENT_BENCHMARK' if key==DEFERRED_CHILD else 'PENDING',
            'reason':'Child-only frozen input lacks parent activity' if key==DEFERRED_CHILD else 'Diagnostics are not human gold',
            'reviewer':'','reviewed_at':'','input_fingerprint':a.fingerprint(case)},
        'provenance':{'source_requirement_id':key[1],'source_fingerprint':case['source_fingerprint'],
            'source_jd_hash':recovered.get('raw_jd_sha256'),'input_fingerprint':a.fingerprint(case),'production_versions':case['versions'],
            'prompt_version':None,'schema_version':SCHEMA,'source_context_status':recovered.get('status','UNAVAILABLE'),
            'source_references':deepcopy(recovered.get('source_references',[])),'verified_source_surfaces':surfaces},
        'remediation_candidate':{'target_subsystem':'parser_parent_fidelity' if key==DEFERRED_CHILD or loss else
            'contextual_relationship_validation' if route=='RELATIONSHIP' else
            'existing_capability_predicate' if route=='CAPABILITY' else 'technology_identity_scope' if route=='TECH_ID' else 'defer',
            'hypothesis':'Investigate bounded source fidelity/predicate; no production answer supplied','risk':'Identity/activity co-occurrence is not capability equivalence',
            'approval_status':'NEEDS_REVIEW','priority':'HIGH_PRIORITY_INVESTIGATION' if key==DEFERRED_CHILD else 'NORMAL'}}
    validate(result,occurrence,recovered,inherited_routes,check_canonical=False)
    return result


def validate(value, occurrence, recovered=None, inherited_routes=(), *, check_canonical=True):
    # Rebuilding makes every ID, span, provenance field and allocation auditable;
    # arbitrary model/edited fields cannot be smuggled through a permissive schema.
    if not isinstance(value,dict) or not isinstance(value.get('technology_candidates'),list) or any(not isinstance(t,dict) for t in value['technology_candidates']):
        raise ValueError('Diagnostic object and bounded technology records required')
    if check_canonical:
        expected=build(occurrence,recovered,inherited_routes,
            [t['matched_text_span'] for t in value.get('technology_candidates',[]) if t.get('registry_candidate_status')=='unresolved'])
        if value!=expected:raise ValueError('Diagnostic schema/grounding/identity mismatch')
    if value['schema_version']!=SCHEMA or value['primary_route']['route'] not in (*a.ROUTES,'undetermined'):
        raise ValueError('Invalid diagnostic version or primary route')
    provenance=value['provenance']
    for name in ('source_fingerprint','input_fingerprint'):
        if not isinstance(provenance[name],str) or not re.fullmatch(r'[0-9a-f]{64}',provenance[name]):raise ValueError('Invalid source/input fingerprint')
    if provenance['source_jd_hash'] is not None and (not isinstance(provenance['source_jd_hash'],str) or not re.fullmatch(r'[0-9a-f]{64}',provenance['source_jd_hash'])):raise ValueError('Invalid JD fingerprint')
    if value['structure']['type'] not in SEMANTICS or value['structure']['scoring_children_created'] is not False:raise ValueError('Unsafe structure')
    if len(value['technology_candidates'])>24 or len(value['capability_candidates'])>6:raise ValueError('Bounded diagnostic arrays required')
    if any(t not in TAGS for t in value['secondary_diagnostic_tags']):raise ValueError('Unknown diagnostic tag')
    for field in ('group_weight_fraction','source_group_fraction'):
        n=value['structure'][field]
        if n is not None and (isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or not 0<=n<=1):raise ValueError('Invalid allocation fraction')
    for allocation in value['structure']['parent_allocations']:
        n=allocation['source_group_fraction']
        if n is not None and (isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or not 0<=n<=1):raise ValueError('Invalid parent allocation')
    if value['human_review']['reviewer'] or value['human_review']['reviewed_at'] or value['remediation_candidate']['approval_status']!='NEEDS_REVIEW':raise ValueError('No automatic human approval')


def validate_batch(rows):
    keys=[(r['job_id'],r['requirement_id']) for r in rows]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate diagnostic case IDs')
