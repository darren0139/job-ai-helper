"""
resume_builder/docx_projects_skills_replacer.py

Updated DOCX resume copy replacer.

Workflow:
    Upload original_resume.docx
    -> optionally save a local copy
    -> generate tailored projects + tailored skills
    -> copy original DOCX
    -> replace only SKILLS and PROJECTS sections
    -> download tailored resume copy

This version improves formatting preservation:
1. Copies paragraph style from the original Projects section.
2. Copies bullet style/numbering from the original bullet paragraphs.
3. Uses a right-aligned tab stop for project dates.
4. Preserves spacing between projects where possible.
5. Inserts real bullet paragraphs instead of plain text paragraphs.

Important:
    This does not overwrite the original uploaded file.
    Work Experience is not changed.
"""



from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import time
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Pt
from docx.document import Document as DocumentObject
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from utils.date_sorting import period_sort_value
from resume_builder.skills_section_compactor import (
    compact_skills_one_step,
    count_skill_items,
    count_skill_reduction_candidates,
    restore_skill_change,
    skill_restoration_quality_gain,
)
from resume_builder.evidence_aware_fitting import (
    PHASE6C_FITTING_VERSION,
    build_evidence_aware_project_reductions,
    restore_removed_bullet_metadata,
    sync_project_bullet_metadata,
)
from resume_builder.fitting_render_optimizer import (
    PHASE6C1_OPTIMIZATION_VERSION,
    build_render_state_fingerprint,
    group_candidates_by_protection_tier,
    rendered_candidate_is_effective,
    source_docx_signature,
)

SAVED_RESUME_DIR = Path("data/saved_resumes")
TAILORED_RESUME_DIR = Path("outputs/tailored_resumes")
PREVIEW_DIR = Path("outputs/resume_previews")

KNOWN_SECTION_HEADINGS = {
    "EDUCATION",
    "WORK EXPERIENCE",
    "EXPERIENCE",
    "PROFESSIONAL EXPERIENCE",
    "PROJECTS",
    "SKILLS",
    "TECHNICAL SKILLS",
    "CERTIFICATIONS",
    "ACHIEVEMENTS",
    "AWARDS",
    "COURSEWORK",
    "SUMMARY",
    "PROFILE",
}

from tailoring.deterministic_project_rules import (
    apply_deterministic_evidence_floors,
)

# ---------------------------------------------------------------------------
# File save helpers
# ---------------------------------------------------------------------------

def _safe_filename(filename: str) -> str:
    """Create a safe filename for local storage."""
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9_. -]", "_", name)
    return name.strip() or "uploaded_resume.docx"


def save_uploaded_docx_for_editing(
    uploaded_file: Any,
    *,
    application_id: int | None = None,
    replace_existing: bool = True,
) -> Path:
    """
    Save the uploaded DOCX so the app can later generate an edited copy.

    This should only be called if the user ticks the save checkbox.

    Keeps only the latest saved DOCX for the same application session
    when replace_existing=True.
    """
    if uploaded_file is None:
        raise ValueError("No uploaded file provided.")

    if not uploaded_file.name.lower().endswith(".docx"):
        raise ValueError("Only DOCX files can be saved for editable resume-copy generation.")

    SAVED_RESUME_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    app_part = f"app_{application_id}_" if application_id is not None else ""
    filename = f"{app_part}{timestamp}_{_safe_filename(uploaded_file.name)}"
    saved_path = SAVED_RESUME_DIR / filename

    saved_path.write_bytes(uploaded_file.getbuffer())

    if replace_existing and application_id is not None:
        for old_path in SAVED_RESUME_DIR.glob(f"app_{application_id}_*.docx"):
            if old_path != saved_path:
                try:
                    old_path.unlink()
                except OSError:
                    pass

    return saved_path


# ---------------------------------------------------------------------------
# Section detection helpers
# ---------------------------------------------------------------------------

def _paragraph_text(paragraph: Paragraph) -> str:
    """Return normalized paragraph text."""
    return " ".join(paragraph.text.replace("\xa0", " ").split())


def _is_heading_named(paragraph: Paragraph, names: set[str]) -> bool:
    """Return True if paragraph is one of the target headings."""
    text = _paragraph_text(paragraph).strip().rstrip(":")
    return text.upper() in {name.upper() for name in names}


def _is_probable_section_heading(paragraph: Paragraph) -> bool:
    """
    Detect the next resume section heading.

    This is intentionally conservative. It checks:
    - Word heading styles
    - known resume heading names
    - short all-caps headings
    """
    text = _paragraph_text(paragraph).strip().rstrip(":")
    if not text:
        return False

    style_name = ""
    try:
        style_name = paragraph.style.name or ""
    except Exception:
        style_name = ""

    if "Heading" in style_name:
        return True

    upper_text = text.upper()

    if upper_text in KNOWN_SECTION_HEADINGS:
        return True

    # Example: "EDUCATION", "PROJECTS", "TECHNICAL SKILLS"
    # Avoid treating long bullet sentences as headings.
    if (
        text == upper_text
        and 1 <= len(text.split()) <= 4
        and len(text) <= 40
        and not text.startswith("•")
        and not text.startswith("-")
    ):
        return True

    return False


def _find_section_range(
    document: DocumentObject,
    heading_names: set[str],
) -> tuple[int, int | None]:
    """
    Find a section by heading name.

    Returns:
        start_index: index of heading paragraph
        end_index: index of next section heading, or None if this is last section
    """
    paragraphs = document.paragraphs

    start_index = None
    for index, paragraph in enumerate(paragraphs):
        if _is_heading_named(paragraph, heading_names):
            start_index = index
            break

    if start_index is None:
        raise ValueError(f"Could not find section heading: {', '.join(sorted(heading_names))}")

    end_index = None
    for index in range(start_index + 1, len(paragraphs)):
        if _is_probable_section_heading(paragraphs[index]):
            end_index = index
            break

    return start_index, end_index


def _is_bullet_paragraph(paragraph: Paragraph) -> bool:
    """Return True if paragraph appears to be a bullet/list item."""
    text = paragraph.text.strip()
    style_name = paragraph.style.name if paragraph.style else ""

    has_numbering = (
        paragraph._p.pPr is not None
        and paragraph._p.pPr.numPr is not None
    )

    return has_numbering or "Bullet" in style_name or text.startswith("•")


def _find_templates_in_section(
    document: DocumentObject,
    heading_names: set[str],
) -> tuple[Paragraph | None, Paragraph | None]:
    """
    Find likely title/normal paragraph template and bullet template in a section.

    Returns:
        normal_template: first non-empty non-bullet paragraph
        bullet_template: first bullet/list paragraph
    """
    start_index, end_index = _find_section_range(document, heading_names)
    paragraphs = document.paragraphs
    section_end = end_index if end_index is not None else len(paragraphs)

    normal_template = None
    bullet_template = None

    for paragraph in paragraphs[start_index + 1 : section_end]:
        text = paragraph.text.strip()
        if not text:
            continue

        if bullet_template is None and _is_bullet_paragraph(paragraph):
            bullet_template = paragraph
            continue

        if normal_template is None and not _is_bullet_paragraph(paragraph):
            normal_template = paragraph

        if normal_template is not None and bullet_template is not None:
            break

    return normal_template, bullet_template


# ---------------------------------------------------------------------------
# Paragraph insertion and formatting helpers
# ---------------------------------------------------------------------------

def _delete_paragraph(paragraph: Paragraph) -> None:
    """Remove a paragraph from the DOCX XML tree."""
    element = paragraph._element
    parent = element.getparent()
    parent.remove(element)


def _insert_paragraph_after(
    paragraph: Paragraph,
    text: str = "",
    style: str | None = None,
) -> Paragraph:
    """Insert a paragraph after another paragraph."""
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_paragraph = Paragraph(new_p, paragraph._parent)

    if style:
        try:
            new_paragraph.style = style
        except Exception:
            pass

    if text:
        new_paragraph.add_run(text)

    return new_paragraph


def _copy_paragraph_format(source: Paragraph | None, target: Paragraph) -> None:
    """Copy basic paragraph styling/formatting from source to target."""
    if source is None:
        return

    try:
        target.style = source.style
    except Exception:
        pass

    source_format = source.paragraph_format
    target_format = target.paragraph_format

    for attr in (
        "left_indent",
        "right_indent",
        "first_line_indent",
        "space_before",
        "space_after",
        "line_spacing",
        "alignment",
        "keep_together",
        "keep_with_next",
        "page_break_before",
        "widow_control",
    ):
        try:
            setattr(target_format, attr, getattr(source_format, attr))
        except Exception:
            pass


def _copy_run_format(source_run: Any, target_run: Any) -> None:
    """Copy basic run/font formatting from source run to target run."""
    if source_run is None:
        return

    try:
        target_run.style = source_run.style
    except Exception:
        pass

    for attr in ("bold", "italic", "underline"):
        try:
            setattr(target_run, attr, getattr(source_run, attr))
        except Exception:
            pass

    try:
        target_run.font.name = source_run.font.name
    except Exception:
        pass

    try:
        target_run.font.size = source_run.font.size
    except Exception:
        pass

    try:
        if source_run.font.color and source_run.font.color.rgb:
            target_run.font.color.rgb = source_run.font.color.rgb
    except Exception:
        pass


def _get_first_run_template(paragraph: Paragraph | None) -> Any:
    """Return first run from a paragraph, or None."""
    if paragraph is not None and paragraph.runs:
        return paragraph.runs[0]
    return None


def _copy_numbering(source: Paragraph | None, target: Paragraph) -> None:
    """
    Copy bullet/numbering XML from source paragraph to target paragraph.

    This helps preserve bullet indentation and bullet style.
    """
    if source is None:
        return

    source_ppr = source._p.pPr
    if source_ppr is None or source_ppr.numPr is None:
        return

    target_ppr = target._p.get_or_add_pPr()

    # Remove existing numbering if present.
    if target_ppr.numPr is not None:
        try:
            target_ppr.remove(target_ppr.numPr)
        except Exception:
            pass

    target_ppr.append(deepcopy(source_ppr.numPr))


def _clear_section_content(
    document: DocumentObject,
    heading_names: set[str],
) -> Paragraph:
    """
    Delete all paragraphs inside a section, keeping the section heading.

    Returns:
        The heading paragraph to use as insertion anchor.
    """
    start_index, end_index = _find_section_range(document, heading_names)
    paragraphs = document.paragraphs

    delete_start = start_index + 1
    delete_end = end_index if end_index is not None else len(paragraphs)

    for index in range(delete_end - 1, delete_start - 1, -1):
        _delete_paragraph(paragraphs[index])

    return document.paragraphs[start_index]


def _add_blank_line_after(anchor: Paragraph) -> Paragraph:
    """
    Insert a blank paragraph after anchor.
    This behaves like pressing Enter once in Word.
    """
    spacer = _insert_paragraph_after(anchor)

    try:
        spacer.paragraph_format.space_before = Pt(0)
        spacer.paragraph_format.space_after = Pt(0)
        spacer.paragraph_format.line_spacing = 1
    except Exception:
        pass

    return spacer

# ---------------------------------------------------------------------------
# One page helpers
# ---------------------------------------------------------------------------
def count_pdf_pages(pdf_path: str | Path) -> int:
    """Count pages in a generated PDF."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return len(reader.pages)



def measure_pdf_page_fill(
    pdf_path: str | Path,
) -> dict[str, Any]:
    """
    Measure vertical text occupancy for one-page and multi-page PDFs.

    The one-page fields preserve the existing Phase 5 diagnostics. For
    multi-page candidates, ``last_page_fill_ratio`` and ``overflow_ratio``
    allow the fitter to detect real layout progress before the document has
    reached one page.
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return {
            "page_fill_ratio": None,
            "estimated_unused_page_ratio": None,
            "last_page_fill_ratio": None,
            "overflow_ratio": None,
            "occupied_page_units": None,
            "measurement_method": "unavailable",
        }

    try:
        document = fitz.open(str(pdf_path))
        page_count = len(document)
        page_fill_ratios: list[float] = []

        for page in document:
            page_height = float(page.rect.height)
            text_blocks = [
                block
                for block in page.get_text("blocks")
                if len(block) >= 5 and str(block[4]).strip()
            ]

            if not text_blocks or page_height <= 0:
                page_fill_ratios.append(0.0)
                continue

            lowest_text_y = max(float(block[3]) for block in text_blocks)
            page_fill_ratios.append(
                max(0.0, min(1.0, lowest_text_y / page_height))
            )

        document.close()

        if not page_fill_ratios:
            return {
                "page_fill_ratio": 0.0,
                "estimated_unused_page_ratio": 1.0,
                "last_page_fill_ratio": 0.0,
                "overflow_ratio": 0.0,
                "occupied_page_units": 0.0,
                "measurement_method": "pymupdf_text_blocks",
            }

        last_page_fill_ratio = page_fill_ratios[-1]
        single_page_fill_ratio = (
            page_fill_ratios[0] if page_count == 1 else None
        )
        overflow_ratio = (
            0.0
            if page_count <= 1
            else max(0.0, float(page_count - 2) + last_page_fill_ratio)
        )

        return {
            "page_fill_ratio": (
                round(single_page_fill_ratio, 3)
                if single_page_fill_ratio is not None
                else None
            ),
            "estimated_unused_page_ratio": (
                round(1.0 - single_page_fill_ratio, 3)
                if single_page_fill_ratio is not None
                else None
            ),
            "last_page_fill_ratio": round(last_page_fill_ratio, 3),
            "overflow_ratio": round(overflow_ratio, 3),
            "occupied_page_units": round(sum(page_fill_ratios), 3),
            "measurement_method": "pymupdf_text_blocks",
        }

    except Exception:
        return {
            "page_fill_ratio": None,
            "estimated_unused_page_ratio": None,
            "last_page_fill_ratio": None,
            "overflow_ratio": None,
            "occupied_page_units": None,
            "measurement_method": "failed",
        }



