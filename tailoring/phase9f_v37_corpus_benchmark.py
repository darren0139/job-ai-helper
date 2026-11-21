"""Read-only, bounded selection benchmark using saved Phase 9F inputs."""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

from tailoring.phase9f_certified_selection_v36 import MAX_COUNT_DELTA, MAX_TOTAL_EDITS, _candidate, _matrix_program, _solve
from tailoring.phase9f_final_evidence_comparison_v2_4 import build_final_evidence_audit
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _get_rank, _key, _rank_weights, _source_pool, _support
from tailoring.phase9f_v365_jd_evidence import (
    PREFERRED, REQUIRED, explain_bullet, requirement_catalog, requirement_fragment,
)
from taxonomy_discovery.offline_execution import offline_execution

VERSION = 'phase9f-v37-corpus-benchmark-v1'
MAX_PILOT_CASES = 5
SOURCE_RULES = {
    'base_only': {'Selected Base'},
    'library_only': {'Evidence Library'},
    'mixed': {'Selected Base', 'Evidence Library'},
}


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _jd_identity(value: str) -> str:
    return value.replace('\r\n', '\n').strip()


def readonly_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


def load_frozen_packet(path: Path) -> tuple[list[dict], str]:
    if path.suffix.lower() == '.zip':
        with ZipFile(path) as archive:
            packet = archive.read('full_raw_42_jds.json')
    else:
        packet = path.read_bytes()
    rows = json.loads(packet)
    counts = Counter(row['cohort'] for row in rows)
    identities = {(row['cohort'], row['job_id']) for row in rows}
    if counts != {'FROZEN': 30, 'RETRO': 12} or len(identities) != len(rows):
        raise ValueError('Expected the saved unique 30-job frozen and 12-job retrospective cohorts.')
    if any(_digest(row['jd'].encode('utf-8')) != row['raw_jd_sha256'] for row in rows):
        raise ValueError('A JD in the frozen packet does not match its recorded hash.')
    return rows, _digest(packet)


def inventory(packet: list[dict], db: sqlite3.Connection) -> list[dict]:
    """Inspect availability only. No scorer or solver is invoked for cohort inventory."""
    application_jds: dict[str, set[int]] = {}
    for app, raw in db.execute('SELECT application_id, raw_text FROM job_descriptions WHERE application_id IS NOT NULL'):
        if raw:
            application_jds.setdefault(_jd_identity(raw), set()).add(app)
    results = []
    for case in packet:
        job_id, cohort, jd = case['job_id'], case['cohort'], case['jd']
        applications = sorted(application_jds.get(_jd_identity(jd), []))
        saved = None
        if cohort == 'FROZEN':
            # Retrospective IDs are packet indices, not discovered_job IDs.
            job = db.execute('SELECT content_hash, description FROM discovered_jobs WHERE id=?', (job_id,)).fetchone()
            if job and _jd_identity(job['description'] or '') == _jd_identity(jd):
                saved = db.execute(
                    'SELECT id, stable_analysis_json, evidence_snapshot_json FROM job_match_snapshots '
                    'WHERE discovered_job_id=? AND job_content_hash=? ORDER BY id DESC LIMIT 1',
                    (job_id, job['content_hash']),
                ).fetchone()
        snapshot = json.loads(saved['stable_analysis_json']) if saved else {}
        evidence = json.loads(saved['evidence_snapshot_json']) if saved else []
        fitting = []
        for app in applications:
            for row in db.execute(
                "SELECT id, docx_path FROM application_tailoring_versions WHERE application_id=? "
                "AND json_extract(fit_result_json, '$.fit_status')='verified_one_page' ORDER BY id DESC", (app,),
            ):
                if row['docx_path'] and Path(row['docx_path']).is_file():
                    fitting.append(row['id'])
                    break
        results.append({
            'cohort': cohort, 'job_id': job_id, 'raw_jd_sha256': case['raw_jd_sha256'],
            'snapshot_id': saved['id'] if saved else None,
            'saved_requirement_count': len(snapshot.get('canonical_requirements') or []),
            'frozen_library_rows': len(evidence) if isinstance(evidence, list) else 0,
            'exact_jd_application_ids': applications, 'verified_fitted_generation_rows': fitting,
            'selection_preflight': 'possible' if fitting else 'no exact fitted application input',
        })
    return results


