"""Read-only multi-project Decision Explorer for actual fitted-source receipts.

Allows inspecting several projects at once. Checkbox state never changes the
saved generation, candidate pool, fitting, or approval.
"""
from __future__ import annotations
from typing import Any


def project_checkboxes(st, names, *, key, default=(), actions=False):
    """Shared, inspection-only checkbox pattern with durable scoped identities."""
    from hashlib import sha256
    from tailoring.phase9f_navigation_state import navigation_checkbox, STATE_KEY
    keys = {name:key+'_project_'+sha256(name.encode('utf-8')).hexdigest()[:16] for name in names}
    def set_all(value):
        preferences = dict(st.session_state.get(STATE_KEY) or {})
        for widget_key in keys.values():
            st.session_state[widget_key] = value
            preferences[widget_key] = {'scope':'', 'value':value}
        st.session_state[STATE_KEY] = preferences
    if actions:
        left, right = st.columns(2)
        left.button('Select all', key=key+'_all', on_click=set_all, args=(True,))
        right.button('Clear all', key=key+'_none', on_click=set_all, args=(False,))
    return [name for name in names if navigation_checkbox(st, name, key=keys[name], value=name in default)]


def comparison_rows(final_audit:dict)->list[dict]:
    """Pure table rows; read-only and deterministic from verified DOCX audit."""
    if not isinstance(final_audit,dict) or final_audit.get('verified') is not True:
        return []
    out=[]
    for project in final_audit.get('projects') or []:
        if not isinstance(project,dict):continue
        name=str(project.get('project') or '').strip()
        if not name: continue
        out.append({'Inspect':False,'Project':name,
            'Base':len(project.get('base') or []),
            'Library':len(project.get('library') or []),
            'Final DOCX':len(project.get('final') or []),
            'Fitting actions':len(project.get('changes') or [])})
    return out


def render_multi_project_evidence(st:Any,*,application_id:int,generation_id:str,
                                   final_audit:dict)->None:
    """Select projects and read complete wording in the optional fitting audit."""
    rows=comparison_rows(final_audit)
    st.markdown('#### Project sources and fitting')
    st.caption('Select projects to inspect their source bullets and fitted wording.')
    if not rows:
        st.caption('Verified final DOCX project audit is unavailable.')
        return
    # Each row uses a native Streamlit checkbox rather than st.data_editor.
    # A data_editor may require a cell-focus click before an edit, and mirroring
    # its edited values into the input DataFrame creates competing state.
    # Native keyed checkboxes toggle directly on the first click.
    from hashlib import sha256
    key=f'phase9f_v36_multi_projects_{int(application_id)}_{generation_id}'
    wanted=project_checkboxes(st, [row['Project'] for row in rows], key=key)
    # Legacy read-only summary state is retained for compatibility; it is not
    # fed back into checkbox inputs or used to override widget-owned state.
    st.session_state[key]=wanted
    if not wanted:
        return
    by_name={str(item.get('project')):item for item in final_audit['projects'] if isinstance(item,dict)}
    for name in wanted:
        project=by_name.get(name)
        if project is None:continue
        st.markdown('**'+name+'**')
        for label, field, fallback in (
            ('Base bullets', 'base', 'Base Resume bullet'),
            ('Library bullets', 'library', 'Evidence Library bullet'),
            ('Existing fitted résumé', 'final', 'Final DOCX'),
        ):
            st.caption(label)
            for item in project.get(field) or []:
                st.write('• ' + str(item.get('text') or item.get(fallback) or ''))
                if field == 'final' and item.get('lineage'):
                    st.caption(item['lineage'])
        if project.get('changes'):
            with st.expander('Recorded fitter actions — '+name, expanded=False):
                for item in project['changes']:
                    st.write(item.get('action') or 'Fitting action')
                    if item.get('text'):
                        st.write(item['text'])
                    st.caption(item.get('reason') or 'Reason unavailable')
