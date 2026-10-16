"""Offline report preparation; local snapshots are read through read-only APIs."""
import argparse
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import sqlite3

from analysis_stability.stable_evidence_scoring import build_resume_evidence_index, build_deterministic_keyword_match
from database.job_match_manager import list_latest_job_match_corpus_snapshots
from job_discovery.matching import build_profile_evidence_context
from tailoring.capability_taxonomy import evaluate_evidence, TAXONOMY_PATH
from tailoring.phase9e_blueprint_selection import build_phase9e_keyword_match
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from taxonomy_discovery import unresolved_semantic_evidence as diagnostic
from taxonomy_discovery.maintenance_service import production_identity
from taxonomy_discovery.offline_execution import offline_execution
from taxonomy_discovery.unresolved_adjudication import fingerprint
from taxonomy_discovery.technology_registry import REGISTRY_PATH

ROOT = Path(__file__).resolve().parents[1]
CASE_FINDINGS = {
    10: {'verified': 'The child omits the verified Proficiency in heading. Native coherent examples remain one allocated parent; PostgreSQL is already cited as transferable.',
         'hypothesis': 'A source-scoped broad database annotation could explain relational versus non-relational partial relevance more clearly.',
         'not_proven': 'Exact-product-only matching, omitted SQL querying, schema design, database administration or a tailoring omission.',
         'next_owner': 'native JD source provenance / requirement_scope; stable_tailoring_ranking project relevance explainability'},
    15: {'verified': 'ROS has no native registry identity here; no saved ROS implementation evidence was discovered. Related Python/C++ surfaces do not establish robotics maintenance.',
         'hypothesis': 'Separate governed ROS identity/scope investigation, and optionally bounded adjacent engineering evidence discovery.',
         'not_proven': 'A ROS matching false negative, SLAM/navigation capability, or an approved robotics relationship.',
         'next_owner': 'technology_registry / existing governed identity workflow; contextual_relationship_validation'},
    16: {'verified': 'One preferred coherent native requirement retains weight 1. GitHub is already selected as transferable; saved LLM/RAG/CI records provide additional branch-relevance hypotheses.',
         'hypothesis': 'Source-grounded nested alternatives would improve explanation of which advantageous branch is supported.',
         'not_proven': 'Parser inflation, portfolio quality, SLAM/motion planning, simulation experience or project-selection suppression.',
         'next_owner': 'phase6d6_structured_matching / native decomposition source scope; stable_tailoring_ranking'},
    35: {'verified': 'Saved Job AI Helper evidence describes an LLM pipeline and RAG integration. AI application development is already cited as transferable. Saved downstream lineage sources exist.',
         'hypothesis': 'Show the relevant implementation record alongside the broad selected skill citation without promoting match strength.',
         'not_proven': 'Model-response validation, API-failure handling, model training, exact coverage of every branch, or Phase9E omission.',
         'next_owner': 'phase9e_blueprint_selection.build_phase9e_keyword_match; stable_tailoring_ranking; evidence_grounded_bullet_tailoring'},
}