def known_fragment_diagnostics(packet: list[dict], availability: list[dict], db: sqlite3.Connection) -> list[dict]:
    """Record historical fragments with the original parent and sibling allocations."""
    locators = {item['job_id']: item['snapshot_id'] for item in availability
                if item['cohort'] == 'FROZEN' and item['job_id'] in {566, 632}}
    result = []
    for item in packet:
        job = item['job_id']
        if item['cohort'] != 'FROZEN' or job not in locators:
            continue
        snapshot_id = locators[job]
        if snapshot_id is None:
            result.append({'job_id': job, 'status': 'snapshot_unavailable'})
            continue
        snapshot = db.execute('SELECT stable_analysis_json FROM job_match_snapshots WHERE id=?',
                              (snapshot_id,)).fetchone()
        stable = json.loads(snapshot['stable_analysis_json'])
        catalog = requirement_catalog({'stable_analysis': stable, 'raw_jd_text': item['jd']}, {})
        fragments = {rid: requirement_fragment(req, item['jd']) for rid, req in catalog.items()}
        notes = []
        for rid, req in catalog.items():
            flag = fragments[rid]
            availability_sentence = job == 632 and req['text'].casefold().startswith('available for 24/7 standby')
            if flag['grammar_status'] == 'clipped_boundary' or availability_sentence:
                siblings = [entry for entry in catalog.values() if req['parent_occurrence_id']
                            and entry['parent_occurrence_id'] == req['parent_occurrence_id']]
                notes.append({
                    'text': req['text'], 'importance': req['importance'],
                    'advisory_issue': ('availability_condition_review' if availability_sentence
                                       else 'clipped_coordination'),
                    'saved_fraction': req['group_weight_fraction'],
                    'saved_score_eligible': req['score_eligible'], 'saved_evidence_eligible': req['evidence_eligible'],
                    'siblings': [{'text': sibling['text'], 'saved_fraction': sibling['group_weight_fraction']}
                                 for sibling in siblings],
                    **flag,
                })
        result.append({'job_id': job, 'snapshot_id': snapshot_id, 'raw_jd_sha256': item['raw_jd_sha256'],
                       'scoring_version': stable.get('scoring_version'), 'observations': notes})
    return result


def load_case(db: sqlite3.Connection, generation_row: int, repo_root: Path) -> dict:
    row = db.execute(
        'SELECT v.*, a.report_json, a.company, a.job_title FROM application_tailoring_versions v '
        'JOIN applications a ON a.id=v.application_id WHERE v.id=?', (generation_row,),
    ).fetchone()
    if row is None:
        raise ValueError('Saved generation row unavailable.')
    fit = json.loads(row['fit_result_json'] or '{}')
    projects = json.loads(row['projects_json'] or '{}')
    pool = json.loads(row['candidate_pool_json'] or '[]')
    baseline = json.loads(row['report_json'] or '{}')
    jd = baseline.get('raw_jd_text')
    if not jd or not (baseline.get('stable_analysis') or {}).get('canonical_requirements'):
        raise ValueError('Exact saved JD and canonical requirements unavailable.')
    audit = build_final_evidence_audit(projects, fit, pool, repo_root=repo_root,
                                       application_id=row['application_id'],
                                       expected_generation_id=row['generation_id'])
    if not audit['verified']:
        raise ValueError(audit['notice'])
    source = db.execute(
        'SELECT source_type, source_artifact_json FROM phase9f_tailoring_executions '
        'WHERE application_id=? AND generation_id=?', (row['application_id'], row['generation_id']),
    ).fetchone()
    base = json.loads(source['source_artifact_json']) if source and source['source_type'] == 'base_resume' else {}
    return {
        'application_id': row['application_id'], 'generation_row': generation_row,
        'generation_id': row['generation_id'], 'company': row['company'], 'title': row['job_title'],
        'audit': audit, 'projects': projects, 'baseline': baseline, 'raw_jd_text': jd, 'base_artifact': base,
        'source_docx': (repo_root / row['docx_path']).resolve(),
        'generation': {'generation_id': row['generation_id'], 'fit_result': fit, 'projects': projects,
                       'skills': json.loads(row['skills_json'] or '{}')},
    }


