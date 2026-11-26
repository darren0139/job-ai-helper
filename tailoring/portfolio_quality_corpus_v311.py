"""Read-only saved-generation corpus regression for portfolio and prefit deduplication.

No restored generation, DOCX, native score, approval, or private text is modified.
Each historical generation uses its own saved JD-linked project evidence.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from tailoring.portfolio_quality_v311 import optimize_portfolio_projects


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def _original_docx_project_depth(path: Path) -> list[int]:
    """Inspect project bullet depth only; do not export names or résumé content."""
    ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with ZipFile(path,'r') as archive:
        root=ET.fromstring(archive.read('word/document.xml'))
    counts=[]
    in_projects=False
    last=''
    body=root.find(ns+'body')
    for paragraph in (list(body) if body is not None else []):
        if paragraph.tag != ns+'p':
            continue
        pr=paragraph.find(ns+'pPr')
        ps=pr.find(ns+'pStyle') if pr is not None else None
        style=ps.get(ns+'val','') if ps is not None else ''
        text=''.join(t.text or '' for t in paragraph.iter(ns+'t')).strip()
        if style=='ResumeSection':
            in_projects=(text.upper()=='PROJECTS')
            last='section'
        elif in_projects and style=='ResumeEntry':
            if not counts or last=='bullet':
                counts.append(0)
            last='entry'
        elif in_projects and style=='ResumeBullet':
            if counts:
                counts[-1]+=1
            last='bullet'
        elif in_projects and style=='ResumeSubentry':
            last='subentry'
    return counts


def audit_saved_corpus(db_path: str | Path, *, resume_docx: str | Path | None = None,
                       run_dedupe: bool = True) -> dict[str, Any]:
    db_path = Path(db_path).expanduser().resolve(strict=True)
    if db_path.suffix.lower() not in ('.db', '.sqlite', '.sqlite3'):
        raise ValueError('A SQLite .db/.sqlite file is required')
    original_hash = _hash(db_path)
    docx = None
    if resume_docx is not None:
        p = Path(resume_docx).expanduser().resolve(strict=True)
        with ZipFile(p, 'r') as archive:
            if 'word/document.xml' not in archive.namelist():
                raise ValueError('Resume is not a readable DOCX')
        docx = dict(filename=p.name, sha256=_hash(p), validated_docx_zip=True,
                    original_project_bullet_depth=_original_docx_project_depth(p))
    con = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
    con.execute('PRAGMA query_only=ON')
    try:
        integrity = con.execute('PRAGMA quick_check').fetchone()[0]
        if integrity != 'ok':
            raise ValueError('SQLite quick_check failed')
        generations = con.execute('''
            SELECT v.application_id,v.generation_id,v.projects_json,
                   COALESCE(m.status,'unknown')
            FROM application_tailoring_versions AS v
            LEFT JOIN application_tailoring_generation_meta AS m
              ON m.application_id=v.application_id AND m.generation_id=v.generation_id
            WHERE v.projects_json IS NOT NULL ORDER BY v.application_id,v.generation_id
        ''').fetchall()
        applications = con.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
    finally:
        con.close()
    if len(generations) > 1000:
        raise ValueError('Corpus exceeds bounded 1000-generation limit')
    results = []
    for appid, genid, source, status in generations:
        try:
            pool = json.loads(source)
            original = pool.get('adaptive_fit_original_projects') or pool.get('recommended_projects') or []
            final = optimize_portfolio_projects(pool)
            receipt = final['portfolio_quality_selection']
            chosen = final.get('recommended_projects') or []
            record = {
                'generation_hash': hashlib.sha256(str(genid).encode()).hexdigest()[:12],
                'application_id': appid, 'historical_status':status,
                'original_projects':len(original), 'selected_projects':len(chosen),
                'candidates':receipt['candidate_count'],
                'coverage_floor_holds': receipt['winner']['hard_required_core_lost']==0,
                'one_bullet_selected':receipt['one_bullet_selected'],
                'unknown_linkage_projects':receipt['jd_linked_evidence_unknown_projects'],
                'proxy_utility': receipt['winner']['proxy_utility'],
                'status':'selection_preview_only',
            }
            if run_dedupe:
                try:
                    from tailoring.phase9f_prefit_dedupe_v39 import dedupe_prepared_projects
                    from tailoring.phase9f_lead_intro_v310 import apply_lead_first_prepared
                    pre = dedupe_prepared_projects(final)
                    pre = apply_lead_first_prepared(pre)
                    dr = pre.get('_v39_auto_dedupe') or {}
                    lr = pre.get('_v310_lead_intro') or {}
                    record['prefit_dedupe_v39_removals'] = len(dr.get('removals') or [])
                    record['lead_v310_intro_removals'] = len(lr.get('removals') or [])
                    record['prefit_test_status'] = 'simulated_only_not_actual_docx'
                    # Assert all selected input bullets are still sourced from their own project.
                    for prepared, orig in zip(pre.get('recommended_projects') or [], chosen):
                        prepared_text = set(prepared.get('draft_bullets') or [])
                        if not prepared_text.issubset(set(orig.get('draft_bullets') or [])):
                            raise ValueError('Prefit deduplication created an unsupported bullet')
                except ImportError:
                    record['prefit_test_status'] = 'skipped_v39_or_v310_module_unavailable'
            results.append(record)
        except (ValueError, TypeError, KeyError) as exc:
            results.append({
                'generation_hash':hashlib.sha256(str(genid).encode()).hexdigest()[:12],
                'application_id':appid, 'historical_status':status,
                'status':'HELD', 'reason':str(exc)[:150]})
    if _hash(db_path) != original_hash:
        raise ValueError('Database bytes changed during read-only regression')
    ok = sum(row['status']=='selection_preview_only' for row in results)
    report = {
        'version':'portfolio-quality-keith-corpus-v311',
        'purpose':'read_only_proxy_plus_prefit_rehearsal_not_native_approval',
        'database_sha256':original_hash,'sqlite_integrity':integrity,
        'applications':applications,'generations_checked':len(generations),
        'selection_previews':ok,'held':len(results)-ok,
        'historical_approvals_not_modified':True,
        'report_contains_no_resume_bullet_text':True,
        'resume_docx':docx,'generations':results,
        'not_evaluated':('individual native Job Match candidate scores',
                         'one-page DOCX per candidate',
                         'actual final-docx readback'),
    }
    return report
