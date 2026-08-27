"""Streamlit UI for Phase 9F-A intake and transient Phase 9F-B ranking."""

from __future__ import annotations

import hashlib
from typing import Any

import streamlit as st

from analyzer import extract_jd_profile
from database.jd_library_manager import (
    get_exact_job_description_version,
    get_job_description_versions,
    get_recent_job_descriptions,
    save_job_description_to_library,
)
from llm import drain_call_ledger, get_active_model, reset_call_ledger
from rag.jd_chroma_rag import index_job_description_to_chroma
from rag.jd_identity import source_version_id
from tailoring.jd_user_input_overrides import (
    PREFERRED_REQUIREMENTS_HELP,
    PREFERRED_REQUIREMENTS_LABEL,
    normalise_requirement_override_lines,
)
from tailoring.phase9f_jd_intake import (
    build_phase9f_analysis_diagnostics,
    build_reused_exact_jd_snapshot,
    build_saved_exact_jd_snapshot,
    build_transient_exact_jd_snapshot,
    extract_job_description_file,
    phase9f_analysis_diagnostics_json,
    phase9f_jd_input_fingerprint,
    validate_jd_text,
)
from tailoring.phase9f_starting_source_ranking_ui import (
    render_phase9f_starting_source_ranking,
)


SOURCE_LABELS = {
    "Paste job description": "pasted",
    "Upload job-description file": "uploaded",
    "Choose saved JD": "saved",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _saved_job_label(row: tuple[Any, ...]) -> str:
    title = _clean(row[2]) or "Untitled job"
    company = _clean(row[3]) or "Unknown company"
    return f"{company} — {title}"


def _version_label(row: dict[str, Any]) -> str:
    created = _clean(row.get("created_at")) or "timestamp unavailable"
    version = _clean(row.get("source_version_id"))
    return f"{created} · {version[:16]}"


def _find_exact_saved_jd_version(raw_text: str) -> dict[str, Any] | None:
    """Find one exact immutable JD version by raw-text source identity.

    This is a read-only preflight. It never calls a model, creates persistence,
    or indexes Chroma.
    """
    text = str(raw_text or "").strip()
    if not text:
        return None

    target_version = source_version_id(text)
    for job in get_recent_job_descriptions(limit=5000):
        try:
            library_jd_id = int(job[0])
        except (TypeError, ValueError, IndexError):
            continue

        versions = get_job_description_versions(library_jd_id)
        if not any(
            _clean(version.get("source_version_id")) == target_version
            for version in versions
            if isinstance(version, dict)
        ):
            continue

        exact = get_exact_job_description_version(
            library_jd_id,
            target_version,
        )
        if not isinstance(exact, dict):
            continue
        if str(exact.get("raw_text") or "").strip() != text:
            continue
        return exact

    return None


def _current_save_receipt(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    receipt = st.session_state.get("phase9f_jd_save_receipt")
    if not isinstance(receipt, dict):
        return None
    if receipt.get("analysis_snapshot_fingerprint") != snapshot.get(
        "snapshot_fingerprint"
    ):
        return None
    return receipt


def _render_diagnostics(snapshot: dict[str, Any]) -> None:
    receipt = _current_save_receipt(snapshot)
    diagnostics = build_phase9f_analysis_diagnostics(
        snapshot,
        save_receipt=receipt,
    )
    diagnostics_json = phase9f_analysis_diagnostics_json(
        snapshot,
        save_receipt=receipt,
    )
    api_usage = (
        diagnostics.get("extraction", {}).get("api_usage", {})
        if isinstance(diagnostics.get("extraction"), dict)
        else {}
    )
    api_calls = int(api_usage.get("call_count") or 0)
    estimated_cost = api_usage.get("estimated_cost_usd")
    if api_calls:
        if estimated_cost is None:
            st.caption(
                f"Model API usage: {api_calls} call(s) · "
                "estimated cost unavailable for this response/model."
            )
        else:
            st.caption(
                f"Model API usage: {api_calls} call(s) · "
                f"estimated cost ${float(estimated_cost):.6f} USD. "
                "Provider billing is authoritative."
            )

    with st.expander("Analysis diagnostics", expanded=False):
        st.caption(
            "Read-only provenance for this analysis. Opening or downloading "
            "it does not call a model, write to persistence, or index Chroma."
        )
        st.json(diagnostics)
        st.download_button(
            "Download diagnostics JSON",
            data=diagnostics_json,
            file_name=(
                "phase9f_jd_diagnostics_"
                f"{str(snapshot.get('snapshot_fingerprint') or '')[:12]}.json"
            ),
            mime="application/json",
            key="phase9f_download_jd_diagnostics",
        )


def _render_analysis(snapshot: dict[str, Any], *, current_source_url: str) -> None:
    st.subheader("Job Analysis")
    title = _clean(snapshot.get("job_title")) or "Job title not provided"
    company = _clean(snapshot.get("company"))
    st.markdown(f"### {title}")
    if company:
        st.caption(company)

    family = snapshot.get("role_family") or {}
    family_col, confidence_col, scope_col = st.columns(3)
    family_col.metric(
        "Suggested role family",
        _clean(family.get("role_family")) or "General Software Engineering",
    )
    confidence_col.metric(
        "Confidence",
        (_clean(family.get("confidence")) or "low").title(),
    )
    rows = snapshot.get("canonical_requirements") or []
    required_core_count = sum(
        _clean(row.get("importance")) != "preferred"
        for row in rows
        if isinstance(row, dict)
    )
    preferred_count = sum(
        _clean(row.get("importance")) == "preferred"
        for row in rows
        if isinstance(row, dict)
    )
    technology_count = len(
        {
            _clean(value).lower()
            for value in snapshot.get("tools_technologies") or []
            if _clean(value)
        }
    )
    scope_col.metric(
        "Canonical scope",
        f"{required_core_count} Core · {preferred_count} Preferred",
        f"{technology_count} technologies",
    )

    if snapshot.get("source_type") == "saved":
        st.success(
            "Saved JD · Exact version: "
            f"{_clean(snapshot.get('source_version_id'))}"
        )
    elif snapshot.get("reused_exact_saved_version"):
        st.success(
            "Reused the exact JD Library analysis · 0 model calls for "
            "JD extraction."
        )

    with st.expander("View JD analysis", expanded=False):
        profile = snapshot.get("jd_profile") or {}
        details = {
            "Job title": _clean(snapshot.get("job_title")),
            "Company": _clean(snapshot.get("company")),
            "Location": _clean(snapshot.get("location")),
            "Seniority / experience": _clean(
                snapshot.get("experience_level")
            ),
        }
        st.json({key: value for key, value in details.items() if value})
        st.write("**Responsibilities**")
        st.write(list(snapshot.get("responsibilities") or []))
        st.write("**Required/Core requirements**")
        st.dataframe(
            [
                {
                    "Importance": row.get("importance", ""),
                    "Requirement": row.get("text", ""),
                    "Requirement ID": row.get("requirement_id", ""),
                }
                for row in rows
                if isinstance(row, dict)
                and _clean(row.get("importance")) != "preferred"
            ],
            width="stretch",
            hide_index=True,
        )
        st.write("**Preferred requirements**")
        st.dataframe(
            [
                {
                    "Requirement": row.get("text", ""),
                    "Requirement ID": row.get("requirement_id", ""),
                }
                for row in rows
                if isinstance(row, dict)
                and _clean(row.get("importance")) == "preferred"
            ],
            width="stretch",
            hide_index=True,
        )
        st.write("**Required skills**")
        st.write(list(profile.get("required_skills") or []))
        st.write("**Preferred skills**")
        st.write(list(profile.get("preferred_skills") or []))
        st.write("**Technical stack / tools**")
        st.write(list(profile.get("tools_technologies") or []))
        st.write("**Role-family signals**")
        st.write(list(family.get("matched_terms") or []))
        st.caption(
            "Transient snapshot: "
            f"{_clean(snapshot.get('snapshot_fingerprint'))}"
        )

    can_offer_save = snapshot.get("source_type") in {"pasted", "uploaded"}
    has_save_identity = bool(
        _clean(snapshot.get("job_title")) and _clean(snapshot.get("company"))
    )
    if can_offer_save and not has_save_identity:
        st.warning(
            "Add a job title and company, then analyse again before saving. "
            "The transient analysis remains valid without them, but the JD "
            "Library will not persist an ambiguous canonical identity."
        )
    elif can_offer_save:
        if snapshot.get("reused_exact_saved_version"):
            st.caption(
                "This exact JD version already exists in the JD Library. "
                "Saving will reuse it and will not create a duplicate embedding."
            )
        else:
            st.caption(
                "Saving a new JD/version may run the configured "
                "embedding/indexing backend and may incur embedding API charges. "
                "Reusing an exact existing version does not create a duplicate "
                "embedding."
            )
        if st.button(
            "Save to JD Library",
            key="phase9f_save_jd",
            width="stretch",
        ):
            try:
                saved = save_job_description_to_library(
                    raw_text=str(snapshot.get("raw_text") or ""),
                    jd_profile=dict(snapshot.get("jd_profile") or {}),
                    title=str(snapshot.get("job_title") or ""),
                    company=str(snapshot.get("company") or ""),
                    location=str(snapshot.get("location") or ""),
                    source_url=current_source_url,
                )
                index_message = ""
                indexing_attempted = bool(saved.get("needs_chroma_index"))
                indexing_occurred = False
                indexed_chunks = 0
                if indexing_attempted:
                    try:
                        indexed_chunks = int(
                            index_job_description_to_chroma(
                                int(saved["job_description_id"])
                            )
                        )
                        indexing_occurred = True
                        index_message = (
                            f" Indexed {indexed_chunks} Chroma chunks."
                        )
                    except Exception as exc:
                        index_message = f" Chroma indexing skipped: {exc}"
                else:
                    index_message = (
                        " Reused the existing exact JD/version; no duplicate "
                        "version or embedding was created."
                    )
                receipt = {
                    **saved,
                    "analysis_snapshot_fingerprint": snapshot[
                        "snapshot_fingerprint"
                    ],
                    "index_message": index_message,
                    "chroma_indexing_attempted": indexing_attempted,
                    "chroma_indexing_occurred": indexing_occurred,
                    "chroma_indexed_chunk_count": indexed_chunks,
                }
                st.session_state["phase9f_jd_save_receipt"] = receipt
            except Exception as exc:
                st.error(f"Could not save the JD: {exc}")

        receipt = _current_save_receipt(snapshot)
        if receipt:
            st.success(
                "Saved to JD Library · Exact version: "
                f"{receipt.get('source_version_id', '')}."
                f"{receipt.get('index_message', '')}"
            )

    _render_diagnostics(snapshot)
    render_phase9f_starting_source_ranking(snapshot)


def render_phase9f_jd_intake() -> None:
    """Render Phase 9F-A and 9F-B without application/lifecycle mutations."""
    st.header("Tailor Resume")
    st.caption(
        "Analyse and optionally save an exact job description before deciding "
        "whether to start an application."
    )
    source_label = st.selectbox(
        "Job-description source",
        list(SOURCE_LABELS),
        key="phase9f_jd_source_mode",
    )
    source_type = SOURCE_LABELS[source_label]
    raw_text = ""
    title = company = location = source_url = source_filename = ""
    source_artifact_sha256 = ""
    library_jd_id = 0
    saved_source_version_id = ""
    selected_saved: dict[str, Any] | None = None

    if source_type == "pasted":
        raw_text = st.text_area(
            "Paste job description",
            height=280,
            key="phase9f_pasted_jd_text",
            placeholder="Paste the complete job description here...",
        )
    elif source_type == "uploaded":
        uploaded = st.file_uploader(
            "Upload PDF or DOCX job description",
            type=["pdf", "docx"],
            key="phase9f_uploaded_jd",
        )
        if uploaded is not None:
            source_filename = str(uploaded.name or "")
            content = uploaded.getvalue()
            upload_hash = hashlib.sha256(content).hexdigest()
            source_artifact_sha256 = upload_hash
            cache_key = "phase9f_uploaded_jd_extraction"
            cached = st.session_state.get(cache_key)
            if not isinstance(cached, dict) or cached.get("hash") != upload_hash:
                try:
                    cached = {
                        "hash": upload_hash,
                        "text": extract_job_description_file(
                            filename=source_filename,
                            content=content,
                        ),
                    }
                except Exception as exc:
                    cached = {"hash": upload_hash, "text": "", "error": str(exc)}
                st.session_state[cache_key] = cached
            if cached.get("error"):
                st.error(str(cached["error"]))
            elif cached.get("text"):
                st.success("Text extracted locally. Not analysed yet.")
                raw_text = st.text_area(
                    "Extracted JD text — review and correct before analysis",
                    value=str(cached["text"]),
                    height=280,
                    key=f"phase9f_uploaded_jd_text_{upload_hash}",
                )
    else:
        jobs = get_recent_job_descriptions(limit=200)
        if not jobs:
            st.info("No saved JDs are available yet.")
        else:
            selected_job = st.selectbox(
                "Saved job",
                jobs,
                format_func=_saved_job_label,
                key="phase9f_saved_jd",
            )
            library_jd_id = int(selected_job[0])
            versions = get_job_description_versions(library_jd_id)
            if not versions:
                st.error("The selected saved JD has no exact source version.")
            else:
                selected_version = st.selectbox(
                    "Exact version",
                    versions,
                    format_func=_version_label,
                    key="phase9f_saved_jd_version",
                )
                saved_source_version_id = str(
                    selected_version.get("source_version_id") or ""
                )
                raw_text = str(selected_version.get("raw_text") or "")

    if source_type in {"pasted", "uploaded"}:
        with st.expander("Optional JD metadata", expanded=False):
            company = st.text_input("Company", key="phase9f_jd_company")
            title = st.text_input(
                "Job title / Role", key="phase9f_jd_title"
            )
            location = st.text_input("Location", key="phase9f_jd_location")
            source_url = st.text_input("Source URL", key="phase9f_jd_source_url")

    with st.expander("Optional JD requirement overrides", expanded=False):
        preferred_requirement_input = st.text_area(
            PREFERRED_REQUIREMENTS_LABEL,
            height=120,
            key="phase9f_jd_preferred_requirements",
            placeholder=(
                "Paste one full requirement per line, ideally using the "
                "exact wording from the JD."
            ),
            help=PREFERRED_REQUIREMENTS_HELP,
        )
        st.caption(
            "Explicit user input has highest importance precedence. Matching "
            "is deterministic and conservative: no fuzzy requirement "
            "reclassification."
        )
    preferred_requirements = normalise_requirement_override_lines(
        preferred_requirement_input
    )

    exact_saved_match = None
    if source_type in {"pasted", "uploaded"} and _clean(raw_text):
        exact_saved_match = _find_exact_saved_jd_version(raw_text)

    active_analysis_model = (
        get_active_model("analysis")
        if source_type != "saved"
        else ""
    )
    analysis_model = (
        active_analysis_model
        if source_type != "saved" and exact_saved_match is None
        else ""
    )
    input_fingerprint = phase9f_jd_input_fingerprint(
        source_type=source_type,
        raw_text=raw_text,
        title=title,
        company=company,
        location=location,
        library_jd_id=library_jd_id or None,
        source_version_id_value=saved_source_version_id,
        source_artifact_sha256=source_artifact_sha256,
        # The input fingerprint tracks the user's selected analysis model,
        # not whether an exact saved match happens to exist today. Otherwise
        # saving a newly analysed JD would immediately make that same analysis
        # stale when the preflight begins finding the newly saved exact version.
        extraction_model_id=active_analysis_model,
        preferred_requirements=preferred_requirements,
    )
    has_input = bool(_clean(raw_text))
    if has_input and exact_saved_match is not None:
        st.success(
            "This exact JD already exists in the JD Library. Its stored "
            "structured analysis will be reused, so JD analysis requires "
            "0 model calls and no JD-extraction API charge."
        )
    elif has_input and source_type in {"pasted", "uploaded"}:
        st.warning(
            "Analyse Job Description calls the selected analysis API model "
            f"({analysis_model}) and may incur API charges. "
            "The current JD extraction pipeline normally makes two model "
            "requests: extraction and review."
        )
    elif has_input and source_type == "saved":
        st.caption(
            "This exact saved JD reuses its stored structured analysis and "
            "does not call the JD extraction model."
        )

    if st.button(
        "Analyse Job Description",
        type="primary",
        width="stretch",
        key="phase9f_analyse_jd",
        disabled=not has_input,
    ):
        try:
            if source_type == "saved":
                selected_saved = get_exact_job_description_version(
                    library_jd_id,
                    saved_source_version_id,
                )
                if selected_saved is None:
                    raise ValueError("The selected exact saved JD version is missing.")
                snapshot = build_saved_exact_jd_snapshot(
                    selected_saved,
                    preferred_requirements=preferred_requirements,
                )
            elif exact_saved_match is not None:
                validated_text = validate_jd_text(raw_text)
                if (
                    str(exact_saved_match.get("raw_text") or "").strip()
                    != validated_text
                ):
                    raise ValueError(
                        "The exact saved JD changed during preflight. "
                        "Analyse again."
                    )
                snapshot = build_reused_exact_jd_snapshot(
                    exact_saved_match,
                    source_type=source_type,
                    title=title,
                    company=company,
                    location=location,
                    source_url=source_url,
                    source_filename=source_filename,
                    source_artifact_sha256=source_artifact_sha256,
                    preferred_requirements=preferred_requirements,
                )
            else:
                validated_text = validate_jd_text(raw_text)
                reset_call_ledger()
                try:
                    with st.spinner("Analysing job description..."):
                        profile = extract_jd_profile(validated_text)
                finally:
                    calls = drain_call_ledger()
                snapshot = build_transient_exact_jd_snapshot(
                    raw_text=validated_text,
                    jd_profile=profile,
                    source_type=source_type,
                    title=title,
                    company=company,
                    location=location,
                    source_url=source_url,
                    source_filename=source_filename,
                    source_artifact_sha256=source_artifact_sha256,
                    extraction_model_id=analysis_model,
                    model_calls=calls,
                    preferred_requirements=preferred_requirements,
                )
            st.session_state["phase9f_jd_analysis"] = snapshot
            st.session_state["phase9f_jd_analysis_input_fingerprint"] = (
                input_fingerprint
            )
            st.session_state["phase9f_jd_intake_state"] = "analysis_current"
            st.session_state.pop("phase9f_jd_save_receipt", None)
        except Exception as exc:
            st.session_state["phase9f_jd_intake_state"] = "analysis_requested"
            st.error(f"Job-description analysis failed: {exc}")

    analysis = st.session_state.get("phase9f_jd_analysis")
    stored_input = st.session_state.get(
        "phase9f_jd_analysis_input_fingerprint", ""
    )
    if isinstance(analysis, dict) and stored_input != input_fingerprint:
        st.session_state["phase9f_jd_intake_state"] = "stale"
        st.warning(
            "The JD input changed. The previous analysis is historical/stale; "
            "click Analyse Job Description again."
        )
    elif isinstance(analysis, dict):
        st.session_state["phase9f_jd_intake_state"] = "analysis_current"
        _render_analysis(analysis, current_source_url=source_url)
    elif has_input:
        st.session_state["phase9f_jd_intake_state"] = "jd_entered"
        st.info("JD ready. Nothing is analysed or saved until you choose an action.")
    else:
        st.session_state["phase9f_jd_intake_state"] = "idle"
