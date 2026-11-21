"""Task-owned report/ZIP assembly; no application or Git mutations."""
from pathlib import Path
import hashlib, json, subprocess, zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8')
def write_json(path,value): path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

commit=json.loads((OUT/'checkpoint_commit.json').read_text(encoding='utf-8'))
pre=json.loads((OUT/'preflight.json').read_text(encoding='utf-8'))
after=json.loads((OUT/'benchmark_after.json').read_text(encoding='utf-8'))
integrity=json.loads((OUT/'review_integrity.json').read_text(encoding='utf-8'))
selected={f['path'] for f in commit['files']}
def entries(text): return {s.split('\t',1)[1]:s.split('\t',1)[0] for s in text.splitlines()}
before_index=entries((OUT/'index_entries_before.txt').read_text(encoding='utf-8'))
now_index=entries(git('ls-files','--stage'))
unrelated=[p for p,v in before_index.items() if p not in selected and now_index.get(p)!=v]
changed=[p for p,v in pre['files'].items() if not (ROOT/p).exists() or digest(ROOT/p)!=v]
allowed={'tailoring/bullet_choice_estimated.py','tailoring/bullet_choice_lab.py','tailoring/bullet_choice_lab_ui.py','tailoring/phase9f_wording_explanation_ui.py','tests/test_bullet_choice_lab.py'}
unexpected=[p for p in changed if p.replace('\\','/') not in allowed]
db=ROOT/'data/applications.db'
preservation={'head':git('rev-parse','HEAD').strip(),'branch':git('branch','--show-current').strip(),
 'index_sha256':digest(ROOT/'.git/index'),'index_changed_intentionally_for_checkpoint':True,
 'unrelated_index_entries_changed':unrelated,'preflight_existing_files_changed':changed,
 'unexpected_existing_source_changes':unexpected,'live_database_sha256':digest(db),
 'live_database_unchanged':digest(db)==pre['db'],
 'private_fixture_sha256':digest(ROOT/'data/bullet_choice_benchmark/v1.json'),
 'private_fixture_committed':bool(git('ls-files','data/bullet_choice_benchmark/v1.json').strip()),
 'working_status':git('status','--short'),'checkpoint_files':len(commit['files'])}
assert not unrelated and not unexpected and preservation['live_database_unchanged']
assert preservation['head']==commit['commit'] and not preservation['private_fixture_committed']
assert preservation['private_fixture_sha256']=='f102c21822553ef401f55ca0cf9454a9ef92c691ab2b56202f057a10053975b8'
write_json(OUT/'preservation.json',preservation)