def build_case_model(audit: dict, projects: dict, *, evaluator=None) -> tuple[dict, dict]:
    """Use existing evidence evaluation and MILP without invoking the production runner."""
    if not audit.get('verified') or not audit.get('projects'):
        raise ValueError('Verified exact fitted project source audit required.')
    if evaluator is None:
        from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
        evaluator = build_bullet_evidence_priorities
    groups = []
    for section in audit['projects']:
        title = section['project']
        wordings = {}
        for field in ('base', 'library', 'final'):
            for item in section.get(field) or []:
                text = item['text'].strip()
                wordings.setdefault(_key(text), set()).add(text)
        if any(len(values) > 1 for values in wordings.values()):
            raise ValueError(f'{title} contains distinct wordings that the installed solver treats as one identity.')
        rank = _get_rank(projects, title)
        if rank is None:
            raise ValueError(f'{title} has no unambiguous saved project ranking.')
        weights, error = _rank_weights(rank)
        if error:
            raise ValueError(f'{title}: {error}')
        pool, error = _source_pool(section)
        if error:
            raise ValueError(f'{title}: {error}')
        supports, error = _support(pool, rank, evaluator)
        if supports is None:
            raise ValueError(f'{title}: {error}')
        members = {_key(row['text']) for row in section.get('final') or []}
        groups.append({'project': title, 'candidates': [
            {'text': row['text'], 'source_labels': row['sources'], 'word_count': row['words'],
             'saved_jd_ids': sorted(ids & weights.keys()), 'in_original_a': _key(row['text']) in members}
            for row, ids in zip(pool, supports)
        ]})
    source = {'source_comparison': {'projects': groups}}
    return _matrix_program(audit, source, projects), source


def slate_metrics(model: dict, indices: tuple[int, ...], catalog: dict, raw_jd: str) -> dict:
    fragments = {rid: requirement_fragment(req, raw_jd) for rid, req in catalog.items()}
    support = Counter()
    links, terms, tech, activities = set(), set(), set(), set()
    questionable = []
    for i in indices:
        bullet = model['bullets'][i]
        explained = explain_bullet(
            {'bullet': bullet['text'], 'saved_jd_ids': sorted(bullet['ids'])}, catalog,
            raw_jd_text=raw_jd, fragments=fragments,
        )
        links.update(bullet['ids'])
        for link in explained['jd_links']:
            rid = link['id']
            if (fragments[rid]['eligible_for_bonus_explanation'] and link['keyword_overlap']
                    and catalog[rid].get('evidence_eligible') is not False and catalog[rid].get('score_eligible') is not False):
                support[rid] += 1
                terms.update(link['keyword_overlap'])
                tech.update(link['technology_overlap'])
                activities.update(link['activity_overlap'])
            else:
                questionable.append({'project': bullet['project'], 'requirement': link['text'],
                                     'source_status': fragments[rid]['source_status'],
                                     'grammar_status': fragments[rid]['grammar_status']})
        for _ in explained['unresolved_jd_ids']:
            questionable.append({'project': bullet['project'], 'requirement': None,
                                 'source_status': 'no_canonical_requirement'})
    def coverage(scope):
        return [{'text': catalog[rid]['text'], 'importance': catalog[rid]['importance'],
                 'parent': catalog[rid]['parent'], 'source_parent_id': catalog[rid]['parent_occurrence_id'],
                 'saved_parent_fraction': catalog[rid]['group_weight_fraction'],
                 'support': 'unique' if count == 1 else 'shared'}
                for rid, count in sorted(support.items()) if catalog[rid]['importance'] in scope]

    return {
        'selection_proxy_saved_points': round(sum(model['weights'][rid] for rid in links), 4),
        'required_core_lexical_links': coverage(REQUIRED), 'preferred_bonus_lexical_links': coverage(PREFERRED),
        'questionable_links': questionable, 'corroborating_terms': sorted(terms),
        'technologies': sorted(tech), 'activity_cues': sorted(activities),
        'project_bullets': len(indices), 'project_bullet_words': sum(model['bullets'][i]['words'] for i in indices),
    }


