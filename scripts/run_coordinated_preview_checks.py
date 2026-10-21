"""Portable focused Stage 2-2C offline checks; never runs the full/quick runners.

Requires Python 3.13 and the normal repository dependencies. Runtime scratch is
left for inspection. No root preview exports, private launcher or .env is read.
"""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from urllib.parse import unquote,urlparse

FOCUSED_MODULES = (
    'tests.test_coordinated_batch_dashboard',
    'tests.test_coordinated_action_implementation',
    'tests.test_partial_action_credit_preview',
    'tests.test_coordinated_ownership_preview',
    'tests.test_coordinated_evidence_preview',
    'tests.test_coordinated_action_preview',
    'tests.test_source_inventory_export_safety',
    'tests.test_source_aware_inventory',
    'tests.test_bulk_unresolved_v1',
    'tests.test_api_evidence_completeness',
    'tests.test_capability_none_recovery',
    'tests.test_jd_atomic_requirement_decomposition',
    'tests.test_jd_structure_fingerprint_compat',
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-root',type=Path,default=Path(tempfile.gettempdir()))
    parser.add_argument('--stage2d-preview',type=Path,help='Optional new local reports/ JSON; only written after tests pass')
    parser.add_argument('--stage2e-preview',type=Path,help='Optional new local reports/ acceptance JSON')
    parser.add_argument('--batch-dashboard-preview',type=Path,help='Optional local dashboard verification export')
    parser.add_argument('--protected-baseline',type=Path,help='Optional Stage 2D protection ledger; never a test input')
    parser.add_argument('tests',nargs='*',default=list(FOCUSED_MODULES))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    scratch=(args.scratch_root/('coordinated-checks-'+uuid.uuid4().hex)).resolve()
    scratch.mkdir(parents=True,exist_ok=False)
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(root))
    os.environ.update(CAPABILITY_RAG_MODE='off',LITELLM_LOCAL_MODEL_COST_MAP='True',
        PYTHON_DOTENV_DISABLED='true',
        STREAMLIT_BROWSER_GATHER_USAGE_STATS='false',TEMP=str(scratch),TMP=str(scratch),
        TAXONOMY_DISCOVERY_REVIEW_DB=str(scratch/'review.sqlite3'),
        TECHNOLOGY_REGISTRY_PROPOSAL_DB=str(scratch/'proposals.sqlite3'),
        TAVILY_USAGE_DB=str(scratch/'usage.sqlite3'))
    # Let the test exercise its standard-library fallback rather than a private
    # launcher's environment contract. All tempfile output remains in this sandbox.
    os.environ.pop('EVIDENCE_TEST_SCRATCH',None)
    tempfile.tempdir=str(scratch)
    def guard(event,values):
        if event=='open' and isinstance(values[0],(str,os.PathLike)):
            name=Path(values[0]).name.casefold()
            if name=='.env' or name in ('bulk_unresolved_stage2_preview.json',
                'bulk_unresolved_stage2b_preview.json','bulk_unresolved_stage2c_preview.json'):
                raise RuntimeError('Focused checks prohibit local secrets/diagnostic exports')
        if event in ('socket.connect','socket.getaddrinfo'):
            from scripts.offline_loopback import loopback_socket_allowed
            if loopback_socket_allowed(event, values):
                return
            from scripts.offline_socketpair import stdlib_socketpair_allowed
            if stdlib_socketpair_allowed(event, values):
                return
            raise RuntimeError('Focused coordinated checks prohibit all network access')
        if event=='sqlite3.connect':
            name=str(values[0])
            if name==':memory:':return
            if name.startswith('file:'):
                name=unquote(urlparse(name).path)
                if len(name)>2 and name[0]=='/' and name[2]==':':name=name[1:]
            if not Path(name.split('?')[0]).resolve().is_relative_to(scratch):
                raise RuntimeError('Focused coordinated checks prohibit non-disposable SQLite access')
    sys.addaudithook(guard)
    print(f'Offline source root: {root}\nDisposable scratch: {scratch}',flush=True)
    suite=unittest.defaultTestLoader.loadTestsFromNames(args.tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    # An external interpreter is fine; project imports must resolve to this checkout.
    prefixes=('analysis_stability','tailoring','taxonomy_discovery','job_discovery','database','scripts','tests')
    leaks=[name for name,module in list(sys.modules.items()) if name.split('.')[0] in prefixes
           and getattr(module,'__file__',None)
           and not Path(module.__file__).resolve().is_relative_to(root)]
    if leaks:raise RuntimeError('Project modules imported outside checkout: '+str(leaks))
    if result.wasSuccessful() and args.stage2d_preview:
        from scripts.preview_partial_action_credit_v1 import write_preview
        preview=write_preview(args.stage2d_preview,args.protected_baseline)
        print('Stage 2D preview written: '+str(args.stage2d_preview),flush=True)
        print('Stage 2D action confusion: '+str(preview['action_confusion']['2d']),flush=True)
    if result.wasSuccessful() and args.stage2e_preview:
        import json
        from scripts.coordinated_acceptance import all_results
        target=args.stage2e_preview.resolve()
        if target.exists() or not target.is_relative_to(root/'reports'):
            raise ValueError('Use a new local reports/ acceptance path')
        target.write_text(json.dumps(all_results(),sort_keys=True,ensure_ascii=False,indent=2,
                                     allow_nan=False)+'\n',encoding='utf-8')
        print('Stage 2E acceptance written: '+str(target),flush=True)
    if result.wasSuccessful() and args.batch_dashboard_preview:
        import json
        from scripts import coordinated_batch_dashboard as dashboard
        target=args.batch_dashboard_preview.resolve()
        if target.exists() or not target.is_relative_to(root/'reports'):
            raise ValueError('Use a new local reports/ dashboard verification path')
        batch=dashboard.run_batch(dashboard.revision_key())
        target.write_text(json.dumps(batch,sort_keys=True,ensure_ascii=False,indent=2,
                                     allow_nan=False)+'\n',encoding='utf-8')
        print('Dashboard verification written: '+str(target),flush=True)
        print('Dashboard counts: '+str(dashboard.totals(batch)),flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
