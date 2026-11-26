"""Conservative, source-only JD text selection before Job Finder persistence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re
from typing import Any

from analysis_stability.jd_section_inference import (
    JD_STRUCTURE_INFERENCE_VERSION,
    _signals,
    infer_semantic_list_heading,
)
from analysis_stability.stable_evidence_scoring import (
    _normalise_jd_section_heading,
    _raw_section_for_heading,
)
from job_discovery.models import NormalizedJob


STRUCTURAL_TEXT_SELECTION_VERSION = "job-finder-structural-text-selection-v1.2"
_PREVIOUS_SELECTION_VERSIONS = {
    "job-finder-structural-text-selection-v1",
    "job-finder-structural-text-selection-v1.1",
}
PROVENANCE_KEY = "_job_finder_structural_text_selection"

# These additions only identify explicit administrative boundaries or retained
# work context. Core JD headings come from the existing controlled classifier.
_HEADING_ALIASES = {
    "your responsibilities": "responsibilities",
    "what you ll be doing": "responsibilities",
    "what youll be doing": "responsibilities",
    "what you will be doing": "responsibilities",
    "the role": "role overview",
    "your role": "role overview",
    "what you bring": "requirements",
    "who you are": "requirements",
    "about you": "requirements",
    "skills": "requirements",
    "technical skills": "requirements",
    "experience": "requirements",
    "education": "requirements",
    "preferred experience": "preferred qualifications",
    "bonus points": "preferred qualifications",
    "our mission": "about the company",
    "why join us": "what we offer",
    "perks": "benefits",
    "employee benefits": "benefits",
    "equal opportunity": "equal opportunity employer",
    "application instructions": "how to apply",
    "privacy notices": "privacy notice",
    "company description": "about the company",
    "our story": "about the company",
    "role": "role overview",
    "requirements minimum qualifications": "minimum qualifications",
    "bonus": "preferred qualifications",
    "desired experience": "preferred qualifications",
    "example projects": "responsibilities",
}
_CONTEXT_HEADINGS = frozenset({
    "eligibility", "work eligibility", "work authorization", "work authorisation",
    "right to work", "working hours", "work arrangements", "working arrangements",
    "employment conditions", "work location", "security clearance",
    "visa", "sponsorship", "visa sponsorship", "hybrid onsite requirements",
    "hybrid work", "work model", "shift schedule", "shift requirements",
    "weekend requirements", "contract duration", "contract terms",
    "temporary assignment", "travel", "relocation", "travel relocation",
    "physical requirements", "physical location constraints", "location requirements",
    "location", "visas", "remote work",
})
_ADMIN_HEADINGS = frozenset({
    "legal disclaimer", "privacy notice", "privacy policy",
    "equal employment opportunity", "equal opportunities",
    "cookie policy", "cookie notice", "navigation", "footer",
    "related jobs", "similar jobs", "recruiting information", "tracking notice",
    "scam alert", "fraud warning", "fraud alert",
})
_BULLET = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s+")
_CONSTRAINT = re.compile(
    r"\b(?:must|should|shall|required|requirement[s]?|eligib(?:le|ility)|citizen(?:s|ship)?|"
    r"work (?:permit|authori[sz]ation|rights?)|security clearance|"
    r"visa[s]?|sponsor(?:ship|ed|ing)?|hybrid|on[ -]?site|in[ -]person|remote|weekends?|shifts?|"
    r"working hours|travel|relocat(?:e|ion|ing)|contract|temporary|"
    r"physical(?:ly)?\s+(?:requirements?|fitness|fit|abilities|ability|demands?|"
    r"stamina|strength|exertion|labou?r|work|duties|location|presence)|"
    r"lifting|standing|mobility|(?:carry|lift)\s+\d+|"
    r"able to|ability to|licen[cs](?:e[ds]?|ing)|certification|"
    r"experience|knowledge|proficien(?:cy|t))\b",
    re.IGNORECASE,
)


def _has_important_content(text: str) -> bool:
    if _CONSTRAINT.search(text):
        return True
    for line in text.splitlines():
        signals = _signals(_BULLET.sub("", line.strip()))
        if signals["responsibilities"] or signals["requirements"]:
            return True
    return False


def _unknown_heading(line: str) -> bool:
    text = line.strip().strip("*_")
    words = text.rstrip(":").split()
    return (
        not _BULLET.match(line)
        and 0 < len(words) <= 10
        and len(text) <= 100
        and (text.endswith(":") or text.startswith("#") or text.isupper() or text.istitle())
    )


_MIXED_HEADINGS = frozenset({"logistics", "additional information", "additional details"})
_NAVIGATION = frozenset({
    "services", "industries", "insights", "partners", "careers", "about us",
    "products", "solutions", "contact us", "site navigation", "footer navigation",
})
_END_MARKERS = frozenset({
    "scam alert", "fraud alert", "fraud warning", "apply now",
    "related jobs", "similar jobs", "thank you for your interest",
    "site footer", "footer navigation",
})
_METADATA = re.compile(
    r"^(date|location|company|job requisition id|requisition id|job id|"
    r"job posting id|posted date)\s*:\s*\S", re.IGNORECASE,
)
_ROLE_INTRODUCTION = re.compile(
    r"\b(?:we(?:['’]re| are)\s+(?:looking|seeking)|"
    r"as (?:a|an|the)\s+[^.!?\n]{0,70}(?:engineer|developer|"
    r"specialist|analyst|manager|designer|researcher|role)|"
    r"you(?:['’](?:ll|d|re)| will| would)|your (?:role|responsibilities))\b",
    re.IGNORECASE,
)
_ORGANISATION = re.compile(
    r"^[A-Z][\w&.'-]*(?:[ \t]+[A-Z][\w&.'-]*){0,4}[ \t]+"
    r"(?:(?:is|are)\s+(?:an?|the)\s+[^.!?\n]{0,90}"
    r"\b(?:company|organisation|organization|lab|provider|business)\b|"
    r"develops products\b|builds products\b|provides services\b)",
)
_ORGANISATION_CONTINUATION = re.compile(
    r"^(?:we now power|we (?:have )?raised|raised\s+\$|we use our products|"
    r"our (?:products|customers|investors|mission)\b)", re.IGNORECASE,
)
_EQUAL_OPPORTUNITY = re.compile(
    r"^(?:we are|[A-Z][\w&.'-]*(?:[ \t]+[A-Z][\w&.'-]*){0,4} is)"
    r"\s+an?\s+equal (?:opportunity|employment opportunity) employer\b",
    re.IGNORECASE,
)
_APPLICATION_NOTICE = re.compile(
    r"^(?:we receive a (?:high|large) volume of applications|"
    r"due to (?:the )?(?:high|large) volume of applications|"
    r"only shortlisted (?:applicants|candidates) will be notified|"
    r"please (?:submit|send) (?:your|an?) (?:cv|resume|application)\b)",
    re.IGNORECASE,
)


def _heading(line: str) -> tuple[str, str]:
    heading = _normalise_jd_section_heading(line)
    canonical = _HEADING_ALIASES.get(heading, heading)
    detection = "controlled_heading_alias" if canonical != heading else "controlled_heading"
    if heading in _CONTEXT_HEADINGS or heading in {"salary", "compensation"}:
        return "work_context", detection
    if canonical in _ADMIN_HEADINGS:
        return "stop", detection
    if heading in _MIXED_HEADINGS:
        return "mixed_context", detection
    return _raw_section_for_heading(canonical), detection


def _navigation_cluster(lines: list[str]) -> bool:
    for start in range(len(lines)):
        labels = {
            _normalise_jd_section_heading(line)
            for line in lines[start:start + 10] if line.strip()
        }
        if len(labels & _NAVIGATION) >= 3:
            return True
    return False


def _job_region(original: str, job_title: str) -> dict[str, Any]:
    lines = original.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    keys = [_normalise_jd_section_heading(line) for line in lines]
    jd_headings = [
        index for index, line in enumerate(lines)
        if not _BULLET.match(line)
        and _heading(line)[0] in {"responsibilities", "requirements", "core", "preferred"}
    ]
    first_jd = jd_headings[0] if jd_headings else len(lines)
    leading_shell = (
        "skip to main content" in keys[:first_jd]
        or _navigation_cluster(lines[:first_jd])
    )
    trailing_shell = _navigation_cluster(lines[jd_headings[-1] + 1:]) if jd_headings else False
    start = 0
    end = len(original)
    start_reason = "source_description_start"
    end_reason = "source_description_end"
    reason = ""

    if leading_shell or trailing_shell:
        if len(jd_headings) < 2:
            reason = "insufficient_job_structure"
        if leading_shell and not reason:
            candidates = []
            index = 0
            # Navigation can contain legitimate classifier labels (Overview,
            # Education). Establish the metadata anchor before interpreting JD
            # headings, rather than treating the first menu label as the job.
            while index < len(lines):
                match = _METADATA.match(lines[index].strip())
                if not match:
                    index += 1
                    continue
                metadata_start = index
                labels = set()
                while index < len(lines) and index < metadata_start + 10:
                    value = lines[index].strip()
                    field = _METADATA.match(value)
                    if value and not field:
                        break
                    if field:
                        labels.add(field.group(1).casefold())
                    index += 1
                title_index = metadata_start - 1
                while title_index >= 0 and not lines[title_index].strip():
                    title_index -= 1
                if (
                    len(labels) >= 2 and title_index >= 0
                    and 2 <= len(lines[title_index].split()) <= 20
                    and len(lines[title_index].strip()) <= 180
                    and keys[title_index] not in _NAVIGATION
                    and not _heading(lines[title_index])[0]
                ):
                    candidates.append(title_index)
            candidate_reason = "title_with_metadata"
            if not candidates and job_title:
                candidate_reason = "known_title_before_jd"
                candidates = [index for index in range(len(lines))
                              if keys[index] == _normalise_jd_section_heading(job_title)]
            if len(candidates) != 1:
                reason = "unreliable_job_start"
            else:
                start = offsets[candidates[0]]
                start_reason = candidate_reason

        if not reason:
            region_headings = [index for index in jd_headings if offsets[index] >= start]
            if len(region_headings) < 2:
                reason = "insufficient_job_structure"
            else:
                first_jd = region_headings[0]

        if not reason:
            end_candidates = []
            for index in range(first_jd + 1, len(lines)):
                if keys[index] not in _END_MARKERS:
                    continue
                suffix_keys = set(keys[index:])
                if (_navigation_cluster(lines[index:])
                        or len(suffix_keys & _END_MARKERS) >= 2):
                    end_candidates.append(index)
            if not end_candidates:
                reason = "unreliable_job_end"
            else:
                end = offsets[end_candidates[0]]
                end_reason = "standalone_end_marker_with_footer_context"
            if not reason and (end <= start or sum(start <= offsets[i] < end for i in jd_headings) < 2):
                reason = "incomplete_job_region"
            if not reason and (_has_important_content(original[:start])
                               or _has_important_content(original[end:])):
                reason = "important_content_outside_job_region"

    if reason:
        start, end = 0, len(original)
    return {
        "job_region_text": original[start:end],
        "job_region_start": start, "job_region_end": end,
        "job_region_strategy": "full_description_fallback" if reason else (
            "metadata_and_page_shell" if start or end != len(original) else "source_description"
        ),
        "job_region_start_reason": start_reason,
        "job_region_end_reason": end_reason,
        "job_region_fallback": bool(reason),
        "job_region_fallback_reason": reason,
    }


def _blocks(original: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split only at existing blank paragraphs or list-item boundaries."""
    blocks = []
    block_start = start
    cursor = start
    has_content = False
    after_blank = False
    for line in original[start:end].splitlines(keepends=True):
        if line.strip():
            if has_content and (after_blank or _BULLET.match(line)):
                blocks.append((block_start, cursor))
                block_start = cursor
            has_content = True
            after_blank = False
        elif has_content:
            after_blank = True
        cursor += len(line)
    if start < end:
        blocks.append((block_start, end))
    return blocks


