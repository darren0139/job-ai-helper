"""Shared truthful, read-only descriptions of saved native requirement evidence.

Initial/Selected Base starting-source receipts do not become uploaded Initial
DOCX receipts merely because the evidence is displayed in a richer table.
"""
from __future__ import annotations
from typing import Any


def requirement_explanation_rows(stable_analysis: dict[str, Any]) -> list[dict]:
    requirements = stable_analysis.get('canonical_requirements') if isinstance(stable_analysis, dict) else None
    if not isinstance(requirements, list):
        return []
    from tailoring.initial_analysis_explainer import explain_requirement
    rows, seen = [], set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            return []
        rid = str(requirement.get('requirement_id') or '')
        if not rid or rid in seen:
            return []
        seen.add(rid)
        selected = requirement.get('evidence') or []
        if not isinstance(selected, list):
            return []
        cited = [str(e.get('text') or e.get('matched_resume_term') or '').strip()
                 for e in selected if isinstance(e, dict)]
        sources = [str(e.get('source') or '').strip() for e in selected if isinstance(e, dict)]
        explanation = explain_requirement(requirement)
        rows.append({
            'Requirement': str(requirement.get('text') or ''),
            'Importance': str(requirement.get('importance') or ''),
            'Match': str(requirement.get('match_label') or 'none'),
            'Evidence strength (0–5)': requirement.get('evidence_strength'),
            'Match value': requirement.get('match_value'),
            'Selected evidence': ' | '.join(x for x in cited if x) or 'No accepted evidence selected',
            'Evidence source': ' | '.join(x for x in sources if x) or 'Unavailable',
            'How it is matched': explanation.get('explanation') or 'Not established',
            'Requirement ID': rid,
        })
    return rows


def render_saved_requirement_explanations(st: Any, stable_analysis: dict, *, origin: str) -> bool:
    """Reuse native match explanation semantics. No scoring or DB calls."""
    rows = requirement_explanation_rows(stable_analysis)
    if not rows:
        st.warning('Saved requirement explanations unavailable; no new match was inferred.')
        return False
    st.markdown('**How each JD requirement is matched**')
    st.caption(origin+' · Saved native evidence, original scores and exact JD requirement IDs. '
               'A weak/none match does not establish a confirmed applicant deficiency.')
    from tailoring.session_table_ui_v2 import render_session_dataframe
    render_session_dataframe(st, rows, hide_index=True, width='stretch')
    return True
