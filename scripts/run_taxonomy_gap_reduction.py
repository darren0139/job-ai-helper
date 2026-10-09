"""Thin CLI over the same native-backed assistant used by Taxonomy Maintenance."""
import argparse
import json
import os
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
from pathlib import Path
from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery import gap_reduction_assistant as assistant


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["stored", "frozen"], default="stored")
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--audit", type=Path, help="Reuse an exact current native audit snapshot")
    parser.add_argument("--max-actions", type=int, default=10)
    parser.add_argument("--research-budget", type=int, default=3)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute-plan", type=Path)
    mode.add_argument("--validate-plan", type=Path)
    parser.add_argument("--confirm-fingerprint")
    parser.add_argument("--allow-external-research", action="store_true")
    parser.add_argument("--result-id", action="append", default=[])
    parser.add_argument("--preview-research-id", action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(maintenance.REPO_ROOT / ".env", override=False)
    if args.scope == "frozen" and not args.corpus and not args.audit:
        parser.error("Frozen scope requires --corpus or --audit")
    if not args.dry_run and not args.audit:
        parser.error("Execution/validation requires the exact saved --audit and --confirm-fingerprint")
    snapshot = json.loads(args.audit.read_text(encoding="utf-8")) if args.audit else maintenance.run_corpus_audit(
        corpus=json.loads(args.corpus.read_text(encoding="utf-8")) if args.corpus else None, explicit_execution=True)
    if snapshot["manifest"]["scope"] != args.scope:
        parser.error("Audit/corpus scope differs from --scope")
    if args.dry_run:
        plan = assistant.build_plan(snapshot, max_actions=args.max_actions, research_budget=args.research_budget,
            selected_research_ids=args.preview_research_id)
        receipt = None
    else:
        plan = json.loads((args.execute_plan or args.validate_plan).read_text(encoding="utf-8"))
        receipt = (assistant.execute_plan(snapshot, plan, confirmed_fingerprint=args.confirm_fingerprint,
            explicit_execution=True, allow_external_research=args.allow_external_research) if args.execute_plan else
            assistant.validate_drafts(snapshot, plan, args.result_id, confirmed_fingerprint=args.confirm_fingerprint, explicit_execution=True))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "audit.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (args.output / "summary.md").write_text(assistant.markdown_report(plan), encoding="utf-8")
    if receipt is not None:
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"assistant_plan_fingerprint": plan["assistant_plan_fingerprint"],
        "baseline": plan["baseline"], "planned_external_calls": plan["planned_external_calls"],
        "dry_run": args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
