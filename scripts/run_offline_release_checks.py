"""Run unchanged project/focused checks with explicit disposable containment.

No private launcher, database, acceptance export or .env dependency. Keep the
scratch directory for review; this command never cleans the working tree.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-root', type=Path, required=True)
    parser.add_argument('--full-project', action='store_true')
    parser.add_argument('tests', nargs='*')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    scratch = (args.scratch_root/('offline-release-'+uuid.uuid4().hex)).resolve()
    if not scratch.is_relative_to(root/'reports'):
        raise ValueError('Use a new disposable directory under this checkout reports/')
    scratch.mkdir(parents=True)
    guard = scratch/'guard'
    guard.mkdir()
    (guard/'sitecustomize.py').write_text('from scripts.offline_release_guard import install\ninstall()\n', encoding='utf-8')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='true',
        PYTHONPYCACHEPREFIX=str(scratch/'bytecode'), CAPABILITY_RAG_MODE='off',
        LITELLM_LOCAL_MODEL_COST_MAP='True', STREAMLIT_BROWSER_GATHER_USAGE_STATS='false',
        TEMP=str(scratch), TMP=str(scratch), PYTHONPATH=os.pathsep.join((str(guard), str(root))),
        JOB_MATCH_TEST_SCRATCH=str(scratch), JOB_MATCH_TEST_ROOT=str(root), JOB_MATCH_TEST_GUARD_DIR=str(guard),
        TAXONOMY_DISCOVERY_REVIEW_DB=str(scratch/'review.sqlite3'),
        TECHNOLOGY_REGISTRY_PROPOSAL_DB=str(scratch/'proposals.sqlite3'), TAVILY_USAGE_DB=str(scratch/'usage.sqlite3'),
        PHASE9F_BLUEPRINT_ARTIFACT_ROOT=str(scratch/'blueprint_artifacts'))
    if args.full_project:
        if args.tests:
            parser.error('Full project checks do not take a focused test list')
        command = [sys.executable, '-B', str(root/'scripts/run_project_checks.py'), '--mode', 'full']
    else:
        if not args.tests:
            parser.error('Specify focused test modules or --full-project')
        command = [sys.executable, '-B', str(root/'scripts/run_coordinated_preview_checks.py'),
                   '--scratch-root', str(scratch), *args.tests]
    print('Offline disposable root: '+str(scratch), flush=True)
    return subprocess.call(command, cwd=root, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