review_readme='''# Current-code UI review — 21 November 2026

Seven actual normal-app rendered states; seven full-resolution originals and 78 readable, exact-crop sections. No downsampling. Private review packet: do not commit it.

## Method and limits

Normal source root: C:/Users/Admin/Documents/GitHub/Job-AI-Helper/app.py. Local URL during review: http://127.0.0.1:8721/. A fixture wrapper executes that app.py through runpy, restores a saved Application 156 generation through current persistence APIs and isolates all writes in a task-owned disposable database. Saved offline Best-of receipt is explicitly supplied; no new optimization, native scoring, rendering or approval occurred. Public-only view uses the same app with only public benchmark fixtures.

The existing CaptureSession capture/export/stitch/section pipeline was used on task-owned controlled Chromium, with a diagnostic synchronous adapter for Playwright thread affinity. This is NOT a completed sidebar-Firefox capture run. Sidebar automation failed waiting for controls/project-widget stability; a native automation provider also rejected the task window's ownership. Those failures are retained separately. Several controlled capture sessions were combined without changing PNG bytes; original capture-session provenance is retained per view.

## Owner checklist

- 01: Best-of saved 31 to 31 tie; incumbent retained; 13 to 12 bullets and 220 to 204 words. Do not attribute a native improvement to a bullet.
- 02: Job AI Helper unit-testing wording, selected in both saved combinations; partial testing support, not integration/system/UAT or database proficiency. Estimated relevance, saved membership and native evidence remain separate.
- 03: QueryAI shared provenance and React alternative handling. No wording-level winner for identical wording. Saved-document diagnostic and wording-only estimate need not agree.
- 04: CyberSphere source wording relevance and honest unavailable individual selection cause. Strict pairing remains unchanged.
- 05/06: C++ example at desktop/760px. Human C++ label retained; registry hash does not become lexical support. Explicit C++ alone does not demonstrate proficiency. Narrow page has no horizontal page overflow.
- 07: Fresh/public-only Lab shows 96 available controls, 90/96 agreement and 20 real cases unavailable. Missing private data is not a pass.

Long app captures include advanced content after the primary explanations. Section coordinates in manifest trace every exact crop to full.png. Automatic page heading sometimes reports Navigation; capture names, selected controls and notes describe the actual state. Screenshots show saved snapshots and estimates, not newly measured native outcomes. No independent owner/ChatGPT assessment has yet been performed on this packet.
'''
final_zip=OUT/'JobAIHelper_V37_Correctness_Review.zip'
with zipfile.ZipFile(OUT/'direct_chromium_review.zip') as src,zipfile.ZipFile(final_zip,'w',zipfile.ZIP_DEFLATED) as dst:
    manifest=json.loads(src.read('JobAIHelper_UI_Review/manifest.json'))
    manifest.update({'review_method':'Existing CaptureSession service on controlled Chromium; sidebar Firefox acceptance incomplete',
      'runtime_root':str(ROOT/'app.py'),'runtime_url':'http://127.0.0.1:8721/',
      'session_note':'Combined captures from controlled sessions; preserve per-capture origin_capture_session.',
      'integrity':{k:v for k,v in integrity.items() if k!='captures'}})
    for name in src.namelist():
        if name.endswith('.png'): dst.writestr(name,src.read(name))
    dst.writestr('JobAIHelper_UI_Review/README.md',review_readme.encode())
    dst.writestr('JobAIHelper_UI_Review/manifest.json',json.dumps(manifest,indent=2).encode())
with zipfile.ZipFile(final_zip) as z:
    assert z.testzip() is None
    with zipfile.ZipFile(OUT/'direct_chromium_review.zip') as src:
        assert all(z.read(n)==src.read(n) for n in z.namelist() if n.endswith('.png'))
failures=[{'case_id':r['case_id'],'expected':r['expected'],'failure_type':r['failure_type']} for r in after['rows'] if r['pass'] is False]
tests=[{'command':r'.\.venv\Scripts\python.exe -B reports/v37_release_readiness/run_checks.py','result':'80 named focused tests passed; all116 benchmark cases replayed; selector7/7; JSON/CSV/ZIP integrity passed','log':'checks-public-final.txt'},
 {'command':'Fresh checkpoint archive: original .venv Python, named tests.test_benchmark_public_fixture tests.test_cpp_relevance_identity tests.test_bullet_choice_lab tests.test_v37_bestof_release with process-local TEMP adapter','result':'29 run:28 passed,1 optional-private-data skip','log':'fresh4-tests.txt'},
 {'command':'Fresh checkpoint archive after punctuation-only UI restore: original .venv Python, named tests.test_benchmark_public_fixture tests.test_cpp_relevance_identity tests.test_bullet_choice_lab with process-local TEMP adapter','result':'18 run:17 passed,1 optional-private-data skip','log':'fresh-public-final-tests.txt'}]