def _block_decision(text: str, *, follows_company: bool = False) -> tuple[str, str]:
    content = _BULLET.sub("", text.strip())
    if _ROLE_INTRODUCTION.search(content):
        return "include", "role_introduction"
    if _has_important_content(content):
        return "include", "protected_content"
    if _EQUAL_OPPORTUNITY.search(content):
        return "discard", "equal_opportunity_notice"
    if _APPLICATION_NOTICE.search(content):
        return "discard", "application_notice"
    label, separator, body = content.partition(":")
    if separator and "\n" not in label and _heading(label)[0] == "stop":
        if _signals(body)["stop"] or _APPLICATION_NOTICE.search(body.strip()):
            return "discard", "labelled_non_jd_list_item"
    if _ORGANISATION.search(content):
        return "discard", "organisation_overview"
    if follows_company and _ORGANISATION_CONTINUATION.search(content):
        return "discard", "organisation_overview_continuation"
    return "include", "uncertain_content_preserved"


def select_structural_jd_text(description: str, *, job_title: str = "") -> dict[str, Any]:
    """Select structured source content, retaining the full original on uncertainty."""
    original = description
    region = _job_region(original, job_title)
    lines = region["job_region_text"].splitlines(keepends=True)
    raw_lines = [line.rstrip("\r\n") for line in lines]
    starts = []
    offset = region["job_region_start"]
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
        section, detection = _heading(line)
        if not section:
            inferred = infer_semantic_list_heading(raw_lines, index)
            if inferred.get("section") in {"responsibilities", "requirements"}:
                section = inferred["section"]
                detection = "inferred_child_list"
            elif inferred.get("is_heading_candidate") or _unknown_heading(line):
                ambiguous.append(index)
        if section:
            boundaries.append((index, section, detection))
    starts.append(region["job_region_end"])

    sections = []
    for position, (line_index, section, detection) in enumerate(boundaries):
        start = starts[line_index]
        if position == 0 and start > region["job_region_start"]:
            sections.append({
                "heading": "", "section": "preamble", "detection": "paragraph_classification",
                "start": region["job_region_start"], "end": start,
                "body_start": region["job_region_start"],
            })
        end = region["job_region_end"]
        if position + 1 < len(boundaries):
            end = starts[boundaries[position + 1][0]]
        sections.append({
            "heading": raw_lines[line_index].strip(), "section": section,
            "detection": detection, "start": start, "end": end,
            "body_start": starts[line_index + 1],
        })
    if not sections:
        sections.append({
            "heading": "", "section": "preamble", "detection": "full_text",
            "start": region["job_region_start"], "end": region["job_region_end"],
            "body_start": region["job_region_start"],
        })

    jd_sections = [
        section for section in sections
        if section["section"] in {"responsibilities", "requirements", "core", "preferred"}
        and section["detection"] in {"controlled_heading", "controlled_heading_alias"}
        and original[section["body_start"]:section["end"]].strip()
    ]
    body = "\n".join(original[row["body_start"]:row["end"]] for row in jd_sections).strip()
    reason = region["job_region_fallback_reason"]
    if not reason and not jd_sections:
        reason = "no_confident_jd_structure"
    if not reason and (len(body) < 80 or len([line for line in body.splitlines() if line.strip()]) < 2):
        reason = "insufficient_jd_content"

    decisions = []
    for section in sections:
        section_type = section["section"]
        pieces = []
        if section_type in {"preamble", "mixed_context"}:
            follows_company = False
            for start, end in _blocks(original, section["body_start"], section["end"]):
                action, why = _block_decision(original[start:end], follows_company=follows_company)
                follows_company = why.startswith("organisation_overview")
                pieces.append({
                    **section, "start": start, "end": end, "action": action, "reason": why,
                })
                if section_type == "preamble" and why == "protected_content" and not reason:
                    reason = "important_unsectioned_text"
            if section_type == "mixed_context":
                action = "include" if any(row["action"] == "include" for row in pieces) else "discard"
                decisions.append({
                    **section, "end": section["body_start"], "action": action,
                    "reason": "mixed_context_heading",
                })
            decisions.extend(pieces)
        elif section_type == "stop":
            section_body = original[section["body_start"]:section["end"]]
            if not section_body.strip():
                reason = reason or "empty_non_jd_section"
            elif any(section["body_start"] <= starts[index] < section["end"] for index in ambiguous):
                reason = reason or "ambiguous_heading_in_non_jd_section"
            elif _has_important_content(section_body):
                reason = reason or "possible_requirement_in_non_jd_section"
            decisions.append({**section, "action": "discard", "reason": "explicit_non_jd_section"})
        else:
            decisions.append({**section, "action": "include", "reason": "jd_or_work_context"})

    for start, end in ((0, region["job_region_start"]), (region["job_region_end"], len(original))):
        if start < end:
            decisions.append({
                "heading": "", "section": "page_shell", "detection": "job_region_boundary",
                "start": start, "end": end, "action": "discard", "reason": "page_shell",
            })
    decisions.sort(key=lambda row: row["start"])
    selected = "".join(original[row["start"]:row["end"]] for row in decisions if row["action"] == "include").strip()
    if not reason and len(selected) < 80:
        reason = "insufficient_selected_content"
    if not reason and not any(row["action"] == "discard" for row in decisions):
        reason = "no_confident_non_jd_sections"
    if reason:
        selected = original
        for row in decisions:
            row["action"] = "include"
    diagnostics = [{key: value for key, value in row.items() if key != "body_start"} for row in decisions]
    preamble = [row for row in diagnostics if row["section"] == "preamble"]
    return {
        "version": STRUCTURAL_TEXT_SELECTION_VERSION,
        "section_inference_version": JD_STRUCTURE_INFERENCE_VERSION,
        "strategy": "full_description_fallback" if reason else "conservative_section_selection",
        "fallback_occurred": bool(reason),
        "original_description": original, **region,
        "selected_description": selected,
        "original_character_count": len(original),
        "job_region_character_count": len(region["job_region_text"]),
        "selected_character_count": len(selected),
        "discarded_character_count": len(original) - len(selected),
        "preamble_strategy": "full_description_fallback" if reason else (
            "paragraph_classification" if preamble else "no_preamble"
        ),
        "preamble_retained": [row for row in preamble if row["action"] == "include"],
        "preamble_discarded": [row for row in preamble if row["action"] == "discard"],
        "preamble_reason": "high_confidence_company_blocks_only",
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
        and previous.get("version") in _PREVIOUS_SELECTION_VERSIONS | {STRUCTURAL_TEXT_SELECTION_VERSION}
        and previous.get("selected_description") == job.description
        and isinstance(previous.get("original_description"), str)
    )
    original = previous["original_description"] if owned else job.description
    provenance = select_structural_jd_text(original, job_title=job.title)
    if owned:
        if "source_provenance_value" in previous:
            provenance["source_provenance_value"] = previous["source_provenance_value"]
    elif PROVENANCE_KEY in raw:
        provenance["source_provenance_value"] = raw[PROVENANCE_KEY]
    raw[PROVENANCE_KEY] = provenance
    return replace(job, description=provenance["selected_description"], raw_payload=raw)
