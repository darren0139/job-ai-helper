"""
parse.py — PDF and plain-text reading; no LLM calls.

Task 1 of the Day 4 lab (Track A).
Study material reference: §5 Document Parsing
"""

import re
import sys

from pypdf import PdfReader
from docx import Document

# Résumé text below this character count likely means an image-only PDF.
_MIN_RESUME_CHARS = 200

# JD text below this character count likely means the student forgot to paste content.
_MIN_JD_CHARS = 100

# Rough token estimate: 1 token ≈ 4 chars. Truncate above ~6 000 tokens.
_MAX_RESUME_CHARS = 6000 * 4

def read_resume_docx(path: str) -> str:
    """
    Extract plain text from a DOCX résumé.

    Args:
        path: Path to the DOCX file.

    Returns:
        Extracted plain text.

    Raises:
        ValueError: If the file cannot be opened or contains too little text.
    """
    try:
        document = Document(path)
    except FileNotFoundError as exc:
        raise ValueError(f"Resume DOCX not found: {path}") from exc
    except Exception as exc:
        raise ValueError(f"Could not open resume DOCX '{path}': {exc}") from exc

    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    text = "\n".join(paragraphs).strip()

    if len(text) < _MIN_RESUME_CHARS:
        raise ValueError(
            f"Resume text is too short ({len(text)} chars). "
            f"Expected at least {_MIN_RESUME_CHARS} chars. "
            "The DOCX may be empty or mostly image-based."
        )

    if len(text) > _MAX_RESUME_CHARS:
        text = text[:_MAX_RESUME_CHARS]

    return text


def read_resume_pdf(path: str) -> str:
    """
    Extract plain text from a PDF résumé using pypdf.

    Requirements:
    1. Open the file with ``pypdf.PdfReader(path)``.
       Raise ``ValueError`` with a clear message if the file is not found or
       cannot be opened (catch ``FileNotFoundError`` separately from ``Exception``).
    2. If the résumé has more than 2 pages, print a warning to ``sys.stderr``.
       ATS systems typically expect a one-page résumé.
    3. Extract text from each page with ``page.extract_text() or ""``.
       Join page texts with ``"\\n\\n"``.
    4. Collapse runs of 3 or more consecutive blank lines to 2 using ``re.sub``.
    5. Strip leading/trailing whitespace from the full text.
    6. Raise ``ValueError`` if the result is shorter than ``_MIN_RESUME_CHARS``
       characters (likely an image-based / scanned PDF — no text layer).
    7. Truncate to ``_MAX_RESUME_CHARS`` characters if very long, and print a
       warning to ``sys.stderr``.

    Args:
        path: Path to the PDF file.

    Returns:
        Extracted plain text.

    Raises:
        ValueError: If the file is not found, cannot be opened, or is too short.
    """
      # Step 1: Open the PDF safely.
    try:
        reader = PdfReader(path)
    except FileNotFoundError as exc:
        raise ValueError(f"Resume PDF not found: {path}") from exc
    except Exception as exc:
        raise ValueError(f"Could not open resume PDF '{path}': {exc}") from exc

    # Step 2: Warn if the resume is longer than expected.
    page_count = len(reader.pages)

    if page_count > 2:
        print(
            f"WARNING: Resume has {page_count} pages. "
            "ATS systems typically expect a one-page resume.",
            file=sys.stderr,
        )

    # Step 3: Extract text from every page.
    try:
        page_texts = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            page_texts.append(page_text)

    except Exception as exc:
        raise ValueError(f"Could not extract text from resume PDF '{path}': {exc}") from exc

    # Step 4: Join pages with two newlines.
    text = "\n\n".join(page_texts)

    # Step 5: Collapse runs of 3 or more blank lines to 2 newlines.
    text = re.sub(r"(?:\n\s*){3,}", "\n\n", text)

    # Step 6: Strip leading/trailing whitespace.
    text = text.strip()

    # Step 7: Reject image-only / scanned PDFs.
    if len(text) < _MIN_RESUME_CHARS:
        raise ValueError(
            f"Resume text is too short ({len(text)} chars). "
            f"Expected at least {_MIN_RESUME_CHARS} chars. "
            "This may be an image-based or scanned PDF with no text layer."
        )

    # Step 8: Truncate very long resumes.
    if len(text) > _MAX_RESUME_CHARS:
        print(
            f"WARNING: Resume text is very long ({len(text)} chars). "
            f"Truncating to {_MAX_RESUME_CHARS} chars.",
            file=sys.stderr,
        )
        text = text[:_MAX_RESUME_CHARS]

    return text
    #raise NotImplementedError


def read_jd_text(path: str) -> str:
    """
    Read a plain-text job description file (UTF-8).

    Requirements:
    1. Open the file with ``open(path, encoding="utf-8")``.
       Raise ``ValueError`` with a clear message if the file is not found.
       Catch other ``Exception`` types and raise ``ValueError`` with the cause.
    2. Strip the content.
    3. Raise ``ValueError`` if the stripped content has fewer than
       ``_MIN_JD_CHARS`` characters.

    Args:
        path: Path to the plain-text job description file.

    Returns:
        Content of the file as a string.

    Raises:
        ValueError: If the file is not found or the content is too short.
    """
    # TODO: implement this function

        # Step 1: Open and read the JD file safely.
    try:
        with open(path, encoding="utf-8") as file:
            text = file.read()
    except FileNotFoundError as exc:
        raise ValueError(f"Job description file not found: {path}") from exc
    except Exception as exc:
        raise ValueError(f"Could not read job description file '{path}': {exc}") from exc

    # Step 2: Strip leading/trailing whitespace.
    text = text.strip()

    # Step 3: Reject empty or incomplete JD text.
    if len(text) < _MIN_JD_CHARS:
        raise ValueError(
            f"Job description text is too short ({len(text)} chars). "
            f"Expected at least {_MIN_JD_CHARS} chars. "
            "Did you forget to paste the full job description?"
        )

    return text
    #raise NotImplementedError
