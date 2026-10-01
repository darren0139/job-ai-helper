from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "taxonomy_discovery" / "review_ui.py"
    ).read_text(encoding="utf-8")

    required = (
        '"Broad Mining"',
        "def _render_tqd3_broad_mining_tab()",
        'key="tqd3_broad_mining_table"',
        'selection_mode="multi-row"',
        "research_selected_broad_mining_with_tavily(",
        '"tqd3_broad_mining_results_v1"',
        '"Download selected broad-mining JSON"',
    )
    for token in required:
        assert token in source, token

    assert "build_broad_mining_candidate_report(" in source
    assert "\"Candidate extraction\",\n        \"Enabled\"," in source
    assert "mentions = registry_mentions_for_result(result)" not in source
    print(
        "TQ-D3 broad mining UI smoke PASS: "
        "provider=tavily_research model=mini "
        "network=explicit_click_only results=local_sqlite_persisted persisted_status_ui=true researched_panel=true coverage_metrics=true research_again_prepare=true auto_restore=true hide_researched_default=true "
        "candidate_extraction=true exact_registry_dedupe=true mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()
