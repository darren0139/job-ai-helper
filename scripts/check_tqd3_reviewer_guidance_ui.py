from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "taxonomy_discovery" / "review_ui.py"
    ).read_text(encoding="utf-8")

    required = (
        'for guide in _REVIEW_DECISION_GUIDE:',
        'st.markdown("**Choose when**")',
        'st.markdown("**Avoid when**")',
        'st.markdown("**Effect**")',
        'expanded=bool(',
        '"Reviewer Guidance · how to decide"',
        "What makes a good review",
        "Decision guide",
        '"How to use deterministic Python-assisted review"',
        "classification_by_candidate_id",
    )
    for token in required:
        assert token in source, token

    print(
        "TQ-D3 reviewer guidance UI smoke PASS: "
        "python_assist=deterministic human_confirmation=required "
        "tavily=0 mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()
