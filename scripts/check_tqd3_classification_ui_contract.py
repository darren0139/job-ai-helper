from __future__ import annotations
from pathlib import Path
from taxonomy_discovery.classification import CLASSIFICATION_VERSION

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "taxonomy_discovery" / "review_ui.py"
    ).read_text(encoding="utf-8")
    for token in (
        'TQD3_UI_MARKER = "tqd3-classification-readonly-ui-v1.1.0"',
        '"TQ-D3 Classification"',
        "build_classification_report(",
        '"Research eligibility"',
        '"Affects scoring"',
        '"**Recommended next action**"',
        'key="tqd3_classification_table"',
        'selection_mode="multi-row"',
        '"TQ-D3 classes (multi-select)"',
    ):
        assert token in source, token

    start = source.index("def _render_tqd3_classification_tab(")
    end = source.index(
        "\ndef render_capability_discovery_review()", start
    )
    helper = source[start:end]
    for token in (
        "save_review(",
        "save_proposal_review(",
        "ask_local_ai",
        "st.button(",
        "st.form(",
    ):
        assert token not in helper, token

    print(
        "TQ-D3 read-only classification UI smoke PASS: "
        f"classifier={CLASSIFICATION_VERSION} "
        "ui=tqd3-classification-readonly-ui-v1.1.0 "
        "mutation_controls=0 ai_controls=0"
    )

if __name__ == "__main__":
    main()