def source_constraint_preflight(model: dict, permitted: set[int]) -> dict:
    """A necessary edit-count bound for a source-pure slate."""
    groups = model['groups']
    originals = model['baseline_indices']
    retained = originals & permitted
    min_total = max(len(groups), model['baseline_count'] - MAX_COUNT_DELTA)
    min_project_adds = sum(not retained.intersection(owned) for _, _, owned, _ in groups)
    missing_projects = [group['project'] for group, _, owned, _ in groups if not permitted.intersection(owned)]
    required_removals = len(originals - permitted)
    min_adds = max(min_project_adds, min_total - len(retained))
    return {
        'minimum_membership_edits': required_removals + min_adds,
        'mandatory_original_removals': required_removals,
        'minimum_new_memberships': min_adds,
        'maximum_membership_edits': MAX_TOTAL_EDITS,
        'minimum_total_bullets': min_total,
        'projects_without_source_wording': missing_projects,
    }


def selection_trials(case: dict, *, time_limit: float = 1.0, evaluator=None) -> tuple[dict, dict]:
    if not 0 < time_limit <= 3:
        raise ValueError('Select a solver limit of up to three seconds per priority.')
    model, source = build_case_model(case['audit'], case['projects'], evaluator=evaluator)
    jd = case['raw_jd_text']
    catalog = requirement_catalog(case['baseline'], case['projects'])
    strategies = {}
    proposals = {}
    for name, tags in SOURCE_RULES.items():
        permitted = {i for i, row in enumerate(model['bullets']) if tags.intersection(row['source_labels'])}
        bound = source_constraint_preflight(model, permitted)
        if bound['projects_without_source_wording']:
            strategies[name] = {'status': 'ineligible', 'reason': 'A retained project lacks an eligible bullet from this source.',
                                'source_preflight': bound}
            continue
        if bound['minimum_membership_edits'] > bound['maximum_membership_edits']:
            strategies[name] = {'status': 'infeasible', 'reason': 'The required membership edits exceed the existing edit cap.',
                                'source_preflight': bound}
            continue
        forced = {i: 0 for i in range(len(model['bullets'])) if i not in permitted}
        try:
            solution = _solve(model, [], time_limit=time_limit, forced=forced)
        except (RuntimeError, ValueError, OverflowError) as error:
            strategies[name] = {'status': 'failed', 'reason': str(error), 'source_preflight': bound}
            continue
        if solution['status'] != 'optimal_proxy':
            status = 'infeasible' if solution.get('solver_status') == 2 else 'unverified'
            strategies[name] = {'status': status, 'reason': solution.get('reason'), 'source_preflight': bound}
            continue
        indices = solution['selected_indices']
        proposal = _candidate(model, source, solution, 1)
        proposals[name] = proposal
        strategies[name] = {'status': 'optimal_proxy',
                            'source_preflight': bound,
                            'same_membership_as_existing': set(indices) == model['baseline_indices'],
                            'metrics': slate_metrics(model, indices, catalog, jd),
                            'proxy_objectives': solution['phase_receipts'],
                            'slate': proposal['projects']}
    return strategies, proposals


