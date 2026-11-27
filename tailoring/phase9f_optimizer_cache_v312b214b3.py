"""Exact-input reuse of completed ordinary Best-of trials, never approval.
The saved PDF is the verified artifact, not a prediction of a future render.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import math
import platform
import re
import subprocess
import sys
from importlib.metadata import version, PackageNotFoundError

VERSION = 'phase9f-v312b214b3-exact-trial-cache-v1'
MODES = ('v35-relevance', 'v37-same-work')
PREFIX = 'b214b3-cache:'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def file_digest(path):
    with Path(path).open('rb') as stream:
        return sha256(stream.read()).hexdigest()


def _runtime_identity(repo_root):
    """Conservative content identity of tracked runtime code/config, not Git HEAD.
    No private benchmark files, DBs, or generated documents are read here.
    """
    root = Path(repo_root).resolve()
    names = subprocess.run(['git', 'ls-files', '-z'], cwd=root, check=True,
        capture_output=True, timeout=10).stdout.decode('utf-8').split('\0')
    paths = [n for n in names if n and not n.startswith(('tests/', 'scripts/', 'data/bullet_choice_benchmark/'))
             and (n.endswith('.py') or n.startswith(('analysis_stability/', 'taxonomy_discovery/', 'tailoring/', 'job_discovery/'))
                  and n.endswith(('.json', '.yaml', '.yml')) or n.startswith('requirements') and n.endswith('.txt')
                  or n in ('pyproject.toml', 'uv.lock'))]
    # Include this new module even before it is staged during installer tests.
    paths.append('tailoring/phase9f_optimizer_cache_v312b214b3.py')
    if 'analysis_stability/stable_evidence_scoring.py' not in paths:
        raise ValueError('Native runtime source inventory unavailable')
    files = {name: file_digest(root / name) for name in sorted(set(paths))}
    from tailoring.phase9f_joint_resume_optimizer_v2_6 import _soffice
    renderer = Path(_soffice()).resolve()
    packages = {}
    for name in ('numpy', 'scipy', 'python-docx', 'pypdf', 'PyMuPDF', 'lxml', 'rapidfuzz'):
        try: packages[name] = version(name)
        except PackageNotFoundError: packages[name] = 'not-installed'
    return {'files': digest(files), 'python': sys.version, 'platform': platform.platform(),
            'packages': packages, 'renderer': str(renderer), 'renderer_sha256': file_digest(renderer)}


def active_identity(raw_jd):
    from tailoring.job_match_ab_analysis import current_ab_identity
    return current_ab_identity(raw_jd)


def display_scope(*, application_id, generation_id, audit, projects, fit, baseline_report,
                  raw_jd_text, identity):
    """Separate UI history from older unscoped display receipts."""
    try:
        return digest({'version': VERSION, 'app': int(application_id), 'generation': str(generation_id),
                       'audit': audit, 'projects': projects, 'fit': fit, 'baseline': baseline_report,
                       'jd': raw_jd_text, 'active': identity})
    except (TypeError, ValueError, OverflowError, RecursionError):
        return ''


def display_context(scope, mode, tie=False, manual=False):
    return digest({'scope': scope, 'mode': mode, 'tie': bool(tie), 'manual': bool(manual)})


def trial_scope(*, application_id, generation, audit, projects, fit, baseline_report,
                raw_jd_text, source_docx, repo_root, mode, tie=False,
                identity=None, runtime=None):
    """Strict JSON identity: invalid/missing scope never becomes a cache hit."""
    try:
        identity = active_identity(raw_jd_text) if identity is None else identity
        scorer = identity['scoring_version']
        if (mode not in MODES or not isinstance(scorer, str) or not scorer
            or (baseline_report.get('stable_analysis') or {}).get('scoring_version') != scorer
            or baseline_report.get('raw_jd_text') != raw_jd_text
            or not raw_jd_text.strip() or audit.get('verified') is not True
            or fit.get('fit_one_page') is not True or fit.get('page_count') != 1
            or str(generation.get('generation_id') or '') != str(audit.get('generation_id') or '')
            or not audit.get('generation_id')
            or (generation.get('fit_result') or {}).get('docx_path') != fit.get('docx_path')):
            return None, 'Missing or stale exact trial scope'
        path = Path(source_docx).resolve()
        path.relative_to((Path(repo_root)/'outputs'/'tailored_resumes').resolve())
        if (path != (Path(repo_root)/str(fit.get('docx_path') or '')).resolve()
                or path.suffix.lower() != '.docx' or not path.name.casefold().startswith(f'app_{int(application_id)}_')
                or file_digest(path) != audit['docx_sha256']):
            return None, 'Incumbent artifact identity changed'
        if runtime is None:
            runtime = _runtime_identity(repo_root)
        if not runtime:
            return None, 'Runtime identity unavailable'
        rows = (baseline_report.get('stable_analysis') or {}).get('canonical_requirements')
        ids = [r['requirement_id'] for r in rows]
        if not ids or any(not isinstance(r,str) or not r for r in ids) or len(set(ids)) != len(ids):
            return None, 'Invalid canonical JD scope'
        scope = {'version':VERSION,'application_id':int(application_id), 'generation_id':str(audit['generation_id']),
                 'mode':mode,'tie':bool(tie),'scorer_version':scorer,'docx_sha256':audit['docx_sha256'],
                 'jd_sha256':sha256(raw_jd_text.encode('utf-8')).hexdigest(), 'requirement_ids':sorted(ids),
                 'input_sha256':digest({'generation':generation,'audit':audit,'projects':projects,'fit':fit,
                     'baseline':baseline_report,'active_identity':identity,'runtime':runtime})}
        scope['key'] = digest(scope)
        return scope, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError, ImportError, subprocess.SubprocessError):
        return None, 'Exact trial identity could not be established'


def valid_result(result, scope, repo_root):
    """Only complete ordinary verified trials; recheck both artifact bindings."""
    try:
        if (not isinstance(result,dict) or result.get('status') != 'verified'
            or result.get('candidate_approved') is not False
            or result.get('winner') not in ('existing_final','optimized_candidate')
            or result.get('scoring_version') != scope['scorer_version']
            or result.get('generation_id') != scope['generation_id']
            or result.get('a_docx_sha256') != scope['docx_sha256']
            or result.get('guarded_review') or result.get('reviewed_core_floor')
            or (result.get('proposal') or {}).get('requires_base_review')):
            return False
        starting = result.get('a_vs_starting') or {}
        if (starting.get('status') != 'verified' or starting.get('scoring_version') != scope['scorer_version']
            or starting.get('a_docx_sha256') != scope['docx_sha256'] or starting.get('a_score') != result.get('a_score')
            or starting.get('selected_base_comparison_status') not in ('maintained','improved','regressed')):
            return False
        if result['winner'] == 'optimized_candidate' and (result.get('base_floor_verdict') != 'passed_by_transitivity'
            or starting.get('selected_base_comparison_status') not in ('maintained','improved')
            or starting.get('selected_base_required_core_losses') or result.get('hard_regressed_ids')):
            return False
        for name in ('a_score','b_score','delta'):
            if type(result.get(name)) not in (int,float) or not math.isfinite(result[name]): return False
        if not (0 <= result['a_score'] <= 100 and 0 <= result['b_score'] <= 100
                and round(result['b_score']-result['a_score'],6) == result['delta']): return False
        trials = result.get('v35_trial_receipts')
        if result.get('v35_bounded_search') and (not isinstance(trials,list) or not trials
            or result.get('v35_tested_candidates') != len(trials) or result.get('v35_verified_candidates') != len(trials)
            or any(t.get('status')!='verified' or t.get('a_score')!=result['a_score'] for t in trials)):
            return False
        for label, field in (('existing','a_docx_sha256'),('alternative','b_docx_sha256')):
            row = result['native_document_evidence'][label]
            ids = [r['requirement_id'] for r in row['requirements']]
            if (row['docx_sha256'] != result[field] or type(row['pages']) is not int or row['pages'] != 1
                or sorted(ids) != scope['requirement_ids'] or any(
                    r.get('match_label') not in ('none','weak','transferable','direct')
                    or type(r.get('evidence_strength')) is not int or not 0<=r['evidence_strength']<=5
                    for r in row['requirements'])):
                return False
        root = (Path(repo_root)/'outputs'/'tailored_resumes'/'optimizations').resolve()
        paths = []
        for field, hash_field, suffix in (('candidate_file','b_docx_sha256','.docx'),('candidate_pdf','candidate_pdf_sha256','.pdf')):
            p = Path(result[field]).resolve(); p.relative_to(root); paths.append(p)
            if p.suffix.lower() != suffix or not p.name.casefold().startswith(f'app_{scope["application_id"]}_') or file_digest(p) != result[hash_field]:
                return False
        if paths[0].stem != paths[1].stem or result['b_docx_sha256']==scope['docx_sha256']:
            return False
        return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return False


def run_cached_trial(*, execute, application_id, generation, audit, projects, fit, baseline_report,
                     raw_jd_text, source_docx, repo_root, mode, tie=False, force=False,
                     identity=None, runtime=None):
    """One explicit user action. Cache errors fall back to the original full trial."""
    scope, reason = trial_scope(application_id=application_id,generation=generation,audit=audit,
        projects=projects,fit=fit,baseline_report=baseline_report,raw_jd_text=raw_jd_text,
        source_docx=source_docx,repo_root=repo_root,mode=mode,tie=tie,identity=identity,runtime=runtime)
    from database.phase9f_bestof_review_state import (load_bestof_display_receipt, save_bestof_display_receipt, discard_bestof_execution_cache)
    lookup = None
    if scope:
        lookup = dict(application_id=scope['application_id'],generation_id=scope['generation_id'],
                      context=PREFIX+scope['key'],docx_sha256=scope['docx_sha256'],
                      raw_jd_text=raw_jd_text,scorer_version=scope['scorer_version'])
        if not force:
            try:
                saved = load_bestof_display_receipt(**lookup)
                candidate = (saved or {}).get('result') or {}
                if ((saved or {}).get('run_mode') == mode and candidate.get('_exact_trial_scope') == scope
                    and valid_result(candidate,scope,repo_root)):
                    out=deepcopy(candidate)
                    out['_optimizer_cache']={'status':'hit','key':scope['key'],'mode':mode,'comparison_executed':False}
                    return out
                reason='No complete matching verified receipt, or artifact check failed'
            except Exception:
                reason='Cache read unavailable'
        else:
            reason='Explicit fresh comparison requested'
            try:
                discard_bestof_execution_cache(application_id=scope['application_id'],generation_id=scope['generation_id'],context=lookup['context'])
            except Exception:
                reason+='; previous cache could not be invalidated'
    result = execute()
    out = dict(result)
    out['_optimizer_cache']={'status':'fresh','key':scope['key'] if scope else '', 'mode':mode,
                            'comparison_executed':True,'reason':reason,'persisted':False}
    # Do not label partially verified or reviewed results reusable, even if the UI can display them.
    if scope and valid_result(out,scope,repo_root):
        try:
            # Check exact input and artifacts again after the expensive operation.
            end_scope,_=trial_scope(application_id=application_id,generation=generation,audit=audit,
                projects=projects,fit=fit,baseline_report=baseline_report,raw_jd_text=raw_jd_text,
                source_docx=source_docx,repo_root=repo_root,mode=mode,tie=tie,identity=identity,runtime=runtime)
            if end_scope==scope:
                out['_exact_trial_scope']=deepcopy(scope)
                stored=deepcopy(out); stored.pop('_optimizer_cache',None); stored['_exact_trial_scope']=scope
                digest(stored)  # Reject cycles and non-JSON rather than caching a detached approximation.
                out['_optimizer_cache']['persisted']=bool(save_bestof_display_receipt(**lookup,run_mode=mode,
                    mode_receipt={'generation_id':scope['generation_id'],'mode':mode,'cache_only':True},result=stored))
        except Exception:
            pass
    return out
