"""Read-only admission of frozen Job Finder handoffs; no live library fallback."""
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3

from database import db_manager
from job_discovery import coordinated_preview as preview
from job_discovery import developer_comparison as synthetic
from job_discovery.coordinated_sources import fingerprint
from job_discovery.matching import current_match_versions, fingerprint_evidence_items
from tailoring.phase9f_application_confirmation import fingerprint_value

STATE = 'developer_real_comparison_v1'
INDEX = 'developer_real_applications_v1'
SCHEMA = 'developer-real-frozen-handoff-v1'
RETROSPECTIVE = 'RETROSPECTIVE_FROZEN_INPUTS_V1'
RETROSPECTIVE_LABEL = ('Retrospective diagnostic — original frozen inputs evaluated using current scoring implementations. '
                       'Does not reproduce or update the saved historical analysis.')


class Blocked(ValueError):
    """Only fixed, privacy-safe explanations may cross the UI error boundary."""


def _require(condition, message):
    if not condition:
        raise Blocked(message)


def _gate(consent):
    _require(synthetic.enabled() and consent is True, 'BLOCKED: developer comparison is OFF.')


@contextmanager
def _read(db_path=None):
    path = Path(db_path or db_manager.DB_PATH).resolve()
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA query_only=ON')
            conn.execute('BEGIN')
            yield conn
    except Blocked:
        raise
    except (sqlite3.Error, OSError, KeyError, TypeError, ValueError, IndexError, AttributeError) as from_error:
        raise Blocked('BLOCKED: saved source schema or receipt is unavailable/inconsistent.') from from_error


def list_applications(*, session_enabled=False, db_path=None):
    """Same application/session identity as the sidebar, without its RW connector.

    Never use tracking.list_application_tracking_rows: that read migrates and
    repairs tracking. No detailed receipts are fetched by this listing.
    """
    _gate(session_enabled)
    with _read(db_path) as conn:
        return [dict(r) for r in conn.execute(
            'SELECT id,session_name,job_title,company FROM applications ORDER BY id DESC')]


def load(application_id, *, session_enabled=False, db_path=None):
    """Admit only the exact saved library handoff, never a newer document.

    Currentness here means compatible frozen inputs, not equality with today's
    global library. That library is deliberately never read.
    """
    return _load(application_id, session_enabled=session_enabled, db_path=db_path)


def load_retrospective(application_id, *, session_enabled=False, db_path=None):
    """Separate admission: authenticate old inputs, then parse raw JD afresh."""
    return _load(application_id, session_enabled=session_enabled, db_path=db_path, retrospective=True)


