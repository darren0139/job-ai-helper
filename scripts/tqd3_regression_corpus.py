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
    args = parser.parse_args(argv)
    if args.command == "export":
        result = export_saved_corpus(db_path=args.db_path)
        if args.csv:
            Path(args.csv).write_text(corpus_csv(result), encoding="utf-8")
    elif args.command == "compare":
        result = compare_regression_corpus(json.loads(Path(args.corpus).read_text(encoding="utf-8")))
    else:
        from taxonomy_discovery.taxonomy_gaps import aggregate_corpus_gaps
        result = aggregate_corpus_gaps(json.loads(Path(args.corpus).read_text(encoding="utf-8")))
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"command": args.command, "job_count": len(result.get("jobs", [])), "gap_count": len(result.get("observations", [])), "classification_counts": result.get("classification_counts")}))
    return int(bool(result.get("classification_counts", {}).get("hard_regression/invariant_violation")))


if __name__ == "__main__":
    raise SystemExit(main())
