"""Bounded native-resolver review preview. No persistence or activation writer."""
from copy import deepcopy
import io
import json
import re
import zipfile

from job_discovery.matching import current_match_versions
from tailoring.capability_taxonomy import (CapabilityTaxonomy, get_default_taxonomy,
    temporary_taxonomy_scope, _validate_capability, PRODUCT_CONTEXT_GUARD_VERSION)
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from tailoring.requirement_scope import API_DEVELOPMENT_SCOPE_POLICY, API_RECOGNITION_FALLBACK, bounded_api_development_scope
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.candidate_refinement import product_context_names
from taxonomy_discovery.governed_research import knowledge_fingerprint
from taxonomy_discovery.resolver_improvement import PRODUCT_CONTEXT_GUARD
from taxonomy_discovery.unresolved_multidimensional_triage import predicate_observations

VERSION='governed-requirement-resolution-preview-v1.1'
FIELDS=('requirement_id','text','atomic_focus','importance','score_eligible','sources',
    'parent_text','source_provenance','decomposition','scope','parent_requirement_id',
    'atomic_group_id','group_weight_fraction','scoring_parent_occurrence_id','is_atomic')
ACTIVATION_BLOCKERS=(
    'A saved, current local deterministic research result and exact governed draft are required.',
    'A full native scoring-regression receipt, provisional rule controls and explicit reviewer approval are required.',
    'Live publication has not been authorized; preview is not approval.',
)

API_PLURAL_REVIEW_VERSION = 'source-bound-api-plural-review-v1'


def api_plural_review(row, raw_jd_text, *, explicit_execution=False):
    """A1: native recognition candidate only, never an analysis/draft approval.

    No taxonomy context escapes this call. Complete parent admission for numeric
    credit is intentionally not inferred from this concept-recognition receipt.
    """
    if explicit_execution is not True:
        raise ValueError('Explicit recognition review required')
    inp = requirement_input(row)
    before = resolve_requirement_with_production_knowledge(inp)
    body = dict(review_version=API_PLURAL_REVIEW_VERSION, input=inp,
        input_fingerprint=fingerprint(inp), raw_jd_fingerprint=fingerprint(raw_jd_text),
        current_versions=current_match_versions(), knowledge_fingerprint=knowledge_fingerprint(),
        native=summarize(before), candidate_capability_id=None, recognition_changed=False,
        evidence_credit=None, parent_contribution=None, whole_jd_score=None,
        disposition='REVIEW_REQUIRED', requires_human_approval=True, activation_ready=False,
        development_preview_only=True, preview_namespace='governed-api-plural-review',
        reason='outside_source_bound_development_plural_review')
    # Preserve taxonomy, registry and pure identity resolutions before considering
    # this candidate. Do not let a high-priority new phrase steal an existing ID.
    if before['knowledge_status'] != 'UNRESOLVED':
        body.update(reason='existing_native_identity_preserved', disposition='UNCHANGED')
    elif _api_plural_source_admitted(inp, raw_jd_text):
        from taxonomy_discovery.resolver_improvement import additive_phrase_overlay
        overlay = additive_phrase_overlay('backend.api_development', ['restful apis'],
                                         identity='review-only-'+API_PLURAL_REVIEW_VERSION)
        with temporary_taxonomy_scope(overlay):
            candidate = resolve_requirement_with_production_knowledge(inp)
        if candidate['decision']['capability_id'] == 'backend.api_development':
            body.update(candidate_capability_id='backend.api_development', recognition_changed=True,
                        reason='development_concept_recognized_complete_credit_scope_unapproved',
                        native_candidate=summarize(candidate))
    return {**body, 'review_fingerprint':fingerprint(body)}


