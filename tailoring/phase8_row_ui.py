"""Readable, read-only rows for Phase 8 evidence and score receipts."""
from html import escape
from typing import Any


_PRIMARY_FIELDS = ('Requirement', 'JD requirement', 'requirement', 'requirement_text',
                   'Bullet', 'bullet', 'Baseline', 'Component')
_STYLE = """
<style>
.phase8-receipt-rows {max-width:100%; min-width:0; overflow-wrap:anywhere;}
.phase8-receipt-rows--scroll {max-height:34rem; overflow-y:auto; padding-inline-end:.4rem;}
.phase8-receipt-rows > article {border-bottom:1px solid var(--border-color, currentColor);
    padding:.6rem 0;}
.phase8-receipt-rows > article:last-child {border-bottom:0;}
.phase8-receipt-rows h5 {font:inherit; font-weight:600; padding:0; margin:0 0 .3rem;
    white-space:pre-wrap;}
.phase8-receipt-rows dl {display:grid; grid-template-columns:
    repeat(auto-fit, minmax(min(100%, 11rem), 1fr)); gap:.35rem .9rem; margin:0;}
.phase8-receipt-rows dt {font-size:.8rem; font-weight:600;}
.phase8-receipt-rows dd {margin:0; white-space:pre-wrap;}
</style>
"""


def render_phase8_rows(st: Any, rows: list[dict], *, label: str = 'Verification rows') -> None:
    """Render every field in reading order, including long text and exports' IDs."""
    if not rows:
        st.caption('No rows to display.')
        return

    cards = []
    for row in rows:
        primary = next((field for field in _PRIMARY_FIELDS if row.get(field)), None)
        heading = f'<h5>{escape(str(row[primary]))}</h5>' if primary else ''
        fields = []
        for key, value in row.items():
            if key == primary or value is None or value == '':
                continue
            display_key = key.replace('_', ' ').capitalize() if '_' in key else key
            fields.append(f'<div><dt>{escape(display_key)}</dt><dd>{escape(str(value))}</dd></div>')
        cards.append(f'<article>{heading}<dl>{"".join(fields)}</dl></article>')
    css = 'phase8-receipt-rows'
    focus = ''
    instruction = ''
    if len(rows) > 8:
        css += ' phase8-receipt-rows--scroll'
        focus = ' tabindex="0"'
        instruction = f'<small>{len(rows)} rows · Scroll to see all</small>'
    st.html(_STYLE + instruction + f'<section class="{css}" aria-label="{escape(label)}"{focus}>'
            + ''.join(cards) + '</section>')
