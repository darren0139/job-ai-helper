"""Read-only V3 source audit. Editorial recommendations are never gold labels."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from database.job_match_manager import list_latest_job_match_corpus_snapshots
from scripts.adjudicate_unresolved_requirements import prepare
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as review
from taxonomy_discovery.technology_registry import get_default_registry
from taxonomy_discovery.contextual_relationship_validation import context
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from tailoring.phase6d6_structured_matching import technology_requirement_structure

VERSION = 'unresolved-source-decision-review-v3'
SUPPORTED = 'SUPPORTED_FOR_HUMAN_CONFIRMATION'
CONTRADICTED = 'PROPOSED_ROUTE_CONTRADICTED'
MORE = 'NEEDS_MORE_SOURCE_REVIEW'
DEFER = 'DEFER'

# Explicitly reconstruct the user's discussion proposals, never model predictions.
PRELIMINARY = {2: 'TRUE_GAP_CANDIDATE', 3: 'TRUE_GAP_CANDIDATE',
    **{i: 'NOT_TAXONOMY_ADDRESSABLE' for i in (4, 6, 7, 8, 9, 39)},
    **{i: 'STRUCTURAL' for i in (11, 12, 13, 14, 16, 19, 23, 25, 28, 32, 35)},
    21: 'RELATIONSHIP', 33: 'RELATIONSHIP', 27: 'CAPABILITY', 34: 'CAPABILITY'}

# Human decision preparation, bound to the sealed original selection. These are
# editorial analyses, not production route rules, reviewed labels or receipts.
DISCUSSION = {
 1: ('RELATIONSHIP', SUPPORTED, ['database.design', 'data.processing'], 'The complete Requirements sentence contains explicit persistence/search activity with alternative products. Scope is preserved as a whole parent; identity is not the primary missing knowledge. Governed relationship/scope validation is appropriate, but no existing mapping is proven. Persistence/search is not schema design; this remains a non-gap control.'),
 2: ('TRUE_GAP_CANDIDATE', SUPPORTED, ['database.access_control', 'network.packet_analysis', 'network.dns_dhcp'], 'Inherited NAC semantic gap contract remains positive. The full parent lists endpoint/security technologies; the child is explicitly network access control, not generic database authorization. Preserve child allocation and historical confirmation; do not publish.'),
 3: ('TRUE_GAP_CANDIDATE', SUPPORTED, ['database.access_control', 'network.packet_analysis', 'network.dns_dhcp'], 'Inherited NAC positive control is a literal Responsibilities list entry under delivery/operations of endpoint services; network admission scope remains distinct from database authorization and DNS/packet analysis.'),
 4: ('NOT_TAXONOMY_ADDRESSABLE', SUPPORTED, ['collaboration.cross_functional', 'security.ci_cd'], 'Continuous-learning aspiration names no bounded technical obligation. A separate sentence about cross-agency collaboration must not be folded into this canonical requirement. Preserve legitimate learning/soft-skill semantics and scoring eligibility.'),
 5: ('UNKNOWN', DEFER, ['delivery.end_to_end_application', 'fullstack.integration'], 'Original source establishes a real traffic-control development project, not merely administrative prose. It does not establish the bounded existing delivery predicate or a new gap contract for this broad sentence. Historical non-addressable bucket is not an exact route.'),
 6: ('NOT_TAXONOMY_ADDRESSABLE', SUPPORTED, ['motivation.subjective'], 'Public-service motivation is not an independently bounded technical-taxonomy obligation. Its inferred programming-list heading is not evidence that motivation is programming. Do not erase motivation or alter eligibility.'),
 7: ('NOT_TAXONOMY_ADDRESSABLE', SUPPORTED, ['collaboration.cross_functional', 'collaboration.stakeholder'], 'Professional growth and mentoring are legitimate leadership responsibilities, but not bounded technical collaboration predicates in this taxonomy. General/technical areas does not create a technical capability requirement.'),
 8: ('NOT_TAXONOMY_ADDRESSABLE', SUPPORTED, ['operations.evaluation'], 'Broad prevailing-technology/market awareness is not the bounded product/system evaluation activity. Do not confuse general market knowledge with product evaluation.'),
 9: ('NOT_TAXONOMY_ADDRESSABLE', SUPPORTED, ['motivation.subjective'], 'Learning speed under Qualities We Value is a legitimate personal quality, not a named technical identity or capability.'),
 10: ('TECH_ID', SUPPORTED, ['database.design'], 'The recovered Requirements list explicitly requests proficiency in relational/non-relational databases with such-as examples. It does not request SQL querying or schema design. Identity familiarity is primary; retain example/one-of scope, not separate mandatory technologies. Production whole-scope diagnostics still block it; do not rewrite them.'),
 11: ('UNKNOWN', DEFER, ['data.processing', 'realtime.messaging_streaming', 'database.design'], 'The full source confirms cloud-service examples AND warehousing/lakehouse architecture. The complete parent is retained, but no native component model is available. Multiple names alone do not prove structure is the primary blocker; cloud/data relationship and capability boundaries still need human adjudication.'),
 12: ('STRUCTURAL', SUPPORTED, ['language.modern_cpp'], 'Explicit one-or-more languages with Python/Node.js examples are not represented as native alternative components. The whole-scope identity parser fails closed; preserve one-of semantics before identity routing. Node.js does not imply API work.'),
 13: ('UNKNOWN', DEFER, ['language.modern_cpp', 'backend.api_development'], 'The complete preferred requirement combines programming experience with an AND language list. Native structure is unavailable, but the whole sentence is retained. Human review must distinguish an identity familiarity list from programming activity; an AND/list count alone cannot decide the primary blocker. C# is not backend evidence.'),
 14: ('UNKNOWN', CONTRADICTED, ['game.engine_systems', 'embedded.firmware'], 'Native structure explicitly preserves a coherent example/alternative parent. ROS 2 plus simulation platforms is not automatically a decomposition failure. Familiarity/robotics relationship boundary remains unresolved; neither game-engine nor firmware scope is established. Reject the unqualified STRUCTURAL proposal.'),
 15: ('RELATIONSHIP', SUPPORTED, ['embedded.firmware', 'game.engine_systems'], 'Recovered parent explicitly says develop AND maintain ROS-based robotics solutions. Technology plus activity supports governed contextual investigation, not firmware/game-engine equivalence and not identity-only routing.'),
 16: ('STRUCTURAL', SUPPORTED, ['devops.ci_cd', 'ai.model_evaluation'], 'The source has heterogeneous OR qualifications spanning portfolio, AI/ML, SLAM/motion planning, pipelines and simulation. Native alternatives are unavailable. Preserve alternatives and qualification boundaries before routing components; GitHub portfolio is not CI/CD work.'),
 17: ('STRUCTURAL', MORE, ['frontend.ui_development'], 'The actual JD lists CSS under (a) C#, JavaScript, HTML, CSS, with a following other-languages qualifier. CSS is not an independently recovered canonical child: its frozen ID is absent from the current native snapshot. Do not infer an atomic identity obligation or reconstruct child allocation from a nearby mention.'),
 18: ('STRUCTURAL', MORE, ['frontend.ui_development'], 'HTML is in the same recovered (a) proficiency list, but its frozen canonical child ID is absent from the native snapshot. Native decomposition lineage/AND allocation needs a separately versioned input review. HTML alone cannot imply UI implementation.'),
 19: ('STRUCTURAL', SUPPORTED, ['devops.ci_cd', 'network.dns_dhcp'], 'The native child is sliced from an infrastructure-design/build parent; raw context adds networking/computer systems activity. Missing validated child scope is primary, not a single DevOps identity. Do not let the shortened mixed child hide parent obligations.'),
 20: ('RELATIONSHIP', SUPPORTED, ['backend.api_development', 'data.processing'], 'Exact source requests Python for building tools/modules. This is explicit technology-plus-activity, not identity-only. Generic internal tools do not satisfy an API or data-processing predicate without further contextual validation.'),
 21: ('RELATIONSHIP', SUPPORTED, ['backend.api_development', 'frontend.ui_development', 'fullstack.integration'], 'Java plus web-application development is explicit and whole-source grounded. Governed contextual relationship validation applies; web applications do not universally establish API, frontend or full-stack integration.'),
 22: ('CAPABILITY', SUPPORTED, ['frontend.ui_development'], 'Native parent explicitly requests building responsive user interfaces with React.js; the UI child is linked by exact native ID. Semantically fits existing UI development, despite plural wording/current matcher failure. JavaScript/TypeScript belongs to the parent; do not manufacture a universal React/JS mapping or claim native resolution changed.'),
 23: ('UNKNOWN', DEFER, ['backend.api_development', 'fullstack.integration'], 'Recovered source requests basic programming OR application-development knowledge; Python is an example. Whole parent is preserved, but no bounded programming/application knowledge capability is proven. An OR alone does not establish that decomposition is the primary blocker.'),
 24: ('TECH_ID', SUPPORTED, ['devops.ci_cd', 'fullstack.integration'], 'The exact native parent is a complete preferred Azure-familiarity sentence. Separate Azure DevOps/CI-CD and integration sentences are not parent evidence. Familiarity supports identity semantics, not architecture or CI/CD. Current scope parser does not accept this wording: recommendation is semantic, not a native resolver answer.'),
 25: ('STRUCTURAL', SUPPORTED, ['backend.api_development', 'devops.observability'], 'Recovered parent also names .NET (MVC & Core) and SQL Server, which the shortened C# child drops. Code, APIs, fixes and monitoring are mixed obligations without complete native component scope. Do not allow C# identity to imply backend completeness.'),
 26: ('UNKNOWN', DEFER, ['security.ci_cd', 'security.bug_hack_handling', 'database.access_control'], 'National-infrastructure security protocols and a following Security by Design sentence do not establish CI/CD scanning, incident/exploit handling or database authorization. No governed missing-capability contract is present.'),
 27: ('CAPABILITY', SUPPORTED, ['data.processing', 'realtime.messaging_streaming'], 'The recovered parent is design/build/maintain one data pipeline with ingest/transform/serve scope. Existing data.processing explicitly covers data pipeline/ETL/transformation. Native diagnostics over-split contextual fragments and currently miss plural wording; this is a bounded semantic fit, not proof of a missing capability or a resolver correction. Real-time feeds alone do not prove messaging implementation.'),
 28: ('UNKNOWN', CONTRADICTED, ['systems.memory_cache_performance', 'algorithms.data_structures_algorithms'], 'The source preserves a coherent autonomy-performance/reliability parent. Native structure unavailable is not proof that decomposition is primary. Existing memory/cache capability explicitly excludes generic performance; algorithms knowledge does not cover autonomy robustness. Reject unqualified STRUCTURAL; defer bounded activity equivalence.'),
 29: ('UNKNOWN', DEFER, ['ai.model_evaluation', 'embedded.firmware'], 'The source parent explicitly develops/integrates/deploys autonomy across perception/navigation/swarm/learning robotics. Robotics-AI is broad activity context, not a specific identified technology for relationship validation. Neither model-evaluation nor firmware equivalence nor a governed missing-capability contract is established.'),
 30: ('UNKNOWN', DEFER, ['integration.client_software', 'fullstack.integration', 'ai.rag_application'], 'Exploratory GenAI orchestration is not automatically client-facing system integration or RAG development. Existing client integration requires client/customer context and explicit integration, not generic procurement users.'),
 31: ('UNKNOWN', DEFER, ['integration.client_software', 'fullstack.integration', 'ai.rag_application'], 'Exact procurement context establishes exploration of linked solutions, not a proven existing integration or RAG predicate. Do not infer implementation from exploratory wording.'),
 32: ('STRUCTURAL', SUPPORTED, ['frontend.ui_development'], 'Native child drops the building-responsive-UI obligation from its shared parent. JavaScript/TypeScript is not an independently established pure identity scope. Parent/child fidelity is primary, not a universal JavaScript-to-frontend relationship.'),
 33: ('RELATIONSHIP', SUPPORTED, ['database.design', 'data.processing'], 'One complete persistence/retrieval sentence names MongoDB/Elasticsearch and CRUD/transactions. Multiple products alone are not a structural failure. Existing governed MongoDB context detects mixed database activities and does not justify schema-design mapping; relationship/scope investigation remains the destination, not a proven gap.'),
 34: ('CAPABILITY', SUPPORTED, ['backend.api_development'], 'Explicit building of RESTful APIs semantically fits backend.api_development. Frameworks are such-as alternatives, not independent obligations. Current singular-term selector misses the plural phrase: do not claim native resolution or evidence completeness has been fixed. Does not prove distributed systems or gRPC.'),
 35: ('STRUCTURAL', SUPPORTED, ['integration.client_software', 'backend.api_development', 'ai.rag_application'], 'Heterogeneous OR familiarity scopes (tools, application development, APIs, integration) lack validated native alternative components. Preserve one-of scope; tools alone do not prove RAG/application implementation.'),
 36: ('UNKNOWN', DEFER, ['delivery.end_to_end_application', 'language.modern_cpp', 'data.processing'], 'The full raw line adds C++ real-time control and Python automation/processing, but these are separate sentences. The frozen broad production-software sentence does not meet end-to-end user-facing delivery; do not import adjacent technology evidence as its atomic scope.'),
 37: ('UNKNOWN', DEFER, ['quality.qa_testing', 'systems.memory_cache_performance'], 'Failsafe pride follows proactive reliability/security initiative. No explicit testing criteria or memory/cache scope is established. Preserve motivation/safety ambiguity rather than declaring a technical gap or erasing a legitimate expectation.'),
 38: ('UNKNOWN', DEFER, ['security.ci_cd', 'database.access_control', 'security.bug_hack_handling'], 'Security by Design in an infrastructure-security line is broader than CI/CD scanning, database authorization or exploit triage. Parent context is recovered, but existing predicate equivalence/new-gap contract is not.'),
 39: ('UNKNOWN', CONTRADICTED, ['quality.qa_testing'], 'The raw source is Commitment to Quality (QA), explicitly naming automated testing frameworks, CI/CD and debugging, followed by the ethos sentence. An unqualified non-addressable classification risks discarding technical QA context. Human must adjudicate whether this frozen second sentence independently requires QA or is only ethos; do not auto-promote adjacent-parent content into its gold route.'),
 40: ('UNKNOWN', DEFER, ['delivery.end_to_end_application', 'security.ci_cd', 'language.modern_cpp'], 'The raw source contains software-quality, Linux/version-control and debugging statements. These do not prove one bounded capability for the frozen engineering-excellence sentence; no universal secure-software mapping or new gap contract is established.'),
}


def surface(text):
    """Whitespace-only comparison for source verification, never production normalization."""
    return ' '.join(str(text or '').split())


def recover(case, snapshot):
    """Never infer parent provenance from nearby text or another job's snapshot."""
    result = {'status': 'UNAVAILABLE', 'reason': 'No matching saved job source', 'source_references': [],
              'parent_provenance': [], 'nearby_lines': [], 'native_requirement': None}
    if not snapshot or snapshot['discovered_job_id'] != case['job_id']:
        return result
    raw = snapshot.get('raw_jd_text')
    if not raw or snapshot.get('raw_jd_provenance') != 'stored_job_matching_snapshot_hash':
        result['reason'] = 'Historical JD unavailable or current job content hash differs'
        return result
    result.update(status='PARTIALLY_RECOVERED', reason='Hash-pinned JD recovered; exact canonical lineage not yet verified',
        source_references=[f"data/applications.db::discovered_jobs[id={case['job_id']}].description",
                           f"data/applications.db::job_match_snapshots[id={snapshot['id']}].stable_analysis_json"],
        snapshot_id=snapshot['id'], job_content_hash=snapshot['job_content_hash'],
        raw_jd_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        snapshot_versions={k: snapshot.get(k) for k in ('match_version', 'scoring_version', 'taxonomy_version')})
    reqs = snapshot['stable_analysis']['canonical_requirements']
    matches = [r for r in reqs if r['requirement_id'] == case['requirement_id']]
    if len(matches) != 1 or matches[0].get('text') != case['requirement_text']:
        # Exact occurrences only. A CSS/HTML mention is a source location, never
        # reconstructed canonical child or assumed AND/OR allocation.
        result['exact_text_locations'] = [{'line': i, 'text': line} for i, line in enumerate(raw.splitlines(), 1)
            if re.search(r'(?<!\w)' + re.escape(case['requirement_text']) + r'(?!\w)', line)]
        result['reason'] = 'JD recovered but exact frozen canonical ID/text is absent or conflicting; source mention is not child provenance'
        return result
    native = matches[0]
    result['native_requirement'] = {k: deepcopy(native[k]) for k in ('requirement_id', 'text', 'atomic_focus', 'importance',
        'parent_text', 'source_provenance', 'is_atomic', 'decomposition', 'scope', 'scoring_parent_occurrence_id', 'group_weight_fraction') if k in native}
    parents = native.get('source_provenance') or []
    verified = bool(parents)
    for parent in parents:
        grounding = parent.get('grounding') or {}
        raw_parent = parent.get('raw_parent_text')
        check = bool(parent.get('parent_occurrence_id') and raw_parent and surface(raw_parent) in surface(raw)
                     and grounding.get('span_id'))
        result['parent_provenance'].append({**deepcopy(parent), 'raw_parent_verified_in_jd': check})
        verified = verified and check
        # Nearby lines are anchored to the exact recorded raw parent, not a
        # guessed preceding canonical requirement. Keep recorded indices separate.
        found = [i for i, line in enumerate(raw.splitlines(), 1) if surface(raw_parent) and surface(raw_parent) in surface(line)]
        for i in found:
            for j in range(max(1, i-1), min(len(raw.splitlines()), i+1)+1):
                record = {'line': j, 'text': raw.splitlines()[j-1], 'anchor_raw_parent_line': i}
                if record not in result['nearby_lines']: result['nearby_lines'].append(record)
    if verified:
        result.update(status='RECOVERED_AND_VERIFIED', reason='Exact job/requirement ID and text; every recorded parent/span is grounded in hash-pinned original JD')
    return result


