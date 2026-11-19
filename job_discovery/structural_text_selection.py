"""Conservative, source-only JD text selection before Job Finder persistence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re
from typing import Any

from analysis_stability.jd_section_inference import (
    JD_STRUCTURE_INFERENCE_VERSION,
    infer_semantic_list_heading,
)
from analysis_stability.stable_evidence_scoring import (
    _normalise_jd_section_heading,
    _raw_section_for_heading,
)
from job_discovery.models import NormalizedJob


STRUCTURAL_TEXT_SELECTION_VERSION = "job-finder-structural-text-selection-v1"
PROVENANCE_KEY = "_job_finder_structural_text_selection"

# These additions only identify explicit administrative boundaries or retained
# work context. Core JD headings come from the existing controlled classifier.
_CONTEXT_HEADINGS = frozenset({
    "eligibility", "work eligibility", "work authorization", "work authorisation",
    "right to work", "working hours", "work arrangements", "working arrangements",
    "employment conditions", "work location", "security clearance",
})
_ADMIN_HEADINGS = frozenset({
    "legal disclaimer", "privacy notice", "privacy policy",
    "equal employment opportunity", "equal opportunities",
})
_BULLET = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s+")
_CONSTRAINT = re.compile(
    r"\b(?:must|required|requirement[s]?|eligib(?:le|ility)|citizen(?:ship)?|"
    r"work (?:permit|authori[sz]ation|rights?)|security clearance|"
    r"weekends?|night shifts?|working hours|travel|able to|ability to|"
    r"licen[cs]e|certification|experience|knowledge|proficien(?:cy|t))\b",
    re.IGNORECASE,
)


def _unknown_heading(line: str) -> bool:
    text = line.strip().strip("*_")
    words = text.rstrip(":").split()
    return (
        not _BULLET.match(line)
        and 0 < len(words) <= 10
        and len(text) <= 100
        and (text.endswith(":") or text.startswith("#") or text.isupper() or text.istitle())
    )


def select_structural_jd_text(description: str) -> dict[str, Any]:
    """Keep full input unless explicit JD and removable sections are meaningful."""
    original = description
    lines = original.splitlines(keepends=True)
    raw_lines = [line.rstrip("\r\n") for line in lines]
    starts = []
    offset = 0
    boundaries = []
    ambiguous = []
    for index, line in enumerate(lines):
        starts.append(offset)
        offset += len(line)
        if not line.strip():
            continue
        if _BULLET.match(line):
            if line.strip().endswith(":"):
                ambiguous.append(index)
            continue
        heading = _normalise_jd_section_heading(line)
        section = _raw_section_for_heading(line)
        detection = "controlled_heading"
        if heading in _CONTEXT_HEADINGS or heading in {"salary", "compensation"}:
            section = "work_context"
        elif heading in _ADMIN_HEADINGS:
            section = "stop"
        elif not section:
            inferred = infer_semantic_list_heading(raw_lines, index)
            if inferred.get("section") in {"responsibilities", "requirements"}:
                section = inferred["section"]
                detection = "inferred_child_list"
            elif inferred.get("is_heading_candidate") or _unknown_heading(line):
                ambiguous.append(index)
        if section:
            boundaries.append((index, section, detection))
    starts.append(len(original))

    sections = []
    for position, (line_index, section, detection) in enumerate(boundaries):
        start = starts[line_index]
        if position == 0 and start:
            sections.append({
                "heading": "", "section": "unheaded", "detection": "preserved_prefix",
                "start": 0, "end": start, "body_start": 0,
            })
        end = len(original)
        if position + 1 < len(boundaries):
            end = starts[boundaries[position + 1][0]]
        sections.append({
            "heading": raw_lines[line_index].strip(),
            "section": section, "detection": detection,
            "start": start, "end": end, "body_start": starts[line_index + 1],
        })
    if not sections:
        sections.append({
            "heading": "", "section": "unheaded", "detection": "full_text",
            "start": 0, "end": len(original), "body_start": 0,
        })

    jd_sections = [
        section for section in sections
        if section["section"] in {"responsibilities", "requirements", "core", "preferred"}
        and section["detection"] == "controlled_heading"
        and original[section["body_start"]:section["end"]].strip()
    ]
    discarded = [section for section in sections if section["section"] == "stop"]
    included = [section for section in sections if section["section"] != "stop"]
    body = "\n".join(
        original[section["body_start"]:section["end"]] for section in jd_sections
    ).strip()
    reason = ""
    if not jd_sections:
        reason = "no_confident_jd_structure"
    elif len(body) < 80 or len([line for line in body.splitlines() if line.strip()]) < 2:
        reason = "insufficient_jd_content"
    elif not discarded:
        reason = "no_confident_non_jd_sections"
    else:
        for section in discarded:
            if not original[section["body_start"]:section["end"]].strip():
                reason = "empty_non_jd_section"
                break
            if any(section["body_start"] <= starts[index] < section["end"] for index in ambiguous):
                reason = "ambiguous_heading_in_non_jd_section"
                break
            if _CONSTRAINT.search(original[section["body_start"]:section["end"]]):
                reason = "possible_requirement_in_non_jd_section"
                break

    selected = original
    if not reason:
        selected = "".join(original[section["start"]:section["end"]] for section in included).strip()
    diagnostics = []
    for section in sections:
        action = "include"
        if not reason and section["section"] == "stop":
            action = "discard"
        diagnostics.append({
            "heading": section["heading"], "section": section["section"],
            "detection": section["detection"],
            "start": section["start"], "end": section["end"], "action": action,
        })
    return {
        "version": STRUCTURAL_TEXT_SELECTION_VERSION,
        "section_inference_version": JD_STRUCTURE_INFERENCE_VERSION,
        "strategy": "full_description_fallback" if reason else "conservative_section_selection",
        "original_description": original,
        "selected_description": selected,
        "included_sections": [row for row in diagnostics if row["action"] == "include"],
        "discarded_sections": [row for row in diagnostics if row["action"] == "discard"],
        "fallback_reason": reason,
    }


def select_job_description(job: NormalizedJob) -> NormalizedJob:
    """Preserve full source payload and original text across repeated refreshes."""
    raw = deepcopy(job.raw_payload)
    previous = raw.get(PROVENANCE_KEY)
    owned = (
        isinstance(previous, dict)
        and previous.get("version") == STRUCTURAL_TEXT_SELECTION_VERSION
        and previous.get("selected_description") == job.description
        and isinstance(previous.get("original_description"), str)
    )
    original = previous["original_description"] if owned else job.description
    provenance = select_structural_jd_text(original)
    if owned:
        if "source_provenance_value" in previous:
            provenance["source_provenance_value"] = previous["source_provenance_value"]
    elif PROVENANCE_KEY in raw:
        provenance["source_provenance_value"] = raw[PROVENANCE_KEY]
    raw[PROVENANCE_KEY] = provenance
    return replace(job, description=provenance["selected_description"], raw_payload=raw)
