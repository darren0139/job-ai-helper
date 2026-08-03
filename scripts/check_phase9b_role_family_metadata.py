from __future__ import annotations

from tailoring.phase9b_role_family import (
    build_default_candidate_name,
    suggest_role_family,
)


def main() -> int:
    ai = suggest_role_family(
        {
            "jd_profile": {
                "job_title": (
                    "Junior AI and Full-Stack Software Engineer"
                )
            }
        }
    )
    game = suggest_role_family(
        {
            "jd_profile": {
                "job_title": "Associate, Configuration & QA"
            }
        }
    )
    name = build_default_candidate_name(
        application_id=94,
        generation_id="ac8191407bea4aecac63b1330729e5ec",
        role_family=ai["role_family"],
    )

    passed = (
        ai["role_family"]
        == "AI & Full-Stack Software Engineering"
        and game["role_family"]
        == "Game Operations, Configuration & QA"
        and name
        == "AI & Full-Stack — App 94 — ac819140"
    )
    print("Application 94 family:", ai["role_family"])
    print("Application 91 family:", game["role_family"])
    print("Generated candidate name:", name)
    print(
        "PHASE 9B ROLE FAMILY + METADATA REFINEMENT:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