def _api_plural_source_admitted(row, raw_jd):
    """Finite experimental admission, not a new published matching policy."""
    clean = lambda s:' '.join(str(s or '').split()).rstrip('. ')
    text = clean(row.get('text'))
    if not text or clean(row.get('atomic_focus', text)) != text or not raw_jd:
        return False
    parents = row.get('source_provenance')
    if not isinstance(parents, list) or len(parents) != 1:
        return False  # No cross-occurrence ownership reconstruction.
    parent = parents[0]
    if not isinstance(parent, dict):
        return False
    grounding = parent.get('grounding') or {}
    raw_parent = parent.get('raw_parent_text')
    if not (parent.get('source') in ('raw_jd.requirements', 'raw_jd.responsibilities')
            and parent.get('parent_occurrence_id') and raw_parent and raw_parent in raw_jd
            and clean(parent.get('parent_text')) == text
            and clean(row.get('parent_text', text)) == text
            and grounding.get('kind') == 'explicit_raw_section' and grounding.get('span_id')
            and type(grounding.get('sentence_index')) is int and grounding['sentence_index'] >= 1
            and clean(grounding.get('sentence_text')) == text and clean(raw_parent) == text
            and parent.get('contributes_scoring_allocation', True)
            and isinstance(parent.get('source_group_fraction'), (int, float))
            and 0 < parent['source_group_fraction'] <= 1):
        return False
    # Framework examples retain their OR list; alternatives in the main duty do
    # not become a mandatory API-development obligation.
    duty = re.split(r'\bframeworks\s+such\s+as\b', text, flags=re.I)[0]
    if re.search(r'\b(?:no|not|never|without|optional|optionally|preferably|preferred|or)\b|and/or', duty, re.I):
        return False
    if row.get('importance') != 'core' or row.get('score_eligible') is False:
        return False
    # Bind the development verb to the actual plural API object; never borrow
    # an unrelated build verb from another object/sentence.
    return bool(re.search(
        r'\b(?:build(?:ing)?|develop(?:ing)?|implement(?:ing)?|creat(?:e|ing))'
        r'(?:\s+and\s+(?:integrat(?:e|ing)|consum(?:e|ing)))?\s+'
        r'(?:(?:efficient|secure)\s*,?\s+)*restful\s+apis\b', duty, re.I))
CONTROLS=(
    ('Design and develop RESTful APIs',True,'one API-development obligation'),
    ('Experience building RESTful APIs',True,'experience explicitly building APIs'),
    ('Develop RESTful API endpoints',True,'one API endpoint-development obligation'),
    ('Implement REST APIs',True,'one API implementation obligation'),
    ('Read REST API documentation',False,'reading is not implementation'),
    ('Design and develop Amazon Web Services',False,'product name is not an API-development obligation'),
    ('Knowledge of REST APIs',False,'mention without development activity'),
    ('No experience developing RESTful APIs is required',False,'negated/nonrequired scope'),
    ('Design and develop RESTful APIs and maintain databases',False,'additional mandatory obligation'),
    ('Develop RESTful APIs and gRPC services',False,'mandatory compound protocols'),
    ('Develop RESTful APIs or maintain MongoDB',False,'alternatives must not collapse'),
    ('Experience building RESTful APIs or GraphQL APIs',False,'alternative API scope needs separate review'),
    ('Develop RESTful APIs for AWS',False,'unvalidated platform qualification'),
)


def requirement_input(row):
    return {k:deepcopy(row[k]) for k in FIELDS if k in row}


def propose(row):
    inp=requirement_input(row)
    if not bounded_api_development_scope(inp):
        raise ValueError('No complete bounded REST API-development obligation; separate review required')
    body={'preview_version':VERSION,'scope_policy':API_DEVELOPMENT_SCOPE_POLICY,
        'kind':'existing_capability_recognition_preview','target_capability_id':'backend.api_development',
        'input':inp,'input_fingerprint':fingerprint(inp),'current_versions':current_match_versions(),
        'knowledge_fingerprint':knowledge_fingerprint(),'product_context_names':product_context_names(),
        'status':'inactive_preview_only','requires_human_approval':True,
        'proposed_change':{'recognition_fallback_rules':[deepcopy(API_RECOGNITION_FALLBACK)],
            'existing_terms_and_evidence_preserved':True}}
    return {**body,'proposal_fingerprint':fingerprint(body)}


def validate_proposal(proposal):
    if proposal.get('proposal_fingerprint')!=fingerprint({k:v for k,v in proposal.items() if k!='proposal_fingerprint'}):
        raise ValueError('Preview proposal edited')
    expected=propose(proposal['input'])
    if proposal!=expected:raise ValueError('Preview proposal/current knowledge changed; preview again')


def preview_taxonomy(proposal):
    validate_proposal(proposal)
    base=get_default_taxonomy();entries=deepcopy(list(base.capabilities))
    target=next(e for e in entries if e['capability_id']=='backend.api_development')
    if target['requirement'].get('recognition_fallback_rules'):
        raise ValueError('Recognition fallback already published; no duplicate draft')
    target['requirement']['recognition_fallback_rules']=[deepcopy(API_RECOGNITION_FALLBACK)]
    seen=set()
    for entry in entries:_validate_capability(entry,seen)
    return CapabilityTaxonomy('review-only-'+proposal['proposal_fingerprint'][:24],tuple(entries))


def summarize(native):
    return {'status':native['status'],'knowledge_status':native['knowledge_status'],
        'capability_id':native['decision'].get('capability_id'),
        'reason':native['taxonomy_diagnostics']['reason'],
        'registry_reason':(native.get('registry_resolution') or {}).get('reason'),
        'resolution_source':native['resolution_source']}


