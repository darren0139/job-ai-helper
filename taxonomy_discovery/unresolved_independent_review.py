"""Blinded V5 review preparation/validation; no inference, DB access or imports."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from scripts.adjudicate_unresolved_requirements import prepare
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as gold
from taxonomy_discovery import unresolved_review_packet as v4

ROOT=gold.ROOT
VERSION='unresolved-independent-review-packet-v5'
DEFERRED_CHILD=(31,'req_8d47527c8f34')
ROUTE_HELP={
 'CAPABILITY':'An explicit bounded activity may fit a supplied existing requirement predicate. Check conjunctions and exclusions. Lexical overlap is not predicate coverage; an actual resolver defect requires native evidence.',
 'TECH_ID':'Investigate an unresolved technology identity or familiarity scope. A name/alias candidate is not successful full-scope resolution and never implies implementation expertise. Native evidence is needed to identify identity as the actual blocker.',
 'RELATIONSHIP':'Investigate contextual technology-to-activity knowledge when source explicitly connects both. Co-occurrence does not prove an approved mapping or that missing relationship knowledge caused unresolved matching.',
 'STRUCTURAL':'Requires demonstrated source-scope/parent-child/alternative-representation loss, rather than merely AND/OR or unavailable structure. Do not infer missing parent wording.',
 'NOT_TAXONOMY_ADDRESSABLE':'No independently bounded technical-taxonomy obligation is established in the permitted scope. Professional meaning can remain legitimate; this does not decide scoring eligibility. Technology familiarity alone is not professional-only.',
 'TRUE_GAP_CANDIDATE':'Requires positive evidence of a bounded missing reusable capability and sufficiently complete existing contracts shown insufficient. Unresolved status, token overlap or absent context alone cannot prove a gap.',
 'UNKNOWN / DEFER':'Record insufficient diagnostic/source evidence or unresolved competing blockers. No actionable label is created. Do not use missing applicant proof to replace analysis of source meaning.'}
INSTRUCTIONS=[
 'Review only this packet and its blank receipt template before recording a decision. Do not open earlier review reports, manifests containing expectations, AI conversations, deterministic triage proposals or model results.',
 'If you have previously seen recommendations for a case, declare that exposure truthfully; that review cannot be independently blind. Software cannot authenticate this attestation.',
 'Separate explicit JD meaning, native diagnostic observations, and the proposed investigation route. A technology/activity link is not by itself proof of a production subsystem failure.',
 'Exact frozen wording below is the only permitted requirement source text. Source references are provenance locators, not permission to expand this child-only evidence. No parent, heading, sibling or full JD text is supplied.',
 'Native observations are the original bounded production outputs, not gold answers. Candidate lists are frozen lexical/alias candidates, not predicate fits or resolved identities; abbreviated terms are not complete contracts.',
 'If outside context or complete contracts are indispensable, defer the frozen decision and request a separately versioned context-aware review. Never silently append source context.',
 'All seven routes remain available, with UNKNOWN/DEFER when evidence is insufficient. Numeric targets must never influence individual decisions. No applicant evidence or scoring obligations are inferred.',
 'Record exact source spans, evidence accessed, diagnostic label kind, native evidence for any causal claim, uncertainty, actual reviewer identity/reference and actual timezone-aware review time. Leave unreviewed fields blank.']


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def state():
    parent=gold.original();cases,skipped=prepare(parent)
    if skipped or len(cases)!=40:raise ValueError('Frozen inputs unavailable/changed')
    reviewed=read(ROOT/'tests/fixtures/unresolved_adjudication_benchmark_v2.json')
    gold.validate(reviewed,cases=cases)
    source=read(ROOT/'reports/unresolved_gold_decision_review_v3.json')
    if source['parent_manifest_fingerprint']!=parent['fingerprint'] or source['source_fingerprint']!=parent['source_fingerprint']:
        raise ValueError('Recovered source identity changed')
    if len(source['cases'])!=40 or [r['key'] for r in source['cases']]!=[e['key'] for e in parent['expectations']]:
        raise ValueError('Recovered source selection mismatch')
    occurrences={(o['job_id'],o['requirement']['requirement_id']):o for o in a.load_occurrences()}
    return parent,cases,reviewed,source,occurrences


def allocation(native):
    # Numerical provenance only. No parent/source sentence or inferred scope.
    return {k:deepcopy(native.get(k)) for k in ('group_weight_fraction','atomic_group_id','is_atomic','scoring_parent_occurrence_id')}


def build_packet():
    protected_hashes()
    parent,cases,reviewed,source,occurrences=state();rows=[]
    for e,c,s in zip(parent['expectations'],cases,source['cases']):
        if e['acceptable_routes']:continue  # Existing approvals never enter blind review.
        if c['requirement_text']!=s['exact_requirement'] or a.fingerprint(c)!=e['input_fingerprint']:
            raise ValueError('Frozen source/wording/fingerprint mismatch')
        sc=s['source_context'];jd=source['sources'].get(str(c['job_id']))
        if jd and sha_text(jd['raw_jd_text'])!=sc['raw_jd_sha256']:raise ValueError('Original JD hash mismatch')
        # Allowlist from frozen contract; never copy prior conclusions or context.
        frozen={k:deepcopy(c[k]) for k in ('job_id','requirement_id','requirement_text','importance','nearby_context','resolver','taxonomy_candidates','registry_candidates','source_fingerprint','versions')}
        row={'review_case_number':len(rows)+1,'key':deepcopy(e['key']),'input_fingerprint':e['input_fingerprint'],
             'frozen_input':frozen,
             'source_provenance':{'original_source_references':deepcopy(sc['source_references']),
                                  'original_jd_sha256':sc.get('raw_jd_sha256'),'snapshot_id':sc.get('snapshot_id'),
                                  'job_content_hash':sc.get('job_content_hash'),
                                  'references_are_locators_only_not_additional_review_text':True},
             'allocation_provenance':allocation(occurrences[tuple(e['key'])]['requirement']),
             'reviewer_judgment':{'chosen_route':'','acceptable_routes':[],'diagnostic_label_kind':'',
                                  'source_spans':[],'uncertainty':'','deferral_rationale':''}}
        row['review_context_fingerprint']=a.fingerprint(row)
        rows.append(row)
    packet={'packet_version':VERSION,'parent_manifest_fingerprint':parent['fingerprint'],
            'source_fingerprint':parent['source_fingerprint'],'instructions':INSTRUCTIONS,
            'route_help':ROUTE_HELP,'cases':rows,'preparation_only':True}
    packet['packet_fingerprint']=a.fingerprint(packet)
    return packet


def sha_text(value):return hashlib.sha256(value.encode()).hexdigest()


def validate_packet(packet):
    # Exact rebuild/allowlist catches resealed leaks as well as input drift.
    if packet!=build_packet():raise ValueError('Packet altered, leaked fields or frozen provenance mismatch')
    keys=[tuple(r['key']) for r in packet['cases']]
    if len(keys)!=38 or len(set(keys))!=38:raise ValueError('Exactly 38 distinct pending cases required')
    return True


def template(packet):
    return {'template_version':VERSION,'review_packet_fingerprint':packet['packet_fingerprint'],
        'instructions':'Fill only actually reviewed decisions. All decisions, identities, times and attestations remain blank. Submit a separate JSON list of completed entries only.',
        'decisions':[{'review_packet_version':VERSION,'review_packet_fingerprint':packet['packet_fingerprint'],
            'key':deepcopy(r['key']),'input_fingerprint':r['input_fingerprint'],
            'source_fingerprint':packet['source_fingerprint'],'review_context_fingerprint':r['review_context_fingerprint'],
            'chosen_route':'','acceptable_routes':[],'diagnostic_label_kind':'',
            'origin':'','independent_of_model_predictions':None,'reviewer_has_seen_ai_recommendations':None,
            'independence_basis':'','reviewer':'','reviewed_at':'','rationale':'','source_reference':'',
            'source_spans':[],'evidence_accessed':[],'native_supporting_evidence':[],
            'uncertainty':'','deferral_rationale':'','parent_context_consulted':None,'parent_source_spans':[],
            'decision_scope':'','frozen_input_sufficient':None} for r in packet['cases']]}


def compatible_packet(packet):
    """Private compatibility envelope for the existing V4 receipt validator.

    Never displayed as V4 provenance, never persisted. Original V5 receipts are
    returned/importable; the existing gold validator accepts their extra fields.
    """
    compat={'packet_version':v4.VERSION,'cases':[{
        'key':r['key'],'input_fingerprint':r['input_fingerprint'],
        'source_fingerprint':packet['source_fingerprint'],'review_context_fingerprint':r['review_context_fingerprint'],
        'exact_frozen_requirement':r['frozen_input']['requirement_text'],
        'additional_verified_parent_context':[], 'inherited_control':None} for r in packet['cases']]}
    compat['packet_fingerprint']=a.fingerprint(compat)
    return compat


def validate_decisions(packet,receipts):
    validate_packet(packet)
    if not isinstance(receipts,list):raise ValueError('Completed receipts must be a JSON list')
    allowed={tuple(r['key']):r for r in packet['cases']};compat=compatible_packet(packet);converted=[]
    for receipt in receipts:
        if not isinstance(receipt,dict) or set(receipt)!=set(template(packet)['decisions'][0]):
            raise ValueError('Exact blank-template receipt fields required; no prediction fields')
        key=tuple(receipt.get('key',[]));row=allowed.get(key)
        if not row:raise ValueError('Unknown, duplicate or inherited-gold replacement receipt')
        if receipt.get('review_packet_version')!=VERSION or receipt.get('review_packet_fingerprint')!=packet['packet_fingerprint']:
            raise ValueError('Actual V5 receipt identity required')
        if receipt.get('diagnostic_label_kind') not in ('INVESTIGATION_ROUTE','VERIFIED_ROOT_CAUSE','DEFERRED'):
            raise ValueError('Declare investigation route versus verified causal claim or deferral')
        routes=receipt.get('acceptable_routes');choice=receipt.get('chosen_route')
        if (choice in ('DEFER','UNKNOWN'))!=(receipt['diagnostic_label_kind']=='DEFERRED'):
            raise ValueError('Deferral label-kind must agree with the decision')
        for field in ('uncertainty','deferral_rationale'):
            if not isinstance(receipt.get(field),str):raise ValueError('Human uncertainty/deferral fields required')
        if choice in ('DEFER','UNKNOWN') and not receipt['deferral_rationale'].strip():raise ValueError('Explicit deferral rationale required')
        if key==DEFERRED_CHILD and routes and receipt.get('decision_scope')=='FROZEN_INPUT':
            raise ValueError('Existing deferred child requires a separately versioned context-aware review')
        if receipt.get('parent_context_consulted') and receipt.get('decision_scope')=='FROZEN_INPUT':
            raise ValueError('Parent consultation cannot enter the blinded child-only benchmark')
        if receipt.get('parent_source_spans'):raise ValueError('Parent text requires separately versioned review material; absent from V5')
        evidence=receipt.get('evidence_accessed')
        if not isinstance(evidence,list) or not evidence:raise ValueError('Actual evidence accessed must be declared')
        for ev in evidence:
            if not isinstance(ev,dict) or set(ev)!= {'kind','reference','fingerprint'}:raise ValueError('Evidence receipt schema')
            if ev['kind'] in ('FROZEN_INPUT','NATIVE_FROZEN_DIAGNOSTICS','FROZEN_KNOWLEDGE_CANDIDATES'):
                if ev['reference']!=f"{row['key'][0]}/{row['key'][1]}" or ev['fingerprint']!=row['input_fingerprint']:
                    raise ValueError('Evidence access must bind the permitted frozen view')
            elif ev['kind']=='OUTSIDE_FROZEN_CONTRACT':
                if receipt.get('decision_scope')!='CONTEXT_AWARE_REVIEW':raise ValueError('Extended evidence cannot label frozen input')
                if not isinstance(ev['reference'],str) or not ev['reference'].strip() or not isinstance(ev['fingerprint'],str) or len(ev['fingerprint'])!=64:
                    raise ValueError('Actual extended evidence reference/fingerprint required')
            else:raise ValueError('Unknown evidence access kind')
        if not any(ev['kind']=='FROZEN_INPUT' for ev in evidence):
            raise ValueError('Actual frozen requirement source access must be recorded')
        native=receipt.get('native_supporting_evidence')
        if not isinstance(native,list):raise ValueError('Native evidence field required')
        for ev in native:
            if not isinstance(ev,dict) or set(ev)!= {'field','exact_value'} or ev['field'] not in row['frozen_input']['resolver'] or ev['exact_value']!=row['frozen_input']['resolver'][ev['field']]:
                raise ValueError('Native support must cite an exact frozen diagnostic fact')
        substantive=any(ev['field'] in ('reason','registry_reason','scope_reason','taxonomy_status') and
                        ev['exact_value'] not in (None,'','unrecognised_capability') for ev in native)
        if receipt['diagnostic_label_kind']=='VERIFIED_ROOT_CAUSE' and (not substantive or not any(ev['kind']=='NATIVE_FROZEN_DIAGNOSTICS' for ev in evidence)):
            raise ValueError('Causal claims require actual native diagnostics, not a semantic keyword')
        changed=deepcopy(receipt)
        changed['review_packet_version']=v4.VERSION;changed['review_packet_fingerprint']=compat['packet_fingerprint']
        converted.append(changed)
    result=v4.validate_decisions(compat,converted)
    # Restore authentic V5 provenance, rather than exporting internal envelopes.
    eligible=[deepcopy(r) for r in receipts if r.get('origin')=='INDEPENDENT_HUMAN' and r.get('decision_scope')=='FROZEN_INPUT']
    cases,_=prepare(gold.original());hypothetical=gold.versioned_manifest(gold.original(),eligible,cases)
    result['eligible_independent_receipts_for_separately_authorized_import']=eligible
    result['hypothetical_frozen_labeling_prerequisite']=gold.summary(hypothetical)
    result['review_packet_version']=VERSION
    result['causal_truth_and_reviewer_independence_not_authenticated_by_software']=True
    return result


def protected_hashes():
    hashes=deepcopy(read(ROOT/'reports/ollama_unresolved_prompt_comparison_v1_3_plan.json')['protected_hashes'])
    for rel in ('docs/ollama_unresolved_prompt_comparison_v1_3.md','reports/ollama_unresolved_prompt_comparison_v1_3.json',
                'reports/ollama_unresolved_prompt_comparison_v1_3_plan.json','scripts/review_ollama_unresolved_comparison_v1_3.py','tests/test_ollama_prompt_review_v1_3.py'):
        hashes[rel]=sha(ROOT/rel)
    for rel,value in hashes.items():
        if sha(ROOT/rel)!=value:raise ValueError('Prior protected bytes changed')
    return hashes


def readiness(packet):
    parent,cases,reviewed,source,occurrences=state();v4_packet=read(ROOT/'reports/unresolved_gold_review_packet_v4.json')
    by_key={tuple(r['key']):r for r in source['cases']};included={tuple(r['key']) for r in packet['cases']}
    summary=gold.summary(reviewed)
    return {'current_gold':summary,'minimum_actionable':20,'minimum_non_unknown_categories':4,
            'additional_actionable_needed':20-summary['confirmed'],'prepared_pending_cases':len(included),
            'independently_actionable_cases_new':0,'actionability_not_determined_by_preparation':True,
            'all_pending_critical_covered':all(tuple(k) in included for k in summary['critical_pending']),
            'pending_critical_keys':summary['critical_pending'],
            'v4_selected_keys':[r['key'] for r in v4_packet['cases']],
            'new_material_not_in_v4':[r['key'] for r in packet['cases'] if r['key'] not in [x['key'] for x in v4_packet['cases']]],
            'source_recovery_verified_pending':[r['key'] for r in packet['cases'] if by_key[tuple(r['key'])]['source_context']['status']=='RECOVERED_AND_VERIFIED'],
            'source_recovery_partial_pending':[r['key'] for r in packet['cases'] if by_key[tuple(r['key'])]['source_context']['status']!='RECOVERED_AND_VERIFIED'],
            'frozen_child_existing_deferral':list(DEFERRED_CHILD),
            'potential_frozen_review_attempts_excluding_existing_deferral':len(included)-1,
            'v4_genuinely_blinded':False,
            'v4_leak_locations':['prior_ai_assisted_recommendations_appendix','cases[].review_question',
                                 'cases[].inherited_control','cases[].additional_verified_parent_context',
                                 'cases[].activity / structure / applicable_predicate_ids (editorial diagnostics)'],
            'protected_hashes':protected_hashes()}


def markdown(packet):
    lines=['# Independent source-only review packet V5','',
           'All decisions are blank. This packet contains only pending frozen cases; no prior answers are supplied.','']
    lines.extend('- '+s for s in packet['instructions'])
    lines+=['','## Neutral route definitions','']
    lines.extend('- **'+route+'**: '+text for route,text in packet['route_help'].items())
    lines+=['','## Blank evidence/decision worksheet','',
            'For each case record: decision ___; acceptable routes ___; investigation route or verified root cause ___; '
            'reviewer/reference ___; actual timestamp ___; prior AI exposure ___; exact source spans ___; '
            'evidence accessed ___; native diagnostic support ___; uncertainty ___; deferral rationale ___; '
            'frozen input sufficient ___; parent consulted ___; decision scope ___.','',
            'Use the JSON receipt template for submission. Do not fill any independence or source sufficiency field by default.','']
    for row in packet['cases']:
        c=row['frozen_input']
        lines += [f"## Review {row['review_case_number']} — Job {row['key'][0]} / {row['key'][1]}",'',
                  'Exact frozen source wording (JSON preserves invisible characters):','',
                  '```json',json.dumps(c['requirement_text'],ensure_ascii=True),'```','',
                  f"Importance: {c['importance']}. Input fingerprint: `{row['input_fingerprint']}`.",'',
                  'Original source references — provenance only; no permission to consult additional parent wording:','',
                  '```json',json.dumps(row['source_provenance'],indent=2),'```','',
                  'Native frozen observations — facts about recorded outputs, not a primary root-cause decision:','',
                  '```json',json.dumps(c['resolver'],indent=2),'```','',
                  'Neutral frozen candidate facts — token/alias matches only; not complete predicate contracts:','',
                  '```json',json.dumps({'taxonomy_candidates':c['taxonomy_candidates'],'registry_candidates':c['registry_candidates']},indent=2),'```','',
                  'Unchanged numerical allocation provenance (no parent wording):','',
                  '```json',json.dumps(row['allocation_provenance'],indent=2),'```','',
                  f"Knowledge/version provenance: `{a.fingerprint(c['versions'])}`; full values in the V5 JSON packet.",'',
                  'Decision ___; exact spans ___; native evidence ___; uncertainty ___; further context request ___.','']
    return '\n'.join(lines)+'\n'