def _load(application_id, *, session_enabled=False, db_path=None, retrospective=False):
    _gate(session_enabled)
    _require(type(application_id) is int and application_id > 0,
             'BLOCKED: select an existing application ID.')
    from database.job_match_manager import _decode_row
    from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint
    from tailoring.initial_analysis_explainer import build_analysis_receipt
    with _read(db_path) as conn:
        app = conn.execute('SELECT * FROM applications WHERE id=?', (application_id,)).fetchone()
        _require(app is not None, 'BLOCKED: application missing or deleted.')
        app = dict(app)
        binding = json.loads(app.get('entry_binding_json') or '{}')
        _require(binding.get('origin') == 'job_finder',
                 'INCOMPATIBLE: no frozen library handoff. Document/legacy authority is unsupported; no substitution.')
        _require(binding.get('binding_fingerprint') == fingerprint_value(
            {k: v for k, v in binding.items() if k != 'binding_fingerprint'}),
            'BLOCKED: saved handoff identity is inconsistent.')
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'phase9f_application_confirmations' in tables:
            _require(not conn.execute('SELECT 1 FROM phase9f_application_confirmations WHERE application_id=?',
                                     (application_id,)).fetchone(),
                     'INCOMPATIBLE: configured Application Session/document scope requires separate admission.')
        source = binding['snapshot']
        snapshot = _decode_row(conn.execute(
            'SELECT * FROM job_match_snapshots WHERE id=? AND discovered_job_id=?',
            (source['id'], binding['discovered_job_id'])).fetchone())
        _require(snapshot == source, 'STALE: exact saved Job Finder snapshot changed or unavailable.')
        job = conn.execute('SELECT * FROM discovered_jobs WHERE id=?', (binding['discovered_job_id'],)).fetchone()
        _require(job is not None, 'BLOCKED: original JD source unavailable.')
        job = dict(job)
        raw = binding['raw_jd_text']
        import hashlib
        _require(isinstance(raw, str) and bool(raw.strip()), 'BLOCKED: original JD text unavailable.')
        _require(raw == job['description'] and binding['job_content_hash'] == job['content_hash']
                 and source['job_content_hash'] == binding['job_content_hash']
                 and binding['raw_jd_sha256'] == hashlib.sha256(raw.strip().encode()).hexdigest(),
                 'STALE: exact JD generation differs; no newest-version fallback.')
        saved = conn.execute('SELECT * FROM application_analysis_versions WHERE application_id=? AND analysis_id=?',
                             (application_id, binding['initial_analysis_id'])).fetchall()
        _require(len(saved) == 1, 'BLOCKED: application-owned Initial Analysis unavailable or ambiguous.')
        saved = dict(saved[0])
        report = json.loads(saved['report_json'])
        _require(saved['input_fingerprint'] == binding['binding_fingerprint']
                 and report.get('meta', {}).get('initial_analysis_reference') == binding,
                 'BLOCKED: Initial Analysis belongs to a different source receipt.')
        _require(not app.get('initial_analysis_id') or app['initial_analysis_id'] == binding['initial_analysis_id'],
                 'INCOMPATIBLE: conflicting Initial Analysis references.')
        _require(not app.get('initial_resume_analysis_id'),
                 'INCOMPATIBLE: a separate résumé-document authority exists.')
        current_differs = bool(app.get('report_json') and json.loads(app['report_json']) != report)
        if not retrospective:
            _require(not current_differs,
                     'INCOMPATIBLE: current application report/local overrides differ from the frozen handoff.')
        versions = current_match_versions()
        stable = source['stable_analysis']
        if not retrospective:
            _require(all(source.get(k) == versions[k] for k in ('match_version','scoring_version','taxonomy_version')),
                     'STALE: saved match/scorer/taxonomy versions are incompatible.')
            _require(all(stable.get(k) == versions[v] for k, v in (
                ('scoring_version','scoring_version'), ('capability_taxonomy_version','taxonomy_version'),
                ('technology_registry_version','technology_registry_version'))),
                     'STALE: saved scorer/knowledge identities are incompatible.')
        else:
            # Known source schemas only. This is not a claim that their old
            # labels or scores reproduce under the current implementation.
            allowed = {('stable-evidence-v1.16-phase6d20', 'phase6d-capability-taxonomy-v1.5'),
                       (versions['scoring_version'], versions['taxonomy_version'])}
            _require((source.get('scoring_version'), source.get('taxonomy_version')) in allowed
                     and source.get('match_version') == versions['match_version']
                     and stable.get('scoring_version') == source.get('scoring_version')
                     and stable.get('capability_taxonomy_version') == source.get('taxonomy_version')
                     and stable.get('technology_registry_version') == versions['technology_registry_version'],
                     'INCOMPATIBLE: unverified historical input schema or inconsistent archived identities.')
            from analysis_stability.coordinated_runtime import assert_analysis_publishable
            assert_analysis_publishable(stable)
        items = source.get('evidence_snapshot')
        _require(isinstance(items, list) and bool(items),
                 'BLOCKED: frozen evidence snapshot unavailable; no current-library fallback.')
        _require(source.get('evidence_fingerprint') == fingerprint_evidence_items(items),
                 'BLOCKED: frozen evidence identity differs.')
        try:
            request = preview.prepare_comparison(raw_jd_text=raw, jd_profile=source['jd_profile'], evidence_items=items)
        except ValueError as exc:
            raise Blocked('BLOCKED: original evidence ownership/projection cannot be verified.') from exc
        context = request.projection['context']
        _require(all(report.get(k) == v for k, v in (
            ('raw_jd_text', raw), ('jd_profile', source['jd_profile']), ('stable_analysis', stable),
            ('resume_profile', context['resume_profile']), ('raw_resume_text', context['raw_resume_text']))),
                 'BLOCKED: saved report inputs differ from original handoff evidence/JD.')
        if retrospective:
            _require(binding['canonical_requirement_fingerprint'] ==
                     canonical_requirement_scope_fingerprint(stable['canonical_requirements']),
                     'BLOCKED: historical requirement allocation differs from its sealed scope.')
            # No archived extraction/capability IDs enter either fresh scorer.
            request = preview.prepare_comparison(raw_jd_text=raw, jd_profile={}, evidence_items=items)
        expected_rows = preview.native.canonicalise_requirements(
            jd_profile=request.jd_profile, raw_jd_text=raw)['requirements']
        scope = canonical_requirement_scope_fingerprint(expected_rows)
        _require(binding['canonical_requirement_fingerprint'] == scope,
                 'STALE: saved requirement scope differs from the current parser.' if not retrospective else
                 'INCOMPATIBLE: current raw-JD parsing changes historical identities/importance/parent allocation; retrospective comparison blocked.')
        fields = ('requirement_id', 'text', 'importance', 'atomic_group_id', 'group_weight_fraction')
        _require([[r.get(k) for k in fields] for r in stable['canonical_requirements']] ==
                 [[r.get(k) for k in fields] for r in expected_rows],
                 'INCOMPATIBLE: saved requirement allocation or local scope differs.')
        receipt = build_analysis_receipt(stable, raw_jd_text=raw, provenance='JOB_FINDER_INITIAL_MATCH',
            identity={'application_id': application_id, 'initial_analysis_id': binding['initial_analysis_id'],
                      'saved_snapshot_id': saved['id'], 'source_snapshot_id': source['id']})
        identity_payload = {'schema': SCHEMA, 'application': app, 'snapshot': source,
                            'saved': saved, 'source_job': job, 'request': request.identity}
        if retrospective:
            identity_payload['mode'] = RETROSPECTIVE
        identity = fingerprint(identity_payload)
        loaded = {'application_id': application_id, 'identity': identity, 'request': request, 'saved': receipt,
            'context': {'application_id': application_id, 'title': binding.get('title'), 'company': binding.get('company'),
                'jd_authority': 'FROZEN_JOB_FINDER_SOURCE', 'discovered_job_id': binding['discovered_job_id'],
                'jd_version_id': None, 'jd_content_hash': binding['job_content_hash'],
                'raw_jd_sha256': binding['raw_jd_sha256'], 'source_snapshot_id': source['id'],
                'evidence_fingerprint': source['evidence_fingerprint'], 'evidence_items': len(items),
                'authority': preview.LIBRARY_AUTHORITY, 'currentness': 'COMPATIBLE_FROZEN_INPUTS_NOT_CURRENT_LIBRARY',
                'local_overrides': 'NONE_ADMITTED', 'versions': versions}}
        if retrospective:
            loaded['mode'] = RETROSPECTIVE
            loaded['context'].update(mode=RETROSPECTIVE, current_application_report_differs=current_differs,
                local_overrides='CURRENT_APPLICATION_REPORT_NOT_USED',
                historical_versions={k: stable.get(k) for k in ('scoring_version','capability_taxonomy_version','technology_registry_version')},
                fresh_interpretation='CURRENT_RAW_JD_PARSER_AND_CURRENT_TAXONOMY',
                historical_geometry='EXACT_IDENTITIES_IMPORTANCE_AND_ALLOCATION_RECONCILED',
                historical_scope_fingerprint=scope)
        return loaded


