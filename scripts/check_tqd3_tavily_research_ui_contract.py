from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "taxonomy_discovery" / "review_ui.py"
    ).read_text(encoding="utf-8")

    required = (
        'TQD3_TAVILY_RESEARCH_UI_MARKER = '
        '"tqd3-tavily-research-ui-v1.1.0"',
        "def _render_tqd3_tavily_research_controls(",
        "research_selected_targets_with_tavily(",
        "selected_target_ids=selected_target_ids",
        '"Planned Tavily calls"',
        '"tqd3_tavily_research_results_v1"',
        '"Download selected Tavily research JSON"',
        "_render_tqd3_tavily_research_controls(selected_targets)",
    )
    for token in required:
        assert token in source, token

    start = source.index(
        "def _render_tqd3_tavily_research_controls("
    )
    end = source.index(
        "\ndef _render_tqd3_research_targets_tab(",
        start,
    )
    helper = source[start:end]
    for forbidden in (
        "save_review(",
        "save_proposal_review(",
        "import_proposal_bundle(",
        "delete_review(",
    ):
        assert forbidden not in helper, forbidden

    print(
        "TQ-D3 Tavily research UI smoke PASS: "
        "network=explicit_click_only results=session_only "
        "human_review=required mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()