def _delete_generated_output(
    docx_path: str | Path | None,
    pdf_path: str | Path | None,
) -> None:
    """Delete an unselected temporary DOCX/PDF candidate."""
    for raw_path in (
        docx_path,
        pdf_path,
    ):
        if not raw_path:
            continue

        try:
            Path(raw_path).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

# def _project_priority_score(project: dict[str, Any]) -> int:
#     """Rank projects for space reduction."""
#     priority = str(project.get("priority", "")).lower()

#     if priority == "high":
#         base = 300
#     elif priority == "medium":
#         base = 200
#     elif priority == "low":
#         base = 100
#     else:
#         base = 150

#     matched_count = len(project.get("matched_jd_requirements", []) or [])

#     return base + matched_count

def _project_priority_score(
    project: dict[str, Any],
) -> int:
    """Rank projects for space reduction."""
    priority = str(
        project.get("priority", "")
    ).lower()

    if priority == "high":
        base = 300
    elif priority == "medium":
        base = 200
    elif priority == "low":
        base = 100
    else:
        base = 150

    fit_score = int(
        project.get("project_fit_score", 0)
        or 0
    )

    direct_matches = len(
        project.get("matched_jd_requirements", [])
        or []
    )

    transferable_matches = len(
        project.get(
            "transferable_jd_requirements",
            [],
        )
        or []
    )

    return (
        base
        + fit_score
        + direct_matches * 10
        + transferable_matches * 5
    )

# _WEAK_TRAILING_WORDS = {
#     "and",
#     "or",
#     "but",
#     "for",
#     "to",
#     "of",
#     "in",
#     "on",
#     "with",
#     "by",
#     "as",
#     "the",
#     "a",
#     "an",
#     "that",
#     "which",
#     "including",
# }


# def _trim_words(text: str, max_words: int) -> str:
#     """
#     Trim a bullet to a rough word limit without ending on a weak
#     connector such as 'and', 'to', or 'with'.
#     """
#     cleaned_text = " ".join(str(text).split())
#     words = cleaned_text.split()

#     if len(words) <= max_words:
#         return cleaned_text

#     trimmed_words = words[:max_words]

#     # Avoid results such as:
#     # "... degree fit, and."
#     while trimmed_words:
#         final_word = re.sub(
#             r"[^a-z0-9]+",
#             "",
#             trimmed_words[-1].lower(),
#         )

#         if final_word not in _WEAK_TRAILING_WORDS:
#             break

#         trimmed_words.pop()

#     if not trimmed_words:
#         return cleaned_text

#     trimmed_text = " ".join(trimmed_words).rstrip(" ,;:.-")
#     return trimmed_text + "."

# def _trim_words(text: str, max_words: int) -> str:
#     """Trim a bullet to a rough word limit."""
#     words = str(text).split()

#     if len(words) <= max_words:
#         return str(text).strip()

#     trimmed = " ".join(words[:max_words]).rstrip(".,;:")
#     return trimmed + "."


# def compact_tailored_projects_for_space(
#     tailored_projects: dict[str, Any],
#     *,
#     attempt: int,
# ) -> dict[str, Any]:
#     """
#     Reduce Projects section size only after the generated DOCX exceeds one page.

#     attempt 1:
#         Keep projects and bullet counts mostly intact, only trim long bullets.
#     attempt 2:
#         Keep 3 projects. High priority gets up to 2 bullets, others up to 1-2.
#     attempt 3:
#         Keep 3 projects. High priority gets up to 2 bullets;
#         medium and low priority get 1 bullet.

#     attempt 4+:
#         Keep 2 strongest projects with 1 concise bullet each.
#     """
#     compacted = deepcopy(tailored_projects)
#     projects = compacted.get("recommended_projects", [])

#     projects = sorted(
#         projects,
#         key=_project_priority_score,
#         reverse=True,
#     )

#     if attempt == 1:
#         max_projects = 3
#         max_words = 24
#         bullet_limits_by_priority = {
#             "high": 3,
#             "medium": 2,
#             "low": 1,
#         }
#         note = "Trimmed long project bullets but kept useful evidence where possible."

#     elif attempt == 2:
#         max_projects = 3
#         max_words = 24
#         bullet_limits_by_priority = {
#             "high": 2,
#             "medium": 2,
#             "low": 1,
#         }
#         note = "Reduced lower-priority project detail because the resume exceeded one page."

#     elif attempt == 3:
#         max_projects = 3
#         max_words = 20
#         bullet_limits_by_priority = {
#             "high": 2,
#             "medium": 1,
#             "low": 1,
#         }
#         note = (
#         "Kept up to two bullets for high-priority projects and one bullet "
#         "for medium- and low-priority projects."
#         )

#     else:
#         max_projects = 2
#         max_words = 18
#         bullet_limits_by_priority = {
#             "high": 1,
#             "medium": 1,
#             "low": 1,
#         }
#         note = "Kept only the two strongest projects because the resume still exceeded one page."

#     kept_projects = []

#     for project in projects[:max_projects]:
#         priority = str(project.get("priority", "")).lower()
#         bullet_limit = bullet_limits_by_priority.get(priority, 1)

#         original_bullets = project.get("draft_bullets", []) or []


#         compacted_bullets = [
#             _trim_words(bullet, max_words)
#             for bullet in original_bullets[:bullet_limit]
#             if str(bullet).strip()
#         ]

#         project["draft_bullets"] = compacted_bullets

#         if len(compacted_bullets) == 1:
#             project["space_action"] = "single_bullet"
#         elif compacted_bullets != original_bullets:
#             project["space_action"] = "shorten"
#         else:
#             project["space_action"] = "keep_full"

#         # bullets = project.get("draft_bullets", []) or []
#         # project["draft_bullets"] = [
#         #     _trim_words(bullet, max_words)
#         #     for bullet in bullets[:bullet_limit]
#         #     if str(bullet).strip()
#         # ]

#         # if len(project["draft_bullets"]) == 1:
#         #     project["space_action"] = "single_bullet"
#         # elif attempt >= 1:
#         #     project["space_action"] = "shorten"

#         kept_projects.append(project)



#     removed_projects = projects[max_projects:]

#     kept_projects = sorted(
#     kept_projects,
#     key=lambda project: period_sort_value(project.get("period", "")),
#     reverse=True,
#     )

#     compacted["recommended_projects"] = kept_projects
#     compacted["projects_to_remove_or_deprioritize"] = compacted.get(
#         "projects_to_remove_or_deprioritize",
#         [],
#     )

#     for project in removed_projects:
#         compacted["projects_to_remove_or_deprioritize"].append(
#             {
#                 "title": project.get("display_title") or project.get("title", "Untitled Project"),
#                 "reason": "Removed during compacting because the resume exceeded one page.",
#             }
#         )

#     compacted.setdefault("notes_for_user", []).append(
#         f"Applied compact mode attempt {attempt}: {note}"
#     )

#     return compacted

def _bullet_word_count(values: list[str]) -> int:
    """Return the total word count for a bullet list."""
    return sum(
        len(str(value).split())
        for value in values
    )


_COMPACT_ACTION_VERBS = {
    "applied",
    "automated",
    "built",
    "collaborated",
    "configured",
    "containerised",
    "containerized",
    "contributed",
    "created",
    "deployed",
    "designed",
    "developed",
    "engineered",
    "implemented",
    "integrated",
    "led",
    "managed",
    "optimised",
    "optimized",
    "scripted",
    "secured",
    "tested",
    "validated",
}


def _compact_bullets_are_quality_preserving(
    full_bullets: list[str],
    compact_bullets: list[str],
) -> bool:
    """
    Return True only for conservative, one-to-one compact rewrites.

    Complete-bullet removal is handled later by the fitting loop. The compact
    pass should save lines without silently deleting evidence or producing
    weak sentence fragments.
    """
    if not full_bullets or not compact_bullets:
        return False

    if len(compact_bullets) != len(full_bullets):
        return False

    full_word_count = _bullet_word_count(
        full_bullets
    )
    compact_word_count = _bullet_word_count(
        compact_bullets
    )

    if full_word_count <= 0:
        return False

    if compact_word_count >= full_word_count:
        return False

    if compact_word_count / full_word_count < 0.65:
        return False

    for bullet in compact_bullets:
        cleaned = str(bullet or "").strip()
        words = cleaned.split()

        if not 10 <= len(words) <= 24:
            return False

        first_word = re.sub(
            r"[^a-z]+",
            "",
            words[0].lower(),
        )

        if first_word not in _COMPACT_ACTION_VERBS:
            return False

        if cleaned[-1:] not in {".", ";", ":"}:
            return False

    return True


def _count_quality_compact_candidates(
    tailored_projects: dict[str, Any],
) -> int:
    """Count projects with an unused quality-preserving compact alternative."""
    count = 0

    for project in (
        tailored_projects.get(
            "recommended_projects",
            [],
        )
        or []
    ):
        full_bullets = [
            str(value).strip()
            for value in (
                project.get(
                    "draft_bullets",
                    [],
                )
                or []
            )
            if str(value).strip()
        ]

        compact_bullets = [
            str(value).strip()
            for value in (
                project.get(
                    "compact_bullets",
                    [],
                )
                or []
            )
            if str(value).strip()
        ]

        if _compact_bullets_are_quality_preserving(
            full_bullets,
            compact_bullets,
        ):
            count += 1

    return count


