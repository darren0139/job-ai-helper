"""Read-only visual previews for Phase 9E Tailoring Base sources."""

from __future__ import annotations

import shutil
import tempfile
import textwrap
from pathlib import Path
from typing import Any

import fitz

from database.global_master_resume_manager import (
    get_global_master_resume_artifact,
)
from resume_builder.docx_projects_skills_replacer import (
    convert_docx_to_pdf_if_possible,
    get_latest_saved_docx_for_application,
    pdf_to_preview_html,
)


PHASE9E_TAILORING_BASE_VISUAL_PREVIEW_VERSION = (
    "phase9e-tailoring-base-visual-preview-v3"
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _download_fields(
    *,
    content: bytes | None,
    filename: str,
    media_type: str,
    label: str,
) -> dict[str, Any]:
    if not isinstance(content, bytes) or not content:
        return {}
    safe_name = Path(filename or "resume").name
    return {
        "download_bytes": content,
        "download_name": safe_name,
        "download_mime": _clean(media_type) or "application/octet-stream",
        "download_label": label,
    }


def _pdf_bytes_to_preview_html(
    content: bytes,
    *,
    filename: str,
) -> str:
    if not isinstance(content, bytes) or not content:
        return ""
    safe_name = Path(filename or "preview.pdf").name
    if not safe_name.lower().endswith(".pdf"):
        safe_name = "preview.pdf"

    with tempfile.TemporaryDirectory(
        prefix="phase9e_tailoring_base_preview_"
    ) as name:
        path = Path(name) / safe_name
        path.write_bytes(content)
        return pdf_to_preview_html(
            path,
            max_width=820,
            max_pages=5,
            zoom=1.35,
            include_download=False,
        )


def _wrap_preview_line(value: str, *, width: int = 92) -> list[str]:
    text = str(value or "").rstrip()
    if not text:
        return [""]

    initial_indent = ""
    subsequent_indent = ""
    body = text
    for prefix in ("• ", "- ", "* "):
        if body.startswith(prefix):
            initial_indent = prefix
            subsequent_indent = "  "
            body = body[len(prefix):]
            break

    wrapped = textwrap.wrap(
        body,
        width=max(40, int(width)),
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        replace_whitespace=False,
        drop_whitespace=True,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped or [text]


def _scoring_text_to_pdf_bytes(resume_text: str) -> bytes:
    """Create an ephemeral, deterministic page preview from scoring text.

    This is deliberately a visualisation of the exact scoring representation,
    not a reconstruction of the original uploaded document's formatting.
    """
    text = str(resume_text or "")
    if not text.strip():
        return b""

    document = fitz.open()
    page_width = 595.0
    page_height = 842.0
    margin_x = 46.0
    margin_top = 48.0
    margin_bottom = 48.0
    body_font_size = 9.2
    body_line_height = 13.0
    heading_font_size = 10.2
    heading_line_height = 15.0
    y = margin_top

    def new_page():
        nonlocal y
        created = document.new_page(
            width=page_width,
            height=page_height,
        )
        y = margin_top
        return created

    page = new_page()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        is_heading = bool(
            stripped
            and len(stripped) <= 40
            and stripped.upper() == stripped
            and any(char.isalpha() for char in stripped)
        )
        lines = _wrap_preview_line(
            raw_line,
            width=84 if is_heading else 92,
        )

        for line in lines:
            font_size = (
                heading_font_size
                if is_heading
                else body_font_size
            )
            line_height = (
                heading_line_height
                if is_heading
                else body_line_height
            )

            if y + line_height > page_height - margin_bottom:
                page = new_page()

            page.insert_text(
                (margin_x, y),
                line,
                fontsize=font_size,
                fontname="helv",
            )
            y += line_height

        if not stripped:
            y += 3.0
        elif is_heading:
            y += 2.0

    output = document.tobytes(
        garbage=4,
        deflate=True,
    )
    document.close()
    return output


def _derived_scoring_text_preview(resume_text: str) -> dict[str, str]:
    content = _scoring_text_to_pdf_bytes(resume_text)
    if not content:
        return {
            "html": "",
            "mode": "derived_scoring_text",
            "source_kind": "exact_scoring_text",
            "note": (
                "No scoring text is available to create a visual preview."
            ),
        }

    return {
        "html": _pdf_bytes_to_preview_html(
            content,
            filename="scoring_snapshot.pdf",
        ),
        "mode": "derived_scoring_text",
        "source_kind": "exact_scoring_text",
        "note": (
            "Derived visual preview of the exact scoring text. "
            "This shows scoring content in page form; it is not the original "
            "uploaded document formatting."
        ),
    }


def _saved_application_docx_preview(
    application_id: int | None,
) -> dict[str, Any] | None:
    """Render and expose the saved application DOCX without mutating it."""
    if application_id is None:
        return None

    try:
        app_id = int(application_id)
    except (TypeError, ValueError):
        return None
    if app_id < 0:
        return None

    saved_docx = get_latest_saved_docx_for_application(app_id)
    if saved_docx is None:
        return None

    saved_docx = Path(saved_docx)
    try:
        if not saved_docx.is_file() or saved_docx.stat().st_size <= 0:
            return None
        source_bytes = saved_docx.read_bytes()
    except OSError:
        return None
    if not source_bytes:
        return None

    generated_pdf: Path | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=f"phase9e_app_{app_id}_original_preview_"
        ) as name:
            temp_root = Path(name)
            unique_stem = temp_root.name.replace(" ", "_")
            temp_docx = (
                temp_root
                / f"{unique_stem}_{saved_docx.stem}.docx"
            )
            temp_docx.write_bytes(source_bytes)

            generated_pdf = convert_docx_to_pdf_if_possible(
                temp_docx
            )
            if generated_pdf is None:
                return None

            generated_pdf = Path(generated_pdf)
            if (
                not generated_pdf.is_file()
                or generated_pdf.stat().st_size <= 0
            ):
                return None

            html = pdf_to_preview_html(
                generated_pdf,
                max_width=820,
                max_pages=5,
                zoom=1.35,
                include_download=False,
            )

        result: dict[str, Any] = {
            "html": html,
            "mode": "saved_application_docx",
            "source_kind": "application_saved_docx",
            "artifact_name": saved_docx.name,
            "note": (
                "Original saved application résumé formatting. "
                f"Rendered from {saved_docx.name}. "
                "This visual is for document inspection; deterministic "
                "alignment still uses the normalized text shown in "
                "Exact scoring text."
            ),
        }
        result.update(
            _download_fields(
                content=source_bytes,
                filename=saved_docx.name,
                media_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                label="Download application source résumé",
            )
        )
        return result
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        return None
    finally:
        if generated_pdf is not None:
            try:
                generated_pdf.unlink(missing_ok=True)
            except OSError:
                pass


def _stored_master_pdf_preview(
    base_resume_starting_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Render the Master source with original-format parity when possible."""
    snapshot = (
        base_resume_starting_snapshot
        if isinstance(base_resume_starting_snapshot, dict)
        else {}
    )
    identity = snapshot.get("source_identity") or {}
    master_version_id = _clean(identity.get("source_id"))
    if not master_version_id:
        return None

    original = get_global_master_resume_artifact(
        master_version_id,
        "original",
    )
    preview = get_global_master_resume_artifact(
        master_version_id,
        "preview_pdf",
    )

    original_content = (
        original.get("artifact_bytes")
        if isinstance(original, dict)
        else None
    )
    original_filename = (
        str(original.get("filename") or "")
        if isinstance(original, dict)
        else ""
    )
    original_media_type = (
        _clean(original.get("media_type"))
        if isinstance(original, dict)
        else ""
    )

    def with_master_download(
        result: dict[str, Any],
    ) -> dict[str, Any]:
        if isinstance(original_content, bytes) and original_content:
            result.update(
                _download_fields(
                    content=original_content,
                    filename=(
                        original_filename
                        or "master_resume"
                    ),
                    media_type=(
                        original_media_type
                        or "application/octet-stream"
                    ),
                    label="Download Master résumé source",
                )
            )
            return result

        if isinstance(preview, dict):
            preview_bytes = preview.get("artifact_bytes")
            if isinstance(preview_bytes, bytes) and preview_bytes:
                result.update(
                    _download_fields(
                        content=preview_bytes,
                        filename=str(
                            preview.get("filename")
                            or "master_resume_preview.pdf"
                        ),
                        media_type=str(
                            preview.get("media_type")
                            or "application/pdf"
                        ),
                        label="Download Master résumé preview",
                    )
                )
        return result

    if isinstance(preview, dict):
        content = preview.get("artifact_bytes")
        if isinstance(content, bytes) and content:
            return with_master_download(
                {
                    "html": _pdf_bytes_to_preview_html(
                        content,
                        filename=str(
                            preview.get("filename")
                            or "master_resume_preview.pdf"
                        ),
                    ),
                    "mode": "stored_master_pdf",
                    "source_kind": "master_preview_pdf",
                    "artifact_name": str(
                        preview.get("filename")
                        or "master_resume_preview.pdf"
                    ),
                    "note": (
                        "Stored Master résumé visual preview. "
                        "This uses the same shared PDF-to-image renderer as "
                        "Build & Fit and Résumé Workspace."
                    ),
                }
            )

    if isinstance(original, dict):
        content = original_content
        media_type = original_media_type.lower()
        filename = original_filename
        is_pdf = bool(
            media_type == "application/pdf"
            or filename.lower().endswith(".pdf")
        )
        is_docx = bool(
            filename.lower().endswith(".docx")
            or media_type
            == (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        )

        if is_pdf and isinstance(content, bytes) and content:
            return with_master_download(
                {
                    "html": _pdf_bytes_to_preview_html(
                        content,
                        filename=filename or "master_resume.pdf",
                    ),
                    "mode": "stored_master_pdf",
                    "source_kind": "master_original_pdf",
                    "artifact_name": filename or "master_resume.pdf",
                    "note": (
                        "Authoritative Master résumé PDF preview. "
                        "This uses the same shared PDF-to-image renderer as "
                        "Build & Fit and Résumé Workspace."
                    ),
                }
            )

        if is_docx and isinstance(content, bytes) and content:
            generated_pdf: Path | None = None
            try:
                with tempfile.TemporaryDirectory(
                    prefix="phase9e_master_original_preview_"
                ) as name:
                    temp_root = Path(name)
                    safe_stem = (
                        Path(filename or "master_resume.docx").stem
                        or "master_resume"
                    )
                    temp_docx = (
                        temp_root
                        / f"{temp_root.name}_{safe_stem}.docx"
                    )
                    temp_docx.write_bytes(content)

                    generated_pdf = convert_docx_to_pdf_if_possible(
                        temp_docx
                    )
                    if generated_pdf is None:
                        return None

                    generated_pdf = Path(generated_pdf)
                    if (
                        not generated_pdf.is_file()
                        or generated_pdf.stat().st_size <= 0
                    ):
                        return None

                    html = pdf_to_preview_html(
                        generated_pdf,
                        max_width=820,
                        max_pages=5,
                        zoom=1.35,
                        include_download=False,
                    )

                return with_master_download(
                    {
                        "html": html,
                        "mode": "converted_master_docx",
                        "source_kind": "master_original_docx",
                        "artifact_name": (
                            filename or "master_resume.docx"
                        ),
                        "note": (
                            "Original Master résumé DOCX formatting. "
                            "The stored authoritative DOCX was converted to "
                            "an ephemeral PDF for preview only; deterministic "
                            "alignment still uses the normalized text shown "
                            "in Exact scoring text."
                        ),
                    }
                )
            except (
                FileNotFoundError,
                OSError,
                RuntimeError,
                ValueError,
            ):
                return None
            finally:
                if generated_pdf is not None:
                    try:
                        generated_pdf.unlink(missing_ok=True)
                    except OSError:
                        pass

    return None


def build_tailoring_base_visual_preview(
    *,
    selected_source: str,
    resume_text: str,
    application_id: int | None = None,
    base_resume_starting_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return read-only preview HTML and provenance without state mutation."""
    source = _clean(selected_source)

    if source == "original_resume":
        original = _saved_application_docx_preview(
            application_id
        )
        if original is not None:
            return original

    if source == "base_resume":
        stored = _stored_master_pdf_preview(
            base_resume_starting_snapshot
        )
        if stored is not None:
            return stored

    return _derived_scoring_text_preview(resume_text)
