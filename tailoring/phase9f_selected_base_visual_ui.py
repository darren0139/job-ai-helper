"""Read-only visual preview of the exact Phase 9F-D confirmed starting source.

Only immutable, hash-verified artifacts from the current exact Phase 9F-D
binding are eligible. No source selection, JD analysis, rescoring or DB writes.
"""
from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class SelectedBasePreviewUnavailable(ValueError):
    """The exact confirmed visual artifact cannot be authenticated or rendered."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _verified_artifact_rows(source_bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Independently verify the source resolver's immutable artifact hashes."""
    rows = source_bundle.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise SelectedBasePreviewUnavailable("The confirmed source has no saved artifacts.")
    verified: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SelectedBasePreviewUnavailable("Invalid confirmed source artifact record.")
        kind = _clean(row.get("artifact_type")).lower()
        if kind not in {"pdf", "docx"}:
            continue
        if kind in verified:
            raise SelectedBasePreviewUnavailable("The confirmed source has ambiguous artifact formats.")
        raw = row.get("artifact_bytes")
        if not isinstance(raw, bytes) or not raw:
            raise SelectedBasePreviewUnavailable("Confirmed source artifact bytes are missing.")
        if (hashlib.sha256(raw).hexdigest() != _clean(row.get("sha256"))
                or len(raw) != int(row.get("byte_size") or -1)):
            raise SelectedBasePreviewUnavailable("The confirmed source artifact failed SHA-256 verification.")
        if (kind == "pdf" and not raw.startswith(b"%PDF")) or (kind == "docx" and not raw.startswith(b"PK")):
            raise SelectedBasePreviewUnavailable("The confirmed source artifact format is invalid.")
        verified[kind] = row
    if not verified:
        raise SelectedBasePreviewUnavailable("The confirmed source has no DOCX or PDF artifact.")
    return verified


