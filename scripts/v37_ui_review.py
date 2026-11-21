"""Read-only Streamlit receipt replay and local diagnostic capture."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / 'Downloads'
OUTPUT = ROOT / 'reports' / 'v37_ui_diagnostics'


def review_app() -> None:
    import streamlit as st

    from tailoring.phase8_verification_ui import _render_result
    from tailoring.phase9f_multi_project_evidence_v36 import render_multi_project_evidence
    from tailoring.phase9f_v364_decision_explorer import render_compact_decision_explorer
    from tailoring.phase9f_v37_corpus_benchmark import load_case, readonly_db

    st.set_page_config(page_title='Job AI Helper · Receipt review', layout='wide')
    with closing(readonly_db(ROOT / 'data' / 'applications.db')) as db:
        case = load_case(db, 251, ROOT)
        receipt = db.execute(
            'SELECT result_json FROM application_tailoring_verifications WHERE application_id=? '
            'AND generation_id=? ORDER BY id DESC LIMIT 1',
            (case['application_id'], case['generation_id']),
        ).fetchone()
    selection = json.loads((DOWNLOADS / 'phase9f_app_156_v365_jd_decisions.json').read_bytes())
    native = selection['native_whole_resume']
    calculation = selection['selection_calculation']
    result = {**calculation['actual_verification'], 'a_score': native['existing_score'],
              'b_score': native['proposal_score']}
    with st.sidebar:
        st.html(ROOT / 'assets' / 'streamlit_capture.html')
    st.title('Job AI Helper')
    st.caption('App 156 receipt replay · Local diagnostic session')
    decision, phase8, legacy, shadow = st.tabs(('Decision', 'Phase 8', 'Source audit', 'Shadow lead verification'))
    with decision:
        render_compact_decision_explorer(
            st, calc=calculation, result=result, proposal={}, audit=case['audit'],
            projects=case['projects'], application_id=case['application_id'], context='visual_review',
            baseline_report=case['baseline'], raw_jd_text=case['raw_jd_text'],
        )
    with phase8:
        st.subheader('Phase 8 verification and approval floor')
        if receipt:
            _render_result(json.loads(receipt['result_json']))
        else:
            st.info('Saved verification is unavailable.')
    with legacy:
        render_multi_project_evidence(st, application_id=case['application_id'],
                                      generation_id=case['generation_id'], final_audit=case['audit'])
    with shadow:
        st.subheader('Shadow fitted project sections')
        trial_path = ROOT / 'reports' / 'v37_app156_weak_ats.json'
        if not trial_path.is_file():
            st.info('Wait for a rendered trial receipt.')
            return
        trial = json.loads(trial_path.read_bytes())['factual_library']
        if not trial['native']['docx_leads_verified']:
            st.warning('No one-page lead readback was verified.')
            return
        st.caption(f"Factual Library · {trial['native']['pages']} PDF page · Exact DOCX order")
        for row in trial['native']['docx_project_order']:
            st.markdown('#### ' + row['project'])
            st.caption('Project introduction')
            st.write(row['after'][0])
            if row['after'][1:]:
                st.caption('Supporting bullets')
                for wording in row['after'][1:]:
                    st.write(wording)


def capture_review(*, phase8_only: bool = False) -> None:
    import re
    import runpy

    from playwright.sync_api import sync_playwright

    capture = runpy.run_path(str(DOWNLOADS / 'capture_streamlit_scroll_stitched_v2.py'))['_capture']
    output = ROOT / 'reports' / 'v37_readiness_ui' if phase8_only else OUTPUT
    output.mkdir(exist_ok=True)
    stats = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(timeout=15_000)
        try:
            page = browser.new_page(viewport={'width': 1366, 'height': 900})
            page.route('**/*', lambda route: route.continue_()
                       if route.request.url.startswith('http://127.0.0.1:8587/') else route.abort())
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:8587/', wait_until='domcontentloaded')
            page.get_by_text('JD Bullet Relevance Ranking', exact=True).wait_for(timeout=30_000)

            def snapshot(name):
                page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30_000)
                page.wait_for_timeout(650)
                toolbar = page.add_style_tag(content='[data-testid="stHeader"] {visibility:hidden!important}')
                try:
                    return capture(page, output / name, settle_ms=250)
                finally:
                    toolbar.evaluate('(element) => element.remove()')

            if phase8_only:
                page.get_by_role('tab', name='Phase 8', exact=True).click()
                page.get_by_text('Final check — Tailored vs Selected Base', exact=True).wait_for()
                rows = page.locator('.phase8-receipt-rows:visible')
                rows.first.wait_for()
                page.get_by_text('Score components and contribution tables', exact=True).wait_for()
                for width in (1366, 760):
                    page.set_viewport_size({'width': width, 'height': 900})
                    page.wait_for_timeout(400)
                    metrics = rows.evaluate_all("""elements => ({
                        groups: elements.length,
                        overflowing: elements.filter(e => e.scrollWidth > e.clientWidth + 1).length,
                        wrappingUnderPressure: elements.flatMap(e => [...e.querySelectorAll('h5, dd')])
                          .filter(e => e.scrollWidth > e.clientWidth + 1).length,
                        maxTextLength: Math.max(0, ...elements.flatMap(e => [...e.querySelectorAll('h5, dd')])
                          .map(e => e.textContent.length))
                    })""")
                    if metrics['overflowing'] or metrics['wrappingUnderPressure'] or metrics['maxTextLength'] < 60:
                        raise ValueError(f'Full Phase 8 rows failed width assertion at {width}: {metrics}')
                    stats[str(width)] = {**metrics, 'stitch': snapshot(f'phase8-{width}.png')}
                stats['page_errors'] = errors
                (output / 'capture-metrics.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
                print(json.dumps(stats))
                return

            visible = page.locator('[data-testid="stSelectbox"]').filter(has=page.get_by_text('Project', exact=True))
            visible.get_by_role('combobox').click()
            page.get_by_role('option', name=re.compile('^Job AI Helper')).click()
            page.get_by_text(re.compile('10 of 30 eligible wordings')).wait_for(timeout=15_000)
            page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30_000)
            evidence = page.locator('summary').filter(has_text='Added automated unit tests').first
            evidence.click()
            page.get_by_text(re.compile('Exact bullet wording|Selected Library|Added automated unit tests')).first.wait_for()
            stats['decision'] = snapshot('decision-ranking-evidence.png')

            for name, file, ready in [
                ('Phase 8', 'phase8-verification.png', 'Base no-regression approval floor'),
                ('Source audit', 'base-library-audit.png', 'Project sources and fitting'),
                ('Shadow lead verification', 'shadow-docx-leads.png', 'Shadow fitted project sections'),
            ]:
                page.get_by_role('tab', name=name, exact=True).click()
                page.get_by_text(ready, exact=True).wait_for()
                if name == 'Phase 8':
                    page.get_by_text('Final check — Tailored vs Selected Base', exact=True).wait_for()
                if name == 'Source audit':
                    page.get_by_test_id('stCheckbox').filter(has_text='Job AI Helper').locator('label').click()
                    page.get_by_text('Existing fitted résumé', exact=True).last.wait_for(timeout=10_000)
                stats[name] = snapshot(file)
            page.get_by_role('tab', name='Decision', exact=True).click()
            page.set_viewport_size({'width': 760, 'height': 900})
            page.wait_for_timeout(400)
            stats['main_panel_width'] = page.locator('[data-testid="stMain"]').evaluate(
                '(el) => ({client: el.clientWidth, scroll: el.scrollWidth})')
            stats['narrow'] = snapshot('decision-narrow.png')
            stats['page_errors'] = errors
        finally:
            browser.close()
    (output / 'capture-metrics.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
    print(json.dumps(stats))


if __name__ == '__main__':
    import sys

    if '--capture' in sys.argv:
        capture_review(phase8_only='--phase8-only' in sys.argv)
    else:
        review_app()
