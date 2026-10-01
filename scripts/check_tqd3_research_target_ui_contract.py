from __future__ import annotations

from pathlib import Path

from taxonomy_discovery.research_targets import (
    RESEARCH_TARGET_VERSION,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "taxonomy_discovery" / "review_ui.py"
    ).read_text(encoding="utf-8")

    for token in (
        'TQD3_RESEARCH_TARGET_UI_MARKER = '
        '"tqd3-research-target-readonly-ui-v1.2.0"',
        '"Research Targets"',
        "build_research_target_report(",
        '"Tavily eligible"',
        '"**Research question**"',
        'TQD3_RESEARCH_TARGET_SELECTION_UI_MARKER = '
        '"tqd3-research-target-clickable-table-v1.2.2"',
        'key="tqd3_research_target_table"',
        'on_select="rerun"',
        'selection_mode="multi-row"',
        '"Target types (multi-select)"',
    ):
        assert token in source, token

    assert '"Inspect research target"' not in source
    assert 'key="tqd3_research_target_inspector"' not in source

    start = source.index(
        "def _render_tqd3_research_targets_tab("
    )
    end = source.find("\ndef ", start + 1)
    assert end > start, "research-target helper end boundary"
    helper = source[start:end]
    for token in (
        "save_review(",
        "save_proposal_review(",
        "ask_local_ai",
        "st.button(",
        "st.form(",
        "research_selected_targets_with_tavily(",
    ):
        assert token not in helper, token

    assert (
        "_render_tqd3_tavily_research_controls(selected_targets)"
        in helper
    )

    print(
        "TQ-D3 research-target UI smoke PASS: "
        f"targets={RESEARCH_TARGET_VERSION} "
        "network=delegated_explicit "
        "direct_mutation_controls=0 direct_ai_controls=0"
    )


if __name__ == "__main__":
    main()