def compare_inputs(rows, proposal):
    """Existing pure resolver in context-local native taxonomy; no score shortcuts."""
    overlay=preview_taxonomy(proposal);result=[]
    for row in rows:
        inp=requirement_input(row);frozen=fingerprint(inp)
        before=resolve_requirement_with_production_knowledge(inp)
        with temporary_taxonomy_scope(overlay):
            after=resolve_requirement_with_production_knowledge(inp)
        if fingerprint(inp)!=frozen:raise ValueError('Requirement input mutated')
        result.append({'requirement_id':inp.get('requirement_id'),'text':inp.get('text'),
            'input_fingerprint':frozen,'before':summarize(before),'after':summarize(after),
            'knowledge_changed':(before['knowledge_status'],before['decision'].get('capability_id'))!=
                (after['knowledge_status'],after['decision'].get('capability_id')),
            'evidence_credit_computed':False,'parent_weight_modified':False})
    return result


def preview(proposal, *, explicit_execution=False):
    if explicit_execution is not True:raise ValueError('Explicit preview required')
    rows=[{'text':text,'atomic_focus':text,'importance':'core'} for text,_,_ in CONTROLS]
    tests=compare_inputs(rows,proposal)
    for row,(_,expected,basis) in zip(tests,CONTROLS):
        preserved=row['before']['status']=='resolved'
        row.update(expected_api_recognition=(row['before']['capability_id']=='backend.api_development') if preserved else expected,
            expected_new_fallback_meaning=expected,oracle_basis=basis,
            legacy_resolution_preserved=preserved,
            passed=row['after']==row['before'] if preserved else
                (row['after']['capability_id']=='backend.api_development')==expected)
    selected=compare_inputs([proposal['input']],proposal)[0]
    body={'preview_version':VERSION,'proposal_fingerprint':proposal['proposal_fingerprint'],
        'input_fingerprint':proposal['input_fingerprint'],'current_versions':proposal['current_versions'],
        'knowledge_fingerprint':proposal['knowledge_fingerprint'],'selected_requirement':selected,
        'controls':tests,'validation_passed':all(x['passed'] for x in tests),
        'activation_ready':False,'activation_blockers':list(ACTIVATION_BLOCKERS),
        'analyst_interpretations_not_human_gold':True,'database_writes':0,'scoring_recalculations':0}
    return {**body,'preview_fingerprint':fingerprint(body)}


def activate(proposal, validation, *, explicit_confirmation=False):
    """Fail closed until the existing governor can represent this policy."""
    if explicit_confirmation is not True:raise ValueError('Explicit human confirmation required')
    validate_proposal(proposal)
    if validation!=preview(proposal,explicit_execution=True):raise ValueError('Validation stale or edited')
    raise ValueError('Governed approval and publication receipts required: '+' '.join(ACTIVATION_BLOCKERS))


def create_local_governed_draft(row, provenance, *, explicit_execution=False, db_path=None):
    """Actual existing local-only governor; persists no approval or publication."""
    if explicit_execution is not True:raise ValueError('Explicit local draft creation required')
    inp=requirement_input(row);propose(inp)
    if not provenance or any(not p.get('job_id') or not p.get('snapshot_id') or p.get('requirement_id')!=inp.get('requirement_id') for p in provenance):
        raise ValueError('Exact original job/snapshot/requirement provenance required')
    from taxonomy_discovery.taxonomy_evolution import gap_candidates
    from taxonomy_discovery.taxonomy_gaps import GAP_VERSION
    from taxonomy_discovery import governed_research as governor
    from database.taxonomy_discovery_review_manager import save_governed_research_draft
    gap={'gap_id':'recognition_'+fingerprint({'input':inp,'provenance':provenance})[:24],
        'normalized_cluster':inp['text'],'examples':[inp['text']],'occurrence_count':len(provenance),
        'job_count':len({p['job_id'] for p in provenance}),'importance_distribution':{inp.get('importance','core'):len(provenance)},
        'technology_terms':[],'retrieval_suggestions':[],'provenance':deepcopy(provenance),
        'taxonomy_version':current_match_versions()['taxonomy_version'],
        'registry_version':current_match_versions()['technology_registry_version'],
        'recommended_research_route':'resolver_issue','research_input_only':True}
    candidate=gap_candidates({'gap_version':GAP_VERSION,'observations':[gap]})[0]
    candidate.update(candidate_route='existing_capability_resolver_issue',
        routing_reason='Explicit bounded existing-capability recognition review; not a confirmed old-contract bug',
        requested_recognition_rule=deepcopy(API_RECOGNITION_FALLBACK),recognition_requirement=inp)
    candidate.pop('candidate_id');candidate.pop('candidate_fingerprint')
    candidate['candidate_fingerprint']=fingerprint(candidate)
    candidate['candidate_id']='tqd3taxgap_'+candidate['candidate_fingerprint'][:24]
    plan=governor.research_plan([candidate],selected_candidate_ids=[candidate['candidate_id']],external_resolver=False)
    if any(t['external_requested'] for t in plan['targets']):raise ValueError('External research forbidden')
    output=governor.execute_plan(plan,[candidate],explicit_execution=True,db_path=db_path,
        transport=lambda _:(_ for _ in ()).throw(ValueError('External transport forbidden')))
    if output['failures']:raise ValueError(str(output['failures']))
    result=output['results'][0];draft=governor.create_draft(result,explicit_creation=True)
    save_governed_research_draft(result,draft,db_path=db_path)
    return {'result':result,'draft':draft}


