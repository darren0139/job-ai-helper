from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    text = (root / "app.py").read_text(encoding="utf-8")
    failures: list[str] = []

    if 'current_application.get("job_description")' in text:
        failures.append("Undefined current_application reference remains.")
    if "get_job_description_by_application_id(" not in text:
        failures.append("Linked JD lookup is missing.")
    if 'phase8_jd_record.get("raw_text")' not in text:
        failures.append("JD raw_text lookup is missing.")
    if 'report.get("raw_jd_text")' not in text:
        failures.append("Report raw_jd_text fallback is missing.")
    if "raw_jd_text=phase8_raw_jd_text" not in text:
        failures.append("Resolved JD text is not passed to Phase 8.")

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        print("PHASE 8 JD SOURCE CHECK: FAIL")
        return 1

    compile(text, str(root / "app.py"), "exec")
    print("PHASE 8 JD SOURCE CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