def build_report(snapshots=None):
    parent = review.original()
    cases, skipped = prepare(parent)
    if skipped or len(cases) != 40:
        raise ValueError('Original frozen inputs must remain unchanged')
    snapshots = list_latest_job_match_corpus_snapshots() if snapshots is None else snapshots
    by_job = {s['discovered_job_id']: s for s in snapshots}
    if len(by_job) != len(snapshots): raise ValueError('Conflicting saved job snapshots')
    taxonomy = get_default_taxonomy().by_id()
    registry = get_default_registry()
    occurrences = {(o['job_id'], o['requirement']['requirement_id']): o for o in a.load_occurrences()}
    rows, sources = [], {}
    for i, case in enumerate(cases, 1):
        source = recover(case, by_job.get(case['job_id']))
        route, state, cap_ids, explanation = DISCUSSION[i]
        native = source['native_requirement']
        if source['status'] != 'RECOVERED_AND_VERIFIED':
            state = MORE
        predicate_records = [{k: deepcopy(taxonomy[c].get(k)) for k in
            ('capability_id', 'label', 'requirement', 'does_not_prove', 'explicit_only')} for c in cap_ids]
        entities = {r['technology_id'] for r in case['registry_candidates']}
        identities = [{k: deepcopy(e.get(k)) for k in ('technology_id', 'label', 'aliases', 'entry_kind', 'capability_relationships')}
                      for e in registry.entries if e['technology_id'] in entities]
        contextual = [{ 'technology_id': t, 'result': context(native or occurrences[(case['job_id'],case['requirement_id'])]['requirement'], t)} for t in sorted(entities)]
        resolved = resolve_requirement_with_production_knowledge(native) if native else None
        rows.append({'number': i, 'key': [case['job_id'],case['requirement_id']], 'exact_requirement': case['requirement_text'],
            'input_fingerprint': parent['expectations'][i-1]['input_fingerprint'], 'frozen_resolver': case['resolver'],
            'source_context': source, 'preliminary_route': PRELIMINARY.get(i), 'recommendation': route,
            'recommendation_state': state, 'rationale': explanation,
            'uncertainty': 'AI-assisted recommendation, not independent gold; exact native matching can differ from semantic fit',
            'human_decision': '', 'reviewer': '', 'reviewed_at': '',
            'predicate_records': predicate_records, 'registry_records': identities, 'governed_relationship_diagnostics': contextual,
            'native_structure': technology_requirement_structure(native) if native else None,
            'recovered_native_resolver': {k: deepcopy(resolved.get(k)) for k in ('status','knowledge_status','resolution_source','identity_scope','decision')} if resolved else None,
            'context_changes_frozen_input': bool(native or source.get('exact_text_locations')),
            'input_action': 'Separate versioned input benchmark required before transmitting recovered context; v1/v2 fingerprints retained',
            'original_review_provenance': parent['expectations'][i-1]['review_reason'],
            'original_review_record': deepcopy(occurrences[(case['job_id'],case['requirement_id'])]['review']),
            'context_sensitive_route': i in (10,14,17,18,19,22,24,25,27,28,32,39),
            'inherited_gold': parent['expectations'][i-1]['acceptable_routes']})
        snap = by_job.get(case['job_id'])
        if source.get('raw_jd_sha256'):
            sources[str(case['job_id'])] = {'raw_jd_text': snap['raw_jd_text'], 'raw_jd_sha256': source['raw_jd_sha256'],
                'job_content_hash': source['job_content_hash'], 'snapshot_id': snap['id'], 'source_references': source['source_references']}
            sources[str(case['job_id'])]['job_identity'] = {'table':'discovered_jobs', 'job_id':case['job_id'],
                'application_id':None, 'application_identity_note':'Discovered-job ID is not an application ID; no application association inferred'}
    counts = Counter(r['source_context']['status'] for r in rows)
    proposed = Counter(r['recommendation_state'] for r in rows if r['preliminary_route'])
    supported = Counter(r['recommendation'] for r in rows if r['recommendation_state'] == SUPPORTED)
    return {'review_version': VERSION, 'parent_manifest_fingerprint': parent['fingerprint'],
        'source_fingerprint': parent['source_fingerprint'], 'sources': sources, 'cases': rows,
        'production_knowledge_identity': cases[0]['versions'],
        'summary': {'total_cases':len(rows),'source_context': {s:counts[s] for s in ('RECOVERED_AND_VERIFIED','PARTIALLY_RECOVERED','UNAVAILABLE')},'preliminary_23':dict(proposed),
            'additional_17_investigated':sum(r['preliminary_route'] is None for r in rows),
            'supported_route_distribution':dict(supported),'independent_gold_labels':2,'new_human_labels':0,
            'quality_gate':'BENCHMARK INCONCLUSIVE', 'verdict':'READY_FOR_HUMAN_GOLD_CONFIRMATION' if supported else 'GOLD_REVIEW_SOURCE_BLOCKED'},
        'model_calls':0,'network_calls':0,'production_mutation':False}