def run_pilot(db_path: Path, repo_root: Path, generation_rows: list[int], packet_path: Path,
              *, time_limit: float = 1.0, evaluate=None) -> dict:
    if not 1 <= len(generation_rows) <= MAX_PILOT_CASES or len(set(generation_rows)) != len(generation_rows):
        raise ValueError('Specify 1–5 distinct generation rows for a bounded pilot.')
    packet, digest = load_frozen_packet(packet_path)
    result = {'schema': VERSION, 'packet_sha256': digest, 'packet_path': str(packet_path),
              'development': [], 'held_out': [], 'outcomes': {}}
    seen = set()
    with closing(readonly_db(db_path)) as db, offline_execution('V3.7 corpus benchmark is offline'):
        result['cohort_inventory'] = inventory(packet, db)
        result['historical_fragment_diagnostics'] = known_fragment_diagnostics(packet, result['cohort_inventory'], db)
        for row in generation_rows:
            try:
                case = load_case(db, row, repo_root)
                jd = _jd_identity(case['raw_jd_text'])
                if jd in seen:
                    raise ValueError('The pilot already contains this exact JD.')
                seen.add(jd)
                variants, proposals = selection_trials(case, time_limit=time_limit)
                variants['original_base'] = {'status': 'unavailable',
                    'reason': 'Requires separately hash-pinned original Base DOCX and a same-version native analysis.',
                    'document_sha256': case['base_artifact'].get('sha256')}
                for entry in variants.values():
                    entry['native'] = {'status': 'unavailable', 'score': None, 'pages': None}
                if evaluate is not None:
                    evaluate(case, variants, proposals)
                result['development'].append({
                    **{key: case[key] for key in ('application_id', 'generation_row', 'generation_id', 'company', 'title')},
                    'jd_sha256': _digest(jd.encode('utf-8')),
                    'cohort_matches': [{'cohort': item['cohort'], 'job_id': item['job_id']}
                                       for item in packet if _jd_identity(item['jd']) == jd],
                    'scoring_version_frozen': case['baseline']['stable_analysis'].get('scoring_version'),
                    'layout_reference_sha256': case['audit']['docx_sha256'],
                    'strategies': variants, 'native_outcome': native_outcome(variants),
                })
            except (OSError, ValueError, TypeError, KeyError) as error:
                result['development'].append({'generation_row': row, 'status': 'unavailable',
                                              'reason': str(error), 'native_outcome': 'unavailable'})
    counts = Counter(case['native_outcome'] for case in result['development'])
    result['outcomes'] = {label: counts[label] for label in (*SOURCE_RULES, 'original_base', 'tie', 'failure', 'unavailable')}
    return result


def native_outcome(variants: dict) -> str:
    """Only like-for-like one-page verified native source selection can win."""
    native = {name: variants[name].get('native') or {} for name in SOURCE_RULES}
    if any(value.get('status') in {'failed', 'fit_failed'} for value in native.values()):
        return 'failure'
    identities = {(value.get('scoring_version'), value.get('jd_sha256'), value.get('layout_reference_sha256'))
                  for value in native.values()}
    if (len(identities) != 1 or any(not field for field in next(iter(identities)))
            or any(value.get('status') != 'verified' or value.get('pages') != 1
                   or not isinstance(value.get('score'), (float, int))
                   for value in native.values())):
        return 'unavailable'
    eligible = {name: value for name, value in native.items() if value.get('hard_regressions') == []}
    if not eligible:
        return 'failure'
    best = max(value['score'] for value in eligible.values())
    winners = [name for name, value in eligible.items() if value['score'] == best]
    return winners[0] if len(winners) == 1 else 'tie'
