"""Offline V5 review preparation and validation only; never imports labels."""
import argparse
import json
from pathlib import Path
from taxonomy_discovery import unresolved_independent_review as review


def readiness_markdown(packet,audit):
    lines=['# V5 maintainer readiness audit — do not distribute to blinded reviewers','',
      'Reviewer distribution is limited to docs/unresolved_independent_review_packet_v5.md, '
      'reports/unresolved_independent_review_packet_v5.json and its blank V5 receipt template. '
      'This audit deliberately discusses prior artifacts/controls and is not blinded material.','',
      '## Verified current state','',
      f"Prepared {audit['prepared_pending_cases']} pending cases; no new human decisions. "
      f"Current gold: {audit['current_gold']['confirmed']} inherited, {audit['current_gold']['pending']} pending. "
      f"Need at least {audit['additional_actionable_needed']} more actionable independent labels, four non-UNKNOWN "
      'categories, and all seven pending critical controls. Neither coverage nor actionability is guaranteed.','',
      f"V4 had 20 cases (two inherited controls and 18 blank reviews). V5 supplies {len(audit['new_material_not_in_v4'])} "
      'additional pending cases, including the traffic-light control. Existing NAC controls are excluded from the '
      'new reviewer packet/template; their original receipts/answers remain unchanged. No reapproval is requested.','',
      '### V4 blinding audit','',
      'V4 was NOT genuinely blinded. Source-specific questions suggested routes and rejected mappings; '
      'an appendix exposed V3 AI and deterministic proposals; inherited control fields exposed expected answers; '
      'parent wording/headings were visible beside frozen children. Moving recommendations later in the file '
      'did not isolate them. Activity/structure annotations and predicate shortlists also carried editorial judgments.','']
    lines.extend('- '+x for x in audit['v4_leak_locations'])
    lines+=['','### V5 leakage and evidence boundaries','',
      'V5 reconstructs its packet from an exact allowlist of the frozen input. Native resolver outputs '
      '(including production scope codes) are displayed as recorded facts, not gold root causes. '
      'Candidate lists retain original bounded token/alias facts with a uniform warning; no V3 predicate '
      'shortlists, multidimensional routes, historic buckets, prior conclusions, case questions or expected answers '
      'are copied. Exact canonical wording, fingerprints, source locators, source hashes and numeric allocations '
      'remain distinct. No original-JD/parent/sibling/heading excerpts are included. References do not authorize '
      'opening contaminated reports or expanding source scope. Packet integrity rejects extra fields even if resealed.','',
      'The blank receipt has no preselected route, origin, reviewer, timestamp, sufficiency or independence '
      'attestation. A prepared case is not an actionable label. A reviewer who saw AI suggestions must truthfully '
      'choose AI-assisted review, which cannot enter independent gold. Software cannot prove a reviewer is blind.','',
      '### Reviewability and source limits','',
      'All 38 pending cases have frozen child text, IDs and original input fingerprints and are available for '
      'source-only decision or explicit deferral. There are 37 potential frozen decision attempts after excluding '
      'the already deferred child #32; this is NOT 37 independently supportable actionable labels. '
      f"Recovered-source status is verified for {len(audit['source_recovery_verified_pending'])} pending cases and "
      f"partial for {len(audit['source_recovery_partial_pending'])}. These are provenance availability counts, not route labels.",'',
      'Job 31 req_8d47527c8f34 (#32) retains DEFERRED_FOR_CURRENT_BENCHMARK and HIGH_PRIORITY_INVESTIGATION '
      'for parent fidelity. Its UI-development parent is absent from frozen text; V5 supplies no parent wording '
      'or prefilled reviewer answer. An actionable child-only receipt is blocked. Separate context-aware inputs, '
      'fingerprints and independent review are required before changing that evaluation contract. '
      'The existing 0.333333 allocation and other production allocations are preserved.','',
      'Partial-source cases:','']
    lines.extend(f"- Job {k[0]} / {k[1]}" for k in audit['source_recovery_partial_pending'])
    lines+=['','CSS/HTML (#17/#18) have source mentions but no corroborated canonical child identity in the '
      'recovered snapshot; standalone wording lacks proficiency/list context. Their actual production blocker '
      'cannot be established from the missing parent; request source verification or defer causal classification. '
      'The #19 and #25 snapshots retain the exact child but not every parent provenance link is verified. '
      'They require source/provenance review before a causal structural assertion. Do not automatically classify '
      'any of these as STRUCTURAL solely because recovery is partial.','',
      'Database-list #10 omits a proficiency heading; #14/#15 robotics and several other canonical children '
      'have additional source clauses outside the frozen view. If a decision requires those clauses, it must '
      'be deferred or separately context-reviewed. We do not adjudicate frozen-input sufficiency from AI history.','',
      '### All pending critical controls','']
    lines.extend(f"- Job {k[0]} / {k[1]} — included, blank decision." for k in audit['pending_critical_keys'])
    lines+=['','### Semantic content, root cause and investigation route','',
      'Semantic content is what the permitted exact source requests. Native facts show what the recorded '
      'production resolver did under its frozen versions; an unresolved result does not identify its cause. '
      'An investigation route is a governed next destination to examine. A technology/activity link can motivate '
      'contextual investigation without establishing a missing registry relationship, canonical identity failure '
      'or parser defect. A causal label requires relevant native diagnostic evidence and a reasoned human claim.','',
      'The route standards in the source packet preserve existing definitions. They do not silently change '
      'the V1–V4 validators or old gold. Label kind is recorded explicitly in new receipts: INVESTIGATION_ROUTE, '
      'VERIFIED_ROOT_CAUSE, or DEFERRED. A causal claim must cite exact native facts and declare that native '
      'evidence was accessed; validation checks citation structure, not causal truth. Semantic words alone are insufficient.','',
      'Existing definitions are NOT fully unambiguous. Human clarification is needed before importing new labels:','',
      '- TECH_ID can mean identity investigation or an established identity blocker; alias candidates do not '
      'settle full native identity resolution.',
      '- RELATIONSHIP currently describes contextual investigation, not necessarily proved missing mapping. '
      'Technology-plus-activity alone cannot settle which subsystem failed.',
      '- CAPABILITY may mean reviewing a bounded existing predicate versus diagnosing a native selector miss. '
      'Truncated candidate terms do not reveal every conjunction/exclusion.',
      '- STRUCTURAL requires demonstrated loss, while frozen views often expose only a coarse production scope '
      'code. Missing native context is uncertainty, not demonstrated parser failure.',
      '- TRUE_GAP_CANDIDATE requires sufficiently complete contract-insufficiency evidence, which bounded '
      'candidate lists do not provide. No new true-gap conclusion is inferred.',
      '- NOT_TAXONOMY_ADDRESSABLE concerns technical-taxonomy scope, not employment relevance or scoring '
      'eligibility; optional technology familiarity is not automatically professional-only.',
      '- UNKNOWN/DEFER records missing source/diagnostic information. It is not actionable coverage.','',
      'Human approval point: agree whether benchmark targets are investigation routes or verified root causes '
      'and whether the bounded evidence suffices, before separately authorizing receipt import or a benchmark. '
      'Do not extend definitions merely to achieve four categories. Any new complete predicate/native trace '
      'or parent source context outside this frozen contract belongs to a separately versioned review, not an '
      'unreported advantage over frozen model inputs.','',
      '## Actual reviewer workflow','',
      '1. A coordinator distributes only the three blinded V5 files. Recruit an unexposed reviewer per case; '
      'a person exposed to previous AI suggestions may provide assisted review, not blind independent gold.',
      '2. Review exact child source and bounded native/candidate facts. Keep source observations separate from '
      'native causal evidence. Record a justified route or deferral without considering numeric quotas.',
      '3. Copy only actually completed template entries into a separate JSON list. Fill real identity/reference, '
      'actual timezone-aware timestamp, source spans, rationale, evidence-access records and explicit exposure '
      'and sufficiency declarations. No identity/date or decision is automatically generated.',
      '4. Evidence records use kind FROZEN_INPUT, NATIVE_FROZEN_DIAGNOSTICS or FROZEN_KNOWLEDGE_CANDIDATES; '
      'reference is JobID/RequirementID and fingerprint is the exact input_fingerprint. Native support records '
      'have field and exact_value from frozen_input.resolver. A VERIFIED_ROOT_CAUSE claim requires a substantive native reason '
      'and a native-access record, but human scrutiny still determines whether it actually establishes causality.',
      '5. If parent or other outside evidence was consulted, decision_scope must be CONTEXT_AWARE_REVIEW and '
      'parent_context_consulted must be truthful. Extended evidence uses kind OUTSIDE_FROZEN_CONTRACT, actual '
      'reference and SHA256. V5 does not accept parent quotes: a separately versioned source packet is needed. '
      'Such records may document review but never enter the child-only independent benchmark.',
      '6. UNKNOWN/DEFER has acceptable_routes=[] and an explicit deferral_rationale. Leave unreviewed entries '
      'out of the submitted list. The untouched blank template is intentionally invalid as completed receipts.',
      '7. Run read-only validation first. Resolve route-definition ambiguity and inspect actual provenance '
      'before seeking separate human authorization to import eligible independent frozen receipts.','',
      '```powershell', "$env:PYTHONDONTWRITEBYTECODE='1'", "$env:LITELLM_LOCAL_MODEL_COST_MAP='True'", "$env:CAPABILITY_RAG_MODE='off'",
      '.venv\\Scripts\\python.exe -B -m scripts.prepare_unresolved_independent_review_v5 --validate-only',
      '.venv\\Scripts\\python.exe -B -m scripts.prepare_unresolved_independent_review_v5 --validate-receipts reports/completed_independent_review_v5.json',
      '```','',
      'The second command requires a JSON list written by the actual review process; that file does not exist '
      'as a completed ledger in this task. Output separates independent actionable decisions, deferrals, assisted '
      'and context-only records. It returns original V5 provenance in '
      'eligible_independent_receipts_for_separately_authorized_import. Save only that array after separate '
      'authorization; never import the whole validator object or assisted/context-only entries.','',
      'V5 prechecks bind evidence/scope and protect #32; they delegate actual receipt provenance, route/spans, '
      'timestamps, exposure and hypothetical eligibility to the existing V4 validator through an ephemeral '
      'compatibility envelope. That envelope is not saved or represented as a real V4 review. The original '
      'V5 receipts are revalidated by existing gold.versioned_manifest in memory and returned unchanged. '
      'The original reviewer version/fingerprint and label kind survive a later import. No validator can '
      'authenticate an identity, establish actual blinding, or prove a causal claim.','',
      '### Separately authorized import (NOT executed here)','',
      'After actual review and explicit import authorization, use new output paths with the existing importer:','',
      '```powershell',
      '.venv\\Scripts\\python.exe -B -m scripts.prepare_unresolved_gold_review --receipts reports/eligible_independent_v5.json --manifest-output reports/independently_reviewed_v5_manifest.json --worksheet-output reports/independently_reviewed_v5_source.md --packet-output reports/independently_reviewed_v5_audit.json --template-output reports/independently_reviewed_v5_blank.json',
      '```','',
      'Do not overwrite V1/V2. The importer-produced historical worksheet/audit still contains editorial '
      'questions: keep it with the coordinator, not future blinded reviewers. This task executes no import. '
      'Even satisfied labeling prerequisites do not authorize Qwen or establish model quality.','',
      '## Preservation and validation','',
      f"Protected prior byte hashes: {len(audit['protected_hashes'])}. Production/scoring/registry/taxonomy/JD "
      'parser versions, frozen 40 fingerprints, parent allocations, V1–V4 and Qwen artifacts remain unchanged. '
      'The four requested artifacts and additive preparation/validation code are the only new deliverables. '
      'No models, network, application database reads/writes, labels, imports, benchmark execution or publication. '
      'No commits, pushes, merges, resets, cleanup or branch switches.','',
      'Focused validation: 17 V5 tests passed in 8.684s; 25 existing V4/gold tests passed in 20.728s. '
      'An initial 16-test V5 run passed before the source-access/causal-evidence guards were tightened. '
      'Preparation and read-only --validate-only passed; three AST checks, seven new-artifact whitespace '
      'checks and git diff --check passed. No full suite, project gate or inference was run.','',
      'Files added: taxonomy_discovery/unresolved_independent_review.py; '
      'scripts/prepare_unresolved_independent_review_v5.py; tests/test_unresolved_independent_review_v5.py; '
      'docs/unresolved_independent_review_packet_v5.md; reports/unresolved_independent_review_packet_v5.json; '
      'reports/unresolved_independent_review_receipts_template_v5.json; '
      'docs/unresolved_independent_review_readiness_v5.md. No existing file was edited.','',
      'Source availability, critical-control membership and V4 coverage inventory (coordinator only):','',
      '```json',json.dumps(audit,indent=2),'```','']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--validate-only',action='store_true')
    mode.add_argument('--validate-receipts',type=Path)
    args=parser.parse_args(argv)
    packet=review.build_packet()
    if args.validate_receipts:
        value=review.validate_decisions(packet,json.loads(args.validate_receipts.read_text(encoding='utf-8')))
        print(json.dumps(value,indent=2));return value
    outputs=[review.ROOT/'docs/unresolved_independent_review_packet_v5.md',review.ROOT/'reports/unresolved_independent_review_packet_v5.json',
             review.ROOT/'reports/unresolved_independent_review_receipts_template_v5.json',review.ROOT/'docs/unresolved_independent_review_readiness_v5.md']
    if args.validate_only:
        saved=review.read(outputs[1]);review.validate_packet(saved)
        if review.read(outputs[2])!=review.template(saved):raise ValueError('Blank receipt template changed')
        if outputs[0].read_text(encoding='utf-8')!=review.markdown(saved):raise ValueError('Reviewer Markdown diverged')
        # Readiness audit is coordinator-only; rebuilding checks all preservation bytes.
        audit=review.readiness(saved)
        if outputs[3].read_text(encoding='utf-8')!=readiness_markdown(saved,audit):raise ValueError('Readiness audit drift')
        value={'validation_only_no_import':True,'prepared_pending_cases':38,'new_labels':0,
               'critical_controls_covered':audit['all_pending_critical_covered'],'protected_hashes_verified':len(audit['protected_hashes'])}
        print(json.dumps(value));return value
    if any(p.exists() for p in outputs):parser.error('Existing versioned artifacts must not be overwritten')
    audit=review.readiness(packet)
    values=[review.markdown(packet),json.dumps(packet,indent=2)+'\n',json.dumps(review.template(packet),indent=2)+'\n',readiness_markdown(packet,audit)]
    for path,value in zip(outputs,values):path.write_text(value,encoding='utf-8')
    print(json.dumps({'prepared_pending_cases':38,'new_labels':0,'protected_hashes':len(audit['protected_hashes'])}));return packet


if __name__=='__main__':main()
