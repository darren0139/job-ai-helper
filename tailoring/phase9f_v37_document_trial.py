"""Isolated actual-document scoring shared by V3.7 benchmark and comparisons."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from subprocess import TimeoutExpired
from tempfile import TemporaryDirectory

from tailoring.phase9f_automatic_bestof_v30 import native_document_score
from tailoring.phase9f_automatic_bestof_v30 import RANK
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _render_pdf, write_optimized_docx
from tailoring.phase9f_v364_document_reverify import build_frozen_selected_base_document_report
from tailoring.phase9f_v365_jd_evidence import PREFERRED, REQUIRED
from tailoring.phase9f_verified_best_of_v291 import build_candidate_scoring_state
from taxonomy_discovery.offline_execution import offline_execution
from pypdf.errors import PdfReadError


def _pdf_pages(path: Path, work: Path) -> int:
    from pypdf import PdfReader
    if path.resolve().parent != work.resolve() or not path.is_file() or path.suffix.lower() != '.pdf':
        raise ValueError('The page verifier must return a PDF from the isolated work folder.')
    return len(PdfReader(str(path)).pages)


def _pack(case: dict, score: dict, docx_sha: str, pages: int, layout: str) -> dict:
    expected = (case['baseline'].get('stable_analysis') or {}).get('canonical_requirements') or []
    reqs = score.get('canonical_requirements') or []
    frozen_jd = {row['requirement_id']: row['importance'] for row in expected}
    actual = {row['requirement_id']: row['importance'] for row in reqs}
    if not actual or frozen_jd != actual or len(actual) != len(reqs):
        raise ValueError('Native JD requirement IDs or importance differ from the frozen application analysis.')
    value = score.get('deterministic_alignment_score')
    if not isinstance(value, (float, int)) or isinstance(value, bool) or not 0 <= value <= 100:
        raise ValueError('The native scorer did not return a valid Job Match score.')
    return {
        'status': 'verified', 'pages': pages, 'score': value, 'docx_sha256': docx_sha,
        'jd_sha256': sha256(case['raw_jd_text'].encode('utf-8')).hexdigest(),
        'layout_reference_sha256': layout, 'scoring_version': score.get('scoring_version'),
        'requirements': [{'id': row['requirement_id'], 'text': row['text'], 'importance': row['importance'],
                          'match_label': row['match_label'], 'evidence_strength': row.get('evidence_strength'),
                          'evidence': [item['text'] for item in row.get('evidence') or []
                                       if isinstance(item, dict) and item.get('text')]}
                         for row in reqs if row['importance'] in REQUIRED | PREFERRED],
    }


def evaluate_document_trial(case: dict, proposal: dict | None = None, *, base_docx: Path | None = None,
                            work_root: Path | None = None, renderer=_render_pdf,
                            scorer=native_document_score) -> dict:
    """Verify actual bytes and page count in temporary storage. No application writes."""
    receipt = {'status': 'failed', 'score': None, 'pages': None, 'docx_sha256': None}
    try:
        with TemporaryDirectory(prefix='v37-document-trial-', dir=work_root) as folder, offline_execution(
            'V3.7 document trial is offline'
        ):
            work = Path(folder)
            docx = work / 'trial.docx'
            src = base_docx if base_docx is not None else case['source_docx']
            expected = case['base_artifact'].get('sha256') if base_docx is not None else case['audit']['docx_sha256']
            content = Path(src).read_bytes()
            if not expected or sha256(content).hexdigest() != expected:
                raise ValueError('Source DOCX bytes do not match the saved artifact digest.')
            if base_docx is not None and proposal is not None:
                raise ValueError('Original Base must be evaluated unchanged.')
            if proposal is None:
                docx.write_bytes(content)
            else:
                source_copy = work / 'source.docx'
                source_copy.write_bytes(content)
                write_optimized_docx(source_path=source_copy, audit_sha=expected,
                                     proposal=proposal, destination=docx)
            digest = sha256(docx.read_bytes()).hexdigest()
            receipt['docx_sha256'] = digest
            pdf = Path(renderer(docx, work))
            pages = _pdf_pages(pdf, work)
            receipt['pages'] = pages
            if pages != 1 and base_docx is None:
                return {**receipt, 'status': 'fit_failed', 'reason': f'The actual fitted variant has {pages} pages.'}
            if base_docx is not None:
                sealed, _ = build_frozen_selected_base_document_report(
                    baseline_report=case['baseline'], jd_text=case['raw_jd_text'],
                    source_artifact={**case['base_artifact'], 'artifact_bytes': content},
                )
                score = sealed['stable_analysis']
            else:
                state = deepcopy(case['generation'])
                if proposal is not None:
                    state = build_candidate_scoring_state(
                        original=state, proposal=proposal, output={
                            'status': 'generated', 'pages': pages, 'docx_path': docx, 'pdf_path': pdf,
                        },
                    )
                score = scorer(docx_path=docx, generation_state=state, baseline_report=case['baseline'],
                               raw_jd_text=case['raw_jd_text'], expected_sha256=digest)
                if score.get('docx_sha256') != digest or score.get('actual_docx_evidence') is not True:
                    raise ValueError('Native receipt does not verify these DOCX bytes.')
            return _pack(case, score, digest, pages, expected)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, TimeoutExpired, PdfReadError) as error:
        return {**receipt, 'reason': str(error)}


def compare_native_trials(baseline: dict, alternative: dict) -> dict:
    unavailable = {'comparison_status': 'unavailable', 'native_delta': None,
                   'hard_regressions': None, 'preferred_bonus_coverage_delta': None}
    identity = ('jd_sha256', 'scoring_version', 'layout_reference_sha256')
    if (baseline.get('status') != 'verified' or alternative.get('status') != 'verified'
            or not all(baseline.get(key) and baseline[key] == alternative.get(key) for key in identity)):
        return unavailable
    before = {row['id']: row for row in baseline['requirements']}
    after = {row['id']: row for row in alternative['requirements']}
    if before.keys() != after.keys() or any(before[rid]['importance'] != after[rid]['importance'] for rid in before):
        return unavailable
    hard_regressions = []
    bonus_gains, bonus_losses = [], []
    for rid, row in before.items():
        previous = RANK[row['match_label']]
        current = RANK[after[rid]['match_label']]
        detail = {'requirement': row['text'], 'before': row['match_label'], 'after': after[rid]['match_label']}
        if row['importance'] in REQUIRED and current < previous:
            hard_regressions.append(detail)
        elif row['importance'] in PREFERRED and current > previous:
            bonus_gains.append(detail)
        elif row['importance'] in PREFERRED and current < previous:
            bonus_losses.append(detail)
    native_delta = round(alternative['score'] - baseline['score'], 6)
    bonus_before = sum(row['importance'] in PREFERRED and row['match_label'] != 'none' for row in before.values())
    bonus_after = sum(row['importance'] in PREFERRED and row['match_label'] != 'none' for row in after.values())
    return {
        'comparison_status': 'verified', 'native_delta': native_delta, 'hard_regressions': hard_regressions,
        'preferred_bonus_coverage_delta': bonus_after - bonus_before,
        'preferred_bonus_strength_gains': bonus_gains, 'preferred_bonus_strength_losses': bonus_losses,
        'prefer_existing_on_tie': native_delta == 0,
    }
