"""Isolated zero-cost Streamlit harness for Phase 9F-B."""

from __future__ import annotations

import copy

import fitz
import streamlit as st

from tailoring import phase9f_starting_source_ranking_ui as ui
from tests.test_phase9f_starting_source_ranking import (
    make_base,
    make_blueprint,
    make_exact_jd,
)


exact_jd = make_exact_jd()
base, base_artifact = make_base(strong=False)
same_family = make_blueprint(
    strong=True,
    role_family_id="ai_fullstack_software_engineering",
    role_family_label="AI & Full-Stack Software Engineering",
    marker="streamlit-same",
)
additional = make_blueprint(
    strong=False,
    role_family_id="backend_cloud_software_engineering",
    role_family_label="Backend & Cloud Software Engineering",
    marker="streamlit-added",
)

st.set_page_config(page_title="Phase 9F-B Test", layout="wide")
changed_scope = st.checkbox(
    "Test changed source scope",
    key="phase9f_b_test_changed_scope",
)
missing_source_application = st.checkbox(
    "Test missing source Application provenance",
    key="phase9f_b_test_missing_source_application",
)


def _test_scope():
    blueprints = [copy.deepcopy(same_family)]
    if changed_scope:
        blueprints.append(copy.deepcopy(additional))
    return copy.deepcopy(base), copy.deepcopy(base_artifact), blueprints


ui._load_immutable_source_scope = _test_scope
ui.get_global_master_resume_artifact = lambda *_args, **_kwargs: None
ui.get_application_by_id = lambda application_id: {
    "report": {"overall_score": 74},
    "cover_letter": "",
    "resume_filename": "source.docx",
} if int(application_id) == 94 else None


def _test_provenance(blueprint):
    source_resolved = not missing_source_application
    candidate = blueprint.get("candidate_id")
    evaluation = blueprint.get("evaluation_id")
    return {
        "chain_status": "resolved" if source_resolved else "incomplete",
        "blueprint_identity": {
            "display_name": blueprint.get("display_name"),
            "blueprint_id": blueprint.get("blueprint_id"),
            "blueprint_fingerprint": blueprint.get("blueprint_fingerprint"),
            "version_number": blueprint.get("version_number"),
            "status": blueprint.get("status"),
        },
        "blueprint_role_family": {
            "role_family_id": blueprint.get("role_family_id"),
            "role_family_label": blueprint.get("role_family_label"),
        },
        "source_application": {
            "resolved": source_resolved,
            "application_id": 94,
            "session_name": "Synthetic source Application",
        },
        "source_jd": {
            "resolved": True,
            "exact_identity_match": True,
            "canonical_jd_id": "source-jd",
            "source_version_id": "source-jd-version",
        },
        "source_resume_result_or_generation": {
            "source_generation": {
                "resolved": True,
                "approval_resolved": True,
                "fit_identity_match": True,
                "generation_id": "source-generation",
            },
            "immutable_artifact_hash_records": [],
        },
        "phase8_verification": {
            "resolved": True,
            "blueprint_ready": True,
            "verification_id": "phase8-verification",
        },
        "phase9b_candidate": {
            "resolved": True,
            "candidate_id": candidate,
            "candidate_fingerprint": blueprint.get("candidate_fingerprint"),
            "score_summary": {"approved_tailored_score": 92},
        },
        "phase9c_evaluation": {
            "resolved": True,
            "evaluation_id": evaluation,
            "evaluation_fingerprint": blueprint.get(
                "evaluation_fingerprint"
            ),
        },
        "phase9d_approval": {"status": "active"},
        "fingerprints": {
            "blueprint_fingerprint": blueprint.get("blueprint_fingerprint")
        },
        "missing_provenance_links": (
            [] if source_resolved else ["source_application"]
        ),
        "zero_cost_diagnostics": {
            "model_call_count": 0,
            "embedding_call_count": 0,
            "chroma_read_count": 0,
            "chroma_write_count": 0,
            "persistence_write_count": 0,
        },
    }


ui.load_blueprint_provenance_read_only = _test_provenance


def _pdf_bytes() -> bytes:
    document = fitz.open()
    try:
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 72), "Immutable Phase 9F-B source preview")
        return document.tobytes()
    finally:
        document.close()


PREVIEW_PDF = _pdf_bytes()


def _test_artifacts(*, ranked_candidate, **_kwargs):
    source_id = str(ranked_candidate.get("source_id") or "source")
    return {
        "source_type": ranked_candidate.get("source_type"),
        "source_id": source_id,
        "preview_pdf": {
            "artifact_type": "pdf",
            "artifact_kind": "approved_fitted_source",
            "filename": f"{source_id[:8]}.pdf",
            "media_type": "application/pdf",
            "artifact_bytes": PREVIEW_PDF,
            "provenance_label": "Immutable test source PDF",
            "verification_method": "synthetic_read_only_verification",
            "sha256": "synthetic-pdf-sha256",
            "byte_size": len(PREVIEW_PDF),
        },
        "artifacts": [
            {
                "artifact_type": "pdf",
                "artifact_kind": "approved_fitted_source",
                "filename": f"{source_id[:8]}.pdf",
                "media_type": "application/pdf",
                "artifact_bytes": PREVIEW_PDF,
                "provenance_label": "Immutable test source PDF",
                "verification_method": "synthetic_read_only_verification",
                "sha256": "synthetic-pdf-sha256",
                "byte_size": len(PREVIEW_PDF),
            },
            {
                "artifact_type": "docx",
                "artifact_kind": "approved_fitted_source",
                "filename": f"{source_id[:8]}.docx",
                "media_type": (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                "artifact_bytes": b"immutable-test-docx",
                "provenance_label": "Immutable test source DOCX",
                "verification_method": "synthetic_read_only_verification",
                "sha256": "synthetic-docx-sha256",
                "byte_size": len(b"immutable-test-docx"),
            },
        ],
    }


ui.resolve_starting_source_artifacts = _test_artifacts
ui.render_phase9f_starting_source_ranking(exact_jd)
st.markdown("MODEL_CALLS=0")
st.markdown("EMBEDDING_CALLS=0")
st.markdown("CHROMA_READS=0")
st.markdown("CHROMA_WRITES=0")
st.markdown("PERSISTENCE_WRITES=0")