report={'schema_version':1,'status':'CHECKPOINT AND CHROMIUM RENDERED REVIEW COMPLETE; SIDEBAR FIREFOX ACCEPTANCE UNVERIFIED',
 'checkpoint':commit,'preservation':preservation,'tests_run':tests,
 'benchmark_results':{'summary':after['summary'],'comparison':json.loads((OUT/'benchmark_diff.json').read_text()),'remaining_failures':failures},
 'ui_review':{'zip':str(final_zip),'sha256':digest(final_zip),'originals':7,'sections':78,'integrity':integrity,'console_errors':[],'streamlit_exceptions':[],
 'sidebar_firefox':'Automation failed; not accepted. Chromium service capture is a documented diagnostic fallback.'},
 'optional_fixture':{'path':'data/bullet_choice_benchmark/v1.json','sha256':preservation['private_fixture_sha256'],'committed':False,'instructions':'Owner copies original unchanged private fixture locally; see docs/v37_code_checkpoint.md. Public96 remain functional without it.'},
 'known_limitations':['Owner full run_tests not executed by Codex.','Sidebar Firefox capture acceptance remains open.','Six frozen controlled expectation failures remain unchanged.','20 real cases are independently unlabelled; no real accuracy claim.','Local installed Python3.14; repository supports3.13.','Fresh fixture hashes require exact bytes; -text attributes preserve pinned CRLF.'],
 'next_steps':['Owner inspect current-code review ZIP.','Verify sidebar Firefox session manually; retain failure receipts if it fails.','Owner run run_tests before any selective merge.','Review only checkpoint60-file/hunk manifest against master44665813; do not merge unrelated dirty work.'],
 'post_merge_backlog':['Performed-action recognition with independent semantic controls.','419 Core/Supporting review integration only behind confirmation, whole-JD/source and migration gates.','Independent portfolio and end-to-end optimization evaluation.','Broad OR/action grammar redesign deferred.','No new optimizer objectives or V1.17 activation.'],
 'continuation_prompt':'Continue from reports/v37_release_readiness/README.md and manifest.json. Checkpoint612218de51cc5fa8c6b5a11b69ec7a06d5891722 includes public Benchmark Lab fixtures and excludes privatev1.json. Preserve dirty work/index. C++ atomic-ID diagnostic fix and116-case regression complete90/96, selector7/7. Seven current normal-app Chromium captures passed integrity and rendered checks, but sidebar Firefox automation did not pass. Resolve/verify that acceptance only; do not rerun research, alter scoring, benchmarks, approval or419 policy. Owner runs full run_tests; no merge/push without authorization.'}