def require_current(loaded, *, session_enabled=False, db_path=None):
    loader = load_retrospective if loaded.get('mode') == RETROSPECTIVE else load
    current = loader(loaded['application_id'], session_enabled=session_enabled, db_path=db_path)
    _require(current == loaded, 'STALE: source or implementation changed after loading; explicitly load again.')
    return current


def evaluate(loaded, *, session_enabled=False, db_path=None):
    current = require_current(loaded, session_enabled=session_enabled, db_path=db_path)
    comparison = preview.run_comparison(current['request'], developer_enabled=True)
    if current.get('mode') == RETROSPECTIVE:
        from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint as scope
        _require(comparison.identity == current['request'].identity
                 and comparison.published.scoring_version == preview.native.SCORING_VERSION
                 and comparison.gated.scoring_version == preview.PROJECTED_SCORER_VERSION
                 and comparison.authority == current['context']['authority']
                 and all(a.get('capability_taxonomy_version') == current['context']['versions']['taxonomy_version']
                         and a.get('technology_registry_version') == current['context']['versions']['technology_registry_version']
                         for a in (comparison.published_analysis, comparison.gated_analysis)),
                 'BLOCKED: fresh diagnostic implementation/input identity differs.')
        _require(scope(comparison.published_analysis['canonical_requirements']) ==
                 current['context']['historical_scope_fingerprint'],
                 'INCOMPATIBLE: fresh published requirements differ from the admitted parser geometry.')
    from analysis_stability import jd_metadata_policy as v22, jd_metadata_v123 as v23
    metadata = {m.SCORER_VERSION: m.classify(current['request'].raw_jd_text) for m in (v22, v23)}
    require_current(current, session_enabled=session_enabled, db_path=db_path)
    result = {'identity': current['identity'], 'comparison': comparison, 'metadata': metadata}
    if current.get('mode') == RETROSPECTIVE:
        from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint as scope
        result.update(mode=RETROSPECTIVE, geometry_comparable=(
            scope(comparison.published_analysis['canonical_requirements']) == scope(comparison.gated_analysis['canonical_requirements'])),
            comparison_semantics=RETROSPECTIVE_LABEL)
    return result