def apply_compact_bullets_once(
    tailored_projects: dict[str, Any],
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """
    Apply one quality-preserving compact project rewrite.

    Only one project is compacted per render attempt. This prevents every
    project from being shortened when a smaller change may already make the
    resume fit. Lower-relevance projects are compacted first.
    """
    compacted = deepcopy(
        tailored_projects
    )

    projects = (
        compacted.get(
            "recommended_projects",
            [],
        )
        or []
    )

    eligible_projects: list[
        tuple[dict[str, Any], list[str], list[str]]
    ] = []

    for project in projects:
        if (
            str(
                project.get(
                    "space_action",
                    "",
                )
            )
            == "compact_rewrite"
        ):
            continue

        full_bullets = [
            str(value).strip()
            for value in (
                project.get(
                    "draft_bullets",
                    [],
                )
                or []
            )
            if str(value).strip()
        ]

        compact_bullets = [
            str(value).strip()
            for value in (
                project.get(
                    "compact_bullets",
                    [],
                )
                or []
            )
            if str(value).strip()
        ]

        if _compact_bullets_are_quality_preserving(
            full_bullets,
            compact_bullets,
        ):
            eligible_projects.append(
                (
                    project,
                    full_bullets,
                    compact_bullets,
                )
            )

    if not eligible_projects:
        return (
            compacted,
            False,
            {
                "change_type": (
                    "compact_rewrite_unavailable"
                ),
                "reason": (
                    "No unused quality-preserving compact "
                    "project bullets were available."
                ),
            },
        )

    target_project, full_bullets, compact_bullets = min(
        eligible_projects,
        key=lambda item: (
            _project_priority_score(
                item[0]
            ),
            -(
                _bullet_word_count(
                    item[1]
                )
                - _bullet_word_count(
                    item[2]
                )
            ),
        ),
    )

    previous_space_action = str(
        target_project.get(
            "space_action",
            "keep_full",
        )
    )

    target_project[
        "draft_bullets"
    ] = list(compact_bullets)

    target_project[
        "space_action"
    ] = "compact_rewrite"

    # Compact bullets preserve a one-to-one relationship with the full
    # bullets. Keep the Phase 6B.1 evidence metadata aligned by index.
    sync_project_bullet_metadata(
        target_project,
        bullet_texts=compact_bullets,
    )

    project_title = (
        target_project.get(
            "display_title"
        )
        or target_project.get(
            "title"
        )
        or "Untitled Project"
    )

    change = {
        "change_type": "compact_rewrite",
        "project": project_title,
        "previous_space_action": (
            previous_space_action
        ),
        "original_draft_bullets": list(
            full_bullets
        ),
        "compact_draft_bullets": list(
            compact_bullets
        ),
        "project_priority_score": (
            _project_priority_score(
                target_project
            )
        ),
        "full_bullet_count": len(
            full_bullets
        ),
        "compact_bullet_count": len(
            compact_bullets
        ),
        "full_word_count": (
            _bullet_word_count(
                full_bullets
            )
        ),
        "compact_word_count": (
            _bullet_word_count(
                compact_bullets
            )
        ),
    }

    compacted[
        "recommended_projects"
    ] = sorted(
        projects,
        key=lambda project: (
            period_sort_value(
                project.get(
                    "period",
                    "",
                )
            )
        ),
        reverse=True,
    )

    compacted.setdefault(
        "notes_for_user",
        [],
    ).append(
        "Applied a quality-preserving compact rewrite "
        f"to {project_title} before deleting any "
        "complete project bullet."
    )

    return (
        compacted,
        True,
        change,
    )

def compact_tailored_projects_one_step(
    tailored_projects: dict[str, Any],
    *,
    minimum_bullets_per_project: int = 1,
    minimum_projects_to_keep: int = 3,
    prefer_balanced_bullets: bool = False,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """
    Return the safest deterministic Phase 6C reduction.

    The full one-page fitting loop calls
    ``build_evidence_aware_project_reductions`` directly so it can render and
    compare every eligible bullet candidate. This wrapper remains compatible
    with callers and tests that expect one reduction.
    """
    candidates = build_evidence_aware_project_reductions(
        tailored_projects,
        minimum_bullets_per_project=minimum_bullets_per_project,
        minimum_projects_to_keep=minimum_projects_to_keep,
        prefer_balanced_bullets=prefer_balanced_bullets,
    )

    if not candidates:
        return (
            deepcopy(tailored_projects),
            False,
            {
                "fitting_version": PHASE6C_FITTING_VERSION,
                "change_type": "none",
                "reason": "No evidence-aware project reduction is available.",
            },
        )

    compacted, change = candidates[0]
    return compacted, True, change

def _project_change_title(
    project: dict[str, Any],
) -> str:
    """Return the stable display title used by fitting changes."""
    return str(
        project.get("display_title")
        or project.get("title")
        or "Untitled Project"
    )


def _find_project_for_change(
    tailored_projects: dict[str, Any],
    project_title: str,
) -> dict[str, Any] | None:
    """Find a retained project by the title recorded in a change."""
    for project in (
        tailored_projects.get(
            "recommended_projects",
            [],
        )
        or []
    ):
        if (
            _project_change_title(
                project
            )
            == project_title
        ):
            return project

    return None


def _restore_fitting_change(
    tailored_projects: dict[str, Any],
    change: dict[str, Any],
) -> tuple[
    dict[str, Any],
    bool,
    dict[str, Any],
]:
    """
    Reverse one earlier fitting reduction without changing other projects.
    """
    restored = deepcopy(
        tailored_projects
    )

    change_type = str(
        change.get(
            "change_type",
            "",
        )
    )

    project_title = str(
        change.get(
            "project",
            "",
        )
    )

    if change_type == "compact_rewrite":
        project = _find_project_for_change(
            restored,
            project_title,
        )

        original_bullets = [
            str(value).strip()
            for value in (
                change.get(
                    "original_draft_bullets",
                    [],
                )
                or []
            )
            if str(value).strip()
        ]

        if (
            project is None
            or not original_bullets
        ):
            return (
                restored,
                False,
                {
                    "change_type": (
                        "restore_unavailable"
                    ),
                    "reason": (
                        "The compact rewrite could not "
                        "be restored."
                    ),
                },
            )

        project[
            "draft_bullets"
        ] = original_bullets

        project[
            "space_action"
        ] = str(
            change.get(
                "previous_space_action",
                "keep_full",
            )
        )

        restore_info = {
            "change_type": (
                "restore_compact_rewrite"
            ),
            "project": project_title,
            "restored_change_type": (
                change_type
            ),
            "restored_word_count": (
                _bullet_word_count(
                    original_bullets
                )
            ),
        }

    elif change_type == "remove_bullet":
        project = _find_project_for_change(
            restored,
            project_title,
        )

        removed_bullet = str(
            change.get(
                "removed_bullet",
                "",
            )
        ).strip()

        if project is None or not removed_bullet:
            return (
                restored,
                False,
                {
                    "change_type": (
                        "restore_unavailable"
                    ),
                    "reason": (
                        "The removed bullet could not "
                        "be restored."
                    ),
                },
            )

        bullets = [
            str(value).strip()
            for value in (
                project.get(
                    "draft_bullets",
                    [],
                )
                or []
            )
            if str(value).strip()
        ]

        insert_index = int(
            change.get(
                "removed_bullet_index",
                len(bullets),
            )
            or 0
        )

        insert_index = max(
            0,
            min(
                insert_index,
                len(bullets),
            ),
        )

        bullets.insert(
            insert_index,
            removed_bullet,
        )

        project[
            "draft_bullets"
        ] = bullets

        restore_removed_bullet_metadata(
            project,
            bullet_index=insert_index,
            bullet_text=removed_bullet,
            removed_metadata=change.get("removed_bullet_metadata"),
        )

        project[
            "space_action"
        ] = str(
            change.get(
                "previous_space_action",
                (
                    "single_bullet"
                    if len(bullets) == 1
                    else "keep_full"
                ),
            )
        )

        restore_info = {
            "change_type": (
                "restore_removed_bullet"
            ),
            "project": project_title,
            "restored_change_type": (
                change_type
            ),
            "restored_bullet": (
                removed_bullet
            ),
        }

    elif change_type == "remove_project":
        removed_project = change.get(
            "removed_project_data"
        )

        if not isinstance(
            removed_project,
            dict,
        ):
            return (
                restored,
                False,
                {
                    "change_type": (
                        "restore_unavailable"
                    ),
                    "reason": (
                        "The removed project data is "
                        "not available."
                    ),
                },
            )

        projects = (
            restored.get(
                "recommended_projects",
                [],
            )
            or []
        )

        if any(
            _project_change_title(project)
            == project_title
            for project in projects
        ):
            return (
                restored,
                False,
                {
                    "change_type": (
                        "restore_unavailable"
                    ),
                    "reason": (
                        "The project is already present."
                    ),
                },
            )

        projects.append(
            deepcopy(
                removed_project
            )
        )

        restored[
            "recommended_projects"
        ] = sorted(
            projects,
            key=lambda project: (
                period_sort_value(
                    project.get(
                        "period",
                        "",
                    )
                )
            ),
            reverse=True,
        )

        restore_info = {
            "change_type": (
                "restore_removed_project"
            ),
            "project": project_title,
            "restored_change_type": (
                change_type
            ),
        }

    else:
        return (
            restored,
            False,
            {
                "change_type": (
                    "restore_unavailable"
                ),
                "reason": (
                    "Unsupported fitting change."
                ),
            },
        )

    restored.setdefault(
        "notes_for_user",
        [],
    ).append(
        "Restored stronger project content after "
        "confirming the resume still fits on one page."
    )

    return (
        restored,
        True,
        restore_info,
    )


def _restoration_quality_gain(
    change: dict[str, Any],
) -> int:
    """Score evidence recovered by reversing a fitting change."""
    project_priority = int(change.get("project_priority_score", 0) or 0)
    change_type = str(change.get("change_type", ""))

    if change_type == "compact_rewrite":
        recovered_words = max(
            0,
            int(change.get("full_word_count", 0) or 0)
            - int(change.get("compact_word_count", 0) or 0),
        )
        return project_priority * 10 + recovered_words

    if change_type == "remove_bullet":
        recovered_words = len(
            str(change.get("removed_bullet", "")).split()
        )
        legacy_gain = project_priority * 10 + recovered_words * 3
        phase6c_gain = (
            int(change.get("evidence_loss_score", 0) or 0) * 10
            + recovered_words
        )
        return max(legacy_gain, phase6c_gain)

    if change_type == "remove_project":
        removed_project = change.get("removed_project_data") or {}
        recovered_words = (
            _bullet_word_count(
                removed_project.get("draft_bullets", []) or []
            )
            if isinstance(removed_project, dict)
            else 0
        )
        legacy_gain = 10000 + project_priority * 10 + recovered_words
        phase6c_gain = (
            int(change.get("evidence_loss_score", 0) or 0) * 10
            + recovered_words
        )
        return max(legacy_gain, phase6c_gain)

    return 0

def _restorable_change_indices(
    active_changes: list[
        dict[str, Any]
    ],
) -> list[int]:
    """
    Return changes that can be reversed without conflicting with a later
    change to the same project.
    """
    restorable: list[int] = []

    for index, change in enumerate(
        active_changes
    ):
        project_title = str(
            change.get(
                "project",
                "",
            )
        )

        later_same_project = any(
            str(
                later_change.get(
                    "project",
                    "",
                )
            )
            == project_title
            for later_change in active_changes[
                index + 1:
            ]
        )

        if not later_same_project:
            restorable.append(index)

    return restorable


# ---------------------------------------------------------------------------
# Skills replacement
# ---------------------------------------------------------------------------

def _add_skill_line_after(
    anchor: Paragraph,
    *,
    category: str,
    items: list[str],
    template: Paragraph | None = None,
) -> Paragraph:
    """
    Add one skill line after anchor.

    If the original Skills section used bullets, this preserves that bullet style.
    """
    new_paragraph = _insert_paragraph_after(anchor)

    if template is not None:
        _copy_paragraph_format(template, new_paragraph)
        _copy_numbering(template, new_paragraph)
    else:
        try:
            new_paragraph.style = "List Bullet"
        except Exception:
            pass

    source_run = _get_first_run_template(template)

    if category:
        category_run = new_paragraph.add_run(f"{category}: ")
        _copy_run_format(source_run, category_run)
        category_run.bold = True

        items_run = new_paragraph.add_run(", ".join(items))
        _copy_run_format(source_run, items_run)
        items_run.bold = False
    else:
        line_run = new_paragraph.add_run(", ".join(items))
        _copy_run_format(source_run, line_run)

    return new_paragraph


def replace_skills_section(
    document: DocumentObject,
    tailored_skills: dict[str, Any],
) -> None:
    """
    Replace SKILLS / TECHNICAL SKILLS section content while preserving formatting.
    """
    _, skill_bullet_template = _find_templates_in_section(document, {"SKILLS", "TECHNICAL SKILLS"})

    anchor = _clear_section_content(document, {"SKILLS", "TECHNICAL SKILLS"})
    skill_lines = tailored_skills.get("skill_lines", [])

    if not skill_lines:
        _insert_paragraph_after(anchor, "No tailored skills were generated.")
        return

    for row in skill_lines:
        category = str(row.get("category", "")).strip()
        items = [str(item).strip() for item in row.get("items", []) if str(item).strip()]

        if items:
            anchor = _add_skill_line_after(
                anchor,
                category=category,
                items=items,
                template=skill_bullet_template,
            )


# ---------------------------------------------------------------------------
# Projects replacement
# ---------------------------------------------------------------------------

# def _format_project_heading(project: dict[str, Any]) -> str:
#     """
#     Build a project heading from optional project fields.

#     Supported fields:
#         title: "QueryAI"
#         role: "AI Programmer"
#         display_details: "React, Team of 4"

#     Output examples:
#         QueryAI (React, Team of 4)
#         Job AI Helper – AI Programmer (Python, Streamlit, Solo)

#     If your title already contains bracket details, you can leave role/details empty.
#     """
#     title = str(project.get("title", "Untitled Project")).strip() or "Untitled Project"
#     role = str(project.get("role", "")).strip()
#     details = str(project.get("display_details", "")).strip()

#     heading = title

#     if role and role.lower() not in heading.lower():
#         heading += f" – {role}"

#     if details and details.lower() not in heading.lower():
#         heading += f" ({details})"

#     return heading

def _format_project_heading(project: dict[str, Any]) -> str:
    """
    Build the project heading used in the DOCX.

    Priority:
    1. display_title from the tailored project JSON
    2. title
    3. title + optional role/display_details fallback
    """
    display_title = str(project.get("display_title", "")).strip()
    if display_title:
        return display_title

    title = str(project.get("title", "Untitled Project")).strip() or "Untitled Project"
    role = str(project.get("role", "")).strip()
    details = str(project.get("display_details", "")).strip()

    heading = title

    if role and role.lower() not in heading.lower():
        heading += f" – {role}"

    if details and details.lower() not in heading.lower():
        heading += f" ({details})"

    return heading

def _add_project_title_after(
    anchor: Paragraph,
    *,
    title: str,
    period: str = "",
    template: Paragraph | None = None,
    right_tab_position: Any = None,
    add_space_before: bool = False,
    space_before_pt: int = 10,
) -> Paragraph:
    """
    Add project title line after anchor, preserving original formatting.

    Uses a right-aligned tab stop for the period/date.
    """
    new_paragraph = _insert_paragraph_after(anchor)

    if template is not None:
        _copy_paragraph_format(template, new_paragraph)
    
    if add_space_before:
        new_paragraph.paragraph_format.space_before = Pt(space_before_pt)

    # Keep title and following bullet together where Word supports it.
    try:
        new_paragraph.paragraph_format.keep_with_next = True
    except Exception:
        pass

    # Right tab stop for date.
    if right_tab_position is not None:
        try:
            new_paragraph.paragraph_format.tab_stops.add_tab_stop(
                right_tab_position,
                WD_TAB_ALIGNMENT.RIGHT,
            )
        except Exception:
            pass

    source_run = _get_first_run_template(template)

    title_run = new_paragraph.add_run(title)
    _copy_run_format(source_run, title_run)
    title_run.bold = True

    if period:
        date_run = new_paragraph.add_run(f"\t{period}")
        _copy_run_format(source_run, date_run)
        date_run.bold = False

    return new_paragraph

# def _add_project_title_after(
#     anchor: Paragraph,
#     *,
#     title: str,
#     period: str = "",
#     template: Paragraph | None = None,
#     right_tab_position: Any = None,
#     add_space_before: bool = False,
# ) -> Paragraph:
#     """
#     Add project title line after anchor, preserving original formatting.

#     Uses a right-aligned tab stop for the period/date.
#     """
#     new_paragraph = _insert_paragraph_after(anchor)

#     if template is not None:
#         _copy_paragraph_format(template, new_paragraph)
    
#     if add_space_before:
#         new_paragraph.paragraph_format.space_before = Pt(10)

#     # Keep title and following bullet together where Word supports it.
#     try:
#         new_paragraph.paragraph_format.keep_with_next = True
#     except Exception:
#         pass

#     # Right tab stop for date.
#     if right_tab_position is not None:
#         try:
#             new_paragraph.paragraph_format.tab_stops.add_tab_stop(
#                 right_tab_position,
#                 WD_TAB_ALIGNMENT.RIGHT,
#             )
#         except Exception:
#             pass

#     source_run = _get_first_run_template(template)

#     title_run = new_paragraph.add_run(title)
#     _copy_run_format(source_run, title_run)
#     title_run.bold = True

#     if period:
#         date_run = new_paragraph.add_run(f"\t{period}")
#         _copy_run_format(source_run, date_run)
#         date_run.bold = False

#     return new_paragraph

# def _add_project_title_after(
#     anchor: Paragraph,
#     *,
#     title: str,
#     period: str = "",
#     template: Paragraph | None = None,
#     right_tab_position: Any = None,
# ) -> Paragraph:
#     """
#     Add project title line after anchor, preserving original formatting.

#     Uses a right-aligned tab stop for the period/date.
#     """
#     new_paragraph = _insert_paragraph_after(anchor)

#     if template is not None:
#         _copy_paragraph_format(template, new_paragraph)

#     # Keep title and following bullet together where Word supports it.
#     try:
#         new_paragraph.paragraph_format.keep_with_next = True
#     except Exception:
#         pass

#     # Right tab stop for date.
#     if right_tab_position is not None:
#         try:
#             new_paragraph.paragraph_format.tab_stops.add_tab_stop(
#                 right_tab_position,
#                 WD_TAB_ALIGNMENT.RIGHT,
#             )
#         except Exception:
#             pass

#     source_run = _get_first_run_template(template)

#     title_run = new_paragraph.add_run(title)
#     _copy_run_format(source_run, title_run)
#     title_run.bold = True

#     if period:
#         date_run = new_paragraph.add_run(f"\t{period}")
#         _copy_run_format(source_run, date_run)
#         date_run.bold = False

#     return new_paragraph


def _add_project_bullet_after(
    anchor: Paragraph,
    *,
    bullet: str,
    template: Paragraph | None = None,
) -> Paragraph:
    """
    Add bullet after anchor, preserving original bullet formatting.
    """
    new_paragraph = _insert_paragraph_after(anchor)

    if template is not None:
        _copy_paragraph_format(template, new_paragraph)
        _copy_numbering(template, new_paragraph)
    else:
        try:
            new_paragraph.style = "List Bullet"
        except Exception:
            pass

    source_run = _get_first_run_template(template)

    run = new_paragraph.add_run(str(bullet).strip())
    _copy_run_format(source_run, run)

    return new_paragraph


def replace_projects_section(
    document: DocumentObject,
    tailored_projects: dict[str, Any],
    *,
    max_projects: int = 3,
    max_bullets_per_project: int = 2,
    spacing_mode: str = "paragraph_spacing",
    project_spacing_pt: int = 10,
    after_projects_spacing_pt: int = 10,
    blank_lines_between_projects: int = 1,
    blank_lines_after_projects: int = 1,
    add_spacing_before_first_project: bool = False,
) -> None:
    """
    Replace PROJECTS section content while preserving original formatting.
    """
    project_title_template, project_bullet_template = _find_templates_in_section(document, {"PROJECTS"})

    section = document.sections[0]
    right_tab_position = section.page_width - section.left_margin - section.right_margin

    anchor = _clear_section_content(document, {"PROJECTS"})
    projects = tailored_projects.get("recommended_projects", [])[:max_projects]

    if not projects:
        _insert_paragraph_after(anchor, "No tailored projects were generated.")
        return
    
    for project_index, project in enumerate(projects):
        title = _format_project_heading(project)
        period = str(project.get("period", "")).strip()
        bullets = project.get("draft_bullets", [])[:max_bullets_per_project]

        should_add_spacing_before = project_index > 0 or add_spacing_before_first_project

        if spacing_mode == "blank_line" and should_add_spacing_before:
            for _ in range(blank_lines_between_projects):
                anchor = _add_blank_line_after(anchor)

        anchor = _add_project_title_after(
            anchor,
            title=title,
            period=period,
            template=project_title_template,
            right_tab_position=right_tab_position,
            add_space_before=(
                spacing_mode == "paragraph_spacing"
                and should_add_spacing_before
            ),
            space_before_pt=project_spacing_pt,
        )

        for bullet in bullets:
            if str(bullet).strip():
                anchor = _add_project_bullet_after(
                    anchor,
                    bullet=str(bullet).strip(),
                    template=project_bullet_template,
                )

    if spacing_mode == "blank_line":
        for _ in range(blank_lines_after_projects):
            anchor = _add_blank_line_after(anchor)
    else:
        try:
            anchor.paragraph_format.space_after = Pt(after_projects_spacing_pt)
        except Exception:
            pass

    # for project_index, project in  enumerate(projects):
    #     title = _format_project_heading(project)
    #     period = str(project.get("period", "")).strip()
    #     bullets = project.get("draft_bullets", [])[:max_bullets_per_project]

    #     anchor = _add_project_title_after(
    #         anchor,
    #         title=title,
    #         period=period,
    #         template=project_title_template,
    #         right_tab_position=right_tab_position,
    #         add_space_before=project_index > 0,
    #     )

    #     for bullet in bullets:
    #         if str(bullet).strip():
    #             anchor = _add_project_bullet_after(
    #                 anchor,
    #                 bullet=str(bullet).strip(),
    #                 template=project_bullet_template,
    #             )
    
    #     # Add spacing between the final project entry and the next section heading, e.g. SKILLS.
    # try:
    #     anchor.paragraph_format.space_after = Pt(10)
    # except Exception:
    #     pass

# ---------------------------------------------------------------------------
# Saved Docx Loader
# ---------------------------------------------------------------------------
def get_latest_saved_docx_for_application(application_id: int | None) -> Path | None:
    """
    Return the latest saved DOCX for an application session.

    This works because saved files are named with app_{application_id}_.
    """
    if application_id is None:
        return None

    if not SAVED_RESUME_DIR.exists():
        return None

    matches = sorted(
        SAVED_RESUME_DIR.glob(f"app_{application_id}_*.docx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not matches:
        return None

    return matches[0]

# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_tailored_resume_copy(
    *,
    saved_resume_docx_path: str | Path,
    tailored_projects: dict[str, Any] | None = None,
    tailored_skills: dict[str, Any] | None = None,
    application_id: int | None = None,
    max_projects: int = 3,
    max_bullets_per_project: int = 2,
    spacing_mode: str = "paragraph_spacing",
    project_spacing_pt: int = 10,
    after_projects_spacing_pt: int = 10,
    blank_lines_between_projects: int = 1,
    blank_lines_after_projects: int = 1,
    add_spacing_before_first_project: bool = False,
) -> Path:
    """
    Generate a new tailored resume DOCX copy.

    Only Skills and Projects are changed.
    Work Experience is not changed.
    """
    saved_resume_docx_path = Path(saved_resume_docx_path)

    if not saved_resume_docx_path.exists():
        raise FileNotFoundError(f"Saved resume DOCX not found: {saved_resume_docx_path}")

    TAILORED_RESUME_DIR.mkdir(parents=True, exist_ok=True)

    # cleanup_old_tailored_outputs_for_application(application_id)

    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    app_part = f"app_{application_id}_" if application_id is not None else ""
    output_path = TAILORED_RESUME_DIR / f"{app_part}tailored_resume_{timestamp}.docx"

    # Never edit the saved original directly. Always copy first.
    shutil.copy2(saved_resume_docx_path, output_path)

    document = Document(output_path)

    # Change only the sections that were generated.
    if not tailored_projects and not tailored_skills:
        raise ValueError("Generate a tailored Projects section or Skills section first.")

    if tailored_skills:
        replace_skills_section(document, tailored_skills)

    if tailored_projects:
        replace_projects_section(
            document,
            tailored_projects,
            max_projects=max_projects,
            max_bullets_per_project=max_bullets_per_project,
            spacing_mode=spacing_mode,
            project_spacing_pt=project_spacing_pt,
            after_projects_spacing_pt=after_projects_spacing_pt,
            blank_lines_between_projects=blank_lines_between_projects,
            blank_lines_after_projects=blank_lines_after_projects,
            add_spacing_before_first_project=add_spacing_before_first_project,
        )

    # # Change only these sections.
    # replace_skills_section(document, tailored_skills)
    # replace_projects_section(
    #     document,
    #     tailored_projects,
    #     max_projects=max_projects,
    #     max_bullets_per_project=max_bullets_per_project,
    # )

    document.save(output_path)

    return output_path


# def _project_priority_score(project: dict[str, Any]) -> int:
#     """Rank projects so weaker projects are reduced first."""
#     priority = str(project.get("priority", "")).lower()

#     if priority == "high":
#         base = 300
#     elif priority == "medium":
#         base = 200
#     elif priority == "low":
#         base = 100
#     else:
#         base = 150

#     matched_count = len(project.get("matched_jd_requirements", []) or [])

#     return base + matched_count


# def _trim_words(text: str, max_words: int) -> str:
#     """Trim a bullet to a rough word limit."""
#     words = str(text).split()

#     if len(words) <= max_words:
#         return str(text).strip()

#     trimmed = " ".join(words[:max_words]).rstrip(".,;:")
#     return trimmed + "."

# old version
# def compact_tailored_projects_for_space(
#     tailored_projects: dict[str, Any],
#     *,
#     attempt: int,
# ) -> dict[str, Any]:
#     """
#     Reduce Projects section size when the generated resume exceeds one page.

#     attempt 1: keep 3 projects, high priority gets up to 2 bullets, others 1.
#     attempt 2: keep 3 projects, everyone gets 1 shorter bullet.
#     attempt 3: keep 2 strongest projects, everyone gets 1 short bullet.
#     """
#     compacted = deepcopy(tailored_projects)
#     projects = compacted.get("recommended_projects", [])

#     projects = sorted(projects, key=_project_priority_score, reverse=True)

#     if attempt == 1:
#         max_projects = 3
#         high_bullets = 2
#         other_bullets = 1
#         max_words = 24
#     elif attempt == 2:
#         max_projects = 3
#         high_bullets = 1
#         other_bullets = 1
#         max_words = 20
#     else:
#         max_projects = 2
#         high_bullets = 1
#         other_bullets = 1
#         max_words = 18

#     kept_projects = []

#     for project in projects[:max_projects]:
#         priority = str(project.get("priority", "")).lower()
#         bullet_limit = high_bullets if priority == "high" else other_bullets

#         bullets = project.get("draft_bullets", []) or []
#         project["draft_bullets"] = [
#             _trim_words(bullet, max_words)
#             for bullet in bullets[:bullet_limit]
#             if str(bullet).strip()
#         ]

#         if len(project["draft_bullets"]) <= 1:
#             project["space_action"] = "single_bullet"
#         else:
#             project["space_action"] = "shorten"

#         kept_projects.append(project)

#     removed_projects = projects[max_projects:]
#     compacted["recommended_projects"] = kept_projects

#     compacted.setdefault("projects_to_remove_or_deprioritize", [])

#     for project in removed_projects:
#         compacted["projects_to_remove_or_deprioritize"].append(
#             {
#                 "title": project.get("display_title") or project.get("title", "Untitled Project"),
#                 "reason": "Removed during compacting because the generated resume exceeded one page.",
#             }
#         )

#     compacted.setdefault("notes_for_user", []).append(
#         f"Applied compact mode attempt {attempt} to reduce page overflow."
#     )

#     return compacted

# def compact_tailored_projects_for_space(
#     tailored_projects: dict[str, Any],
#     *,
#     attempt: int,
# ) -> dict[str, Any]:
#     """
#     Reduce the Projects section only after the full generated resume
#     exceeds one page.

#     attempt 1:
#         Keep 3 projects.
#         High priority: up to 3 bullets.
#         Medium priority: up to 2 bullets.
#         Low priority: up to 1 bullet.

#     attempt 2:
#         Keep 3 projects.
#         High and medium priority: up to 2 bullets.
#         Low priority: 1 bullet.

#     attempt 3:
#         Keep 3 projects.
#         High priority: up to 2 bullets.
#         Medium and low priority: 1 bullet.

#     attempt 4+:
#         Keep the 2 strongest projects with 1 bullet each.
#     """
#     compacted = deepcopy(tailored_projects)
#     projects = compacted.get("recommended_projects", [])

#     # Sort by relevance only to decide which projects survive compaction.
#     projects = sorted(
#         projects,
#         key=_project_priority_score,
#         reverse=True,
#     )

#     if attempt == 1:
#         max_projects = 3
#         max_words = 24
#         bullet_limits_by_priority = {
#             "high": 3,
#             "medium": 2,
#             "low": 1,
#         }
#         note = (
#             "Kept most selected content while trimming long bullets. "
#             "Medium-priority projects retain up to two bullets."
#         )

#     elif attempt == 2:
#         max_projects = 3
#         max_words = 22
#         bullet_limits_by_priority = {
#             "high": 2,
#             "medium": 2,
#             "low": 1,
#         }
#         note = (
#             "Reduced project detail moderately because the resume "
#             "still exceeded one page."
#         )

#     elif attempt == 3:
#         max_projects = 3
#         max_words = 20
#         bullet_limits_by_priority = {
#             "high": 2,
#             "medium": 1,
#             "low": 1,
#         }
#         note = (
#             "Reduced lower-priority project detail further because "
#             "the resume still exceeded one page."
#         )

#     else:
#         max_projects = 2
#         max_words = 18
#         bullet_limits_by_priority = {
#             "high": 1,
#             "medium": 1,
#             "low": 1,
#         }
#         note = (
#             "Kept only the two strongest projects because the resume "
#             "still exceeded one page."
#         )

#     kept_projects = []

#     for project in projects[:max_projects]:
#         priority = str(project.get("priority", "")).lower()
#         bullet_limit = bullet_limits_by_priority.get(priority, 1)

#         original_bullets = project.get("draft_bullets", []) or []

#         project["draft_bullets"] = [
#             _trim_words(bullet, max_words)
#             for bullet in original_bullets[:bullet_limit]
#             if str(bullet).strip()
#         ]

#         if len(project["draft_bullets"]) == 1:
#             project["space_action"] = "single_bullet"
#         elif len(project["draft_bullets"]) < len(original_bullets):
#             project["space_action"] = "shorten"
#         else:
#             project["space_action"] = "keep_full"

#         kept_projects.append(project)

#     removed_projects = projects[max_projects:]

#     # Sort the final displayed projects by latest period first.
#     kept_projects = sorted(
#         kept_projects,
#         key=lambda project: period_sort_value(project.get("period", "")),
#         reverse=True,
#     )

#     compacted["recommended_projects"] = kept_projects
#     compacted.setdefault("projects_to_remove_or_deprioritize", [])

#     for project in removed_projects:
#         compacted["projects_to_remove_or_deprioritize"].append(
#             {
#                 "title": (
#                     project.get("display_title")
#                     or project.get("title", "Untitled Project")
#                 ),
#                 "reason": (
#                     "Removed during compacting because the generated "
#                     "resume exceeded one page."
#                 ),
#             }
#         )

#     compacted.setdefault("notes_for_user", []).append(
#         f"Applied compact mode attempt {attempt}: {note}"
#     )

#     return compacted


def _project_reduction_quality_loss(
    change: dict[str, Any],
) -> int:
    """Estimate evidence loss for one project fitting change."""
    phase6c_loss = change.get("evidence_loss_score")
    if phase6c_loss is not None:
        return max(0, int(phase6c_loss or 0))

    priority = int(change.get("project_priority_score", 0) or 0)
    change_type = str(change.get("change_type", ""))

    if change_type == "compact_rewrite":
        removed_words = max(
            0,
            int(change.get("full_word_count", 0) or 0)
            - int(change.get("compact_word_count", 0) or 0),
        )
        return 200 + priority // 2 + removed_words

    if change_type == "remove_bullet":
        removed_words = len(
            str(change.get("removed_bullet", "")).split()
        )
        return 600 + priority + removed_words * 5

    if change_type == "remove_project":
        return 10000 + priority * 10

    return 100000

def _skill_reduction_quality_loss(change: dict[str, Any]) -> int:
    """Estimate evidence loss for removing one Skills item."""
    return 100 + int(change.get("skill_priority_score", 0) or 0)


def _whole_resume_change_key(change: dict[str, Any]) -> str:
    section = str(change.get("section", "projects"))

    if section == "skills":
        return (
            "skills:"
            + str(change.get("category", ""))
        )

    return (
        "projects:"
        + str(change.get("project", ""))
    )


def _whole_resume_restorable_change_indices(
    active_changes: list[dict[str, Any]],
) -> list[int]:
    """Return fitting changes that can be reversed without later conflicts."""
    restorable: list[int] = []

    for index, change in enumerate(active_changes):
        resource_key = _whole_resume_change_key(change)
        later_same_resource = any(
            _whole_resume_change_key(later_change) == resource_key
            for later_change in active_changes[index + 1:]
        )

        if not later_same_resource:
            restorable.append(index)

    return restorable


def _restore_whole_resume_change(
    tailored_projects: dict[str, Any] | None,
    tailored_skills: dict[str, Any] | None,
    change: dict[str, Any],
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    bool,
    dict[str, Any],
]:
    section = str(change.get("section", "projects"))

    if section == "skills":
        if not isinstance(tailored_skills, dict):
            return tailored_projects, tailored_skills, False, {
                "section": "skills",
                "change_type": "restore_unavailable",
                "reason": "The tailored Skills result is unavailable.",
            }

        restored_skills, restored, restore_info = restore_skill_change(
            tailored_skills,
            change,
        )
        return tailored_projects, restored_skills, restored, restore_info

    if not isinstance(tailored_projects, dict):
        return tailored_projects, tailored_skills, False, {
            "section": "projects",
            "change_type": "restore_unavailable",
            "reason": "The tailored Projects result is unavailable.",
        }

    restored_projects, restored, restore_info = _restore_fitting_change(
        tailored_projects,
        change,
    )
    restore_info["section"] = "projects"
    return restored_projects, tailored_skills, restored, restore_info


def _whole_resume_restoration_quality_gain(change: dict[str, Any]) -> int:
    if str(change.get("section", "projects")) == "skills":
        return skill_restoration_quality_gain(change)
    return _restoration_quality_gain(change)




_LAYOUT_EFFECT_THRESHOLD = 0.002
_PAGE_DENSITY_MAX_FILL = {
    "balanced": 0.92,
    "maximize": 0.97,
}


def _normalise_page_density_mode(value: str) -> str:
    mode = str(value or "balanced").strip().lower()
    return mode if mode in _PAGE_DENSITY_MAX_FILL else "balanced"


def _rendered_overflow_value(rendered: dict[str, Any]) -> float:
    """Return comparable overflow units above the one-page target."""
    page_count = rendered.get("page_count")
    if page_count is None:
        return float("inf")

    if int(page_count) <= 1:
        return 0.0

    metrics = rendered.get("fill_metrics", {}) or {}
    overflow_ratio = metrics.get("overflow_ratio")
    if overflow_ratio is not None:
        return max(0.0, float(overflow_ratio))

    return float(max(1, int(page_count) - 1))


def _change_identity(change: dict[str, Any]) -> str:
    """Create a deterministic identity for reduction/restoration probes."""
    return "|".join(
        [
            str(change.get("section", "projects")),
            str(change.get("change_type", "")),
            str(change.get("project", "")),
            str(change.get("category", "")),
            str(change.get("removed_skill", "")),
            str(change.get("removed_bullet_index", "")),
        ]
    )


def _choose_layout_aware_reduction(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Choose a rendered reduction while protecting requirement evidence.

    Phase 6C first limits consideration to candidates with the lowest
    protection tier that produce a measurable layout improvement. It then uses
    the existing one-page/efficiency comparison inside that safer tier.
    """
    if not candidates:
        raise ValueError("No rendered fitting candidates were supplied.")

    effective = [
        candidate
        for candidate in candidates
        if candidate.get("reaches_one_page")
        or float(candidate.get("space_saved_ratio", 0.0) or 0.0)
        >= _LAYOUT_EFFECT_THRESHOLD
    ]
    pool = effective or list(candidates)

    def protection_tier(candidate: dict[str, Any]) -> int:
        change = candidate.get("change", {}) or {}
        return max(0, int(change.get("protection_tier", 0) or 0))

    safest_tier = min(protection_tier(candidate) for candidate in pool)
    pool = [
        candidate
        for candidate in pool
        if protection_tier(candidate) == safest_tier
    ]

    def key(
        candidate: dict[str, Any],
    ) -> tuple[float, float, int, int]:
        reaches_one_page = bool(candidate.get("reaches_one_page"))
        space_saved = float(
            candidate.get("space_saved_ratio", 0.0) or 0.0
        )
        quality_loss = float(candidate.get("quality_loss", 0) or 0)
        candidate_order = int(
            candidate.get("candidate_order", 99) or 99
        )
        change = candidate.get("change", {}) or {}
        evidence_priority = max(
            0,
            int(change.get("evidence_priority", 0) or 0),
        )

        if reaches_one_page:
            return (
                0.0,
                quality_loss,
                -evidence_priority,
                candidate_order,
            )

        if space_saved >= _LAYOUT_EFFECT_THRESHOLD:
            return (
                1.0,
                quality_loss / space_saved,
                -evidence_priority,
                candidate_order,
            )

        return (
            2.0,
            quality_loss,
            -evidence_priority,
            candidate_order,
        )

    return min(pool, key=key)

def generate_tailored_resume_copy_fit_one_page(
    *,
    saved_resume_docx_path: str | Path,
    tailored_projects: dict[str, Any] | None = None,
    tailored_skills: dict[str, Any] | None = None,
    application_id: int | None = None,
    max_projects: int = 3,
    max_bullets_per_project: int = 3,
    spacing_mode: str = "paragraph_spacing",
    project_spacing_pt: int = 10,
    after_projects_spacing_pt: int = 10,
    blank_lines_between_projects: int = 1,
    blank_lines_after_projects: int = 1,
    add_spacing_before_first_project: bool = False,
    use_compact_before_delete: bool = False,
    prefer_balanced_bullets: bool = False,
    allow_skills_compaction: bool = False,
    minimum_total_skills: int = 8,
    page_density_mode: str = "balanced",
    generation_id: str | None = None,
) -> dict[str, Any]:
    """
    Fit the tailored resume to one page using layout-aware candidate probes.

    Phase 5.1 does not rerun résumé analysis, project selection, or the LLM.
    It compares the already-generated Projects and Skills using deterministic
    evidence-loss estimates and actual rendered PDF space saved.
    """
    if not tailored_projects and not tailored_skills:
        raise ValueError(
            "Generate a tailored Projects section or Skills section first."
        )

    density_mode = _normalise_page_density_mode(page_density_mode)
    density_max_fill = _PAGE_DENSITY_MAX_FILL[density_mode]

    cleanup_old_tailored_outputs_for_application(application_id)

    attempt_logs: list[dict[str, Any]] = []
    working_projects = deepcopy(tailored_projects) if tailored_projects else None
    working_skills = deepcopy(tailored_skills) if tailored_skills else None

    if working_projects:
        visible_projects = (
            working_projects.get("recommended_projects", []) or []
        )[:max_projects]

        for project in visible_projects:
            project["draft_bullets"] = (
                project.get("draft_bullets", []) or []
            )[:max_bullets_per_project]
            project["compact_bullets"] = (
                project.get("compact_bullets", []) or []
            )[:max_bullets_per_project]

            sync_project_bullet_metadata(
                project,
                bullet_texts=project["draft_bullets"],
            )

        working_projects["recommended_projects"] = visible_projects

    active_changes: list[dict[str, Any]] = []

    source_signature = source_docx_signature(
        saved_resume_docx_path
    )
    render_layout_options = {
        "max_projects": max_projects,
        "max_bullets_per_project": max_bullets_per_project,
        "spacing_mode": spacing_mode,
        "project_spacing_pt": project_spacing_pt,
        "after_projects_spacing_pt": after_projects_spacing_pt,
        "blank_lines_between_projects": blank_lines_between_projects,
        "blank_lines_after_projects": blank_lines_after_projects,
        "add_spacing_before_first_project": (
            add_spacing_before_first_project
        ),
    }
    render_cache: dict[str, dict[str, Any]] = {}
    optimization_stats: dict[str, int] = {
        "candidate_state_requests": 0,
        "render_cache_hits": 0,
        "render_cache_misses": 0,
        "libreoffice_batch_processes": 0,
        "libreoffice_fallback_processes": 0,
        "reduction_tier_batches": 0,
        "reduction_candidates_generated": 0,
        "reduction_candidates_rendered": 0,
        "reduction_candidates_skipped_by_tier_stop": 0,
        "restoration_batch_count": 0,
        "restoration_candidates_rendered": 0,
    }

    def optimization_summary() -> dict[str, Any]:
        return {
            "fitting_optimization_version": (
                PHASE6C1_OPTIMIZATION_VERSION
            ),
            "render_cache_entry_count": len(render_cache),
            "libreoffice_process_count": (
                optimization_stats[
                    "libreoffice_batch_processes"
                ]
                + optimization_stats[
                    "libreoffice_fallback_processes"
                ]
            ),
            **optimization_stats,
        }

    def _empty_fill_metrics() -> dict[str, Any]:
        return {
            "page_fill_ratio": None,
            "estimated_unused_page_ratio": None,
            "last_page_fill_ratio": None,
            "overflow_ratio": None,
            "occupied_page_units": None,
            "measurement_method": "unavailable",
        }

    def _candidate_counts(
        projects_state: dict[str, Any] | None,
        skills_state: dict[str, Any] | None,
    ) -> dict[str, int]:
        projects = (
            (projects_state or {}).get(
                "recommended_projects",
                [],
            )
            or []
        )
        return {
            "project_count": len(projects),
            "bullet_count": sum(
                len(project.get("draft_bullets", []) or [])
                for project in projects
            ),
            "skill_line_count": len(
                (skills_state or {}).get(
                    "skill_lines",
                    [],
                )
                or []
            ),
            "skill_item_count": count_skill_items(
                skills_state
            ),
        }

    def _prepare_candidate(
        specification: dict[str, Any],
    ) -> dict[str, Any]:
        projects_state = specification.get("projects")
        skills_state = specification.get("skills")
        fingerprint = build_render_state_fingerprint(
            source_signature=source_signature,
            projects_state=projects_state,
            skills_state=skills_state,
            layout_options=render_layout_options,
        )
        docx_path = generate_tailored_resume_copy(
            saved_resume_docx_path=saved_resume_docx_path,
            tailored_projects=projects_state,
            tailored_skills=skills_state,
            application_id=application_id,
            max_projects=max_projects,
            max_bullets_per_project=max_bullets_per_project,
            spacing_mode=spacing_mode,
            project_spacing_pt=project_spacing_pt,
            after_projects_spacing_pt=after_projects_spacing_pt,
            blank_lines_between_projects=(
                blank_lines_between_projects
            ),
            blank_lines_after_projects=(
                blank_lines_after_projects
            ),
            add_spacing_before_first_project=(
                add_spacing_before_first_project
            ),
        )
        return {
            **specification,
            "docx_path": Path(docx_path),
            "render_state_fingerprint": fingerprint,
        }

    def _complete_prepared_candidate(
        prepared: dict[str, Any],
        *,
        pdf_path: Path | None,
        batch_label: str,
        batch_size: int,
        cache_hit: bool,
    ) -> dict[str, Any]:
        docx_path = Path(prepared["docx_path"])
        fingerprint = str(
            prepared["render_state_fingerprint"]
        )
        cached = render_cache.get(fingerprint)

        if cache_hit and cached is not None:
            expected_pdf_path = (
                PREVIEW_DIR.resolve()
                / f"{docx_path.stem}.pdf"
            )
            expected_pdf_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            expected_pdf_path.write_bytes(
                cached["pdf_bytes"]
            )
            pdf_path = expected_pdf_path
            page_count = int(cached["page_count"])
            fill_metrics = deepcopy(
                cached["fill_metrics"]
            )
        elif pdf_path is not None:
            page_count = count_pdf_pages(pdf_path)
            fill_metrics = measure_pdf_page_fill(
                pdf_path
            )
            try:
                pdf_bytes = Path(pdf_path).read_bytes()
            except OSError:
                pdf_bytes = b""

            if pdf_bytes:
                render_cache[fingerprint] = {
                    "pdf_bytes": pdf_bytes,
                    "page_count": page_count,
                    "fill_metrics": deepcopy(
                        fill_metrics
                    ),
                }
        else:
            page_count = None
            fill_metrics = _empty_fill_metrics()

        entry: dict[str, Any] = {
            "attempt": len(attempt_logs) + 1,
            "attempt_type": prepared["attempt_type"],
            "docx_path": str(docx_path),
            "pdf_path": (
                str(pdf_path)
                if pdf_path is not None
                else None
            ),
            "page_count": page_count,
            "render_cache_hit": cache_hit,
            "render_state_fingerprint": fingerprint,
            "libreoffice_batch_label": batch_label,
            "libreoffice_batch_size": batch_size,
        }

        if page_count is not None:
            entry.update(
                _candidate_counts(
                    prepared.get("projects"),
                    prepared.get("skills"),
                )
            )
            entry.update(fill_metrics)

        change_applied = prepared.get(
            "change_applied"
        )
        if change_applied is not None:
            entry["change_applied"] = change_applied
        if prepared.get("restoration_candidate"):
            entry["restoration_candidate"] = True
        if (
            prepared.get(
                "restoration_quality_gain"
            )
            is not None
        ):
            entry["restoration_quality_gain"] = (
                prepared[
                    "restoration_quality_gain"
                ]
            )
        if prepared.get("probe_candidate"):
            entry["probe_candidate"] = True
        if prepared.get("quality_loss") is not None:
            entry["quality_loss"] = prepared[
                "quality_loss"
            ]

        attempt_logs.append(entry)
        return {
            "docx_path": docx_path,
            "pdf_path": pdf_path,
            "page_count": page_count,
            "fill_metrics": fill_metrics,
            "attempt_entry": entry,
        }

    def render_candidates_batch(
        specifications: list[dict[str, Any]],
        *,
        batch_label: str,
    ) -> list[dict[str, Any]]:
        if not specifications:
            return []

        optimization_stats[
            "candidate_state_requests"
        ] += len(specifications)

        prepared_candidates = [
            _prepare_candidate(specification)
            for specification in specifications
        ]
        uncached: list[dict[str, Any]] = []

        for prepared in prepared_candidates:
            fingerprint = str(
                prepared[
                    "render_state_fingerprint"
                ]
            )
            if fingerprint in render_cache:
                optimization_stats[
                    "render_cache_hits"
                ] += 1
            else:
                optimization_stats[
                    "render_cache_misses"
                ] += 1
                uncached.append(prepared)

        converted: dict[str, Path | None] = {}
        if uncached:
            converted, diagnostics = (
                convert_docx_batch_to_pdf_if_possible(
                    [
                        prepared["docx_path"]
                        for prepared in uncached
                    ]
                )
            )
            optimization_stats[
                "libreoffice_batch_processes"
            ] += int(
                diagnostics.get(
                    "batch_process_count",
                    0,
                )
                or 0
            )
            optimization_stats[
                "libreoffice_fallback_processes"
            ] += int(
                diagnostics.get(
                    "fallback_process_count",
                    0,
                )
                or 0
            )

        results: list[dict[str, Any]] = []
        batch_size = len(prepared_candidates)

        for prepared in prepared_candidates:
            fingerprint = str(
                prepared[
                    "render_state_fingerprint"
                ]
            )
            cache_hit = fingerprint in render_cache
            pdf_path = None

            if not cache_hit:
                pdf_path = converted.get(
                    str(
                        Path(
                            prepared["docx_path"]
                        ).resolve()
                    )
                )

            results.append(
                _complete_prepared_candidate(
                    prepared,
                    pdf_path=pdf_path,
                    batch_label=batch_label,
                    batch_size=batch_size,
                    cache_hit=cache_hit,
                )
            )

        return results

    def render_candidate(
        projects_state: dict[str, Any] | None,
        skills_state: dict[str, Any] | None,
        *,
        attempt_type: str,
        change_applied: dict[str, Any] | None = None,
        restoration_candidate: bool = False,
        restoration_quality_gain: int | None = None,
        probe_candidate: bool = False,
        quality_loss: int | None = None,
    ) -> dict[str, Any]:
        return render_candidates_batch(
            [
                {
                    "projects": projects_state,
                    "skills": skills_state,
                    "attempt_type": attempt_type,
                    "change_applied": change_applied,
                    "restoration_candidate": (
                        restoration_candidate
                    ),
                    "restoration_quality_gain": (
                        restoration_quality_gain
                    ),
                    "probe_candidate": probe_candidate,
                    "quality_loss": quality_loss,
                }
            ],
            batch_label=attempt_type,
        )[0]

    removable_bullet_count = 0
    removable_project_count = 0
    compact_candidate_count = 0

    if working_projects:
        original_projects = working_projects.get("recommended_projects", []) or []
        removable_bullet_count = sum(
            max(0, len(project.get("draft_bullets", []) or []) - 1)
            for project in original_projects
        )
        removable_project_count = max(0, len(original_projects) - 2)
        compact_candidate_count = (
            _count_quality_compact_candidates(working_projects)
            if use_compact_before_delete
            else 0
        )

    skill_candidate_count = (
        count_skill_reduction_candidates(
            working_skills,
            minimum_total_items=minimum_total_skills,
        )
        if allow_skills_compaction and working_skills
        else 0
    )

    reduction_attempt_limit = (
        compact_candidate_count
        + removable_bullet_count
        + removable_project_count
        + skill_candidate_count
    )

    current_render = render_candidate(
        working_projects,
        working_skills,
        attempt_type="full",
    )

    if current_render["pdf_path"] is None:
        return {
            "generation_id": generation_id,
            "fitting_version": PHASE6C_FITTING_VERSION,
            "docx_path": current_render["docx_path"],
            "pdf_path": None,
            "page_count": None,
            "fit_one_page": None,
            "attempts": attempt_logs,
            "tailored_projects_used": working_projects,
            "tailored_skills_used": working_skills,
            "page_fill_ratio": None,
            "estimated_unused_page_ratio": None,
            "page_density_mode": density_mode,
            "density_target_max": density_max_fill,
            **optimization_summary(),
            "note": (
                "Could not check page count because LibreOffice is unavailable "
                "or DOCX-to-PDF conversion failed. DOCX generation still worked."
            ),
        }

    fitting_render: dict[str, Any] | None = None

    if int(current_render["page_count"]) <= 1:
        fitting_render = current_render

    for _ in range(reduction_attempt_limit):
        if fitting_render is not None:
            break

        candidate_changes: list[dict[str, Any]] = []

        if use_compact_before_delete and working_projects:
            compact_projects, changed, change = apply_compact_bullets_once(
                working_projects
            )
            if changed:
                change = deepcopy(change)
                change["section"] = "projects"
                candidate_changes.append(
                    {
                        "projects": compact_projects,
                        "skills": working_skills,
                        "change": change,
                        "quality_loss": _project_reduction_quality_loss(change),
                        "candidate_order": 1,
                    }
                )

        if allow_skills_compaction and working_skills:
            compact_skills, changed, change = compact_skills_one_step(
                working_skills,
                minimum_total_items=minimum_total_skills,
            )
            if changed:
                candidate_changes.append(
                    {
                        "projects": working_projects,
                        "skills": compact_skills,
                        "change": change,
                        "quality_loss": _skill_reduction_quality_loss(change),
                        "candidate_order": 0,
                    }
                )

        if working_projects:
            project_reductions = build_evidence_aware_project_reductions(
                working_projects,
                prefer_balanced_bullets=prefer_balanced_bullets,
            )
            for reduction_index, (
                reduced_projects,
                raw_change,
            ) in enumerate(project_reductions, start=2):
                change = deepcopy(raw_change)
                change["section"] = "projects"
                candidate_changes.append(
                    {
                        "projects": reduced_projects,
                        "skills": working_skills,
                        "change": change,
                        "quality_loss": _project_reduction_quality_loss(
                            change
                        ),
                        "candidate_order": reduction_index,
                    }
                )

        if not candidate_changes:
            break

        baseline_overflow = _rendered_overflow_value(
            current_render
        )
        rendered_candidates: list[
            dict[str, Any]
        ] = []
        tier_groups = (
            group_candidates_by_protection_tier(
                candidate_changes
            )
        )
        rendered_tiers: list[int] = []
        stopped_after_tier: int | None = None

        optimization_stats[
            "reduction_candidates_generated"
        ] += len(candidate_changes)

        for tier_index, (
            protection_tier,
            tier_candidates,
        ) in enumerate(tier_groups):
            rendered_tiers.append(protection_tier)
            optimization_stats[
                "reduction_tier_batches"
            ] += 1

            rendered_batch = render_candidates_batch(
                [
                    {
                        "projects": candidate[
                            "projects"
                        ],
                        "skills": candidate[
                            "skills"
                        ],
                        "attempt_type": str(
                            candidate["change"].get(
                                "change_type",
                                "fitting_change",
                            )
                        ),
                        "change_applied": candidate[
                            "change"
                        ],
                        "probe_candidate": True,
                        "quality_loss": int(
                            candidate[
                                "quality_loss"
                            ]
                        ),
                    }
                    for candidate in tier_candidates
                ],
                batch_label=(
                    "reduction_tier_"
                    f"{protection_tier}"
                ),
            )

            tier_rendered_candidates: list[
                dict[str, Any]
            ] = []

            for candidate, rendered in zip(
                tier_candidates,
                rendered_batch,
            ):
                optimization_stats[
                    "reduction_candidates_rendered"
                ] += 1

                if rendered["pdf_path"] is None:
                    _delete_generated_output(
                        rendered["docx_path"],
                        None,
                    )
                    continue

                candidate_overflow = (
                    _rendered_overflow_value(
                        rendered
                    )
                )
                space_saved = max(
                    0.0,
                    baseline_overflow
                    - candidate_overflow,
                )
                reaches_one_page = (
                    int(rendered["page_count"]) <= 1
                )
                layout_effect = (
                    "reached_one_page"
                    if reaches_one_page
                    else (
                        "reduced_overflow"
                        if space_saved
                        >= _LAYOUT_EFFECT_THRESHOLD
                        else "no_measurable_effect"
                    )
                )
                efficiency_score = (
                    float(candidate["quality_loss"])
                    / max(
                        space_saved,
                        _LAYOUT_EFFECT_THRESHOLD,
                    )
                )

                rendered[
                    "attempt_entry"
                ].update(
                    {
                        "baseline_overflow_ratio": round(
                            baseline_overflow,
                            3,
                        ),
                        "candidate_overflow_ratio": round(
                            candidate_overflow,
                            3,
                        ),
                        "space_saved_ratio": round(
                            space_saved,
                            3,
                        ),
                        "layout_effect": layout_effect,
                        "layout_efficiency_score": round(
                            efficiency_score,
                            2,
                        ),
                        "phase6c1_protection_tier_batch": (
                            protection_tier
                        ),
                    }
                )

                tier_rendered_candidates.append(
                    {
                        **candidate,
                        "rendered": rendered,
                        "space_saved_ratio": (
                            space_saved
                        ),
                        "reaches_one_page": (
                            reaches_one_page
                        ),
                        "layout_effect": layout_effect,
                        "layout_efficiency_score": (
                            efficiency_score
                        ),
                    }
                )

            rendered_candidates.extend(
                tier_rendered_candidates
            )

            if any(
                rendered_candidate_is_effective(
                    candidate,
                    layout_effect_threshold=(
                        _LAYOUT_EFFECT_THRESHOLD
                    ),
                )
                for candidate in (
                    tier_rendered_candidates
                )
            ):
                stopped_after_tier = protection_tier
                skipped = sum(
                    len(later_candidates)
                    for _, later_candidates
                    in tier_groups[
                        tier_index + 1:
                    ]
                )
                optimization_stats[
                    "reduction_candidates_skipped_by_tier_stop"
                ] += skipped
                break

        if not rendered_candidates:
            break

        chosen = _choose_layout_aware_reduction(rendered_candidates)

        current_render["attempt_entry"]["phase6c1_tier_plan"] = {
            "optimization_version": PHASE6C1_OPTIMIZATION_VERSION,
            "tiers_available": [
                tier
                for tier, _ in tier_groups
            ],
            "tiers_rendered": rendered_tiers,
            "stopped_after_effective_tier": stopped_after_tier,
            "higher_tier_candidate_count_skipped": sum(
                len(candidates)
                for tier, candidates in tier_groups
                if (
                    stopped_after_tier is not None
                    and tier > stopped_after_tier
                )
            ),
        }

        current_render["attempt_entry"]["candidate_changes_considered"] = [
            {
                "section": candidate["change"].get("section", "projects"),
                "change_type": candidate["change"].get("change_type"),
                "project": candidate["change"].get("project"),
                "category": candidate["change"].get("category"),
                "removed_skill": candidate["change"].get("removed_skill"),
                "removed_bullet_index": candidate["change"].get(
                    "removed_bullet_index"
                ),
                "protection_tier": candidate["change"].get(
                    "protection_tier",
                    0,
                ),
                "supported_requirement_ids": candidate["change"].get(
                    "supported_requirement_ids",
                    [],
                ),
                "protected_requirement_ids": candidate["change"].get(
                    "protected_requirement_ids",
                    [],
                ),
                "globally_unique_requirement_ids": candidate["change"].get(
                    "globally_unique_requirement_ids",
                    [],
                ),
                "evidence_loss_score": candidate["change"].get(
                    "evidence_loss_score"
                ),
                "evidence_loss_reason": candidate["change"].get(
                    "evidence_loss_reason"
                ),
                "quality_loss": candidate["quality_loss"],
                "space_saved_ratio": round(
                    float(candidate["space_saved_ratio"]), 3
                ),
                "layout_effect": candidate["layout_effect"],
                "layout_efficiency_score": round(
                    float(candidate["layout_efficiency_score"]), 2
                ),
                "probe_attempt": candidate["rendered"]["attempt_entry"]["attempt"],
                "selected": candidate is chosen,
            }
            for candidate in rendered_candidates
        ]
        current_render["attempt_entry"]["next_change"] = chosen["change"]

        for candidate in rendered_candidates:
            entry = candidate["rendered"]["attempt_entry"]
            entry["probe_selected"] = candidate is chosen
            if candidate is not chosen:
                _delete_generated_output(
                    candidate["rendered"]["docx_path"],
                    candidate["rendered"]["pdf_path"],
                )
                entry["temporary_output_deleted"] = True

        _delete_generated_output(
            current_render["docx_path"],
            current_render["pdf_path"],
        )
        current_render["attempt_entry"]["superseded_output_deleted"] = True

        working_projects = deepcopy(chosen["projects"])
        working_skills = deepcopy(chosen["skills"])
        active_changes.append(deepcopy(chosen["change"]))
        current_render = chosen["rendered"]

        if int(current_render["page_count"]) <= 1:
            fitting_render = current_render

    if fitting_render is None:
        return {
            "generation_id": generation_id,
            "fitting_version": PHASE6C_FITTING_VERSION,
            "docx_path": current_render["docx_path"],
            "pdf_path": current_render["pdf_path"],
            "page_count": current_render["page_count"],
            "fit_one_page": False,
            "attempts": attempt_logs,
            "tailored_projects_used": working_projects,
            "tailored_skills_used": working_skills,
            "page_fill_ratio": None,
            "estimated_unused_page_ratio": None,
            "page_density_mode": density_mode,
            "density_target_max": density_max_fill,
            **optimization_summary(),
            "note": (
                "Resume still exceeds one page after all allowed whole-resume "
                "reductions. Reduce spacing, lower the minimum Skills count, "
                "or allow more than one page."
            ),
        }

    best_projects = deepcopy(working_projects)
    best_skills = deepcopy(working_skills)
    best_render = fitting_render
    restored_change_count = 0
    permanently_rejected_restorations: set[str] = set()

    while active_changes:
        candidate_results: list[
            dict[str, Any]
        ] = []
        best_fill = float(
            (
                best_render.get(
                    "fill_metrics",
                    {},
                )
                or {}
            ).get("page_fill_ratio")
            or 0.0
        )
        restoration_prepared: list[
            dict[str, Any]
        ] = []

        for change_index in (
            _whole_resume_restorable_change_indices(
                active_changes
            )
        ):
            source_change = active_changes[
                change_index
            ]
            change_key = _change_identity(
                source_change
            )

            if (
                change_key
                in permanently_rejected_restorations
            ):
                continue

            (
                restored_projects,
                restored_skills,
                restored,
                restore_info,
            ) = _restore_whole_resume_change(
                best_projects,
                best_skills,
                source_change,
            )

            if not restored:
                continue

            quality_gain = (
                _whole_resume_restoration_quality_gain(
                    source_change
                )
            )
            restoration_prepared.append(
                {
                    "change_index": change_index,
                    "change_key": change_key,
                    "projects": restored_projects,
                    "skills": restored_skills,
                    "quality_gain": quality_gain,
                    "attempt_type": restore_info.get(
                        "change_type",
                        "restore_content",
                    ),
                    "change_applied": restore_info,
                    "restoration_candidate": True,
                    "restoration_quality_gain": (
                        quality_gain
                    ),
                    "probe_candidate": True,
                }
            )

        if not restoration_prepared:
            break

        optimization_stats[
            "restoration_batch_count"
        ] += 1
        rendered_restorations = (
            render_candidates_batch(
                restoration_prepared,
                batch_label="restoration_pass",
            )
        )

        for prepared, rendered in zip(
            restoration_prepared,
            rendered_restorations,
        ):
            optimization_stats[
                "restoration_candidates_rendered"
            ] += 1

            if rendered["pdf_path"] is None:
                _delete_generated_output(
                    rendered["docx_path"],
                    None,
                )
                continue

            entry = rendered["attempt_entry"]
            change_key = str(
                prepared["change_key"]
            )

            if int(rendered["page_count"]) > 1:
                entry[
                    "restoration_accepted"
                ] = False
                entry["rejection_reason"] = (
                    "Restoring this content caused "
                    "the resume to exceed one page."
                )
                permanently_rejected_restorations.add(
                    change_key
                )
                _delete_generated_output(
                    rendered["docx_path"],
                    rendered["pdf_path"],
                )
                entry[
                    "temporary_output_deleted"
                ] = True
                continue

            candidate_fill = float(
                (
                    rendered.get(
                        "fill_metrics",
                        {},
                    )
                    or {}
                ).get("page_fill_ratio")
                or 0.0
            )

            if candidate_fill > density_max_fill:
                entry[
                    "restoration_accepted"
                ] = False
                entry["rejection_reason"] = (
                    "Restoration exceeded the "
                    "selected page-density limit."
                )
                entry[
                    "density_target_max"
                ] = density_max_fill
                permanently_rejected_restorations.add(
                    change_key
                )
                _delete_generated_output(
                    rendered["docx_path"],
                    rendered["pdf_path"],
                )
                entry[
                    "temporary_output_deleted"
                ] = True
                continue

            space_consumed = max(
                0.0,
                candidate_fill - best_fill,
            )
            restoration_efficiency = (
                float(prepared["quality_gain"])
                / max(
                    space_consumed,
                    _LAYOUT_EFFECT_THRESHOLD,
                )
            )
            entry[
                "space_consumed_ratio"
            ] = round(space_consumed, 3)
            entry[
                "restoration_efficiency_score"
            ] = round(
                restoration_efficiency,
                2,
            )

            candidate_results.append(
                {
                    "change_index": prepared[
                        "change_index"
                    ],
                    "change_key": change_key,
                    "projects": prepared[
                        "projects"
                    ],
                    "skills": prepared["skills"],
                    "rendered": rendered,
                    "quality_gain": prepared[
                        "quality_gain"
                    ],
                    "space_consumed_ratio": (
                        space_consumed
                    ),
                    "restoration_efficiency_score": (
                        restoration_efficiency
                    ),
                }
            )

        if not candidate_results:
            break

        chosen = max(
            candidate_results,
            key=lambda candidate: (
                float(
                    candidate[
                        "restoration_efficiency_score"
                    ]
                ),
                int(candidate["quality_gain"]),
            ),
        )

        for candidate in candidate_results:
            entry = candidate[
                "rendered"
            ]["attempt_entry"]
            entry["probe_selected"] = (
                candidate is chosen
            )

            if candidate is chosen:
                entry[
                    "restoration_accepted"
                ] = True
            else:
                entry[
                    "restoration_accepted"
                ] = False
                entry["rejection_reason"] = (
                    "Another one-page restoration "
                    "recovered more value per unit "
                    "of rendered space."
                )
                _delete_generated_output(
                    candidate[
                        "rendered"
                    ]["docx_path"],
                    candidate[
                        "rendered"
                    ]["pdf_path"],
                )
                entry[
                    "temporary_output_deleted"
                ] = True

        _delete_generated_output(
            best_render["docx_path"],
            best_render["pdf_path"],
        )
        best_render[
            "attempt_entry"
        ][
            "superseded_output_deleted"
        ] = True

        best_projects = deepcopy(
            chosen["projects"]
        )
        best_skills = deepcopy(
            chosen["skills"]
        )
        best_render = chosen["rendered"]
        active_changes.pop(
            int(chosen["change_index"])
        )
        restored_change_count += 1

    fill_metrics = best_render.get("fill_metrics", {}) or {}
    first_attempt_was_full_fit = (
        len(attempt_logs) == 1
        and not active_changes
        and restored_change_count == 0
    )

    if first_attempt_was_full_fit:
        note = "Generated resume fits within one page using the full tailored sections."
    elif restored_change_count > 0:
        note = (
            "Generated resume fits within one page after layout-aware fitting "
            "and a restoration pass recovered the strongest content that fit "
            "within the selected density target."
        )
    else:
        note = (
            "Generated resume fits within one page after comparing actual "
            "rendered space saved against deterministic evidence loss."
        )

    remaining_quality_loss = sum(
        _skill_reduction_quality_loss(change)
        if str(change.get("section", "projects")) == "skills"
        else _project_reduction_quality_loss(change)
        for change in active_changes
    )

    return {
        "generation_id": generation_id,
            "fitting_version": PHASE6C_FITTING_VERSION,
        "docx_path": best_render["docx_path"],
        "pdf_path": best_render["pdf_path"],
        "page_count": best_render["page_count"],
        "fit_one_page": True,
        "attempts": attempt_logs,
        "tailored_projects_used": best_projects,
        "tailored_skills_used": best_skills,
        "page_fill_ratio": fill_metrics.get("page_fill_ratio"),
        "estimated_unused_page_ratio": fill_metrics.get(
            "estimated_unused_page_ratio"
        ),
        "page_fill_measurement_method": fill_metrics.get("measurement_method"),
        "page_density_mode": density_mode,
        "density_target_max": density_max_fill,
        **optimization_summary(),
        "fitting_objective": (
            "Protect unique requirement evidence, then minimise deterministic "
            "evidence loss per unit of actual rendered space saved; "
            "do not rerun analysis or project selection."
        ),
        "remaining_quality_loss": remaining_quality_loss,
        "restored_change_count": restored_change_count,
        "remaining_active_reductions": active_changes,
        "permanently_rejected_restoration_count": len(
            permanently_rejected_restorations
        ),
        "note": note,
    }



# def generate_tailored_resume_copy_fit_one_page(
#     *,
#     saved_resume_docx_path: str | Path,
#     tailored_projects: dict[str, Any] | None = None,
#     tailored_skills: dict[str, Any] | None = None,
#     application_id: int | None = None,
#     max_projects: int = 3,
#     max_bullets_per_project: int = 3,
#     max_attempts: int = 5,
#     spacing_mode: str = "paragraph_spacing",
#     project_spacing_pt: int = 10,
#     after_projects_spacing_pt: int = 10,
#     blank_lines_between_projects: int = 1,
#     blank_lines_after_projects: int = 1,
#     add_spacing_before_first_project: bool = False,
# ) -> dict[str, Any]:
#     """
#     Generate a tailored DOCX and keep it to one page if possible.

#     Flow:
#     1. Generate full truthful tailored version first.
#     2. Convert to PDF and count pages.
#     3. If it fits, keep it.
#     4. If it exceeds one page, compact and retry.
#     """
#     if not tailored_projects and not tailored_skills:
#         raise ValueError("Generate a tailored Projects section or Skills section first.")

#     cleanup_old_tailored_outputs_for_application(application_id)

#     attempt_logs = []
#     last_docx_path = None
#     last_pdf_path = None
#     last_page_count = None
#     last_projects_used = deepcopy(tailored_projects) if tailored_projects else None

#     attempt_limit = max_attempts if tailored_projects else 1

#     for attempt_index in range(attempt_limit):
#         if attempt_index == 0:
#             working_projects = deepcopy(tailored_projects) if tailored_projects else None
#             attempt_type = "full"
#         else:
#             working_projects = compact_tailored_projects_for_space(
#                 tailored_projects,
#                 attempt=attempt_index,
#             )
#             attempt_type = f"compact_{attempt_index}"

#         docx_path = generate_tailored_resume_copy(
#             saved_resume_docx_path=saved_resume_docx_path,
#             tailored_projects=working_projects,
#             tailored_skills=tailored_skills,
#             application_id=application_id,
#             max_projects=max_projects,
#             max_bullets_per_project=max_bullets_per_project,
#             spacing_mode=spacing_mode,
#             project_spacing_pt=project_spacing_pt,
#             after_projects_spacing_pt=after_projects_spacing_pt,
#             blank_lines_between_projects=blank_lines_between_projects,
#             blank_lines_after_projects=blank_lines_after_projects,
#             add_spacing_before_first_project=add_spacing_before_first_project,
#         )

#         last_docx_path = docx_path
#         last_projects_used = working_projects

#         pdf_path = convert_docx_to_pdf_if_possible(docx_path)

#         if pdf_path is None:
#             return {
#                 "docx_path": docx_path,
#                 "pdf_path": None,
#                 "page_count": None,
#                 "fit_one_page": None,
#                 "attempts": attempt_logs,
#                 "tailored_projects_used": working_projects,
#                 "note": (
#                     "Could not check page count because LibreOffice is unavailable "
#                     "or DOCX-to-PDF conversion failed. DOCX generation still worked."
#                 ),
#             }

#         page_count = count_pdf_pages(pdf_path)

#         last_pdf_path = pdf_path
#         last_page_count = page_count

#         attempt_logs.append(
#             {
#                 "attempt": attempt_index + 1,
#                 "attempt_type": attempt_type,
#                 "docx_path": str(docx_path),
#                 "pdf_path": str(pdf_path),
#                 "page_count": page_count,
#                 "project_count": len(working_projects.get("recommended_projects", [])) if working_projects else 0,
#                 "bullet_count": sum(
#                     len(project.get("draft_bullets", []) or [])
#                     for project in working_projects.get("recommended_projects", [])
#                 ) if working_projects else 0,
#             }
#         )

#         if page_count <= 1:
#             return {
#                 "docx_path": docx_path,
#                 "pdf_path": pdf_path,
#                 "page_count": page_count,
#                 "fit_one_page": True,
#                 "attempts": attempt_logs,
#                 "tailored_projects_used": working_projects,
#                 "note": (
#                     "Generated resume fits within one page."
#                     if attempt_index == 0
#                     else "Generated resume fits within one page after compacting."
#                 ),
#             }

#     return {
#         "docx_path": last_docx_path,
#         "pdf_path": last_pdf_path,
#         "page_count": last_page_count,
#         "fit_one_page": False,
#         "attempts": attempt_logs,
#         "tailored_projects_used": last_projects_used,
#         "note": (
#             "Resume still appears to exceed one page after compacting. "
#             "Try fewer projects, fewer bullets, or shorter skills."
#         ),
#     }





# ---------------------------------------------------------------------------
# Preview helpers
# ---------------------------------------------------------------------------

def extract_docx_preview_text(docx_path: str | Path) -> str:
    """
    Return a simple text preview of the generated DOCX.

    This is not a visual Word preview, but it works without LibreOffice.
    """
    document = Document(docx_path)
    lines: list[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)

    return "\n".join(lines)


# def _find_libreoffice_executable() -> str | None:
#     """Find LibreOffice executable on Windows/Linux/Mac."""
#     soffice = shutil.which("soffice") or shutil.which("libreoffice")

#     if soffice:
#         return soffice

#     common_windows_paths = [
#         r"C:\Program Files\LibreOffice\program\soffice.exe",
#         r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
#     ]

#     for path in common_windows_paths:
#         if Path(path).exists():
#             return path

#     return None


# def convert_docx_to_pdf_if_possible(docx_path: str | Path) -> Path | None:
#     """
#     Convert DOCX to PDF using LibreOffice if it is installed.

#     Returns:
#         PDF path, or None if LibreOffice is unavailable or conversion fails.
#     """
#     docx_path = Path(docx_path)
#     PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

#     # soffice = shutil.which("soffice") or shutil.which("libreoffice")
#     soffice = _find_libreoffice_executable()
#     if not soffice:
#         return None

#     try:
#         subprocess.run(
#             [
#                 soffice,
#                 "--headless",
#                 "--convert-to",
#                 "pdf",
#                 "--outdir",
#                 str(PREVIEW_DIR),
#                 str(docx_path),
#             ],
#             check=True,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             timeout=60,
#             text=True,
#         )
#     except Exception as exc:
#         print(f"[LibreOffice conversion failed] {exc}")
#         return None

#     pdf_path = PREVIEW_DIR / f"{docx_path.stem}.pdf"

#     if pdf_path.exists():
#         return pdf_path

#     return None


def _find_libreoffice_executable() -> str | None:
    """Find LibreOffice executable on Windows/Linux/Mac."""

    # Prefer the normal Windows install path first.
    # This avoids accidentally picking soffice.COM from PATH.
    common_windows_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files\LibreOffice\program\soffice.com",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
    ]

    for path in common_windows_paths:
        if Path(path).exists():
            return path

    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_docx_to_pdf_if_possible(docx_path: str | Path) -> Path | None:
    """
    Convert DOCX to PDF using LibreOffice if it is installed.

    Returns:
        PDF path, or None if LibreOffice is unavailable or conversion fails.
    """
    docx_path = Path(docx_path).resolve()
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    preview_dir = PREVIEW_DIR.resolve()

    soffice = _find_libreoffice_executable()
    if not soffice:
        print("[LibreOffice conversion failed] LibreOffice executable not found.")
        return None

    expected_pdf_path = preview_dir / f"{docx_path.stem}.pdf"

    # Remove old preview with the same name so we know whether this conversion produced a new file.
    if expected_pdf_path.exists():
        try:
            expected_pdf_path.unlink()
        except OSError:
            pass

    # Give each headless conversion its own LibreOffice profile.
    # This reduces collisions with normal LibreOffice sessions and
    # with the fitter's rapid sequence of conversion attempts.
    lo_profile_dir = (
        preview_dir
        / "lo_profiles"
        / uuid.uuid4().hex
    ).resolve()
    lo_profile_dir.mkdir(parents=True, exist_ok=True)
    lo_profile_uri = lo_profile_dir.as_uri()

    command = [
        soffice,
        "--headless",
        "--nologo",
        "--nodefault",
        "--nofirststartwizard",
        "--nolockcheck",
        f"-env:UserInstallation={lo_profile_uri}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(preview_dir),
        str(docx_path),
    ]

    # Do not pass Python installation overrides into LibreOffice.
    # They can produce warnings such as:
    # "Could not find platform independent libraries <prefix>".
    conversion_env = os.environ.copy()
    conversion_env.pop("PYTHONHOME", None)
    conversion_env.pop("PYTHONPATH", None)

    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            text=True,
            env=conversion_env,
        )

        if result.returncode != 0:
            print("[LibreOffice conversion failed]")
            print("Command:", command)
            print("Return code:", result.returncode)
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return None

        # On Windows, LibreOffice can return just before the PDF is
        # visible to Python. Poll briefly before declaring failure.
        for _ in range(20):
            try:
                if (
                    expected_pdf_path.exists()
                    and expected_pdf_path.stat().st_size > 0
                ):
                    return expected_pdf_path
            except OSError:
                pass

            time.sleep(0.1)

        print(
            "[LibreOffice conversion failed] "
            "Command succeeded but PDF was not created "
            "after waiting 2 seconds."
        )
        print("Expected PDF:", expected_pdf_path)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return None

    except Exception as exc:
        print(f"[LibreOffice conversion crashed] {exc}")
        return None

    finally:
        try:
            shutil.rmtree(
                lo_profile_dir,
                ignore_errors=True,
            )
        except OSError:
            pass


def convert_docx_batch_to_pdf_if_possible(
    docx_paths: list[str | Path],
) -> tuple[dict[str, Path | None], dict[str, Any]]:
    """
    Convert several DOCX files with one LibreOffice process.

    Missing outputs are retried individually through the existing converter.
    The returned dictionary is keyed by each resolved DOCX path.
    """
    resolved_paths: list[Path] = []
    seen: set[str] = set()

    for raw_path in docx_paths:
        path = Path(raw_path).resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        resolved_paths.append(path)

    diagnostics: dict[str, Any] = {
        "requested_count": len(resolved_paths),
        "batch_process_count": 0,
        "fallback_process_count": 0,
        "missing_source_count": 0,
        "batch_return_code": None,
    }
    results: dict[str, Path | None] = {
        str(path): None
        for path in resolved_paths
    }

    valid_paths: list[Path] = []
    for path in resolved_paths:
        try:
            if path.exists() and path.stat().st_size > 0:
                valid_paths.append(path)
            else:
                diagnostics["missing_source_count"] += 1
        except OSError:
            diagnostics["missing_source_count"] += 1

    if not valid_paths:
        return results, diagnostics

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    preview_dir = PREVIEW_DIR.resolve()
    soffice = _find_libreoffice_executable()

    if not soffice:
        print(
            "[LibreOffice batch conversion failed] "
            "LibreOffice executable not found."
        )
        return results, diagnostics

    expected_paths = {
        str(path): preview_dir / f"{path.stem}.pdf"
        for path in valid_paths
    }

    for expected_path in expected_paths.values():
        try:
            expected_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    lo_profile_dir = (
        preview_dir
        / "lo_profiles"
        / uuid.uuid4().hex
    ).resolve()
    lo_profile_dir.mkdir(parents=True, exist_ok=True)

    command = [
        soffice,
        "--headless",
        "--nologo",
        "--nodefault",
        "--nofirststartwizard",
        "--nolockcheck",
        f"-env:UserInstallation={lo_profile_dir.as_uri()}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(preview_dir),
        *[str(path) for path in valid_paths],
    ]

    conversion_env = os.environ.copy()
    conversion_env.pop("PYTHONHOME", None)
    conversion_env.pop("PYTHONPATH", None)

    try:
        diagnostics["batch_process_count"] = 1
        timeout_seconds = max(
            60,
            min(240, 30 + len(valid_paths) * 20),
        )
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            text=True,
            env=conversion_env,
        )
        diagnostics["batch_return_code"] = result.returncode

        if result.returncode != 0:
            print("[LibreOffice batch conversion failed]")
            print("Command:", command)
            print("Return code:", result.returncode)
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)

        for _ in range(40):
            pending = []
            for source_path in valid_paths:
                expected_path = expected_paths[str(source_path)]
                try:
                    ready = (
                        expected_path.exists()
                        and expected_path.stat().st_size > 0
                    )
                except OSError:
                    ready = False

                if ready:
                    results[str(source_path)] = expected_path
                else:
                    pending.append(source_path)

            if not pending:
                break
            time.sleep(0.1)

    except Exception as exc:
        print(f"[LibreOffice batch conversion crashed] {exc}")

    finally:
        try:
            shutil.rmtree(
                lo_profile_dir,
                ignore_errors=True,
            )
        except OSError:
            pass

    # Retry only files that the batch did not produce. This keeps the existing
    # robust individual conversion path as a fallback.
    for source_path in valid_paths:
        if results[str(source_path)] is not None:
            continue

        diagnostics["fallback_process_count"] += 1
        results[str(source_path)] = (
            convert_docx_to_pdf_if_possible(source_path)
        )

    return results, diagnostics