def validate_governed_draft(saved, corpus, *, explicit_execution=False, db_path=None):
    if explicit_execution is not True:raise ValueError('Explicit native regression required')
    from taxonomy_discovery.governed_research import temporary_impact
    from database.taxonomy_discovery_review_manager import save_governed_temporary_impact
    controls=preview(propose(saved['result']['candidate']['recognition_requirement']),explicit_execution=True)
    if not controls['validation_passed']:raise ValueError('Bounded controls failed')
    regression=temporary_impact(corpus,saved['draft'])
    regression.pop('regression_fingerprint',None)
    regression['recognition_policy_controls']={'proposal_fingerprint':controls['proposal_fingerprint'],
        'validation_passed':True,'controls_fingerprint':fingerprint(controls['controls'])}
    regression['regression_fingerprint']=fingerprint(regression)
    save_governed_temporary_impact(saved['result']['research_result_id'],regression,db_path=db_path)
    return regression


def approval_readiness(result_id, *, db_path=None):
    from taxonomy_discovery.governed_publication import prepare_publication
    return prepare_publication(result_id,db_path=db_path)


def diagnostic_view(row):
    inp=requirement_input(row);native=resolve_requirement_with_production_knowledge(inp)
    taxonomy=get_default_taxonomy().by_id()
    observations=predicate_observations(inp.get('atomic_focus') or inp.get('text') or '',
        [{'capability_id':cid} for cid in taxonomy],taxonomy)
    ids={p['capability_id'] for p in observations}
    ids.update(p['capability_id'] for p in (row.get('capability_retrieval') or {}).get('candidates',[])
               if p.get('capability_id') in taxonomy)
    candidates=[]
    for cid in sorted(ids):
        scope=bounded_api_development_scope(inp) if cid=='backend.api_development' else None
        candidates.append({'capability_id':cid,'label':taxonomy[cid]['label'],
            'support':'FULL_BOUNDARY_PROPOSED_NOT_APPROVED' if scope else 'PARTIAL_OR_INSUFFICIENT_NEEDS_REVIEW',
            'contract':deepcopy(taxonomy[cid]),'independent_human_gold':False,
            'separate_confirmation_required':cid=='collaboration.stakeholder'})
    return {'input':inp,'input_fingerprint':fingerprint(inp),'native':summarize(native),
        'native_taxonomy_diagnostics':native['taxonomy_diagnostics'],
        'current_versions':current_match_versions(),'knowledge_fingerprint':knowledge_fingerprint(),
        'candidate_observations':candidates,'activation_blockers':list(ACTIVATION_BLOCKERS),
        'remediation_families':['existing_capability_recognition','technology_identity_or_alias',
            'contextual_relationship','missing_bounded_capability','source_or_decomposition','valid_unresolved']}


def debug_bundle(diagnostics, validation=None):
    """Allowlisted JD-only export, redacted even inside arbitrary source text."""
    exported={k:deepcopy(diagnostics[k]) for k in ('input','native','current_versions',
        'knowledge_fingerprint','candidate_observations','activation_blockers')}
    if diagnostics.get('saved_analysis_identity'):
        exported['saved_analysis_identity']=deepcopy(diagnostics['saved_analysis_identity'])
    if validation:exported['validation']=deepcopy(validation)
    def redact(value):
        if isinstance(value,dict):return {k:redact(v) for k,v in value.items()
            if k not in ('evidence','resume_profile','raw_resume_text','candidate_evidence','selected_evidence',
                         'profile_field','resume_path','document_path','provider_request')}
        if isinstance(value,list):return [redact(v) for v in value]
        if not isinstance(value,str):return value
        value=re.sub(r'(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b','[redacted email]',value)
        value=re.sub(r'(?i)(?:sk-[\w-]{10,}|(?:api[_ -]?key|password|token)\s*[:=]\s*\S+)',
                     '[redacted secret]',value)
        value=re.sub(r'(?i)\bbearer\s+\S+','[redacted secret]',value)
        return re.sub(r'(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)','[redacted contact]',value)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('requirement_review.json',json.dumps(redact(exported),ensure_ascii=False,indent=2))
    return buffer.getvalue()