def selected_export(result, selected_ids):
    """No free-text fields, source strings, contact details or raw receipts."""
    comparison = result['comparison']
    from job_discovery.coordinated_preview_model import analysis_view
    _require(analysis_view(comparison.published_analysis) == comparison.published and
             analysis_view(comparison.gated_analysis) == comparison.gated, 'BLOCKED: comparison receipt changed.')
    rows = synthetic.requirement_rows(comparison)
    ids = {r['Requirement ID'] for r in rows}
    _require(bool(selected_ids) and set(selected_ids) <= ids, 'BLOCKED: select exact requirement identities.')
    fields = ('Requirement ID', 'Published', 'Experimental', 'Published allocation', 'Experimental allocation',
              'Published credit', 'Experimental credit')
    payload = {'schema': SCHEMA, 'development_preview_only': True, 'persistence_eligible': False,
        'input_fingerprint': result['identity'], 'source_text_included': False,
        'published_version': comparison.published.scoring_version, 'experimental_version': comparison.gated.scoring_version,
        'requirements': [{k: r[k] for k in fields} for r in rows if r['Requirement ID'] in selected_ids]}
    if result.get('mode') == RETROSPECTIVE:
        from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint as scope
        _require(result['geometry_comparable'] == (
            scope(comparison.published_analysis['canonical_requirements']) == scope(comparison.gated_analysis['canonical_requirements'])),
            'BLOCKED: comparative geometry receipt changed.')
        payload.update(mode=RETROSPECTIVE, comparison_semantics=RETROSPECTIVE_LABEL,
                       geometry_comparable=result['geometry_comparable'], historical_numeric_delta=None)
        if not result['geometry_comparable']:
            for row in payload['requirements']:
                row['Published credit'] = row['Experimental credit'] = None
            payload['comparative_credit_status'] = 'WITHHELD_INCOMPATIBLE_GEOMETRY'
    return json.dumps(payload, indent=2, allow_nan=False)