def pdf_to_iframe_html(pdf_path: str | Path, *, height: int = 800) -> str:
    """Create HTML iframe for PDF preview in Streamlit."""
    pdf_path = Path(pdf_path)
    encoded = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    return (
        f'<iframe src="data:application/pdf;base64,{encoded}" '
        f'width="100%" height="{height}" type="application/pdf"></iframe>'
    )





def cleanup_stale_libreoffice_profiles(
    *,
    max_age_hours: int = 24,
) -> dict[str, Any]:
    """
    Remove abandoned LibreOffice profile folders only when they are old.

    Recent profiles are left alone because another conversion could still be
    using them. The current converter normally removes its unique profile in a
    ``finally`` block, so this is only a fallback for interrupted processes.
    """
    max_age_seconds = max(1, int(max_age_hours)) * 3600
    now = time.time()
    removed: list[str] = []
    failed: list[dict[str, str]] = []

    candidates: list[Path] = []

    legacy_root = PREVIEW_DIR / "lo_profile"
    if legacy_root.exists():
        candidates.append(legacy_root)

    profiles_root = PREVIEW_DIR / "lo_profiles"
    if profiles_root.exists():
        candidates.extend(
            child
            for child in profiles_root.iterdir()
            if child.is_dir()
        )

    for candidate in candidates:
        try:
            mtimes = [candidate.stat().st_mtime]
            mtimes.extend(
                path.stat().st_mtime
                for path in candidate.rglob("*")
                if path.exists()
            )
            newest_mtime = max(mtimes)
        except OSError as exc:
            failed.append(
                {
                    "path": str(candidate),
                    "error": str(exc),
                }
            )
            continue

        if now - newest_mtime < max_age_seconds:
            continue

        try:
            shutil.rmtree(candidate, ignore_errors=False)
            removed.append(str(candidate))
        except OSError as exc:
            failed.append(
                {
                    "path": str(candidate),
                    "error": str(exc),
                }
            )

    if profiles_root.exists():
        try:
            if not any(profiles_root.iterdir()):
                profiles_root.rmdir()
                removed.append(str(profiles_root))
        except OSError:
            pass

    return {
        "removed_profile_directories": removed,
        "failed_files": failed,
    }


