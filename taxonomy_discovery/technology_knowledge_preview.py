"""Offline review adapter only; never used by production resolution or scoring.

Identity recognition describes knowledge, not candidate evidence or capability.
Native decomposition owns list structure and source allocation.
"""
from collections import Counter
from copy import deepcopy

from taxonomy_discovery import corpus_gap_resolution as gaps, maintenance_service as maintenance
from taxonomy_discovery.technology_registry import (
    TechnologyRegistry, get_default_registry, resolve_requirement_text, normalise,
)
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.technology_identity_remediation import _records, _receipt
from taxonomy_discovery.regression_corpus import replay_current_corpus, duplicate_credit_violations
from taxonomy_discovery.technology_registry import temporary_registry_scope
from taxonomy_discovery.offline_execution import offline_execution

from tailoring.requirement_scope import (
    technology_identity_scope as classify, TECHNOLOGY_IDENTITY_CONCEPTS as CONCEPTS,
    PURE_TECHNOLOGY_SCOPES as PURE,
)


def validated_identity_registry(saved_pairs=()):
    """Reuse sealed historical identity receipts, recheck current native collisions.

    Historical validation is not current approval. This registry may only be
    consumed by the isolated knowledge preview and an explicit offline replay.
    No relationship or inferred identity is admitted.
    """
    production = get_default_registry()
    proposals = []
    for proposal, receipt in saved_pairs:
        maintenance._intact(proposal, 'proposal_fingerprint')
        maintenance._intact(receipt, 'validation_fingerprint')
        if (receipt.get('proposal_fingerprint') != proposal['proposal_fingerprint']
                or receipt.get('validation_status') != 'ready_for_human_review'
                or receipt.get('unexpected_changes')
                or proposal.get('resolution_type') != 'add_technology_identity'
                or proposal.get('current_registry_fingerprint') != fingerprint(production.entries)
                or set(proposal['proposed_change']) != {'technology_id', 'identity'}
                or set(proposal['proposed_change']['identity']) != {'canonical_name', 'technology_kind', 'aliases'}):
            raise ValueError('Unvalidated, stale registry, or non-identity proposal')
        proposals.append(deepcopy(proposal))
    _, registry = gaps._temporary_knowledge(proposals)
    return TechnologyRegistry(production.version, registry.entries)


def preview(audit, *, registry=None):
    """Annotate copied audit rows using its existing denominator and weights."""
    registry = registry or get_default_registry()
    records = _records(audit['corpus'])
    keys = [(r['job_id'], r['requirement_id']) for r in audit['requirements']]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate requirement keys; knowledge union must be unique')
    meaningful_keys = {(r['job_id'], r['requirement_id']) for r in audit['requirements']
                       if r['score_eligible']}
    noise = {(r['job_id'], r['requirement_id']) for q in audit['queue']
             if q['operational_route'] == 'noise_or_non_capability' and not q.get('parent_candidate_id')
             for r in q['candidate']['provenance']}
    meaningful_keys -= noise
    rows = []
    for source in audit['requirements']:
        key = source['job_id'], source['requirement_id']
        if key not in meaningful_keys:
            continue
        raw = records[key]
        decision = classify(raw, registry=registry)
        before = source['current_resolution']
        status = 'CAPABILITY_RESOLVED' if before.get('capability_id') else ('TECHNOLOGY_IDENTITY_RESOLVED' if decision['identity_resolved'] else 'UNRESOLVED')
        rows.append({**deepcopy(source), 'canonical_text': raw['text'], 'atomic_focus': raw.get('atomic_focus'),
                     'source_provenance': deepcopy(raw.get('source_provenance')), 'decision': decision,
                     'weight': gaps._weight(source),
                     'knowledge_status': status, 'capability_id': before.get('capability_id'),
                     'newly_resolved': before['status'] != 'resolved' and status == 'TECHNOLOGY_IDENTITY_RESOLVED'})
    if len(rows) != audit['summary']['meaningful_technical_requirements']:
        raise ValueError('Native meaningful denominator mismatch; fail closed')
    projected = deepcopy(rows)
    for row in projected:
        row['current_resolution']['status'] = 'resolved' if row['knowledge_status'] != 'UNRESOLVED' else 'unresolved'
    return {'rows': rows, 'counts': dict(Counter(r['knowledge_status'] for r in rows)),
            'category_counts': dict(Counter(r['decision']['category'] for r in rows)),
            'newly_resolved': [r for r in rows if r['newly_resolved']],
            'required_core_coverage': gaps._coverage(projected, {'required', 'core', 'deal_breaker'}),
            'overall_coverage': gaps._coverage(projected, {'required', 'core', 'deal_breaker', 'preferred'}),
            'production_writes': 0, 'scoring_influence': False}


