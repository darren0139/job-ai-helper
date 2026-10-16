"""V1.2 investigation-only native previews; no production policy or data writes.

Output contains explicitly supplied fixture-label hypotheses, not a general
knowledge matcher or independent gold labels. All patches are context-local
experiments and are restored before protected hashes are verified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from analysis_stability import stable_evidence_scoring as scoring
from tests.api_knowledge_review_support import matrix, job81_alternatives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protected-baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.protected_baseline.read_text(encoding='utf-8'))
    scenarios, job = matrix(), job81_alternatives()
    for alternative in job['alternatives']:
        native = alternative['native']
        alternative['required_weighted_coverage_components'] = scoring._weighted_coverage(
            native['canonical_requirements'], {'deal_breaker', 'required', 'core'})
    after = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in before}
    assert before == after, 'An existing V1.1/protected artifact changed'
    output = {
        'status': 'INVESTIGATION_AND_DRY_RUN_ONLY', 'python': sys.version,
        'production_scoring_version_unchanged': scoring.SCORING_VERSION,
        'production_policy_modified': False, 'hypotheses_are_verified_gold': False,
        'hypothesis_method': 'Fixture-specific label receipts injected after the actual evaluator; real protocol guards, source selection and scoring retained. The optional weak-recovery exception is an in-memory AST copy of the existing selector with one bounded experimental guard, not a production change.',
        'queryai_provenance': {
            'user_clarification': 'Supabase API CRUD, authentication, Realtime and REST-backed data access; candidate did not implement the separate Python/Flask /message endpoint.',
            'react_source_code_available_in_supplied_request': False,
            'linked_to_job81_saved_row': None,
            'limitation': 'No React source file or source-project title mapping is present in the supplied request/Job81 frozen projection. Do not attach hypothetical concept-practice wording to the candidate.'},
        'matrix': scenarios, 'job81': job,
        'protected_sha256_before': before, 'protected_sha256_after': after,
        'all_existing_v1_1_and_protected_files_unchanged': before == after,
        'live_database_access': False, 'live_snapshot_hashes_verified': False,
        'historical_protection': 'No live records accessed. Historical fixture hashes and focused disposable round-trip tests only.',
        'full_or_quick_project_suite_run': False,
    }
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'scenarios': len(scenarios), 'job81_counterfactuals': len(job['alternatives']),
                      'protected_files_unchanged': len(before), 'output': str(args.output)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
