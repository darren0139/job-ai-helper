"""Read-only historical/current document score diagnostics; never a scoring or approval gate."""
from __future__ import annotations
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

VERSION = 'v312b216a-score-authority-v1'
METRICS = ('deterministic_alignment_score', 'required_core_coverage_score',
           'preferred_coverage_score', 'evidence_strength_score')
ROW_FIELDS = ('text', 'importance', 'match_label', 'match_value', 'evidence_strength', 'score_eligible', 'group_weight_fraction', 'evidence')


def fp(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def rows(analysis):
    result = {}
    for row in analysis.get('canonical_requirements') or []:
        rid = row.get('requirement_id')
        require(isinstance(rid, str) and rid and rid not in result, 'Missing or duplicate requirement identity')
        result[rid] = {k: deepcopy(row.get(k)) for k in ROW_FIELDS}
    require(bool(result), 'No canonical requirement rows')
    return result


def compare(left, right):
    a, b = rows(left), rows(right)
    changed = []
    for rid in sorted(a.keys() & b.keys()):
        fields = [k for k in ROW_FIELDS if a[rid][k] != b[rid][k]]
        if fields:
            changed.append({'requirement_id': rid, 'changed_fields': fields, 'before': a[rid], 'after': b[rid]})
    return {'before_scoring_version': left.get('scoring_version'), 'after_scoring_version': right.get('scoring_version'),
            'before_metrics': {k: left.get(k) for k in METRICS}, 'after_metrics': {k: right.get(k) for k in METRICS},
            'removed_ids': sorted(a.keys()-b.keys()), 'added_ids': sorted(b.keys()-a.keys()), 'changed_rows': changed}


def inspect_receipt(*, historical_report, receipt, application_id, generation_id, expected_decision=None):
    """Join only the original selected-source report to the exact saved A/B receipt."""
    require(receipt.get('application_id') == application_id and receipt.get('generation_id') == generation_id, 'Application or fitted generation differs')
    require(receipt.get('comparison_valid') is True, 'Native comparison is not valid')
    contract = receipt.get('starting_document_contract') or {}
    require(contract.get('mode') == 'selected_base_docx_only', 'No authoritative Selected Base DOCX comparison')
    historical = historical_report.get('stable_analysis') or {}
    before, after = receipt.get('before_stable_analysis') or {}, receipt.get('after_stable_analysis') or {}
    document = receipt.get('document_analysis') or {}
    selected = receipt.get('selected_base_analysis') or {}
    authority = document.get('initial') or {}
    raw = historical_report.get('raw_jd_text')
    require(isinstance(raw, str) and raw.strip() and sha(raw) == authority.get('jd_text_sha256'), 'Exact historical JD differs from verified document JD')
    require(authority == selected.get('document_analysis') and selected.get('stable_analysis') == before, 'Selected Base analysis differs from actual-document authority')
    require(authority.get('input_authority') == 'ACTUAL_RESUME_DOCUMENT' and authority.get('fingerprint') == fp({k:v for k,v in authority.items() if k != 'fingerprint'}), 'Selected Base authority fingerprint invalid')
    require(fp(before) == authority.get('stable_analysis_fingerprint'), 'Selected Base scoring payload fingerprint invalid')
    final_authority = document.get('final') or {}
    require(final_authority.get('input_authority') == 'ACTUAL_RESUME_DOCUMENT' and final_authority.get('jd_text_sha256') == sha(raw) and final_authority.get('fingerprint') == fp({k:v for k,v in final_authority.items() if k != 'fingerprint'}) and final_authority.get('stable_analysis_fingerprint') == fp(after), 'Final document scoring authority invalid')
    require(contract.get('selected_base_document_analysis_fingerprint') == authority.get('fingerprint') and contract.get('selected_base_resume_text_sha256') == authority.get('resume_text_sha256'), 'Selected Base contract differs')
    require(all(isinstance(v, str) and len(v) == 64 for v in (contract.get('selected_base_docx_sha256'), document.get('final_document_sha256'))), 'Document hashes missing')
    ctx = (historical_report.get('meta') or {}).get('phase9e_starting_context') or {}
    selected_ctx = selected.get('starting_context') or {}
    for field in ('decision_fingerprint', 'starting_snapshot_fingerprint'):
        require(bool(ctx.get(field)) and ctx[field] == selected_ctx.get(field), 'Historical starting source differs: '+field)
    if expected_decision is not None:
        require(ctx['decision_fingerprint'] == expected_decision, 'Selected fitted version has a different decision')
    require(before.get('scoring_version') and before['scoring_version'] == after.get('scoring_version'), 'Native A/B scorer differs')
    require(set(rows(before)) == set(rows(after)), 'Native A/B requirement scope differs')
    comp = receipt.get('comparison') or {}
    require(comp.get('before_score') == before.get(METRICS[0]) and comp.get('after_score') == after.get(METRICS[0]), 'Native comparison totals disagree')
    require(all(isinstance(a.get(k), (int, float)) and not isinstance(a.get(k), bool) for a in (historical,before,after) for k in METRICS), 'Score components missing')
    require(comp.get('score_delta') == after[METRICS[0]]-before[METRICS[0]], 'Native score delta disagrees')
    return {'version': VERSION, 'status': 'saved_receipt_diagnostic_only', 'application_id': application_id, 'generation_id': generation_id,
            'verification_id': receipt.get('verification_id'), 'decision_fingerprint': ctx['decision_fingerprint'],
            'exact_jd_sha256': sha(raw), 'selected_base_docx_sha256': contract['selected_base_docx_sha256'],
            'final_docx_sha256': document['final_document_sha256'],
            'historical_to_current_base': compare(historical,before), 'current_base_to_final': compare(before,after),
            'native_score_delta': comp['score_delta'], 'native_core_delta': comp.get('required_core_coverage_delta'),
            'limitations': 'Historical-to-current delta is not a tailoring improvement; causal attribution requires controlled replay.'}


def native_replay(*, report, receipt, base_docx):
    """Replay current policy using controlled profile/text/matcher changes; no DB or model actions."""
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION, canonicalise_requirements, build_deterministic_keyword_match, build_stable_analysis
    from tailoring.fresh_target_evidence_scoring import build_fresh_target_analysis
    from tailoring.phase9f_v364_document_reverify import build_frozen_selected_base_document_report
    from parse import read_resume_docx
    historical = report['stable_analysis']; before = receipt['before_stable_analysis']
    require(before.get('scoring_version') == SCORING_VERSION, 'Reverify Phase 8 under the active scorer first')
    require(not historical.get('effective_requirement_scope') and not historical.get('matching_policy_identity') and not ((report.get('meta') or {}).get('jd_user_inputs') or {}).get('preferred_requirement_overrides'), 'Custom or reviewed scope not supported by controlled replay')
    raw, text, profile, jd = (report[k] for k in ('raw_jd_text','raw_resume_text','resume_profile','jd_profile'))
    data = base_docx.read_bytes(); digest = hashlib.sha256(data).hexdigest()
    require(digest == receipt['starting_document_contract']['selected_base_docx_sha256'], 'Supplied Base DOCX differs from frozen authority')
    actual_text = read_resume_docx(str(base_docx), preserve_complete_text=True)
    require(sha(actual_text) == receipt['starting_document_contract']['selected_base_resume_text_sha256'], 'Current DOCX extraction differs from saved receipt')
    require(hashlib.sha256(base_docx.read_bytes()).hexdigest() == digest, 'Base DOCX changed during extraction')
    canonical = canonicalise_requirements(jd_profile=jd, raw_jd_text=raw)
    def score(source_text, builder):
        kwargs = dict(jd_profile=deepcopy(jd),raw_jd_text=raw,raw_resume_text=source_text,resume_profile=deepcopy(profile),retrieval_mode_override='lexical')
        keyword = build_deterministic_keyword_match(requirements=deepcopy(canonical['requirements']),acronym_map=deepcopy(canonical['acronym_map']),resume_profile=deepcopy(profile),raw_resume_text=source_text)
        return builder(keyword_match=keyword, **kwargs)
    fresh = score(text,build_fresh_target_analysis)
    stable = score(text,build_stable_analysis)
    unbounded_actual = score(actual_text,build_stable_analysis)
    sealed, contract = build_frozen_selected_base_document_report(baseline_report=deepcopy(report),jd_text=raw,source_artifact={'artifact_type':'docx','artifact_bytes':data,'sha256':digest,'byte_size':len(data)})
    actual = sealed['stable_analysis']
    return {'status':'controlled_native_replay_completed','active_scorer':SCORING_VERSION,
            'frozen_text_sha256':sha(text),'actual_text_sha256':sha(actual_text),'actual_contract':contract,
            'historical_to_current_fresh_target':compare(historical,fresh),
            'fresh_target_to_stable_same_inputs':compare(fresh,stable),
            'stable_frozen_to_actual_text_same_profile':compare(stable,unbounded_actual),
            'unbounded_to_document_grounded_profile':compare(unbounded_actual,actual),
            'actual_document_replay_to_saved_base':compare(actual,before),
            'limitations':'Historical-to-fresh may include changes in scorer/runtime/knowledge. Other stages vary one input or scoring entry point at a time. Intermediate unbounded results are diagnostics, not document scores.'}


def render_diagnostic(st, historical, receipt, generation, raw_jd_text):
    if (receipt.get('starting_document_contract') or {}).get('mode') != 'selected_base_docx_only' or not historical:
        return
    try:
        require(historical.get('raw_jd_text') == raw_jd_text, 'Active JD differs from original report')
        require(bool(generation.get('phase9e_decision_fingerprint')), 'Fitted decision identity missing')
        result = inspect_receipt(historical_report=historical, receipt=receipt, application_id=generation['application_id'], generation_id=generation['generation_id'], expected_decision=generation.get('phase9e_decision_fingerprint'))
    except (ValueError, KeyError, TypeError) as exc:
        st.caption('Historical/current score audit unavailable: '+str(exc))
        return
    hist = result['historical_to_current_base']; native = result['current_base_to_final']
    with st.expander('Score authority — historical confirmation vs current document comparison', expanded=False):
        st.caption('Historical confirmation is not the current document baseline. Only the current Base-to-Final delta measures tailoring.')
        st.table([{'Component':k, 'Historical source':hist['before_metrics'][k], 'Current Base DOCX':native['before_metrics'][k], 'Current Final DOCX':native['after_metrics'][k]} for k in METRICS])
        st.caption('Historical scorer: '+str(hist['before_scoring_version'])+' · Current scorer: '+str(native['before_scoring_version']))
        st.write(f"Historical/current Base: {len(hist['changed_rows'])} changed rows; {len(hist['removed_ids'])} removed; {len(hist['added_ids'])} added.")
        st.download_button('Download score authority diagnostic (JSON)',json.dumps(result,ensure_ascii=False,indent=2),file_name=f"phase9f_score_authority_{result['application_id']}_{result['generation_id'][:8]}.json",mime='application/json',key=f"b216a_score_{result['application_id']}_{result['generation_id']}")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug',type=Path,required=True); parser.add_argument('--phase8',type=Path,required=True)
    parser.add_argument('--base-docx',type=Path); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    debug=json.loads(args.debug.read_text(encoding='utf-8-sig')); receipt=json.loads(args.phase8.read_text(encoding='utf-8-sig'))
    report=debug['analysis_report']; app=debug['debug_meta']['application_id']; generation=receipt['generation_id']
    result=inspect_receipt(historical_report=report,receipt=receipt,application_id=app,generation_id=generation)
    if args.base_docx: result['controlled_replay']=native_replay(report=report,receipt=receipt,base_docx=args.base_docx)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print('[PASS] Read-only score authority diagnostic:',args.output)


if __name__=='__main__': main()
