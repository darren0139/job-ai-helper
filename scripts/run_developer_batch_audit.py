"""Offline synthetic developer audit CLI; contained child, no providers or DBs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def peak_memory_bytes():
    if os.name != 'nt':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak_working_set', 'working_set', 'peak_paged', 'paged',
                'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
    values = Counters(); values.cb = ctypes.sizeof(values)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    call = ctypes.windll.psapi.GetProcessMemoryInfo
    call.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    if not call(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(values), values.cb): return None
    return values.peak_working_set


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--developer-enabled', action='store_true', help='Required explicit synthetic-only opt-in')
    parser.add_argument('--preset', choices=('quick','extended','complete'), default='quick')
    parser.add_argument('--cases', nargs='+', help='Optional distinct registry IDs instead of preset')
    parser.add_argument('--include-synthetic-text', action='store_true')
    parser.add_argument('--scratch-root', type=Path, default=ROOT/'reports/coordinated_batch_cli')
    parser.add_argument('--contained', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.developer_enabled: parser.error('Explicit --developer-enabled is required')
    if not args.contained:
        target = args.scratch_root.resolve()
        if not target.is_relative_to(ROOT/'reports'): parser.error('Use a scratch root inside this checkout reports/')
        target = target/('batch-audit-'+uuid.uuid4().hex)
        target.mkdir(parents=True)
        guard = target/'guard'; guard.mkdir()
        (guard/'sitecustomize.py').write_text('from scripts.offline_release_guard import install\ninstall()\n', encoding='utf-8')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='true',
            CAPABILITY_RAG_MODE='off', LITELLM_LOCAL_MODEL_COST_MAP='True',
            STREAMLIT_BROWSER_GATHER_USAGE_STATS='false', TEMP=str(target), TMP=str(target),
            PYTHONPATH=os.pathsep.join((str(guard),str(ROOT))), JOB_MATCH_TEST_SCRATCH=str(target),
            JOB_MATCH_TEST_ROOT=str(ROOT), JOB_MATCH_TEST_GUARD_DIR=str(guard),
            JOB_AI_DEVELOPER_COMPARISON='1')
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '--contained', '--developer-enabled',
                   '--preset', args.preset, '--scratch-root', str(target)]
        if args.cases: command += ['--cases', *args.cases]
        if args.include_synthetic_text: command.append('--include-synthetic-text')
        print('Contained output: '+str(target), flush=True)
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
    if not os.environ.get('JOB_MATCH_TEST_GUARD_DIR') or args.scratch_root.resolve() != Path(os.environ['JOB_MATCH_TEST_SCRATCH']).resolve():
        parser.error('Contained execution requires the offline launcher environment')
    from job_discovery import developer_batch_audit as audit
    ids = args.cases or (audit.QUICK if args.preset == 'quick' else audit.EXTENDED if args.preset == 'extended'
                         else [c['id'] for c in audit.registry()])
    state = audit.new_batch(list(ids)); started = time.perf_counter()
    try:
        audit.run_chunk(state, session_enabled=True, limit=audit.MAX_CASES,
            progress=lambda key,status,done,total: print(f'{key}: {status} ({done}/{total} attempted)',flush=True))
    except KeyboardInterrupt:
        print('Stopped between completed receipts; active case was not recorded as successful.', flush=True)
    files = audit.export_bundle(state, include_text=args.include_synthetic_text)
    for extension, data in files.items():
        (args.scratch_root/('synthetic_batch_audit.'+extension)).write_bytes(data)
    measurements = {'elapsed_seconds': round(time.perf_counter()-started, 3),
        'peak_process_working_set_bytes': peak_memory_bytes(), 'retained_receipt_bytes': state['retained_bytes'],
        'exports': {key: len(data) for key,data in files.items()},
        'completed': sum(e['status']=='COMPLETED' for e in state['entries'].values()),
        'errors': sum(e['status']=='ERROR' for e in state['entries'].values()),
        'pending': len(state['requested'])-len(state['entries']),
        'cases': {key: {'status': value['status'], 'elapsed_seconds': value['elapsed_seconds'],
                        'receipt_bytes': value.get('receipt_bytes')} for key,value in state['entries'].items()}}
    (args.scratch_root/'measurements.json').write_text(json.dumps(measurements, indent=2, sort_keys=True),encoding='utf-8')
    print(json.dumps(measurements, sort_keys=True), flush=True)
    return 0 if measurements['completed'] == len(state['requested']) else 2


if __name__ == '__main__':
    raise SystemExit(main())