def markdown(report):
    def cell(v): return str(v).replace('|','\\|').replace('\n',' ')
    lines = ['# Unresolved gold decision review V3', '', report['summary']['verdict'], '',
        '**AI-assisted source audit, not independent gold. All new human decisions remain blank.** '
        'The human agreed only to starting proposals. Two inherited NAC labels remain; no new receipts or labels were created.', '',
        '## Audit summary', '', '```json',json.dumps(report['summary'],indent=2),'```','',
        'Complete original JDs were recovered using the existing read-only snapshot API, which requires '
        'discovered_jobs.content_hash to equal the saved snapshot hash. RECOVERED_AND_VERIFIED additionally '
        'requires exact frozen ID/text plus every recorded raw parent/span grounded in that JD. '
        'PARTIALLY_RECOVERED does not prove canonical child boundaries. Source verification uses whitespace-only comparisons; '
        'it never normalizes production inputs. The fixture lacks historical job-content hashes, so this is corroboration '
        'through matching local snapshot IDs/text, not a new claim that the entire old corpus snapshot was reproduced.', '',
        'Source fingerprints, full JDs, parent provenance, anchored nearby lines, original stored section headings, '
        'native structure, existing registry aliases/relationships and complete checked requirement predicates/exclusions '
        'are in `reports/unresolved_gold_decision_review_v3.json`. Neither applicant evidence nor model predictions are included.', '',
        'Recovered context is separate evidence. Adding it to model inputs requires a separately versioned input benchmark; '
        'v1/v2 inputs and gold expectations are untouched. Native snapshot diagnostics are displayed separately from frozen diagnostics.', '',
        '## Decision table', '',
        '| Job/Req ID | Exact requirement | Preliminary route | Verified source context | Predicate checked | Recommendation | Confidence/uncertainty | Human decision |',
        '|---|---|---|---|---|---|---|---|']
    for r in report['cases']:
        source = r['source_context']; refs = f"snapshot {source.get('snapshot_id','none')} / JD {r['key'][0]}"
        values=[f"{r['key'][0]} / {r['key'][1]}",r['exact_requirement'],r['preliminary_route'] or 'No agreed proposal',
                source['status']+'; '+refs, ', '.join(p['capability_id'] for p in r['predicate_records']),
                r['recommendation']+'; '+r['recommendation_state'], 'Source-grounded proposal only' if source['status']=='RECOVERED_AND_VERIFIED' else source['reason'], '']
        lines.append('| '+' | '.join(cell(v) for v in values)+' |')
    lines += ['', '## Recommendation rationale and disagreements', '']
    for r in report['cases']:
        lines.append(f"- **{r['number']}. {r['key'][0]} / {r['key'][1]}:** {r['rationale']}")
    lines += ['', '## Protected controls and boundaries', '',
        '- NAC: Job163 req_2f6aedb603aa / req_6677d37f660c retain TRUE_GAP_CANDIDATE inherited expectations. Network admission differs from database authorization, packet analysis and DNS/DHCP. No publication.',
        '- MongoDB: Job31 req_2410dfcbbf45 is a complete persistence/search sentence, not a proven capability gap. RELATIONSHIP is a governed investigation destination; no schema-design mapping is justified. Job31 req_bc26569100e0 likewise mixes persistence/CRUD/search.',
        '- TECH_ID versus STRUCTURAL: Azure familiarity has a complete exact parent; CSS/HTML have source mentions but no matched frozen child IDs. The paired JavaScript/TypeScript child loses its UI parent; one-or-more languages lack native alternative scope. Several technologies alone do not establish a structural failure (ROS 2 coherent parent is the counterexample).',
        '- Unsafe mappings: SQL→querying, AWS/Azure→architecture, Node.js→API, C#→backend, JavaScript→frontend and MongoDB→database design remain prohibited absent independently bounded activity/predicate proof. All original cases/controls remain selected unchanged.',
        '- Predicates versus native matching: UI, RESTful APIs and data pipelines have semantic candidate fits, but native selectors currently miss their wording. No resolver answer, evidence label, scoring or ranking was changed. QA parent context does not automatically turn its second ethos sentence into QA gold.',
        '- NOT_TAXONOMY_ADDRESSABLE concerns technical-taxonomy obligations, not scoring eligibility. Learning, motivation and leadership remain legitimate expectations.', '',
        '## Human confirmation boundary', '',
        'SUPPORTED_FOR_HUMAN_CONFIRMATION is not a confirmed label. Read the cited source/predicate appendix, '
        'resolve primary blockers and exclusions, then explicitly record a decision in a separately authorized step. '
        'No review identities, dates or receipts have been invented. The current quality gate remains inconclusive; '
        'supported proposals are not counted as independently labeled coverage.', '',
        'No Qwen, OpenAI, Tavily, embeddings or external network calls. No production scoring/resolver/taxonomy/registry/database writes. No commit, push or merge.', '']
    if report.get('preservation_observation'):
        lines += ['## Live database observation', '',
            'The live database byte hash changed after the initial bounded audit. All task database access used read-only '
            'connections; no database write path was invoked. The exact cited JD text/content hashes and saved snapshot '
            'IDs/native provenance were rechecked and remain unchanged. Production code/knowledge and both frozen '
            'manifests also remain byte-identical. Whole-database immutability cannot be claimed; details are in '
            '`reports/unresolved_gold_v3_preservation.json`.', '']
    return '\n'.join(lines)
