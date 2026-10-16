"""V4 source-first review preparation; no decisions, gold imports or DB access."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json

from scripts.adjudicate_unresolved_requirements import prepare
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as gold
from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery.technology_registry import get_default_registry

VERSION = 'unresolved-human-review-packet-v4'
SELECTION = (
 (1,31,'req_2410dfcbbf45'),(2,163,'req_2f6aedb603aa'),(3,163,'req_6677d37f660c'),
 (4,15,'req_2b6f4ea8fdb3'),(6,15,'req_7b667a24f1e0'),(7,158,'req_0c34f8e720fe'),
 (8,158,'req_60119945897e'),(9,493,'req_74e080b49b36'),(10,146,'req_ba405c092a55'),
 (12,144,'req_6c3b74434db5'),(15,50,'req_12004e0f666c'),(16,50,'req_b01957201b40'),
 (20,15,'req_a8fc7690ed6f'),(21,15,'req_e33272d9bf25'),(22,31,'req_05c5e7fc5dd5'),
 (24,479,'req_61217e45f716'),(27,16,'req_191dd0c2eef9'),(33,31,'req_bc26569100e0'),
 (34,31,'req_d0a20edbb7ae'),(35,45,'req_076aaad11115'))

QUESTIONS = {
 1:'Does persistence/search establish a bounded relationship-review destination? MongoDB/Elasticsearch aliases are known; Redis has no verified registry ID here. Schema design is not implied. Preserve alternative products instead of making all mandatory.',
 2:'Inherited NAC semantic contract distinguishes network admission from database authorization, packet capture and DNS/DHCP. The long parent is additional context, not a new approval or new capability publication.',
 3:'Inherited NAC control appears under endpoint-services operations. Preserve its original confirmed expectation and source proof; no new reviewer/date is being requested.',
 4:'Learning aspiration has legitimate professional meaning. Does this exact sentence establish any bounded technical predicate, rather than curiosity alone? Additional collaboration sentence is not this requirement.',
 6:'Public-service motivation is legitimate. Is any independently bounded technical obligation stated? An inferred programming-list heading does not turn motivation into programming.',
 7:'Team growth/mentoring is legitimate leadership work. Identify an exact existing technical capability predicate before choosing CAPABILITY; broad general/technical areas alone is insufficient.',
 8:'Technology-market awareness is meaningful professional knowledge. Does it request bounded product/system evaluation or only general awareness?',
 9:'Learning software quickly is a legitimate personal quality. Does it independently request a specific technology or technical capability?',
 10:'Frozen text names database categories and such-as examples but omits the Proficiency in heading. The verified original JD supplies that heading. Decide whether familiarity is independently supported by the child-only wording or needs context-aware review. Neither SQL querying nor schema design follows from product identity.',
 12:'One-or-more Python/Node.js examples are explicit in frozen text. Both aliases are known; native alternatives are unavailable. Determine whether missing representation is truly the primary blocker. Examples must not become two mandatory obligations or extra credit.',
 15:'Frozen text requests ROS-based robotics maintenance; its parent adds develop. ROS has no established registry identity. RELATIONSHIP may be a future investigation destination, but is it a defensible exact gold blocker now? Consider identity dependency versus robotics scope and deferral; never mint a ROS ID.',
 16:'Portfolio OR AI/ML OR SLAM/motion planning OR pipelines/simulation are heterogeneous alternatives. Native representation is unavailable, but OR alone does not prove parser failure. Identify the actual blocking scope before choosing STRUCTURAL.',
 20:'Python is recognized and building internal tools/modules is explicit. Which bounded relationship needs validation? Generic tools do not establish backend APIs or data processing.',
 21:'Java plus web-application development is explicit. Native governed context reports NO_RELATIONSHIP_JUSTIFIED. A relationship-review route is not a Java-to-frontend/backend/API/full-stack mapping; CAPABILITY needs an independently satisfied exact predicate.',
 22:'Frozen child already requests responsive user interfaces with React; parent adds building and JavaScript/TypeScript. frontend.ui_development has user interface scope, with plural wording missed natively. Decide whether CAPABILITY is justified from child-only text. React identity alone does not prove responsiveness or applicant evidence.',
 24:'The complete Azure exposure/preferred sentence is frozen. Identity familiarity does not imply architecture, integration or DevOps. Registry alias is a candidate; native full-scope identity remains unresolved.',
 27:'The frozen maintenance/ingest/transform/serve pipeline scope may fit data.processing; parent adds design/build. Existing predicate includes data pipeline/ETL/transformation, while plural native selection remains unresolved. Native decomposition also exposes contextual fragments: decide primary predicate versus structural blocker, without inferring messaging from real-time feeds.',
 33:'Persistence/retrieval, CRUD and transactions with MongoDB/Elasticsearch require activity boundaries. No explicit schema-design predicate is established. Multiple products alone do not prove structural failure or a true capability gap.',
 34:'Frozen text explicitly requests building RESTful APIs; existing backend.api_development includes restful api. Frameworks are examples. Native plural selector remains unresolved; review predicate and exclusions, without inferring distributed systems or gRPC completeness.',
 35:'GenAI tools OR application development OR APIs/integration are mixed alternatives. OR and missing native structure are observations, not demonstrated parser failure. Explain any primary STRUCTURAL decision; otherwise defer scope.'}

ROUTE_HELP = {
 'CAPABILITY':'Identify one bounded existing requirement predicate and exclusions satisfied by the reviewed scope; token overlap alone is insufficient. No evidence credit is implied.',
 'TECH_ID':'Show independently valid familiarity/identity scope without an implementation mapping; alias recognition does not equal native full-scope resolution.',
 'RELATIONSHIP':'Show technology plus explicit bounded activity needing governed contextual validation; do not approve a global mapping.',
 'STRUCTURAL':'Show demonstrated parent/child, scope or alternative-representation blocker; AND/OR or missing native output alone is not enough.',
 'NOT_TAXONOMY_ADDRESSABLE':'Show absence of an independent technical-taxonomy obligation while preserving legitimate nontechnical meaning and scoring eligibility.',
 'TRUE_GAP_CANDIDATE':'Require positive bounded missing-capability contract and existing-predicate insufficiency; unresolved alone is not a true gap. NAC controls already have inherited proof.',
 'UNKNOWN / DEFER':'Use when primary-route evidence or frozen-input sufficiency is unresolved; no actionable gold label is created.'}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def build_packet():
    parent=gold.original();cases,skipped=prepare(parent)
    if skipped:raise ValueError('Frozen inputs changed')
    v2=load(gold.ROOT/'tests/fixtures/unresolved_adjudication_benchmark_v2.json');gold.validate(v2,cases=cases)
    v3=load(gold.ROOT/'reports/unresolved_gold_decision_review_v3.json')
    audited=load(gold.ROOT/'reports/unresolved_multidimensional_triage_audited_v1.json')
    comparison=load(gold.ROOT/'reports/unresolved_multidimensional_route_audit_comparison_v1.json')
    if v3['source_fingerprint']!=parent['source_fingerprint'] or v3['parent_manifest_fingerprint']!=parent['fingerprint']:
        raise ValueError('Source-review identity mismatch')
    for path,sha in audited['integrity']['protected_hashes'].items():
        if hashlib.sha256(gold.ROOT.joinpath(path).read_bytes()).hexdigest()!=sha:raise ValueError('Protected artifact changed')
    by_key={tuple(e['key']):(e,c) for e,c in zip(parent['expectations'],cases)}
    source={tuple(r['key']):r for r in v3['cases']}
    diagnostics={(r['job_id'],r['requirement_id']):r for r in audited['rows']}
    audit={(r['job_id'],r['requirement_id']):r for r in comparison['cases']}
    taxonomy=get_default_taxonomy().by_id();registry=get_default_registry();rows=[];history=[]
    for number,job,rid in SELECTION:
        key=(job,rid);e,c=by_key[key];s=source[key];d=diagnostics[key]
        if s['number']!=number or s['exact_requirement']!=c['requirement_text'] or d['requirement_text']!=c['requirement_text'] or d['provenance']['input_fingerprint']!=e['input_fingerprint']:
            raise ValueError('Review case identity/text mismatch')
        context=s['source_context'];jd=v3['sources'][str(job)]
        if hashlib.sha256(jd['raw_jd_text'].encode()).hexdigest()!=context['raw_jd_sha256']:raise ValueError('JD source hash mismatch')
        parents=[deepcopy(p) for p in context['parent_provenance'] if p['raw_parent_verified_in_jd']]
        if context['status']!='RECOVERED_AND_VERIFIED' or not parents:raise ValueError('Selected source context not verified')
        for p in parents:
            if ' '.join(p['raw_parent_text'].split()) not in ' '.join(jd['raw_jd_text'].split()):raise ValueError('Ungrounded parent source')
        for field in ('source_group_fraction','group_weight_fraction','parent_allocations','atomic_group_id','is_atomic'):
            if d['structure'][field]!=audit[key]['source_and_native_structure'][field]:raise ValueError('Parent allocation drift')
        ids=list(dict.fromkeys([p['capability_id'] for p in s['predicate_records']]+[p['capability_id'] for p in d['capability_candidates']]))
        definitions=[{k:deepcopy(taxonomy[cid].get(k)) for k in ('capability_id','label','requirement','does_not_prove','explicit_only')} for cid in ids]
        tech=deepcopy(d['technology_candidates'])
        for t in tech:
            if t['technology_id'] and t['technology_id'] not in {r['technology_id'] for r in registry.entries}:raise ValueError('Unknown registry ID')
        contextual_headings=[]
        # Exact stored JD lines, not inferred parent requirements. The heading is
        # displayed only if its literal text precedes the recorded parent line.
        if number==10:
            lines=jd['raw_jd_text'].splitlines()
            parent_line=next(i for i,l in enumerate(lines) if parents[0]['raw_parent_text'] in l)
            contextual_headings=[{'line':i+1,'text':lines[i],'source':'Additional original JD heading, not frozen child input'}
                for i in range(max(0,parent_line-3),parent_line) if lines[i].strip()=='Proficiency in:']
        row={'case_number':number,'key':list(key),'exact_frozen_requirement':c['requirement_text'],
            'input_fingerprint':e['input_fingerprint'],'source_fingerprint':parent['source_fingerprint'],
            'source_context_status':context['status'],'additional_verified_parent_context':parents,
            'additional_verified_headings':contextual_headings,'source_references':context['source_references'],
            'source_jd_sha256':context['raw_jd_sha256'],'technology_candidates':tech,'activity':deepcopy(d['activity']),
            'structure':deepcopy(d['structure']),'capability_candidates':definitions,'native_resolution':deepcopy(d['native_resolution']),
            'applicable_predicate_ids':list(dict.fromkeys([p['capability_id'] for p in s['predicate_records']]+
                [p['capability_id'] for p in d['capability_predicate_observations']])),
            'relationship_diagnostics':deepcopy(d['relationship_diagnostics']),
            'review_question':QUESTIONS[number],'route_options':list(ROUTE_HELP),'human_decision':'',
            'inherited_control':{'acceptable_routes':deepcopy(e['acceptable_routes']),'original_review_reason':e['review_reason'],
                'parent_manifest_fingerprint':parent['fingerprint'],
                'original_review_proof':deepcopy(s['original_review_record'].get('proof',{}))} if e['acceptable_routes'] else None}
        row['review_context_fingerprint']=a.fingerprint({'input_fingerprint':e['input_fingerprint'],'parent_context':parents,'headings':contextual_headings})
        rows.append(row)
        history.append({'case_number':number,'key':list(key),'earlier_v3_ai_proposed_route':s['recommendation'],
            'audited_deterministic_proposal':d['primary_route'],'comparison_status':audit[key]['current_comparison_status'],
            'uncertainty':audit[key]['remaining_uncertainty'],'not_human_gold':True})
    control32=deepcopy(diagnostics[(31,'req_8d47527c8f34')])
    packet={'packet_version':VERSION,'parent_manifest_fingerprint':parent['fingerprint'],'source_fingerprint':parent['source_fingerprint'],
        'cases':rows,'prior_ai_assisted_recommendations_appendix':history,'route_help':ROUTE_HELP,
        'remediation_queue_case32':{'key':[31,'req_8d47527c8f34'],'benchmark_status':control32['human_review']['status'],
            'priority':control32['remediation_candidate']['priority'],'concern':'Parent UI-development activity is missing from child-only input',
            'additional_context':control32['provenance']['verified_source_surfaces'],'allocation':control32['structure'],
            'next_step':'Separate versioned context-aware input benchmark and independent review; never silently append parent to v1/v2'},
        'summary':{'selected_cases':20,'inherited_independent_gold':2,'new_independent_gold':0,'ai_assisted_human_confirmations':0,
            'pending_new_decisions':18,'labeling_prerequisite_satisfied':gold.summary(v2)['labeling_prerequisite_satisfied'],
            'critical_control_outside_batch':[15,'req_71321f9eff59']}}
    packet['packet_fingerprint']=a.fingerprint(packet)
    return packet


def template(packet):
    return {'template_version':VERSION,'instructions':'Complete only reviewed entries; no routes or human attestations are preselected.',
        'decisions':[{'review_packet_version':VERSION,'review_packet_fingerprint':packet['packet_fingerprint'],'key':r['key'],'input_fingerprint':r['input_fingerprint'],
            'source_fingerprint':r['source_fingerprint'],'review_context_fingerprint':r['review_context_fingerprint'],
            'chosen_route':'','acceptable_routes':[],'origin':'','independent_of_model_predictions':None,
            'reviewer_has_seen_ai_recommendations':None,'independence_basis':'','reviewer':'','reviewed_at':'',
            'rationale':'','source_reference':'','source_spans':[],'parent_context_consulted':None,
            'parent_source_spans':[],'decision_scope':'','frozen_input_sufficient':None}
            for r in packet['cases'] if r['inherited_control'] is None],
        'inherited_controls_not_new_receipts':[{'key':r['key'],**r['inherited_control']} for r in packet['cases'] if r['inherited_control']]}


def validate_decisions(packet, receipts):
    """Validate separately; never write/import a manifest or authenticate a person."""
    if not isinstance(receipts,list):raise ValueError('Submit a JSON list of completed decisions only')
    if packet['packet_fingerprint']!=a.fingerprint({k:v for k,v in packet.items() if k!='packet_fingerprint'}):raise ValueError('Review packet integrity mismatch')
    by_key={tuple(r['key']):r for r in packet['cases']};seen=set();eligible=[]
    assisted=0;context_only=0;independent_deferrals=0
    for r in receipts:
        key=tuple(r['key'])
        if key in seen or key not in by_key:raise ValueError('Duplicate or unselected review identity')
        seen.add(key);case=by_key[key]
        if case['inherited_control']:raise ValueError('Inherited NAC provenance must remain unchanged; no new NAC receipt')
        for field in ('input_fingerprint','source_fingerprint','review_context_fingerprint'):
            if r.get(field)!=case[field]:raise ValueError('Stale review input/context/source fingerprint')
        if r.get('review_packet_version')!=VERSION:raise ValueError('V4 receipt version required')
        if r.get('review_packet_fingerprint')!=packet['packet_fingerprint']:raise ValueError('Stale review packet')
        for field in ('reviewer','reviewed_at','rationale','source_reference'):
            if not isinstance(r.get(field),str) or not r[field].strip():raise ValueError('Actual human receipt fields required')
        stamp=datetime.fromisoformat(r['reviewed_at'].replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError('Timezone-aware actual review time required')
        for field in ('parent_context_consulted','frozen_input_sufficient','reviewer_has_seen_ai_recommendations'):
            if type(r.get(field)) is not bool:raise ValueError('Explicit context/exposure declarations required')
        if r.get('decision_scope') not in ('FROZEN_INPUT','CONTEXT_AWARE_REVIEW'):raise ValueError('Explicit decision scope required')
        choice=r.get('chosen_route');routes=r.get('acceptable_routes')
        if choice not in (*a.ROUTES,'DEFER') or not isinstance(routes,list):raise ValueError('Choose a route or explicit deferral')
        if choice in ('UNKNOWN','DEFER'):
            if routes:raise ValueError('Deferral is not actionable gold')
        elif not routes or routes[0]!=choice or len(set(routes))!=len(routes) or any(x not in a.ROUTES or x=='UNKNOWN' for x in routes):raise ValueError('Explicit reviewed routes must agree with chosen primary')
        spans=r.get('source_spans')
        if not isinstance(spans,list) or not spans or any(not isinstance(s,str) or not s or s not in case['exact_frozen_requirement'] for s in spans):raise ValueError('Exact frozen supporting spans required')
        parent_spans=r.get('parent_source_spans')
        if not isinstance(parent_spans,list) or any(not isinstance(s,str) or not s or not any(s in p['raw_parent_text'] for p in case['additional_verified_parent_context']) for s in parent_spans):raise ValueError('Parent evidence must be exact verified source spans')
        if parent_spans and not r['parent_context_consulted']:raise ValueError('Parent evidence requires context declaration')
        if r['decision_scope']=='FROZEN_INPUT' and routes and not r['frozen_input_sufficient']:raise ValueError('Parent-dependent decision cannot label frozen child-only input')
        if r.get('origin')=='AI_ASSISTED_HUMAN':
            if r.get('independent_of_model_predictions') is not False:raise ValueError('AI-assisted confirmation is not independent gold')
            assisted+=bool(routes)
        elif r.get('origin')=='INDEPENDENT_HUMAN':
            if r.get('independent_of_model_predictions') is not True or r['reviewer_has_seen_ai_recommendations'] is not False or not isinstance(r.get('independence_basis'),str) or not r['independence_basis'].strip():
                raise ValueError('Independent source-only review by unexposed reviewer required; exposed confirmation remains AI-assisted')
            if r['decision_scope']=='FROZEN_INPUT':eligible.append(deepcopy(r));independent_deferrals+=not bool(routes)
            else:context_only+=1
        else:raise ValueError('Choose INDEPENDENT_HUMAN or AI_ASSISTED_HUMAN truthfully')
    parent=gold.original();cases,_=prepare(parent)
    hypothetical=gold.versioned_manifest(parent,eligible,cases)
    return {'validation_only_no_import':True,'completed_decisions':len(receipts),
        'independent_frozen_actionable_new':sum(bool(r['acceptable_routes']) for r in eligible),
        'independent_deferrals':independent_deferrals,'ai_assisted_human_confirmations':assisted,
        'independent_context_aware_not_frozen_gold':context_only,
        'hypothetical_frozen_labeling_prerequisite':gold.summary(hypothetical),
        'eligible_independent_receipts_for_separately_authorized_import':eligible}


def markdown(packet):
    def cell(v):return str(v).replace('|','\\|').replace('\n',' ')
    lines=['# V4 human gold review packet','',
        '**Preparation only: 20 selected cases, 2 inherited NAC controls, 18 undecided new reviews.** '
        'Independent gold remains 2; AI-assisted human confirmations remain 0; the labeling prerequisite is not met.', '',
        'Review the evidence and record a decision before opening the recommendations appendix. '
        'You have already seen some AI-assisted suggestions: confirmation should be recorded as AI_ASSISTED_HUMAN. '
        'Independent frozen gold requires a genuinely source-only review by an unexposed reviewer, truthful independence '
        'attestation and proof that the frozen input suffices. A program can check receipt structure, not authenticate independence.', '',
        'Frozen child-only inputs and fingerprints remain unchanged. Additional parent context is for human review, '
        'not part of the old model input. A parent-dependent judgment belongs to a separately reviewed context-aware '
        'benchmark, or must be deferred for the frozen benchmark. Aliases are candidates, not native complete-scope resolution. '
        'Candidate predicates and structure observations do not establish equivalence or applicant evidence.', '',
        'NOT_TAXONOMY_ADDRESSABLE means no independently bounded technical-taxonomy obligation. Learning, motivation, '
        'leadership and awareness remain legitimate professional meanings; their production scoring eligibility is unchanged.', '',
        '## Batch overview — no answers preselected', '',
        '| Case | Job / requirement | Exact frozen requirement | Source context | Human route/comment |',
        '|---:|---|---|---|---|']
    for r in packet['cases']:
        lines.append('| '+' | '.join(cell(v) for v in [r['case_number'],f"{r['key'][0]} / {r['key'][1]}",r['exact_frozen_requirement'],
            'Additional parent verified; inherited control' if r['inherited_control'] else 'Additional parent verified','______'])+' |')
    lines+=['','## Route evidence standards','']
    for route,help_text in ROUTE_HELP.items():lines.append(f'- **{route}:** {help_text}')
    lines+=['','## Source evidence and decisions','']
    for r in packet['cases']:
        lines += [f"### Case {r['case_number']} — Job {r['key'][0]} / {r['key'][1]}",'',
            '**Human decision: ______.** Scope: ______. Parent consulted: ______. Frozen input sufficient: ______. Evidence/rationale: ______.', '',
            '**Exact frozen child-only wording:**', '', '> '+r['exact_frozen_requirement'],'',
            '**Additional verified parent context — NOT frozen model input:**','']
        for p in r['additional_verified_parent_context']:
            lines += ['> '+p['raw_parent_text'],f"Source: `{p.get('source')}`; occurrence `{p.get('parent_occurrence_id')}`; "
                      f"stored section `{(p.get('grounding') or {}).get('section_heading','')}`; "
                      f"span `{(p.get('grounding') or {}).get('span_id')}`.",'']
        for h in r['additional_verified_headings']:lines.append(f"Additional exact JD heading, line {h['line']}: **{h['text']}** (outside frozen child).")
        lines += ['', '**Technology observations:** '+('; '.join(
            f"{t['technology_id'] or 'no verified registry ID'}: {t['matched_text_span']} [{t['registry_candidate_status']}; {t['source']}]"
            for t in r['technology_candidates']) or 'No registered identity established; do not mint one.'),'',
            '**Activity observation:** '+(r['activity']['exact_text_span'] or 'Not established')+f" [{r['activity']['source']}].",'',
            f"**Structure observations:** {r['structure']['type']}; native `{r['structure']['native_structure']['source']}`, "
            f"mode `{r['structure']['native_structure']['mode']}`. These observations do not preselect a primary blocker.",'',
            '**Existing capability candidates — hypotheses, not matches:**','']
        display_ids=r.get('applicable_predicate_ids',[c['capability_id'] for c in r['capability_candidates']])
        for c in r['capability_candidates']:
            if c['capability_id'] not in display_ids:continue
            matcher=c['requirement'] or {}
            lines.append(f"- `{c['capability_id']}`: any={matcher.get('any_terms',[])}; all={matcher.get('all_terms',[])}; groups={matcher.get('all_groups',[])}. "
                         f"Exclusions/does-not-prove={c.get('does_not_prove') or 'none recorded; this is not universal equivalence'}. "
                         +('Additional contextual phrase guards are preserved in the JSON packet.' if matcher.get('contextual_phrase_variants') else ''))
        additional=[c['capability_id'] for c in r['capability_candidates'] if c['capability_id'] not in display_ids]
        if additional:
            lines+=['','Additional lexical-overlap candidates (not matches): '+', '.join(f'`{cid}`' for cid in additional)+
                '. Their complete predicates/exclusions are in this case of the JSON packet; no equivalence is established.']
        lines += ['', f"**Native resolution:** {r['native_resolution']['status']}; knowledge {r['native_resolution'].get('knowledge_status','unknown')}. No production correction.", '',
            '**Source-specific question:** '+r['review_question'], '',
            '**Route options:** all seven categories above, or DEFER. No selection is prefilled.', '',
            f"**Unchanged allocation:** group={r['structure']['group_weight_fraction']}; source={r['structure']['source_group_fraction']}. "
            'Exact occurrence IDs, fractions, source references and frozen/context fingerprints are preserved under this case in '
            '[the JSON packet](../reports/unresolved_gold_review_packet_v4.json).','']
        if r['inherited_control']:
            lines+=['**Inherited control (not a new receipt):** '+str(r['inherited_control']['acceptable_routes'])+'. '
                    +r['inherited_control']['original_review_reason'],
                    'The full original positive gap contract is preserved in the JSON packet, without promotion or modification.',
                    'Original reviewer name/date are unavailable; neither is invented. Optional comments do not replace its original decision.','']
    lines+=['## Case 32 — retained remediation queue, outside this 20-case batch','',
        'Job31 `req_8d47527c8f34`: child-only benchmark **DEFERRED**; parent-fidelity investigation **HIGH_PRIORITY**. '
        'The shared React/JavaScript/TypeScript parent supplies UI activity missing from the isolated child. Keep the original '
        'allocations; do not assign TECH_ID or STRUCTURAL as child-only gold. A future context-aware benchmark needs a new '
        'input/prompt version, exact bounded parent excerpts, new fingerprints and independent source review. A remediation '
        'investigation can be valid while the child-only evaluation remains unfair.', '',
        '## Submitting decisions — validation first, no import in this task','',
        'The JSON template has **18 blank new decisions** and **2 inherited controls that are not new receipts**. '
        'Copy only completed entries from `decisions` into a JSON list at `reports/completed_review_decisions_v4.json`. '
        'Leave inherited controls out. Fill actual reviewer/time, chosen_route, acceptable_routes, exact frozen source_spans, '
        'source_reference and rationale. UNKNOWN/DEFER uses acceptable_routes=[]. Declare exposure, independence, parent '
        'consultation, decision scope and frozen-input sufficiency truthfully. Parent quotes use parent_source_spans and '
        'must be exact verified excerpts.', '',
        'For a reviewer who has seen prior suggestions: origin=AI_ASSISTED_HUMAN, '
        'independent_of_model_predictions=false, reviewer_has_seen_ai_recommendations=true. These records are validated '
        'as human review but never become independent benchmark labels. For a genuinely unexposed source-only reviewer, '
        'origin=INDEPENDENT_HUMAN requires independence_basis, a truthful false exposure flag and true independence attestation.', '',
        '```powershell', "$env:PYTHONDONTWRITEBYTECODE='1'", "$env:LITELLM_LOCAL_MODEL_COST_MAP='True'", "$env:CAPABILITY_RAG_MODE='off'",
        '.venv\\Scripts\\python.exe -B -m scripts.prepare_unresolved_review_packet --validate-receipts reports/completed_review_decisions_v4.json', '```','',
        'This validates only and prints separate counts plus eligible independent frozen receipts. It delegates those '
        'receipts to the existing gold validator in memory; it writes no manifest or approvals. Save only the printed '
        'eligible_independent_receipts_for_separately_authorized_import list to a separate file after explicit authorization. '
        'AI-assisted/context-only records stay in the human-review ledger; do not send them to the old independent-gold importer.', '',
        'The separately authorized existing importer command is:', '', '```powershell',
        '.venv\\Scripts\\python.exe -B -m scripts.prepare_unresolved_gold_review --receipts reports/eligible_independent_v4.json --manifest-output reports/independently_reviewed_v4_manifest.json --worksheet-output reports/independently_reviewed_v4_source.md --packet-output reports/independently_reviewed_v4_packet.json --template-output reports/independently_reviewed_v4_blank.json','```','',
        'Use new output paths; never overwrite v1/v2. The manifest keeps the existing human-review schema and full 40-case '
        'selection. There is **no import authorized in this preparation task**. Even 20 decisions in this batch do not '
        'guarantee the gate: Job15 req_71321f9eff59 is a critical pending control outside the shortlist. '
        'The existing validator must confirm at least20 independently actionable cases, four route categories and all '
        'critical controls. A labeling prerequisite also does not prove model quality or authorize Qwen.', '',
        '## Previous AI-assisted recommendations — consult only after initial source review','',
        'These are historical proposals, never independent gold or preselected answers.', '',
        '| Case | V3 AI proposal | Audited deterministic proposal | Disagreement / uncertainty |', '|---:|---|---|---|']
    for h in packet['prior_ai_assisted_recommendations_appendix']:
        lines.append('| '+' | '.join(cell(v) for v in [h['case_number'],h['earlier_v3_ai_proposed_route'],h['audited_deterministic_proposal']['route'],
            h['comparison_status']+'; '+h['uncertainty']])+' |')
    return '\n'.join(lines)+'\n'
