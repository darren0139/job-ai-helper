"""Seed a local review database and real review artifacts using synthetic evidence."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

root = Path.cwd()
assert root.name == 'v37_normal_final_fixture'
sys.path.insert(0,'C:\\Users\\Admin\\Documents\\GitHub\\Job-AI-Helper')
sys.path.insert(1,'C:\\Users\\Admin\\Documents\\GitHub\\Job-AI-Helper\\reports\\v37_bestof_release_ui_workspace')
from sandbox import enable

enable()
from docx import Document
from pypdf import PdfReader
from database import db_manager, user_profile_manager
from database import phase9f_tailoring_execution_manager as manager
from database.analysis_cache_manager import persist_explicit_application_analysis
from database.tailoring_generation_control import get_tailoring_generation
from parse import read_resume_docx
from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd, seal_document_report
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _render_pdf
from tailoring.phase9f_tailoring_execution import PHASE9F_F_SECTION_SCOPE_POLICY_VERSION
from tests.phase9f_e_test_support import create_d_reuse_session
from unittest.mock import patch

database = root / 'data' / 'applications.db'
source_dir = root / 'ui-fixture-source'
if not database.exists():
    source_dir.mkdir()
    state = create_d_reuse_session(database, source_type='global_blueprint', artifact_root=source_dir,
                                   confirmed_intensity='minor')
    app_id = state['application_id']
    db_manager.rename_application_session(app_id, 'V3.7 UI Review Fixture')
with db_manager._connect() as connection:
    app_id = connection.execute(
        "SELECT id FROM applications WHERE session_name='V3.7 UI Review Fixture'"
    ).fetchone()[0]
source = source_dir / 'approved.docx'
report = db_manager.get_application_by_id(app_id)['report']
jd = report['raw_jd_text']
# Current confirmation APIs already freeze document-grounded source/initial analyses.
# Do not replace that analysis after confirmation.

project = deepcopy(report['resume_profile']['projects'][0])
opening = project['bullets'][0]
alternative = 'Designed secure backend APIs and relational database workflows.'
user_profile_manager.DB_PATH = database
user_profile_manager.init_user_profile_library()
user_profile_manager.create_evidence_item(
    category='Project', title=project['title'], description=opening + '\n' + alternative,
    skills=['Python', 'React', 'PostgreSQL'], tools=['PostgREST'],
)


def scope(**kwargs):
    rows = deepcopy(kwargs['evidence_snapshot']['rows'])
    return {
        'policy_version': PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
        'phase9a_version': 'phase9a-evidence-opportunity-v1',
        'confirmed_intensity': kwargs['confirmed_intensity'], 'opportunity_fingerprint': 'ui-fixture',
        'selected_evidence_ids': [row['id'] for row in rows], 'selected_evidence_fingerprint': 'ui-fixture-evidence',
        'projects_addressable': True, 'skills_addressable': True, 'enabled_sections': ['projects', 'skills'],
        'selected_evidence': rows, 'opportunity': {}, 'scope_fingerprint': 'ui-fixture-scope',
    }


def projects_writer(**kwargs):
    rows = []
    for requirement in kwargs['stable_analysis']['canonical_requirements']:
        rows.append({
            'requirement_id': requirement['requirement_id'],
            'requirement_text': requirement['text'], 'importance': requirement['importance'],
            'match_label': requirement['match_label'] if requirement['match_label'] != 'none' else 'weak',
            'coverage_points': float(requirement.get('weight') or 4),
        })
    excerpt = opening.split(',')[0]
    return {
        'recommended_projects': [{**project, 'project_id': 'ui-queryai', 'display_title': project['title'],
                                  'period': project['date'], 'source': 'both',
                                  'selected_blueprint_bullets': [opening], 'draft_bullets': [opening, excerpt]}],
        'candidate_project_ranking': [{'project_id': 'ui-queryai', 'title': project['title'],
                                        'source': 'both', 'selection_rank': 1, 'requirement_matches': rows}],
    }


def skills_writer(**kwargs):
    return {'skill_lines': [{'category': name, 'items': values}
                            for name, values in kwargs['resume_profile']['skills'].items() if values]}


with patch.object(manager, 'build_section_scope', scope):
    generated = manager.run_phase9f_normal_generation(
        application_id=app_id, projects_writer=projects_writer, skills_writer=skills_writer,
        generation_settings={'max_projects': 2, 'max_bullets': 3},
    )
    gen_id = generated['generation']['generation_id']
    out = root / 'outputs' / 'tailored_resumes'
    out.mkdir(parents=True)

    def fit_writer(**kwargs):
        fitted_projects = kwargs['tailored_projects']
        path = out / f'app_{app_id}_ui_fixture.docx'
        source_document = Document(source)
        document = Document()
        source_lines = [line.text for line in source_document.paragraphs]
        project_start = source_lines.index(project['title'])
        for line in source_lines[:project_start]:
            document.add_paragraph(line)
        document.add_paragraph('PROJECTS')
        document.add_paragraph(project['title'] + '\t' + str(project['date']))
        for bullet in fitted_projects['recommended_projects'][0]['draft_bullets']:
            document.add_paragraph(bullet, style='List Bullet')
        document.add_paragraph('SKILLS')
        for line in kwargs['tailored_skills']['skill_lines']:
            document.add_paragraph(', '.join(line['items']))
        document.save(path)
        pdf = _render_pdf(path, out)
        pages = len(PdfReader(pdf).pages)
        assert pages == 1
        return {
            'generation_id': gen_id, 'fit_one_page': True, 'page_count': pages, 'fit_status': 'verified_one_page',
            'docx_path': str(path), 'pdf_path': str(pdf), 'remaining_active_reductions': [],
            'fitting_input_snapshot': {'prepared_initial_state': {'projects': deepcopy(fitted_projects)}},
            'tailored_projects_used': deepcopy(fitted_projects),
            'tailored_skills_used': deepcopy(kwargs['tailored_skills']),
        }

    fitted = manager.run_phase9f_normal_fit(application_id=app_id, generation_id=gen_id, fit_writer=fit_writer)
    phase8 = manager.run_or_reuse_phase9f_normal_generation_phase8(application_id=app_id, generation_id=gen_id)

verification = phase8['verification']
assert get_tailoring_generation(app_id, gen_id)['status'] == 'draft'
fit = fitted['generation']['fit_result']
summary = {
    'application_id': app_id, 'generation_id': gen_id, 'status': 'draft',
    'docx': fit['docx_path'], 'pdf': fit['pdf_path'], 'pdf_pages': fit['page_count'],
    'docx_sha256': sha256(Path(fit['docx_path']).read_bytes()).hexdigest(),
    'pdf_sha256': sha256(Path(fit['pdf_path']).read_bytes()).hexdigest(),
    'selected_docx_sha256': sha256(source.read_bytes()).hexdigest(),
    'phase8_verdict': verification['verdict'], 'phase8_ready': verification['approval_ready'],
    'phase8_summary': verification['job_match_ab'].get('summary'),
}
(root / 'fixture.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
