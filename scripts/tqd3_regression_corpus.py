"""Explicit read-only export and offline replay; never run by project gates."""
import argparse
import json
from pathlib import Path
from taxonomy_discovery.regression_corpus import export_saved_corpus, corpus_csv, compare_regression_corpus


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--db-path")
    export.add_argument("--output", required=True)
    export.add_argument("--csv")
    compare = commands.add_parser("compare")
    compare.add_argument("--corpus", required=True)
    compare.add_argument("--output", required=True)
    gaps = commands.add_parser("gaps")
    gaps.add_argument("--corpus", required=True)
    gaps.add_argument("--output", required=True)
    coverage = commands.add_parser("coverage")
    coverage.add_argument("--db-path")
    coverage.add_argument("--output", required=True)
    coverage.add_argument("--csv")
    backfill = commands.add_parser("backfill")
    backfill.add_argument("--db-path")
    backfill.add_argument("--output")
    mode = backfill.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    queue = commands.add_parser("model-queue")
    queue.add_argument("--db-path")
    queue.add_argument("--output")
    queue.add_argument("--limit", type=int, default=25)
    args = parser.parse_args(argv)
    if args.command == "export":
        result = export_saved_corpus(db_path=args.db_path)
        if args.csv:
            Path(args.csv).write_text(corpus_csv(result), encoding="utf-8")
    elif args.command == "compare":
        result = compare_regression_corpus(json.loads(Path(args.corpus).read_text(encoding="utf-8")))
    elif args.command == "gaps":
        from taxonomy_discovery.taxonomy_gaps import aggregate_corpus_gaps
        result = aggregate_corpus_gaps(json.loads(Path(args.corpus).read_text(encoding="utf-8")))
    else:
        from taxonomy_discovery.corpus_coverage import corpus_coverage, coverage_csv, deterministic_backfill, model_required_queue
        if args.command == "coverage":
            result = corpus_coverage(db_path=args.db_path)
            if args.csv:
                Path(args.csv).write_text(coverage_csv(result), encoding="utf-8")
        elif args.command == "backfill":
            result = deterministic_backfill(db_path=args.db_path, execute=args.execute)
        else:
            result = model_required_queue(db_path=args.db_path, limit=args.limit)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"command": args.command, "job_count": result.get("job_count",len(result.get("jobs", []))),
                          "gap_count": len(result.get("observations", [])), "classification_counts": result.get("classification_counts"),
                          **{k:result[k] for k in ("discovered_jobs","replayable_jobs_before","zero_cost_backfillable","model_required") if k in result}}))
    else:
        print(json.dumps(result,indent=2,ensure_ascii=False))
    return int(bool(result.get("classification_counts", {}).get("hard_regression/invariant_violation")))


if __name__ == "__main__":
    raise SystemExit(main())
