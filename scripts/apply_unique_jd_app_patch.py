from __future__ import annotations

import shutil
from pathlib import Path


APP_PATH = Path("app.py")
BACKUP_PATH = Path("app.py.before_unique_jd")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Could not safely patch {label}: expected exactly one match, found {count}. "
            "Your app.py may differ from the repository version this patch was built for."
        )
    return text.replace(old, new, 1)


def main() -> None:
    if not APP_PATH.exists():
        raise FileNotFoundError("Run this command from the Job-AI-Helper repository root.")

    text = APP_PATH.read_text(encoding="utf-8")
    if "jd_save_result = save_or_link_job_description_for_application(" in text:
        print("app.py already contains the unique-JD integration; no changes made.")
        return

    old_import = '''from database.jd_library_manager import (
    init_jd_library,
    save_or_update_job_description_for_application,
    get_recent_job_descriptions,
    get_job_description_by_id,
    get_job_description_by_application_id,
    delete_job_description,
    delete_job_description_by_application_id,
)
'''
    new_import = '''from database.jd_library_manager import (
    init_jd_library,
    save_or_link_job_description_for_application,
    save_or_update_job_description_for_application,
    get_recent_job_descriptions,
    get_job_description_by_id,
    get_job_description_by_application_id,
    delete_job_description,
    delete_job_description_by_application_id,
    unlink_job_description_from_application,
)
'''

    old_delete = '''                            # Also remove the linked job description from the RAG library.
                            try:
                                linked_jd = get_job_description_by_application_id(app_id)
                                if linked_jd:
                                    delete_job_description_from_chroma(int(linked_jd["id"]))
                                    delete_job_description_by_application_id(app_id)
                            except Exception:
                                # Deleting the application session should still work even if RAG cleanup fails.
                                pass
'''
    new_delete = '''                            # Remove only this session's link to the canonical JD.
                            # Delete shared SQLite/Chroma data only when no sessions remain.
                            try:
                                unlink_result = unlink_job_description_from_application(app_id)
                                if unlink_result.get("deleted_canonical_job"):
                                    delete_job_description_from_chroma(
                                        unlink_result.get("job_description_id"),
                                        canonical_jd_id=unlink_result.get("canonical_jd_id"),
                                    )
                            except Exception:
                                # Deleting the application session should still work even if RAG cleanup fails.
                                pass
'''

    old_save = '''                jd_library_id = save_or_update_job_description_for_application(
                    application_id=application_id,
                    raw_text=jd_text,
                    jd_profile=jd_profile_for_library,
                    title=jd_profile_for_library.get("job_title", ""),
                    company=jd_profile_for_library.get("company", ""),
                    source_type="application_session",
                    source_url="",
                )

                chunk_count = index_job_description_to_chroma(jd_library_id)
                jd_library_message = f" Indexed JD into Chroma with {chunk_count} chunks."
'''
    new_save = '''                jd_save_result = save_or_link_job_description_for_application(
                    application_id=application_id,
                    raw_text=jd_text,
                    jd_profile=jd_profile_for_library,
                    title=jd_profile_for_library.get("job_title", ""),
                    company=jd_profile_for_library.get("company", ""),
                    location=jd_profile_for_library.get("location", ""),
                    source_type="application_session",
                    source_url="",
                )

                orphaned_canonical_id = jd_save_result.get(
                    "orphaned_canonical_jd_id"
                )
                if orphaned_canonical_id:
                    delete_job_description_from_chroma(
                        jd_save_result.get("orphaned_job_description_id"),
                        canonical_jd_id=orphaned_canonical_id,
                    )

                if jd_save_result.get("needs_chroma_index"):
                    chunk_count = index_job_description_to_chroma(
                        int(jd_save_result["job_description_id"])
                    )
                    jd_library_message = (
                        f" Indexed canonical JD into Chroma with {chunk_count} chunks."
                    )
                else:
                    jd_library_message = (
                        " Reused the existing canonical JD; no duplicate embeddings were created."
                    )
'''

    updated = replace_once(text, old_import, new_import, "JD imports")
    updated = replace_once(updated, old_delete, new_delete, "session deletion")
    updated = replace_once(updated, old_save, new_save, "JD save/index flow")

    if not BACKUP_PATH.exists():
        shutil.copy2(APP_PATH, BACKUP_PATH)
    APP_PATH.write_text(updated, encoding="utf-8")
    print(f"Patched {APP_PATH}.")
    print(f"Backup: {BACKUP_PATH}")


if __name__ == "__main__":
    main()