def protected_hashes():
    paths = list((ROOT/'analysis_stability').glob('*.py')) + list((ROOT/'tailoring').glob('*.py'))
    paths += list((ROOT/'data').glob('*taxonomy*.json'))
    paths += list((ROOT/'data').glob('*registry*.json'))
    paths += list((ROOT/'tests/fixtures').glob('unresolved_adjudication_benchmark*.json'))
    paths += list((ROOT/'reports').glob('unresolved_gold*.json'))
    # Include the diagnostic inputs and frozen scoring source, not generated outputs.
    paths += [ROOT/'tests/fixtures/confirmed_taxonomy_coverage.json',
              Path(TAXONOMY_PATH), Path(REGISTRY_PATH),
              ROOT/'reports/unresolved_multidimensional_triage_audited_v1.json',
              ROOT/'reports/unresolved_multidimensional_route_audit_comparison_v1.json']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def synthetic_controls():
    """Illustrative boundary probes only; never benchmark or applicant evidence."""
    examples = [
        ('database', 'Database proficiency', 'Queried SQL databases.', 'Relevant relational querying only; no schema/security/admin or universal database proof.'),
        ('postgres', 'PostgreSQL proficiency', 'Developed SQL Server reporting queries.', 'Transferable relational experience; not PostgreSQL proficiency.'),
        ('ros', 'Maintain ROS robotics', 'Developed robotics software without ROS.', 'ROS absence explicitly fails closed; related robotics warrants manual adjacency review.'),
        ('llm', 'LLM application development', 'Implemented LLM API integration in an application.', 'Direct relevance to bounded implementation; no model training or full mixed requirement proof.'),
        ('genai', 'GenAI familiarity', 'Used ChatGPT.', 'Tool surface only; no implementation claim.'),
        ('kubernetes', 'Kubernetes proficiency', 'Implemented Docker CI/CD workflows.', 'Adjacent deployment experience; no Kubernetes proficiency.'),
        ('api', 'Backend API development', 'Node.js', 'Runtime listing does not establish API implementation.'),
        ('cloud', 'Cloud architecture', 'AWS', 'Platform listing does not establish architecture.'),
        ('ros', 'Maintain ROS robotics', 'Developed robotics software.', 'Adjacent robotics without explicit ROS proof.'),
        ('api', 'REST API development', 'Implemented a REST API.', 'Bounded API implementation source; no gRPC/architecture implication.'),
    ]
    output = []
    for index, (profile, text, evidence, boundary) in enumerate(examples):
        record = {'evidence_id': 'synthetic_'+str(index), 'source': 'SYNTHETIC_CONTROL_NOT_APPLICANT_EVIDENCE', 'text': evidence}
        req = {'text': text, 'atomic_focus': text, 'requirement_id': 'synthetic_req_'+str(index)}
        native = evaluate_evidence(req, evidence)
        keyword = build_deterministic_keyword_match(requirements=[req], acronym_map={}, resume_profile={}, raw_resume_text=evidence)
        output.append({'kind': 'SYNTHETIC_NOT_GOLD', 'requirement': text, 'evidence': evidence,
            'boundary': boundary, 'discovery': diagnostic.discover(profile, req['requirement_id'], [record]),
            'native_capability': {k: native.get(k) for k in ('capability_id', 'label', 'reason')},
            'native_keyword': redact_keyword(keyword, [record]),
            'actual_tailoring_omission': 'NOT_ESTABLISHED_SYNTHETIC_PROBE'})
    return output


def redact_keyword(result, records):
    """Do not persist matched résumé text, even in a native comparison."""
    present = []
    for row in result.get('present', []):
        term = row.get('matched_resume_term', '')
        record = next((r for r in records if r['text'] == term), None)
        present.append({k: row.get(k) for k in ('match_type', 'evidence_type', 'found_in')} | {
            'evidence_id': record['evidence_id'] if record else None,
            'source_location': record['source'] if record else None,
            'matched_text_sha256': diagnostic.sha(term),
            'selection_basis': row.get('phase9e_evidence_selection', {}).get('selection_basis'),
        })
    return {'present': present, 'missing': bool(result.get('missing')),
            'scope': 'CURRENT_PURE_MATCHER_PROBE_NOT_SAVED_BLUEPRINT_OR_SCORE'}


def downstream(conn, case):
    sha = case['source_jd_sha256']
    decisions = [dict(r) for r in conn.execute(
        'select application_id,decision_id,scoring_version,selected_source from application_blueprint_decisions where raw_jd_sha256=?', (sha,))]
    jd_ids = [r['id'] for r in conn.execute('select id,raw_text from job_descriptions')
              if diagnostic.sha(r['raw_text'] or '') == sha]
    links = [dict(r) for jid in jd_ids for r in conn.execute(
        'select application_id,job_description_id,source_version_id from application_job_links where job_description_id=?', (jid,))]
    return {'exact_jd_hash_decisions': decisions, 'exact_jd_ids': jd_ids, 'exact_application_links': links,
            'phase8': 'NO_EXACT_LINKED_APPLICATION_VERIFICATION_ESTABLISHED' if not links else 'REQUIRES_LINKED_RECORD_REVIEW',
            'phase9e': 'NO_EXACT_SAVED_DECISION' if not decisions else 'REQUIRES_SAVED_DECISION_REVIEW',
            'tailoring': 'INSUFFICIENT_DATA_NO_EXACT_GENERATION_TRACE',
            'project_omission_demonstrated': False,
            'hypothetical_ranking_substituted': False}


