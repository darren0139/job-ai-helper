from __future__ import annotations

from database.jd_library_manager import (
    get_all_job_descriptions,
    get_application_job_links,
    get_jd_library_stats,
    get_job_description_versions,
    init_jd_library,
)


def main() -> None:
    init_jd_library()
    stats = get_jd_library_stats()
    print("JD library statistics")
    print(f"  canonical_jobs={stats['canonical_jobs']}")
    print(f"  versions={stats['versions']}")
    print(f"  session_links={stats['session_links']}")
    print()

    for job in get_all_job_descriptions(limit=500):
        versions = get_job_description_versions(int(job["id"]))
        print(
            f"#{job['id']} {job['company']} — {job['title']} "
            f"({job.get('location') or 'location unknown'})"
        )
        print(f"  canonical={job['canonical_jd_id']}")
        print(f"  latest_version={job['source_version_id']}")
        print(f"  linked_sessions={job.get('application_ids', [])}")
        print(f"  stored_versions={len(versions)}")

    print("\nApplication links")
    for link in get_application_job_links():
        print(
            f"  application={link['application_id']} -> "
            f"job={link['job_description_id']} version={link['source_version_id']}"
        )


if __name__ == "__main__":
    main()
