from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from database import jd_library_manager as jd_manager


def backup_database() -> Path | None:
    source = jd_manager.DB_PATH
    if not source.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = source.with_name(f"{source.stem}_before_jd_identity_{timestamp}{source.suffix}")
    shutil.copy2(source, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate existing JD rows to canonical IDs, versions and session links."
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the automatic SQLite backup.",
    )
    parser.add_argument(
        "--rebuild-chroma",
        action="store_true",
        help=(
            "Clear and rebuild Chroma after migration. This creates embeddings and "
            "may use paid API tokens."
        ),
    )
    args = parser.parse_args()

    if not args.no_backup:
        backup_path = backup_database()
        if backup_path is None:
            print("No existing database found; no backup was needed.")
        else:
            print(f"Database backup: {backup_path}")

    jd_manager.init_jd_library()
    stats = jd_manager.get_jd_library_stats()
    print("Migration complete.")
    print(f"  Canonical jobs: {stats['canonical_jobs']}")
    print(f"  Source versions: {stats['versions']}")
    print(f"  Session links: {stats['session_links']}")

    if args.rebuild_chroma:
        from rag.jd_chroma_rag import rebuild_chroma_index

        chunks = rebuild_chroma_index()
        print(f"Chroma rebuilt with {chunks} canonical JD chunks.")
    else:
        print(
            "Chroma was not rebuilt. Run again with --rebuild-chroma after the "
            "database migration has been reviewed."
        )


if __name__ == "__main__":
    main()