def helper_sources(conn):
    """Bounded source metadata, never résumé text or executable-code achievements."""
    output = []
    for r in conn.execute('select candidate_id,snapshot_json from global_blueprint_candidates'):
        snapshot = json.loads(r['snapshot_json'])
        projects = snapshot.get('resume_profile_snapshot', {}).get('projects', [])
        if not any('job ai helper' in p.get('title', '').lower() for p in projects):
            continue
        verification = conn.execute('select verification_fingerprint,result_json from application_tailoring_verifications where verification_id=?',
                                    (snapshot.get('source_verification_id'),)).fetchone()
        verified = json.loads(verification['result_json']) if verification else {}
        bullet_receipts = [{
            'location': 'claim_lineage.verified_project_bullets['+str(i)+']',
            'project_id': b.get('project_id'), 'bullet_index': b.get('bullet_index'),
            'source_bullet_sha256': diagnostic.sha(b.get('bullet', '')),
            'supported': b.get('supported'), 'support_method': b.get('support_method'),
        } for i, b in enumerate(verified.get('claim_lineage', {}).get('verified_project_bullets', []))
            if 'job ai helper' in b.get('project', '').lower()]
        output.append({'candidate_id': r['candidate_id'],
            'source_application_id': snapshot.get('source_application_id'),
            'source_generation_id': snapshot.get('source_generation_id'),
            'source_verification_id': snapshot.get('source_verification_id'),
            'source_verification_fingerprint': snapshot.get('source_verification_fingerprint'),
            'lineage': snapshot.get('claim_lineage'),
            'verification_record_found': verification is not None,
            'verification_fingerprint_matches': bool(verification and verification['verification_fingerprint'] == snapshot.get('source_verification_fingerprint')),
            'saved_helper_bullet_receipts': bullet_receipts,
            'snapshot_sha256': diagnostic.sha(r['snapshot_json']),
            'meaning': 'Saved downstream source/lineage availability, not independent implementation verification or selection for these JDs.'})
    return sorted(output, key=lambda r: r['candidate_id'])