def validate_bulk(audit, *, saved_pairs=(), explicit_execution=False):
    """Full frozen replay plus isolated knowledge accounting, no live inputs."""
    if explicit_execution is not True:
        raise ValueError('Explicit offline bulk validation required')
    with offline_execution('Technology knowledge validation forbids live research'):
        registry = validated_identity_registry(saved_pairs)
        before = audit['corpus']
        with temporary_registry_scope(registry):
            after = replay_current_corpus(before)
        if after['current_replay']['jobs_blocked']:
            raise ValueError('Incomplete frozen replay')
        b, a = _records(before), _records(after)
        deltas = []
        for key in sorted(b.keys() | a.keys()):
            rb, ra = _receipt(b.get(key)), _receipt(a.get(key))
            # Registry diagnostics are the only permitted native replay change.
            for r in (rb, ra):
                if r is not None:
                    r.pop('technology_registry_resolution', None)
            if rb != ra:
                deltas.append({'job_id': key[0], 'requirement_id': key[1], 'before': rb, 'after': ra})
        rankings = gaps._integrated_ranking(before), gaps._integrated_ranking(after)
        violations = [{'job_id': j['job_id'], 'reason': v} for j in after['jobs']
                      for v in duplicate_credit_violations(j['baseline_stable_analysis'], j['frozen_inputs']['context'])]
        result = preview(audit, registry=registry)
        baseline = preview(audit)
        aliases = [(t, (t,)) for t in CONCEPTS] + [(e['label'], tuple(e['aliases'])) for e in get_default_registry().entries]
        affected = [r for r in result['rows'] if any(gaps._technology_concept_present(r['canonical_text'], terms) for _, terms in aliases)]
        scores = {j['job_id']: j['metrics']['deterministic_alignment_score'] for j in after['jobs']}
        for r in result['rows']:
            r['job_score'] = scores[r['job_id']]
        result.update({'baseline': audit['summary'], 'production_identity_preview_counts': baseline['counts'],
                       'affected_rows': affected, 'affected_category_counts': dict(Counter(r['decision']['category'] for r in affected)),
                       'identity_concepts': [{'concept': t, 'production': resolve_requirement_text(t),
                            'temporary': resolve_requirement_text(t, registry=registry),
                            'state': 'PRODUCTION_RECOGNIZED' if resolve_requirement_text(t).get('technology_id') else 'TEMPORARY_IDENTITY_PROPOSAL_REQUIRED'} for t in CONCEPTS],
                       'evidence_or_capability_deltas': deltas, 'ranking_changes': [] if rankings[0] == rankings[1] else rankings,
                       'frozen_or_duplicate_violations': violations, 'after_ranking': rankings[1],
                       'jobs_replayed': len(after['jobs']), 'provider_calls': 0, 'model_calls': 0, 'network_calls': 0,
                       'approval': False, 'publication': False})
        if deltas or rankings[0] != rankings[1] or violations:
            result['verdict'] = 'NO_SAFE_TECHNOLOGY_KNOWLEDGE_RESOLUTION_PROVEN'
        else:
            result['verdict'] = 'PARTIAL_TECHNOLOGY_RESOLUTION_READY' if result['newly_resolved'] else 'NO_SAFE_TECHNOLOGY_KNOWLEDGE_RESOLUTION_PROVEN'
        return result, after