def validate_bound_visual_source(
    *,
    confirmation: dict[str, Any],
    decision: dict[str, Any],
    selected: dict[str, Any],
    bundle: dict[str, Any],
    execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind visible bytes to this confirmation, not a current/latest résumé."""
    if not all(isinstance(v, dict) for v in (confirmation, decision, selected, bundle)):
        raise SelectedBasePreviewUnavailable("Saved confirmation, source or decision missing.")
    starting = decision.get("starting_snapshot") or {}
    source_identity = starting.get("source_identity") or {}
    if (
        not _clean(confirmation.get("confirmation_id"))
        or _clean(confirmation.get("phase9e_decision_fingerprint")) != _clean(decision.get("decision_fingerprint"))
        or _clean(confirmation.get("starting_snapshot_fingerprint")) != _clean(starting.get("starting_snapshot_fingerprint"))
        or not _clean(decision.get("decision_fingerprint"))
        or not _clean(starting.get("starting_snapshot_fingerprint"))
    ):
        raise SelectedBasePreviewUnavailable("The current Phase 9F-D decision does not match its confirmation.")
    for field in ("source_type", "source_id", "source_fingerprint", "source_content_fingerprint", "normalized_source_fingerprint"):
        if (not _clean(selected.get(field))
                or _clean(source_identity.get(field)) != _clean(selected.get(field))):
            raise SelectedBasePreviewUnavailable("Selected source identity mismatch: " + field)
    if _clean(bundle.get("source_type")) != _clean(selected.get("source_type")):
        raise SelectedBasePreviewUnavailable("Resolved artifact source type does not match the confirmed base.")
    artifacts = _verified_artifact_rows(bundle)
    if isinstance(execution, dict) and execution:
        expected = execution.get("source_artifact") or {}
        expected_hash = _clean(expected.get("sha256"))
        if expected_hash:
            docx = artifacts.get("docx")
            if (docx is None or expected_hash != _clean(docx.get("sha256"))
                    or int(expected.get("byte_size") or -1) != len(docx["artifact_bytes"])):
                raise SelectedBasePreviewUnavailable("Preview source differs from the frozen Phase 9F fitting source.")
    chosen = artifacts.get("pdf") or artifacts.get("docx")
    return {
        "format": _clean(chosen.get("artifact_type")).lower(),
        "source_bytes": bytes(chosen["artifact_bytes"]),
        "sha256": _clean(chosen.get("sha256")),
        "source_name": _clean(selected.get("source_display_name")) or "Selected Base",
        "source_type": _clean(selected.get("source_type")),
        "confirmation_id": _clean(confirmation.get("confirmation_id")),
        "provenance_label": _clean(chosen.get("provenance_label")),
    }


def has_confirmed_selected_base(application_id: int) -> bool:
    """Cheap existence gate; do not affect the normal before/after tabs."""
    try:
        from database.phase9f_application_confirmation_manager import get_phase9f_application_confirmation
        return isinstance(get_phase9f_application_confirmation(int(application_id)), dict)
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        return False


def load_confirmed_visual_artifact(application_id: int) -> dict[str, Any]:
    """Resolve exact D-bound source; never use latest master or arbitrary paths."""
    from database.phase9f_application_confirmation_manager import get_phase9f_application_confirmation
    from database.application_blueprint_manager import get_current_application_blueprint_decision
    from database.phase9f_application_execution_manager import resolve_exact_phase9f_d_source
    from database.phase9f_tailoring_execution_manager import get_phase9f_tailoring_execution
    from tailoring.phase9f_session_handoff import confirmed_source_view

    confirmation = get_phase9f_application_confirmation(int(application_id))
    view = confirmed_source_view(confirmation)
    if not isinstance(view, dict):
        raise SelectedBasePreviewUnavailable("No confirmed Phase 9F starting source is saved for this session.")
    decision = get_current_application_blueprint_decision(int(application_id), validate_current_scope=False)
    if not isinstance(decision, dict):
        raise SelectedBasePreviewUnavailable("No current Phase 9E source binding is available.")
    if (
        decision.get("scope_activation_status") != "active"
        or _clean(decision.get("decision_fingerprint")) != _clean(confirmation.get("phase9e_decision_fingerprint"))
    ):
        raise SelectedBasePreviewUnavailable("The currently active Tailoring Base no longer matches the confirmation.")
    bundle = resolve_exact_phase9f_d_source(
        decision=decision, confirmation=confirmation,
        require_reuse_page_proof=False,
    )
    execution = get_phase9f_tailoring_execution(int(application_id))
    return validate_bound_visual_source(
        confirmation=confirmation, decision=decision, selected=view["selected"],
        bundle=bundle, execution=execution,
    )


def render_verified_source_pdf(artifact: dict[str, Any]) -> tuple[str, bytes, str]:
    """Rasterize a verified PDF, or convert exact DOCX in disposable temp space."""
    from resume_builder.docx_projects_skills_replacer import (
        pdf_to_preview_html, _find_libreoffice_executable,
    )
    raw = artifact["source_bytes"]
    fmt = artifact["format"]
    with tempfile.TemporaryDirectory(prefix="phase9f_selected_base_visual_") as name:
        folder = Path(name)
        if fmt == "pdf":
            pdf_path = folder / "confirmed_selected_base.pdf"
            pdf_path.write_bytes(raw)
            method = "Stored immutable source PDF"
        elif fmt == "docx":
            soffice = _find_libreoffice_executable()
            if not soffice:
                raise SelectedBasePreviewUnavailable("LibreOffice is needed to display the saved source DOCX as an image.")
            docx_path = folder / "confirmed_selected_base.docx"
            docx_path.write_bytes(raw)
            pdf_path = folder / "confirmed_selected_base.pdf"
            profile = folder / "lo_profile"
            profile.mkdir()
            result = subprocess.run([
                soffice, "--headless", "--nologo", "--nodefault",
                "--nofirststartwizard", "--nolockcheck",
                f"-env:UserInstallation={profile.as_uri()}",
                "--convert-to", "pdf", "--outdir", str(folder), str(docx_path),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=75, check=False)
            if result.returncode or not pdf_path.is_file():
                raise SelectedBasePreviewUnavailable("Temporary source DOCX-to-PDF conversion failed.")
            method = "Preview converted from exact, hash-verified source DOCX"
        else:
            raise SelectedBasePreviewUnavailable("Only confirmed PDF/DOCX artifacts can be shown.")
        pdf_bytes = pdf_path.read_bytes()
        if not pdf_bytes.startswith(b"%PDF"):
            raise SelectedBasePreviewUnavailable("The selected source PDF preview is invalid.")
        html = pdf_to_preview_html(
            pdf_path, max_width=820, max_pages=5, zoom=1.35,
            include_download=False,
        )
        return html, pdf_bytes, method


def render_selected_base_visual_tab(st: Any, application_id: int) -> None:
    """Visual-only optional tab: no scorer, generation or application mutation."""
    st.caption(
        "Exact Selected Base from Tailor Resume. This is the pre-tailoring "
        "source document, not an uploaded Initial Résumé Analysis or an unfitted generated draft."
    )
    st.caption("The confirmed Selected Base preview loads automatically. Verified source identity is checked on each rerun; expensive PDF rendering is cached by immutable bytes where supported.")
    try:
        artifact = load_confirmed_visual_artifact(int(application_id))
        cache_data = getattr(st, "cache_data", None)
        if callable(cache_data):
            html, pdf_bytes, method = cache_data(show_spinner=False, max_entries=8)(render_verified_source_pdf)(artifact)
        else:
            html, pdf_bytes, method = render_verified_source_pdf(artifact)
    except (SelectedBasePreviewUnavailable, ValueError, KeyError, TypeError,
            FileNotFoundError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        st.warning("Selected Base image unavailable: " + str(exc))
        st.caption("No other résumé is substituted when the confirmed source cannot be authenticated.")
        return
    st.write("**Confirmed source:** " + artifact["source_name"])
    st.caption(method + " · Phase 9F-D confirmation " + artifact["confirmation_id"][:12] + " · No rescoring")
    st.markdown(html, unsafe_allow_html=True)
    st.download_button(
        "Download confirmed Selected Base PDF preview",
        data=pdf_bytes, file_name=f"app_{int(application_id)}_selected_base_preview.pdf",
        mime="application/pdf", key=f"phase9f_confirmed_base_pdf_{int(application_id)}",
    )
