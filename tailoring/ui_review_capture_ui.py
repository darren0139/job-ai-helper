"""Controller sidebar for a separate session-owned Firefox window."""
import uuid
import streamlit as st
from browser_integration.ui_review_capture import CaptureSession


@st.cache_resource
def _sessions():return {}


def render_ui_review_capture():
    st.markdown('**UI Review Capture**')
    st.caption('Controls a NEW Firefox window, not your personal tab. Navigate and expand content there; return here to capture it. No extension required. End closes that window; collected images remain available until this controller session is discarded.')
    identity=st.session_state.setdefault('ui_review_capture_id',uuid.uuid4().hex)
    sessions=_sessions()
    session=sessions.get(identity)
    url=st.text_input('Local app URL',value='http://localhost:8501',key='ui_review_url')
    if st.button('Start Capture Session',disabled=bool(session and session.active),key='ui_review_start'):
        try:
            if session is None:
                if len(sessions)>=4:raise RuntimeError('Capture service has four controller sessions; restart the app to release abandoned controllers.')
                session=CaptureSession();sessions[identity]=session
            session.start(url)
        except Exception as exc:st.error('Firefox startup failed: '+str(exc))
    if session is None:return
    name=st.text_input('Capture Name',value='Application view',max_chars=120,key='ui_review_name')
    notes=st.text_area('Notes',max_chars=2000,key='ui_review_notes')
    visible=st.checkbox('Visible area only',key='ui_review_visible')
    sidebar=st.checkbox('Include sidebar separately',key='ui_review_sidebar')
    if st.button('Capture Current View',disabled=not session.active,key='ui_review_capture'):
        try:
            with st.spinner('Capturing controlled Firefox…'):session.capture(name,notes,visible,sidebar)
            st.session_state.pop('ui_review_zip',None)
            st.success('Full-resolution image and readable sections saved.')
        except Exception as exc:st.error('Capture failed: '+str(exc))
    st.markdown('**Captured Views**')
    if session.views:
        chosen=st.selectbox('Captured view',[v['id'] for v in session.views],format_func=lambda k:next(f"{v['sequence']:02} · {v['name']} · {v['dimensions']}" for v in session.views if v['id']==k),key='ui_review_chosen')
        if st.button('Retake Capture',disabled=not session.active,key='ui_review_retake'):
            try:session.capture(name,notes,visible,sidebar,replace=chosen);st.session_state.pop('ui_review_zip',None);st.rerun()
            except Exception as exc:st.error('Retake failed: '+str(exc))
        if st.button('Remove Capture',key='ui_review_remove'):session.remove(chosen);st.session_state.pop('ui_review_zip',None);st.rerun()
        if st.button('Finish & Export Review ZIP',key='ui_review_finish'):st.session_state['ui_review_zip']=session.export()
    if st.session_state.get('ui_review_zip'):
        st.download_button('Download UI Review ZIP',st.session_state['ui_review_zip'],'JobAIHelper_UI_Review.zip','application/zip',key='ui_review_download')
    if st.button('End Capture Session',disabled=not session.active,key='ui_review_end'):
        try:session.end();st.rerun()
        except Exception as exc:st.error(str(exc))