def cleanup_application_resume_files(
    application_id: int | None,
    *,
    delete_saved_resume: bool = True,
    delete_generated_outputs: bool = True,
    delete_libreoffice_profiles: bool = True,
) -> dict[str, Any]:
    """
    Delete app-owned résumé files for one application session.

    Safety:
    - Only files beginning with ``app_{application_id}_`` are considered.
    - The function never scans outside the three known application folders.
    - Files already downloaded by the user elsewhere are unaffected.
    """
    if application_id is None:
        return {
            "application_id": None,
            "deleted_file_count": 0,
            "deleted_files": [],
            "failed_files": [],
        }

    try:
        app_id = int(application_id)
    except (TypeError, ValueError):
        raise ValueError("application_id must be an integer.")

    if app_id < 0:
        raise ValueError("application_id must be non-negative.")

    patterns: list[Path] = []

    if delete_saved_resume:
        patterns.append(
            SAVED_RESUME_DIR / f"app_{app_id}_*.docx"
        )

    if delete_generated_outputs:
        patterns.extend(
            [
                TAILORED_RESUME_DIR
                / f"app_{app_id}_tailored_resume_*.docx",
                PREVIEW_DIR
                / f"app_{app_id}_tailored_resume_*.pdf",
                PREVIEW_DIR
                / f"app_{app_id}_tailored_resume_*.png",
            ]
        )

    deleted_files: list[str] = []
    failed_files: list[dict[str, str]] = []

    for pattern in patterns:
        for path in pattern.parent.glob(pattern.name):
            try:
                if path.is_file():
                    path.unlink()
                    deleted_files.append(str(path))
            except OSError as exc:
                failed_files.append(
                    {
                        "path": str(path),
                        "error": str(exc),
                    }
                )

    removed_profile_directories: list[str] = []

    if delete_libreoffice_profiles:
        profile_cleanup = cleanup_stale_libreoffice_profiles(
            max_age_hours=24,
        )
        removed_profile_directories = list(
            profile_cleanup.get(
                "removed_profile_directories",
                [],
            )
        )
        failed_files.extend(
            profile_cleanup.get("failed_files", [])
        )

    return {
        "application_id": app_id,
        "deleted_file_count": len(deleted_files),
        "deleted_files": deleted_files,
        "removed_profile_directories": (
            removed_profile_directories
        ),
        "failed_files": failed_files,
    }


# ---------------------------------------------------------------------------
# Cleaner
# ---------------------------------------------------------------------------

def cleanup_old_tailored_outputs_for_application(application_id: int | None) -> None:
    """
    Remove old generated DOCX/PDF/PNG outputs for this application session.

    Does not remove data/saved_resumes, because that is the original saved DOCX copy.
    """
    if application_id is None:
        return

    patterns = [
        TAILORED_RESUME_DIR / f"app_{application_id}_tailored_resume_*.docx",
        PREVIEW_DIR / f"app_{application_id}_tailored_resume_*.pdf",
        PREVIEW_DIR / f"app_{application_id}_tailored_resume_*.png",
    ]

    for pattern in patterns:
        for path in pattern.parent.glob(pattern.name):
            try:
                path.unlink()
            except OSError:
                pass