def build_report(db_path=None):
    before = protected_hashes()
    packet = json.loads((ROOT/'reports/unresolved_gold_review_packet_v4.json').read_text(encoding='utf-8'))
    sealed = deepcopy(packet)
    seal = sealed.pop('packet_fingerprint')
    if fingerprint(sealed) != seal:
        raise ValueError('V4 packet seal mismatch')
    manifest = json.loads((ROOT/'tests/fixtures/unresolved_adjudication_benchmark_v1.json').read_text(encoding='utf-8'))
    frozen = json.loads((ROOT/'tests/fixtures/confirmed_taxonomy_coverage.json').read_text(encoding='utf-8'))
    current = {(r['job_id'], r['requirement_id']): r for r in frozen['snapshot']['audit']['requirements']}
    snapshots = list_latest_job_match_corpus_snapshots(db_path=db_path) if db_path and db_path.exists() else []
    by_job = {s['discovered_job_id']: s for s in snapshots}
    conn = sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro', uri=True) if snapshots else None
    if conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
    rows = []
    try:
        for number, job, rid, profile in diagnostic.CASES:
            case = next(c for c in packet['cases'] if c['key'] == [job, rid])
            expectation = next(e for e in manifest['expectations'] if e['key'] == [job, rid])
            if case['input_fingerprint'] != expectation['input_fingerprint'] or case['source_fingerprint'] != manifest['source_fingerprint']:
                raise ValueError('Frozen benchmark identity drift')
            if case['case_number'] != number:
                raise ValueError('Frozen case identity mismatch')
            row = {'case_number': number, 'job_id': job, 'requirement_id': rid,
                   'source_jd_sha256': case['source_jd_sha256'],
                   'semantic_layer1': diagnostic.semantics(case),
                   'frozen_current_observation': deepcopy(current[(job, rid)]),
                   'evidence_connections': [], 'native_probe': None,
                   'downstream_trace': {'status': 'LOCAL_SNAPSHOT_UNAVAILABLE'},
                   'diagnostic_dimensions': ['INSUFFICIENT_DATA'],
                   'finding': deepcopy(CASE_FINDINGS[number]),
                   'existing_capability_candidates_not_matches': deepcopy(case['capability_candidates']),
                   'benchmark_decision': 'UNCHANGED_PENDING_HUMAN_REVIEW'}
            job_fixture = next(j for j in frozen['snapshot']['audit']['corpus']['jobs'] if j['job_id'] == job)
            row['frozen_fixture_job_score'] = job_fixture['baseline_stable_analysis']['deterministic_alignment_score']
            row['frozen_fixture_identity'] = 'tests/fixtures/confirmed_taxonomy_coverage.json; not a new scoring replay'
            snap = by_job.get(job)
            if snap:
                if diagnostic.sha(snap['raw_jd_text']) != case['source_jd_sha256']:
                    raise ValueError('Exact saved JD source changed')
                req = next(r for r in snap['stable_analysis']['canonical_requirements'] if r['requirement_id'] == rid)
                if req['text'] != case['exact_frozen_requirement']:
                    raise ValueError('Frozen requirement wording drift')
                context = build_profile_evidence_context(snap['evidence_snapshot'])
                records = build_resume_evidence_index(context['resume_profile'], context['raw_resume_text'])
                connections = diagnostic.discover(profile, rid, records, parent_needed=number == 10)
                diagnostic.validate_connections(connections, records, rid)
                for c in connections:
                    c['source_snapshot_id'] = snap['id']
                    c['source_evidence_fingerprint'] = snap['evidence_fingerprint']
                    c['requested_activities'] = deepcopy(row['semantic_layer1']['explicit_activities'])
                    c['native_discovery'] = ('CITED_BY_SAVED_MATCH' if c['evidence_id'] in
                        {e['evidence_id'] for e in req.get('evidence', [])} else 'NOT_SELECTED_FOR_SAVED_REQUIREMENT_NOT_PROOF_OF_DISCOVERY_FAILURE')
                    evidence_text = next(r['text'] for r in records if r['evidence_id'] == c['evidence_id'] and r['source'] == c['source_location'])
                    native = evaluate_evidence(req, evidence_text)
                    c['native_capability_evaluation'] = {k: native.get(k) for k in ('capability_id', 'label', 'reason')}
                params = dict(requirements=[deepcopy(req)], acronym_map={}, resume_profile=context['resume_profile'], raw_resume_text=context['raw_resume_text'])
                resolution = resolve_requirement_with_production_knowledge(req)
                row.update(evidence_connections=connections,
                    source_snapshot={'id': snap['id'], 'scoring_version': snap['scoring_version'],
                        'analysis_sha256': fingerprint(snap['stable_analysis']),
                        'evidence_fingerprint': snap['evidence_fingerprint'],
                        'saved_job_score': snap['stable_analysis']['deterministic_alignment_score'],
                        'historical_not_current_score': True},
                    saved_match={k: req.get(k) for k in ('match_label', 'match_value', 'importance', 'score_eligible', 'evidence_strength', 'capability_taxonomy_cap_status')},
                    native_probe={'resolution': {k: resolution.get(k) for k in ('status', 'knowledge_status', 'resolution_source', 'technology_id')},
                        'stable_keyword_discovery': redact_keyword(build_deterministic_keyword_match(**deepcopy(params)), records),
                        'phase9e_keyword_discovery': redact_keyword(build_phase9e_keyword_match(**deepcopy(params)), records)},
                    downstream_trace=downstream(conn, case))
                parent_ids = set(row['semantic_layer1']['parent_occurrence_ids'])
                allocations = []
                for member in snap['stable_analysis']['canonical_requirements']:
                    for p in member.get('source_provenance', []):
                        if p.get('parent_occurrence_id') in parent_ids and p.get('contributes_scoring_allocation'):
                            allocations.append({'requirement_id': member['requirement_id'], 'parent_occurrence_id': p['parent_occurrence_id'],
                                                'fraction': p['source_group_fraction']})
                row['native_parent_allocations'] = allocations
                row['allocation_totals'] = {pid: sum(p['fraction'] for p in allocations if p['parent_occurrence_id'] == pid) for pid in sorted(parent_ids)}
                if any(abs(total-1.0)>1e-5 for total in row['allocation_totals'].values()):
                    raise ValueError('Native allocation conservation not established')
                row['diagnostic_dimensions'] = (['JD_SEMANTIC_LOSS', 'RELATIONSHIP_SCOPE_GAP', 'INSUFFICIENT_DATA'] if number == 10 else
                    ['TECHNOLOGY_IDENTITY_GAP', 'RELATIONSHIP_SCOPE_GAP', 'INSUFFICIENT_DATA'] if number == 15 else
                    ['NO_DEMONSTRATED_FAILURE', 'INSUFFICIENT_DATA'])
                row['diagnostic_dimension_status'] = {
                    tag: ('OBSERVED_MISSING_EXACT_DOWNSTREAM_DATA' if tag == 'INSUFFICIENT_DATA' else
                          'VERIFIED_SOURCE_HEADING_OMITTED_FROM_CHILD' if tag == 'JD_SEMANTIC_LOSS' else
                          'OBSERVED_NATIVE_ROS_IDENTITY_ABSENT' if tag == 'TECHNOLOGY_IDENTITY_GAP' else
                          'REVIEW_HYPOTHESIS_NOT_CONFIRMED_FAILURE' if tag == 'RELATIONSHIP_SCOPE_GAP' else
                          'NO_CONFIRMED_FAILURE_IN_AVAILABLE_TRACE') for tag in row['diagnostic_dimensions']}
            rows.append(row)
        report = {'schema_version': diagnostic.VERSION, 'production_identity': production_identity(),
            'cases': rows, 'job_ai_helper_saved_blueprint_sources': helper_sources(conn) if conn else [],
            'synthetic_controls': synthetic_controls(),
            'protected_artifact_hashes': before,
            'restrictions': {'production_changed': False, 'new_scoring_children': 0, 'model_calls': 0,
                'network_calls': 0, 'database_writes': 0, 'human_gold_changed': False, 'claim_authorizations': 0},
            'findings': {'confirmed_discovery_false_negatives': 0, 'phase9e_omissions_demonstrated': 0,
                'quality_metrics': 'NOT_ESTABLISHED_NO_INDEPENDENT_RELEVANCE_LABELS',
                'recommendation': 'Small source-scope annotations and bounded evidence explainability pilot; reuse existing transferable/project relevance and claim lineage. No production fix proven.'},
            'limitations': ['Saved scorer v1.10 observations are historical; frozen current coverage rows are separately identified.',
                'Pure matcher probes are current functions, not rescored jobs or observed project rankings.',
                'Manual library records describe implementation but are not independent implementation verification.',
                'No exact application linkage or selection history for these four requirements was established.',
                'Discovery profiles are limited exploratory surface hypotheses, not general semantic accuracy claims.',
                'Concurrent external database writers are not controlled; no whole-database immutability claim.']}
    finally:
        if conn:
            conn.close()
    if before != protected_hashes():
        raise ValueError('Protected artifacts changed during read-only investigation')
    report['protected_hashes_unchanged'] = True
    report['report_fingerprint'] = fingerprint(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Refusing to overwrite an existing investigation report')
    with offline_execution('semantic-evidence-investigation'):
        report = build_report(args.db)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'cases': len(report['cases']), 'fingerprint': report['report_fingerprint'], 'protected_hashes_unchanged': True}))


if __name__ == '__main__':
    main()
