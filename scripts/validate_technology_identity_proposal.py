"""Headless identity review using the same service as Taxonomy Maintenance."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery import technology_identity_remediation as remediation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--scope", choices=["stored", "frozen"], default="stored")
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(maintenance.REPO_ROOT / ".env", override=False)
    if args.scope == "frozen" and not args.audit and not args.corpus:
        parser.error("Frozen scope requires --audit or --corpus")
    snapshot = json.loads(args.audit.read_text(encoding="utf-8")) if args.audit else maintenance.run_corpus_audit(
        explicit_execution=True, corpus=json.loads(args.corpus.read_text(encoding="utf-8")) if args.corpus else None)
    if snapshot["manifest"]["scope"] != args.scope:
        parser.error("Audit scope differs from requested scope")
    proposal = remediation.prepare_identity_proposal(snapshot, args.candidate_id, explicit_execution=True)
    report = remediation.validate_identity_proposal(snapshot, proposal, explicit_execution=True)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("audit", snapshot), ("proposal", proposal), ("validation", report)):
        (args.output / (name + ".json")).write_text(json.dumps(value, indent=2), encoding="utf-8")
    (args.output / "summary.md").write_text(remediation.markdown_report(proposal, report), encoding="utf-8")
    print(json.dumps({"validation_status": report["validation_status"], "estimated_impact": report["estimated_impact"],
        "validated_impact": report["validated_impact"], "baseline": report["baseline"], "temporary_overlay": report["temporary_overlay"]}))
    return 1 if report["unexpected_changes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
