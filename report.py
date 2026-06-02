"""
report.py — pure Python Markdown renderer; no LLM calls.
"""

from pathlib import Path


def render_markdown(report: dict, *, out_path: str) -> None:
    """Render the full analysis report dict to a Markdown file."""
    lines = _build_lines(report)
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _tick(value: object) -> str:
    return "✓" if value else "✗"


def _build_lines(report: dict) -> list[str]:
    meta    = report.get("meta", {})
    rp      = report.get("resume_profile", {})
    jd      = report.get("jd_profile", {})
    km      = report.get("keyword_match", {})
    bullets = report.get("bullets", {})
    jargon  = report.get("jargon", {})
    struct  = report.get("structure", {})
    degree  = report.get("degree_alignment", {})
    score   = report.get("overall_score", 0)
    passes  = report.get("passes_ats_threshold", False)
    summary = report.get("summary", "")

    lines: list[str] = []

    # 1. Header
    candidate = rp.get("name", "Unknown Candidate")
    jd_title  = jd.get("job_title", "Unknown Role")
    company   = jd.get("company", "Unknown Company")
    verdict   = "PASS" if passes else "FAIL"
    lines += [
        f"# Résumé Analysis Report",
        f"",
        f"**Candidate:** {candidate}  ",
        f"**Target role:** {jd_title} @ {company}  ",
        f"**Degree:** {meta.get('degree', '')}  ",
        f"**Generated:** {meta.get('generated_at', '')}  ",
        f"",
        f"## Overall Score: {score}/100  ({verdict} — 60% ATS threshold)",
        f"",
    ]

    # 2. Executive summary
    lines += [
        "## Executive Summary",
        "",
        summary.strip(),
        "",
    ]

    # 3. Keyword match
    present = km.get("present", [])
    missing = km.get("missing", [])
    km_score = km.get("keyword_match_score", 0)
    lines += [
        "## Keyword Match",
        "",
        f"**Score:** {km_score}/100",
        "",
        "| Present keywords (up to 20) | Missing keywords (up to 20) |",
        "|---|---|",
    ]
    max_rows = max(len(present), len(missing), 1)
    for i in range(min(max_rows, 20)):
        p_cell = present[i]["keyword"] if i < len(present) else ""
        m_item = missing[i] if i < len(missing) else {}
        imp    = m_item.get("importance", "")
        m_cell = f"**{m_item['keyword']}** ({imp})" if m_item else ""
        lines.append(f"| {p_cell} | {m_cell} |")
    lines.append("")

    # 4. Bullet audit
    bullet_list = bullets.get("bullets", [])
    bq_avg = bullets.get("bullet_quality_avg", 0)
    lines += [
        "## Bullet Quality Audit",
        "",
        f"**Average score:** {bq_avg}/100  (L1=OK, L2=Better, L3=Best)",
        "",
        "| Project / Role | Bullet (truncated to 80 chars) | Action | Tech | Impact | Level | What's Missing |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in bullet_list:
        text     = b.get("bullet_text", "")[:80]
        parent   = b.get("parent_title", "")
        action   = _tick(b.get("has_action_verb"))
        tech     = _tick(b.get("has_specific_technology"))
        impact   = _tick(b.get("has_measurable_impact"))
        level    = b.get("level", "")
        missing_ = b.get("what_is_missing", "")
        lines.append(f"| {parent} | {text} | {action} | {tech} | {impact} | {level} | {missing_} |")
    lines.append("")

    # 5. Jargon flags
    flags      = jargon.get("flags", [])
    jargon_sc  = jargon.get("jargon_score", 0)
    lines += [
        "## Game-Dev Jargon Flags",
        "",
        f"**Score:** {jargon_sc}/100",
        "",
    ]
    if flags:
        lines += [
            "| Term Used | Suggested Translation | Severity |",
            "|---|---|---|",
        ]
        for f in flags:
            lines.append(
                f"| {f.get('term_used', '')} "
                f"| {f.get('suggested_translation', '')} "
                f"| {f.get('severity', '')} |"
            )
    else:
        lines.append("No game-dev jargon flags raised. ✓")
    lines.append("")

    # 6. Structure audit
    tt         = struct.get("three_thirds", {})
    ats_flags  = struct.get("ats_red_flags", [])
    struct_sc  = struct.get("structure_score", 0)
    headings_p = ", ".join(struct.get("section_headings_present", [])) or "none detected"
    headings_m = ", ".join(struct.get("section_headings_missing", [])) or "none missing"
    lines += [
        "## Structure Audit",
        "",
        f"**Score:** {struct_sc}/100  "
        f"| Pages (est.): {struct.get('page_count_estimate', '?')}  "
        f"| Single-column: {_tick(struct.get('single_column_likely'))}",
        "",
        f"**Headings present:** {headings_p}  ",
        f"**Headings missing:** {headings_m}",
        "",
        "**Three-Thirds compliance:**",
        "",
        f"| Zone | Check | Status |",
        f"|---|---|---|",
        f"| Top third    | Name present          | {_tick(tt.get('top_third_has_name'))} |",
        f"| Top third    | Contact present       | {_tick(tt.get('top_third_has_contact'))} |",
        f"| Top third    | Summary / featured    | {_tick(tt.get('top_third_has_summary_or_featured'))} |",
        f"| Middle third | Projects / experience | {_tick(tt.get('middle_third_has_projects_or_experience'))} |",
        f"| Bottom third | Skills / keywords     | {_tick(tt.get('bottom_third_has_skills_keywords'))} |",
        "",
    ]
    if ats_flags:
        lines += [
            "**ATS red flags:**",
            "",
            "| Issue | Evidence |",
            "|---|---|",
        ]
        for flag in ats_flags:
            lines.append(f"| {flag.get('issue', '')} | {flag.get('evidence', '')} |")
    else:
        lines.append("No ATS red flags detected. ✓")
    lines.append("")

    # 7. Degree alignment
    lines += [
        "## Degree Alignment",
        "",
        f"**Score:** {degree.get('degree_alignment_score', 0)}/100",
        f"**Degree:** {degree.get('student_degree', '')}  ",
        f"**JD Title:** {degree.get('jd_title', '')}  ",
        f"**On suggested list:** {_tick(degree.get('title_on_suggested_list'))} "
        f"{degree.get('matched_against', '')}  ",
        f"**Commentary:** {degree.get('fit_commentary', '')}",
        "",
    ]

    # 8. Score breakdown
    km_contrib  = round(km.get("keyword_match_score", 0) * 0.40, 1)
    bq_contrib  = round(bullets.get("bullet_quality_avg", 0) * 0.25, 1)
    st_contrib  = round(struct.get("structure_score", 0) * 0.15, 1)
    ja_contrib  = round(jargon.get("jargon_score", 0) * 0.10, 1)
    da_contrib  = round(degree.get("degree_alignment_score", 0) * 0.10, 1)
    lines += [
        "## Score Breakdown",
        "",
        "| Component | Raw | Weight | Contribution |",
        "|---|---|---|---|",
        f"| Keyword match    | {km.get('keyword_match_score', 0)} | 40% | {km_contrib} |",
        f"| Bullet quality   | {bullets.get('bullet_quality_avg', 0)} | 25% | {bq_contrib} |",
        f"| Structure        | {struct.get('structure_score', 0)} | 15% | {st_contrib} |",
        f"| Jargon           | {jargon.get('jargon_score', 0)} | 10% | {ja_contrib} |",
        f"| Degree alignment | {degree.get('degree_alignment_score', 0)} | 10% | {da_contrib} |",
        f"| **Total**        |     |     | **{score}** |",
        "",
    ]

    return lines
