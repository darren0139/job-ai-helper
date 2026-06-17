"""
resume_builder/docx_projects_skills_replacer.py

Option 2 workflow:
    upload original_resume.docx
    -> save a local copy only if user opts in
    -> generate tailored project and skill recommendations
    -> copy original DOCX
    -> replace only SKILLS and PROJECTS sections
    -> download tailored DOCX copy

Work Experience is not changed.
"""

from __future__ import annotations

import base64
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph


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


def _safe_filename(filename: str) -> str:
    """Create a safe filename for local storage."""
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9_. -]", "_", name)
    return name.strip() or "uploaded_resume.docx"


def save_uploaded_docx_for_editing(
    uploaded_file: Any,
    *,
    application_id: int | None = None,
) -> Path:
    """
    Save the uploaded DOCX so the app can later generate an edited copy.

    This should only be called if the user ticks the save checkbox.
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

    return saved_path


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

    if (
        text == upper_text
        and 1 <= len(text.split()) <= 4
        and len(text) <= 40
        and not text.startswith("•")
        and not text.startswith("-")
    ):
        return True

    return False


def _delete_paragraph(paragraph: Paragraph) -> None:
    """Remove a paragraph from the DOCX XML tree."""
    element = paragraph._element
    parent = element.getparent()
    parent.remove(element)


def _insert_paragraph_after(paragraph: Paragraph, text: str = "", style: str | None = None) -> Paragraph:
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


def _add_skill_line_after(anchor: Paragraph, category: str, items: list[str]) -> Paragraph:
    """Add one compact skill line after anchor."""
    line = f"{category}: {', '.join(items)}" if category else ", ".join(items)
    new_paragraph = _insert_paragraph_after(anchor)
    new_paragraph.paragraph_format.space_before = 0
    new_paragraph.paragraph_format.space_after = 0

    if category:
        category_run = new_paragraph.add_run(f"{category}: ")
        category_run.bold = True
        new_paragraph.add_run(", ".join(items))
    else:
        new_paragraph.add_run(line)

    return new_paragraph


def _add_project_title_after(anchor: Paragraph, title: str, period: str = "") -> Paragraph:
    """Add project title line after anchor."""
    new_paragraph = _insert_paragraph_after(anchor)
    new_paragraph.paragraph_format.space_before = 3
    new_paragraph.paragraph_format.space_after = 0

    title_run = new_paragraph.add_run(title)
    title_run.bold = True

    if period:
        period_run = new_paragraph.add_run(f"    {period}")
        period_run.bold = False

    return new_paragraph


def _add_bullet_after(anchor: Paragraph, bullet: str) -> Paragraph:
    """Add bullet after anchor."""
    new_paragraph = _insert_paragraph_after(anchor, style="List Bullet")
    new_paragraph.paragraph_format.space_before = 0
    new_paragraph.paragraph_format.space_after = 0
    new_paragraph.paragraph_format.line_spacing = 1.0
    new_paragraph.add_run(str(bullet).strip())
    return new_paragraph


def replace_skills_section(
    document: DocumentObject,
    tailored_skills: dict[str, Any],
) -> None:
    """
    Replace SKILLS / TECHNICAL SKILLS section content.
    """
    anchor = _clear_section_content(document, {"SKILLS", "TECHNICAL SKILLS"})
    skill_lines = tailored_skills.get("skill_lines", [])

    if not skill_lines:
        anchor = _insert_paragraph_after(anchor, "No tailored skills were generated.")
        return

    for row in skill_lines:
        category = str(row.get("category", "")).strip()
        items = [str(item).strip() for item in row.get("items", []) if str(item).strip()]

        if items:
            anchor = _add_skill_line_after(anchor, category, items)


def replace_projects_section(
    document: DocumentObject,
    tailored_projects: dict[str, Any],
    *,
    max_projects: int = 3,
    max_bullets_per_project: int = 2,
) -> None:
    """
    Replace PROJECTS section content.
    """
    anchor = _clear_section_content(document, {"PROJECTS"})
    projects = tailored_projects.get("recommended_projects", [])[:max_projects]

    if not projects:
        anchor = _insert_paragraph_after(anchor, "No tailored projects were generated.")
        return

    for project in projects:
        title = str(project.get("title", "Untitled Project")).strip() or "Untitled Project"
        period = str(project.get("period", "")).strip()
        bullets = project.get("draft_bullets", [])[:max_bullets_per_project]

        anchor = _add_project_title_after(anchor, title, period=period)

        for bullet in bullets:
            if str(bullet).strip():
                anchor = _add_bullet_after(anchor, str(bullet).strip())


def generate_tailored_resume_copy(
    *,
    saved_resume_docx_path: str | Path,
    tailored_projects: dict[str, Any],
    tailored_skills: dict[str, Any],
    application_id: int | None = None,
    max_projects: int = 3,
    max_bullets_per_project: int = 2,
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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    app_part = f"app_{application_id}_" if application_id is not None else ""
    output_path = TAILORED_RESUME_DIR / f"{app_part}tailored_resume_{timestamp}.docx"

    shutil.copy2(saved_resume_docx_path, output_path)

    document = Document(output_path)

    # Change only these sections.
    replace_skills_section(document, tailored_skills)
    replace_projects_section(
        document,
        tailored_projects,
        max_projects=max_projects,
        max_bullets_per_project=max_bullets_per_project,
    )

    document.save(output_path)

    return output_path


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


def convert_docx_to_pdf_if_possible(docx_path: str | Path) -> Path | None:
    """
    Convert DOCX to PDF using LibreOffice if it is installed.

    Returns:
        PDF path, or None if LibreOffice is unavailable or conversion fails.
    """
    docx_path = Path(docx_path)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None

    try:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(PREVIEW_DIR),
                str(docx_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except Exception:
        return None

    pdf_path = PREVIEW_DIR / f"{docx_path.stem}.pdf"

    if pdf_path.exists():
        return pdf_path

    return None


def pdf_to_iframe_html(pdf_path: str | Path, *, height: int = 800) -> str:
    """Create HTML iframe for PDF preview in Streamlit."""
    pdf_path = Path(pdf_path)
    encoded = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    return (
        f'<iframe src="data:application/pdf;base64,{encoded}" '
        f'width="100%" height="{height}" type="application/pdf"></iframe>'
    )
