"""Classify read-only findings; emit owner-review inventory and plan."""
from pathlib import Path
import ast,csv,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
def read(p):return json.loads((OUT/p).read_text(encoding='utf-8'))
def save(p,v):(OUT/p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode('utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
items=read('inventory_raw.json'); manifest=read('manifest_verification.json');pre=read('preflight.json')
categories={'P':'Already partially checkpointed, with an additional working-tree modification',
 'M':'Intended V3.7 functionality missing from the checkpoint',
 'S':'An existing separate feature that must be checkpointed independently',
 'R':'Development/research-only code',
 'T':'Test or fixture required by an intended feature',
 'X':'Private/generated output that must stay outside Git',
 'U':'Uncertain ownership or dependency requiring review'}
groups={
 'A':{'title':'Release compatibility tests and missing regression coverage','depends_on':['612218de'],'recommendation':'First proposed follow-up. Include four demonstrated stale-test updates plus release contract tests/public synthetic fixture. Run named tests against resulting committed tree; preserve assertions and expectations.'},
 'B':{'title':'Selected Base verification and approval-floor wiring','depends_on':['612218de','A'],'recommendation':'Release-safety review prerequisite: split execution-manager Phase8 hunks from V2.7 fingerprint hunks. Include DB/UI floors, document freshness, genuine-DOCX smoke fixtures/regressions and review namespaces. Existing approval policy is not rewritten during this audit.'},
 'C':{'title':'V2.7 mixed Base/Library normal generation and decision-time traces','depends_on':['A','B'],'recommendation':'Separate behavior-changing checkpoint, explicitly owner-reviewed. Include source pool, allocation, writer, app hooks and generation cache versions together; do not cherry-pick only staged files.'},
 'D':{'title':'Additional pre-fit/final multi-project and legacy native inspectors','depends_on':['C','612218de'],'recommendation':'Separate read-only UI checkpoint. Include all helpers and tests with rendering hooks; optional older V2.9.1 wrapper needs reachability/deduplication decision. B3/B4 themselves already committed.'},
 'E':{'title':'C1 extension/current-tab Capture integration','depends_on':['master Firefox/privacy/part-time extension changes'],'recommendation':'Keep separate from extension-free controlled Capture. Review origin/permission/signing and overlay on newer master manifests; do not copy old whole manifests.'},
 'F':{'title':'JD parser/importance semantics work','depends_on':['separate source/whole-JD review gates'],'recommendation':'Separate policy/parser checkpoint, not implicit V3.7 release dependency. 330 additions/3 deletions affect native requirement extraction/classification. Preserve six new regression modules, no wholesale419 migration.'},
 'R':{'title':'Research and audit tooling','depends_on':['own explicit research fixtures'],'recommendation':'Keep out of normal-runtime release. May later checkpoint sanitized reusable research tools with own data availability contracts; no SQL/bonus/source-neutral activation.'},
 'N':{'title':'No semantic delta / optional hash metadata','depends_on':[],'recommendation':'Capture2/v365 diffs are whitespace only. Full-private-fixture SHA sidecar is optional metadata, not a missing public fixture; no runtime need.'}}
mapping={}
def add(cat,group,note,*paths):
 for p in paths:mapping[p]=(cat,group,note)
add('P','C','Best-of/Lab/controlled Capture hooks already committed. Remaining hunks add V2.7 imports/UI/generation settings plus C1 HTML. Split by function/hunk; never stage whole file.', 'app.py')
add('P','N','Only an extra trailing blank line; current Python AST equals checkpoint. No missing Capture behavior.', 'browser_integration/ui_review_capture.py','browser_integration/ui_review_scroll.py')
add('P','N','Only trailing spaces in7 literal-continuation lines; Python AST equals checkpoint. Evidence logic is already committed.', 'tailoring/phase9f_v365_jd_evidence.py')
add('S','F','Native parser/classification changes: hard-cue context, headings, duties/admin semantics, atomic/inline preference splitting and unbulleted task runs. Not an estimator-only change. Must have separate review.', 'analysis_stability/stable_evidence_scoring.py')
add('M','B','Mixed file: additional frozen Selected Base DOCX/confirmation/source-identity verification handoff AND V2.7 cache/source policy changes. Split B verification hunks from C fingerprints/import.', 'database/phase9f_tailoring_execution_manager.py')
add('M','B','Additional Selected Base floor at direct approval entry before metadata/write. Absent in commit; independent write-intercepted probe floor_calls0. Existing Phase8 gate still exists.', 'database/tailoring_generation_control.py')
add('M','B','Additional native Base-floor checks in current draft and legacy selected-version approval UI; backend counterpart required.', 'tailoring/generation_controls_ui.py')
add('M','B','Reject/reverify legacy profile-only normal-generation receipts lacking actual document analysis. Missing in committed tree.', 'tailoring/phase8_auto_verification.py')
add('M','B','Explicit Selected Base receipt widget namespace, complements committed B2 renderer namespaces; useful call-site follow-up.', 'tailoring/phase9f_base_vs_tailored_explainer.py')
add('M','B','Keeps genuine frozen DOCX fixture alive and uses actual document verification instead of synthetic byte files/mocked success. Tie to helper/test before checkpoint.', 'scripts/check_phase9f_tailoring_execution.py')
add('T','B','Genuine DOCX fixture writers used by smoke/tailoring tests; must accompany smoke integration, not private résumé data.', 'tests/phase9f_e_test_support.py')
add('T','B','Normal-tailoring fixture/test updates for actual document-grounded verification; retain assertions and pair with execution-manager hunks.', 'tests/test_phase9f_tailoring_execution.py')
add('T','B','Regression confirms frozen_selected_base.docx exists and is a real package throughout verification, then temp cleanup. Fails against checkpoint because parser never sees this path.', 'tests/test_phase9f_frozen_source_smoke.py')
add('T','B','Pure floor and direct DB guard tests; module also imports missing V2.8 multi-view helper. Separate tests logically or include that UI helper; do not weaken assertions.', 'tests/test_phase9f_v361_approval_floor.py')
add('T','B','Tests pure source contract already committed plus missing normal verifier/freshness wiring and V2.8 checkbox helper. On checkpoint28-test probe, this module contributes1 failure/1 missing-helper error.', 'tests/test_phase9f_v364_baseline_and_decisions.py')
add('S','C','V2.7 exact Base+Library bullet pool/dedup and shared provenance admission. Staged, not committed. Does not belong in checkpoint merely because staged.', 'tailoring/combined_project_bullet_sources_v2_7.py')
add('S','C','Changes canonical-only normal allocator to mixed-source eligibility, lead policy, coverage-aware selection traces and exact allocated-source propagation. Changes selection behavior; include own policy/cache version.', 'tailoring/deterministic_bullet_allocation.py')
add('S','C','Writer retains exact allocated Base/Library bullet wording and provenance for V2.7. Requires combined source/allocator policy, not standalone UI.', 'tailoring/project_section_tailor.py')
add('S','C','Read-only pre-generation preview built on V2.7 actual source pool/allocator; staged but not committed.', 'tailoring/phase9f_pre_generation_combined_ui_v2_7.py')
add('S','C','Adds saved decision-time trace explanation and new-policy source displays; additionally imports detail comparison helper. Split UI details from allocator contract only if interfaces stay consistent.', 'tailoring/phase9f_project_bullet_sources_v2_3.py')
add('T','C','Staged mixed-source policy/provenance/legacy negative controls. Import fails on checkpoint because source module absent.', 'tests/test_phase9f_combined_selection_v2_7.py')
add('T','C','Allocator wording/behavior compatibility updates required with new mixed-source policy; do not add alone to old allocator.', 'tests/test_all_canonical_before_fitting_v1.py','tests/test_pre_phase9f_tailoring_polish_v1.py')
add('T','C','V2.7 decision-time source trace tests depend on new allocator and explain_saved_bullet_decision API. Not historical selection causes fabricated after the fact.', 'tests/test_phase9f_v27_selection_explanation_trace.py')
add('S','D','Read-only final source audit adds multi-project explorer, final-vs-Base proxy, V2.8 and grouped compact views. Existing committed old panel remains functional but differs materially.', 'tailoring/phase9f_final_evidence_comparison_v2_4.py')
add('S','D','Adds final-vs-Base evidence proxy call to existing stage view; new helper required, does not replace native Job Match.', 'tailoring/phase9f_explainer_stage_v2_1.py')
add('S','D','Pre-fit interactive explorer plus advanced legacy ranking toggle; adds stable_analysis parameter and new helper. Pair with app hook.', 'tailoring/project_selection_explainer_ui.py')
add('S','D','Saved-source lexical highlighting/detail; called by new V2.7 source comparison, never authoritative JD scoring.', 'tailoring/phase9f_bullet_comparison_detail_v1.py')
add('S','D','V2.8 JD-first source/final explorer and multi-project controls; older separate component, not missing B4 itself. Required by omitted direct-floor test module import.', 'tailoring/phase9f_decision_explorer_v28.py')
add('S','D','Project-only coverage proxy used by new final/stage panels, not native whole-résumé score.', 'tailoring/phase9f_final_base_coverage_check_v1.py')
add('S','D','Read-only multi-project evidence view used by new final audit.', 'tailoring/phase9f_multi_project_evidence_v36.py')
add('S','D','Saved pre-fit JD-first view requires corresponding hook in project_selection_explainer_ui; not verified final fitting.', 'tailoring/phase9f_pre_fit_decision_explorer_v281.py')
add('U','D','Older V2.9.1 opt-in native comparison wrapper. No current source caller found; current Best-of V3.0 UI is committed. Owner should decide whether to archive legacy helper or intentionally expose it.', 'tailoring/phase9f_verified_best_of_v291_ui.py')
add('S','D','Caption-only correction: requirement table display setting does not control current Phase8 rendering. Low-risk presentation follow-up.', 'tailoring/session_table_ui_v2.py')
add('T','D','UI/proxy/export/advanced linkage regression for additional saved prefit/final views; include with respective D hooks and helpers.', 'tests/test_final_proxy_visible_v1.py','tests/test_phase9f_decision_explorer_v28.py','tests/test_phase9f_pre_fit_explorer_v281.py','tests/test_phase9f_shadow_v27_compact_integration.py','tests/test_phase9f_v27_detailed_comparison_v1.py')
add('S','E','C1 current-tab extension/local HTML bridge, origin/permission/background scripts and documented setup; deliberately absent from controlled Firefox Capture checkpoint. Reconcile with newer master extension/privacy changes.', 'browser_extension/README.md','browser_extension/manifest.firefox.json','browser_extension/manifest.json','assets/streamlit_capture.html','browser_extension/app_capture.js','browser_extension/app_capture_background.js')
add('T','E','Node extension capture origin/PNG/current-tab controls and optional DOM Chromium smoke. Separate from controlled UI Review Capture service tests already committed.', 'browser_extension/tests/app_capture_test.js','tests/test_v37_capture_browser.py')
add('T','A','Compatibility update for committed UI change; old committed test is demonstrably stale/fails. Preserve semantic assertion, update namespace/wrapping/full-wording contract.', 'tests/test_application_session_first_analysis_binding.py','tests/test_full_page_job_finder_and_score_ui.py','tests/test_job_match_session_ab.py','tests/test_phase8_score_explainability.py')
add('T','A','Current document-role/readiness assertions use committed Phase8 presentation; some master changes also touch this test. Hunk-review preserve both.', 'tests/test_application_workflow_hierarchy.py')
add('T','A','Additional direct tests for already committed diagnostic/selector/guard/lead/receipt modules; omitted from60-file checkpoint. Not dead code or private fixture tests.',
 'tests/test_bullet_relevance_diagnostic.py','tests/test_phase8_final_improvement_verdict_v1.py','tests/test_phase9f_auto_bestof_explain_v32.py','tests/test_phase9f_auto_optimize_v31.py','tests/test_phase9f_certified_selection_v36.py','tests/test_phase9f_evidence_optimizer_v33.py','tests/test_phase9f_jd_relevance_optimizer_v35.py','tests/test_phase9f_v34_candidate_identity_fix.py','tests/test_phase9f_v363_selection_receipts.py','tests/test_phase9f_v364_forced_solver.py','tests/test_phase9f_verified_best_of_v291.py','tests/test_v37_hard_floor.py','tests/test_v37_lead_candidate.py','tests/test_v37_phase8_visual_labels.py','tests/test_v37_project_leads.py')
add('T','A','Synthetic_only weak-résumé negative-control fixture; no real résumé source. Required by untracked selection-receipt test; safe public fixture candidate, expectations must remain unchanged.', 'tests/fixtures/phase9f_v363_weak_resume_challenge.json')
add('T','A','Tests committed opt-in V2.6 writer, source hashes, byte-preserving DOCX edits, page-count failures.15/15 pass on committed source, but this staged test file itself is missing.', 'tests/test_phase9f_joint_resume_optimizer_v2_6.py')
add('T','F','Tests separate parser/extraction/importance changes; must stay with F policy review and frozen expectations, not pulled into diagnostic-only release.', 'tests/test_jd_atomic_modifier_coalescing_v1_3.py','tests/test_jd_corpus_parser_safety_v1.py','tests/test_jd_generic_unbulleted_task_run_v1_1.py','tests/test_jd_hard_cue_context_v1_5.py','tests/test_jd_inline_parenthetical_preference_v1_4.py','tests/test_jd_nested_subsections_admin_v1_2.py')
add('R','R','Explicit bounded corpus/lead/ATS/native/testing/SQL/supporting research runner, not ordinary production UI dependency. Reads saved sources; outputs belong outside Git.', 'scripts/v37_bonus_research.py','scripts/v37_corpus_benchmark.py','scripts/v37_evidence_readiness.py','scripts/v37_lead_ats_experiment.py','scripts/v37_native_bullet_trial.py','scripts/v37_repair_testing_selection.py','scripts/v37_selection_quality.py','scripts/v37_sql_evidence_research.py','scripts/v37_supporting_validation.py','scripts/v37_ui_review.py')
add('R','R','Authoring tool reads external frozen corpus plus private audit cases to create original fixture. Not needed by public Lab runtime; do not rerun/rewrite frozen expectations or add private outputs.', 'scripts/freeze_bullet_choice_benchmark.py')
add('T','N','Hash-only sidecar for optional full privatev1 fixture. No wording/private payload; loader uses embedded verified hash and does not read this file. Optional reproducibility metadata, not release blocker.', 'data/bullet_choice_benchmark/v1.sha256')
add('R','R','Read-only research evidence/selection/counterfactual adapter, not imported by committed normal app. Research-only bonus/SQL/testing/source-neutral behavior must remain inactive.', 'tailoring/phase9f_v37_ats.py','tailoring/phase9f_v37_bonus_coverage.py','tailoring/phase9f_v37_corpus_benchmark.py','tailoring/phase9f_v37_counterfactual.py','tailoring/phase9f_v37_neutral_selection.py','tailoring/phase9f_v37_selection_evidence.py','tailoring/phase9f_v37_sql_evidence.py','tailoring/phase9f_v37_testing_gate.py')
add('R','R','Focused tests for research-only ATS/bonus/corpus/native-swap/gating/SQL/neutral paths. Keep with research source, not standalone failing tests in release.', 'tests/test_v37_ats.py','tests/test_v37_bonus_coverage.py','tests/test_v37_bonus_optimizer.py','tests/test_v37_corpus_benchmark.py','tests/test_v37_native_bullet_swaps.py','tests/test_v37_repaired_selection.py','tests/test_v37_selection_quality.py','tests/test_v37_sql_evidence.py','tests/test_v37_testing_gate.py')
add('R','R','Report-tool test dynamically loads ignored reports/v37_real_bullet_quality code/data. Would fail fresh checkout if committed alone; separate sanitized tooling/data contract needed, private cases stay local.', 'tests/test_real_quality_evidence_binding.py','tests/test_real_quality_owner_packet.py')
assert set(mapping)=={r['path'] for r in items}, {'unclassified':set(r['path'] for r in items)-set(mapping),'extra':set(mapping)-{r['path'] for r in items}}
idx={p.split('\t',1)[1]:p.split('\t',1)[0] for p in git('ls-files','--stage').splitlines()}
def objects(data):
 try:return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(data.decode('utf-8-sig')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
 except:return {}
for r in items:
 cat,group,note=mapping[r['path']];r.update(category=categories[cat],category_code=cat,group=group,reason=note,index_entry=idx.get(r['path']))
 if r['path'].endswith('.py') and r['checkpoint_sha256']:
  before=subprocess.check_output(['git','show','HEAD:'+r['path']],cwd=ROOT,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'));after=(ROOT/r['path']).read_bytes()
  a,b=objects(before),objects(after);r['changed_top_level_symbols']=sorted(k for k in a.keys()|b.keys() if a.get(k)!=b.get(k))
  r['ast_identical']=ast.dump(ast.parse(before.decode('utf-8-sig')),include_attributes=False)==ast.dump(ast.parse(after.decode('utf-8-sig')),include_attributes=False)
counts={c:sum(r['category_code']==c for r in items) for c in categories}
save('inventory.json',items)
with (OUT/'inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
 fields=['path','status','category','group','reason','checkpoint_sha256','working_sha256','index_entry','changed_top_level_symbols','incoming_working_imports']
 w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
 for r in items:w.writerow({**r,'changed_top_level_symbols':'; '.join(r.get('changed_top_level_symbols',[])),'incoming_working_imports':'; '.join(x['path']+':'+str(x['line']) for x in r['incoming_working_imports'])})
save('checkpoint_groups.json',groups)
print(json.dumps({'paths':len(items),'counts':counts,'staged':sum(r['status'][0] not in ' ?' for r in items),'unstaged':sum(r['status'][1] not in ' ?' for r in items),'untracked':sum(r['status']=='??' for r in items)},indent=2))
