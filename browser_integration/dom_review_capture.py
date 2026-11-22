"""Inline CCv2 capture; explicit exports use bounded local temporary ZIP files."""
from pathlib import Path
from io import BytesIO
import base64
import tempfile
import uuid
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
import json

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]


def javascript():
    """Reuse the existing browser-local section/hash/ZIP functions verbatim."""
    def commonjs(path, name):
        return (f"const {name}=(()=>{{const module={{exports:{{}}}};const exports=module.exports;\n"
                + path.read_text(encoding="utf-8")
                + "\nreturn module.exports;})();\n")
    return (commonjs(ROOT / "assets/vendor/html-to-image-1.11.13.js", "domImage")
            + commonjs(ROOT / "browser_extension/app_capture.js", "captureFiles")
            + (ROOT / "assets/dom_review_capture.js").read_text(encoding="utf-8"))


_HTML = """
    <div id="review-controls">
      <label>Capture name <input id="review-name" maxlength="120" value="Current application page"></label>
      <button id="review-capture" type="button">Capture Entire Current Page</button>
      <button id="review-cancel" type="button" disabled>Cancel capture</button>
      <p id="review-status" role="status" aria-live="polite">DOM-rendered capture of this session. No extension or new window. Expanded content is preserved; this is not a browser-pixel screenshot.</p>
      <ol id="review-views"></ol>
      <button id="review-export" type="button" disabled>Export Current Page Review ZIP</button>
      <div id="review-download"></div>
    </div>
    """
_CSS = """
    :host{color:var(--st-text-color);font-family:var(--st-font)}
    label,input,button{display:block;box-sizing:border-box;width:100%;margin:8px 0}
    input,button{font:inherit;padding:9px;border:1px solid #80808080;border-radius:8px;color:inherit;background:var(--st-secondary-background-color)}
    button{cursor:pointer}button:disabled{opacity:.5}p,li{font-size:14px;line-height:1.5}a{color:var(--st-primary-color)}
    """
_JS = javascript()


def _register_capture():
    return st.components.v2.component("jobai_current_page_review",html=_HTML,css=_CSS,js=_JS)


_CAPTURE = _register_capture()


def _mount_capture():
    global _CAPTURE
    try:
        return _CAPTURE(key="ui_review_current_page_v2",on_export_zip_change=lambda:None)
    except ValueError as exc:
        # AppTest/new Runtime managers can replace the registry while Python
        # modules remain cached. Rebind the identical immutable definition only.
        if str(exc) != "Component 'jobai_current_page_review' is not registered":
            raise
        _CAPTURE = _register_capture()
        return _CAPTURE(key="ui_review_current_page_v2",on_export_zip_change=lambda:None)



def validate_export(data):
    if not data or len(data)>64000000:
        raise ValueError("Capture ZIP exceeds its transfer bound")
    with ZipFile(BytesIO(data)) as archive:
        items=archive.infolist()
        if len(items)>1000 or sum(item.file_size for item in items)>180000000:
            raise ValueError("Capture ZIP exceeds its file bounds")
        for item in items:
            parts=Path(item.filename).parts
            if (not item.filename.startswith("JobAIHelper_UI_Review/")
                    or ".." in parts or "\\" in item.filename
                    or Path(item.filename).suffix not in {".png", ".json", ".md"}):
                raise ValueError("Unexpected file in capture ZIP")
        if archive.testzip() is not None:
            raise ValueError("Capture ZIP integrity check failed")
    return data


def canonical_export(data):
    """Preserve each original; reuse exact pixel-crop sectioning on app export.

    Fractional DPR can rasterize an overlap edge slightly differently in SVG.
    Re-cropping the original PNG removes that ambiguity without rescaling it.
    """
    from browser_integration.ui_review_capture import image_files
    data=validate_export(data)
    result=BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(result,"w",ZIP_DEFLATED) as target:
        manifest=json.loads(source.read("JobAIHelper_UI_Review/manifest.json"))
        for capture in manifest["captures"]:
            for panel in capture["panels"]:
                prefix="JobAIHelper_UI_Review/"+capture["directory"]+"/"+panel["name"]+"/"
                original=source.read(prefix+"full.png")
                if sha256(original).hexdigest()!=panel["sha256"]:
                    raise ValueError("Original capture hash mismatch")
                files,meta=image_files(original)
                if meta["dimensions"]!=panel["dimensions"]:
                    raise ValueError("Original capture dimensions mismatch")
                for name,blob in files.items():target.writestr(prefix+name,blob)
                panel["sections"]=meta["sections"]
        manifest["sectioning"]="Exact full-width pixel crops of each original PNG; no rescaling"
        target.writestr("JobAIHelper_UI_Review/manifest.json",json.dumps(manifest,indent=2))
        target.writestr("JobAIHelper_UI_Review/README.md",source.read("JobAIHelper_UI_Review/README.md")+b"\nApp export sections are exact crops of the original PNG. Fractional-DPR overlap rasterization differences have been removed without changing original bytes.\n")
    return validate_export(result.getvalue())


@st.cache_resource
def _local_exports():
    return {}


def save_local_export(identity,data):
    """One bounded, task-owned temporary ZIP per controller; never source files."""
    data=validate_export(data)
    directories=_local_exports()
    if identity not in directories:
        if len(directories)>=4:
            raise ValueError("Local export controller limit reached")
        directories[identity]=tempfile.TemporaryDirectory(prefix="jobai-dom-review-")
    path=Path(directories[identity].name)/"review.zip"
    path.write_bytes(data)
    return str(path)


@st.fragment
def render_dom_review_capture():
    # Capture itself emits nothing. Only explicit ZIP export triggers this
    # isolated fragment, never the application workflow or generation widgets.
    result=_mount_capture()
    if result.export_zip:
        try:
            data=canonical_export(base64.b64decode(result.export_zip,validate=True))
            st.session_state["_ui_review_dom_export_zip"]=validate_export(data)
            identity=st.session_state.setdefault("_ui_review_dom_export_id",uuid.uuid4().hex)
            st.session_state["_ui_review_dom_export_path"]=save_local_export(identity,data)
        except Exception as exc:
            st.error("Capture export rejected: "+str(exc))
    data=st.session_state.get("_ui_review_dom_export_zip")
    if data:
        st.download_button("Download current-page review ZIP via app",data,
            "JobAIHelper_Current_Page_DOM_Review.zip","application/zip",
            key="ui_review_dom_export_download",on_click="ignore")

    if data and st.session_state.get("_ui_review_dom_export_path"):
        st.caption("Saved locally on this app server: "+st.session_state["_ui_review_dom_export_path"])
