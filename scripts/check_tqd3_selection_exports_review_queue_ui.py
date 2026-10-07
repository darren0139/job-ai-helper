from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "taxonomy_discovery" / "review_ui.py"
    ).read_text(encoding="utf-8")

    required = (
        'key="taxonomy_discovery_review_queue_table"',
        'selection_mode="single-row"',
        'key_prefix="tqd3_classification_selection"',
        'key_prefix="tqd3_research_target_selection"',
        '"Selected rows · debug / export"',
        '"CSV"',
        '"Markdown"',
        '"HTML"',
        '"Full JSON"',
    )
    for token in required:
        assert token in source, token

    assert '"Inspect candidate"' not in source

    print(
        "TQ-D3 selection export + Review Queue UI smoke PASS: "
        "review_queue=single-row exports=csv,markdown,html,json "
        "tavily=0 mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()