write_json(OUT/'manifest.json',report)
md=f'''# Controlled V3.7 checkpoint and review

Local checkpoint **{commit['commit']}**, branch {commit['branch']}; parent {commit['parent']}. No merge or push. Code checkpoint and Chromium rendered review are complete. **Sidebar Firefox Capture acceptance remains unverified; no unconditional release-readiness claim.**

## Checkpoint and preservation

60 selected files/hunks, exact checkpoint/working hashes in checkpoint_commit.json; app.py uses selected integration hunks, preserving unrelated development/C1 edits. Includes complete Best-of/B3/B4, Required/Core guard, Phase8 UI, Benchmark Lab, controlled Capture, diagnostics and required dependencies/tests. No production scorer/parser/taxonomy/objective/approval policy changes. Excludes private fixture, DBs, résumé documents, screenshots and secrets. Original index backup is local index_before_checkpoint.bin. HEAD/index changed intentionally for selective checkpoint; unrelated index entries preserved. All preflight existing source changes are the five intended diagnostic/public-fixture files. See preservation.json for exact end status/hashes.

Fresh checkout uses unchanged84 non-real v1 controls plus12 validation controls. Private20 are explicitly unavailable, never passed. Optional identity test skips only for absent private fixture; corrupt supplied fixture fails closed. Owner may locally copy unchanged v1.json with SHA256 {preservation['private_fixture_sha256']}; Git ignores it. See committed docs/v37_code_checkpoint.md. Exact -text Git attributes preserve frozen JSON byte identities.

## C++ defect and bounded fix

Estimator inserted internal technology registry IDs into prose tokenization; C++'s ID leaked a generic 'focused' facet/hash. v1.3 keeps identities atomic and maps only approved labels for display. Named-language-only requirements additionally require an actual requested language identity. Generic programming cannot demonstrate C++; explicit C++ remains recognized but does not prove advanced proficiency or Java/.NET/Python/PHP. Action/negation rules and native scorer are untouched. Six independent positive/negative tests added. Source changes: bullet_choice_estimated.py, bullet_choice_lab_ui.py, phase9f_wording_explanation_ui.py; optional fixture support: bullet_choice_lab.py, test_bullet_choice_lab.py, test_benchmark_public_fixture.py, public fixtures/attributes/docs. Exact full source manifest is checkpoint_commit.json.

## Focused validation

{chr(10).join('- '+t['command']+' → '+t['result']+'; '+t['log'] for t in tests)}

run_checks.py lists only named modules and uses the existing process-local TEMP adapter. Initial cold AppTest exceeded its unchanged3s default while importing pandas; isolated rerun passed, subsequent runner warms pandas only. Early fresh archives exposed line-ending hash normalization; exact-byte attributes fixed it. Failures/logs retained. No assertions/timeouts/frozen expectations weakened. No full runner, model calls or new native renders.

All116 cases replayed: **90/96 controlled agreement unchanged**, no new controlled regressions/improvements. Selector **7/7**. R08/R20 now abstain after false C++ facets were removed; real cases have no independent labels. Six outstanding failures: {', '.join(f['case_id'] for f in failures)}. Real accuracy remains unavailable. Public-only actual UI run96/96 available,90/96 agreement;20 real unavailable. Exports and previous/current comparisons pass.

## Current rendered normal-app review

Root {ROOT/'app.py'}, URL http://127.0.0.1:8721/. Fixture wrapper executes this exact normal app with disposable Application156 DB and immutable saved generation/artifact copies through normal APIs (fixture.json/seed_fixture.py/view_final.py). No source/frozen score identities edited. Existing offline31/31 receipt is labelled; Phase8 saved30/31 remains separate from current ordinary analysis32. No new measurement or approval.

Review ZIP: **{final_zip.name}**, SHA256 **{digest(final_zip)}**. Seven originals,78 numbered full-width sections; all PNGs decoded/hash-checked, sections exact pixel crops, complete vertical coverage; ZIP CRC passed. Job AI Helper partial testing/no database cue, QueryAI React alternatives/shared provenance, CyberSphere unknown cause, Best-of saved tie and C++ corrected facet were observed. Desktop and760px reviewed; no page overflow, Streamlit exceptions or browser console errors in successful current views. See review_integrity.json and public-browser.json.

Important limitation: captures use the existing CaptureSession service/stitch/export on controlled Chromium with a synchronous thread-affinity adapter. They are actual current normal-app renders, **not a successful sidebar-Firefox workflow**. Sidebar automation failed on control/project-widget visibility/stability; fixture navigation originally interrupted the worker and was serialized. Native fallback rejected task-window ownership. Do not call this a sidebar pass. Prior failed logs/screenshots remain separate. Combined views preserve originating capture session; no old screenshots substituted. Automatic heading sometimes says Navigation; names/selectors identify states. Packet README explains these limitations.

## Owner steps and deferred work

1. Inspect ZIP originals/sections and review checklist. Verify sidebar Firefox manually before unconditional Capture acceptance.
2. From repository root run **run_tests** (owner full regression; Codex did not run it). Optional fixture is local-only; missing-private skips are reported distinctly.
3. Review checkpoint manifest/diff against master44665813. Do not merge the entire dirty worktree or copy private fixtures. No merge/push was performed.

Post-merge scope: performed-action recognition, independent semantic controls/portfolio validation and end-to-end optimization evaluation. Six controlled failures remain documented.419 policy changes require separate source/whole-JD confirmation and migration gates. Broad OR/action redesign, historical migrations, new objectives and V1.17 scoring remain deferred. Suggested later branch scope codex/bullet-choice-validation; no branch created now.

Continuation: {report['continuation_prompt']}
'''
(OUT/'README.md').write_text(md,encoding='utf-8')
for name in ['v37_codex_handover.md','v37_codex_handover.json']:
    source=ROOT/'reports'/name; backup=OUT/'backups'/name
    if not backup.exists(): backup.write_bytes(source.read_bytes())
handover=ROOT/'reports/v37_codex_handover.json'
data=json.loads(handover.read_text(encoding='utf-8')); data['head']=commit['commit'];data['release_readiness_checkpoint_20261121']=report
write_json(handover,data)
with (ROOT/'reports/v37_codex_handover.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## Controlled code-only checkpoint — 21 November 2026\n\n'+md+'\n')
print(json.dumps({'commit':commit['commit'],'files':len(selected),'zip':str(final_zip),'sha256':digest(final_zip),'unrelated_changes':unrelated,'unexpected_source_changes':unexpected,'failures':failures},indent=2))
