from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Any


BROAD_MINING_EXPORT_VERSION = (
    "tqd3-broad-mining-export-v1.0.0"
)


def _candidate_rows(
    candidate_report: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = candidate_report.get("candidates")
    rows = rows if isinstance(rows, list) else []
    return [
        row
        for row in rows
        if isinstance(row, dict)
    ]


def build_broad_mining_candidate_summary_csv(
    candidate_report: dict[str, Any],
    reviews: list[dict[str, Any]],
    suggestions: dict[str, dict[str, Any]],
) -> str:
    review_index = {
        str(row.get("candidate_id") or ""): row
        for row in reviews
        if isinstance(row, dict)
    }

    output = io.StringIO()
    fieldnames = [
        "canonical_name",
        "status",
        "entity_type",
        "supporting_sources",
        "primary_official_sources",
        "secondary_sources",
        "unclassified_sources",
        "suggested_decision",
        "suggestion_confidence",
        "reason_code",
        "suggestion_reason",
        "taxonomy_covered",
        "taxonomy_capabilities",
        "review_decision",
        "candidate_id",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()

    for candidate in _candidate_rows(candidate_report):
        candidate_id = str(candidate.get("candidate_id") or "")
        authority = (
            candidate.get("source_authority")
            if isinstance(candidate.get("source_authority"), dict)
            else {}
        )
        counts = authority.get("counts")
        counts = counts if isinstance(counts, dict) else {}
        urls = candidate.get("supporting_source_urls")
        urls = urls if isinstance(urls, list) else []
        suggestion = suggestions.get(candidate_id, {})
        review = review_index.get(candidate_id, {})
        writer.writerow(
            {
                "canonical_name": str(
                    candidate.get("canonical_name") or ""
                ),
                "status": str(candidate.get("status") or ""),
                "entity_type": str(
                    candidate.get("entity_type") or ""
                ),
                "supporting_sources": len(urls),
                "primary_official_sources": int(
                    counts.get("primary_official", 0) or 0
                ),
                "secondary_sources": int(
                    counts.get("secondary", 0) or 0
                ),
                "unclassified_sources": int(
                    counts.get("unclassified", 0) or 0
                ),
                "suggested_decision": str(
                    suggestion.get("suggested_decision") or ""
                ),
                "suggestion_confidence": str(
                    suggestion.get("confidence") or ""
                ),
                "reason_code": str(
                    suggestion.get("reason_code") or ""
                ),
                "suggestion_reason": str(
                    (
                        suggestion.get("reasons")
                        or [""]
                    )[0]
                ),
                "taxonomy_covered": bool(
                    (
                        (
                            suggestion.get("signals")
                            or {}
                        ).get(
                            "taxonomy_coverage",
                            {},
                        )
                        or {}
                    ).get(
                        "matched",
                        False,
                    )
                ),
                "taxonomy_capabilities": ",".join(
                    (
                        (
                            suggestion.get("signals")
                            or {}
                        ).get(
                            "taxonomy_coverage",
                            {},
                        )
                        or {}
                    ).get(
                        "capability_ids",
                        [],
                    )
                ),
                "review_decision": str(
                    review.get("decision") or "unreviewed"
                ),
                "candidate_id": candidate_id,
            }
        )

    return output.getvalue()


def build_broad_mining_debug_zip(
    *,
    research_artifacts: list[dict[str, Any]],
    raw_research: list[dict[str, Any]],
    candidate_report: dict[str, Any],
    candidate_reviews: list[dict[str, Any]],
    suggestions: dict[str, dict[str, Any]],
) -> bytes:
    """Build a deterministic local debug/export ZIP."""
    payloads = {
        "research_artifacts.json": research_artifacts,
        "raw_research.json": raw_research,
        "candidate_report.json": candidate_report,
        "candidate_reviews.json": candidate_reviews,
        "deterministic_review_suggestions.json": suggestions,
        "export_manifest.json": {
            "export_version": BROAD_MINING_EXPORT_VERSION,
            "research_artifact_count": len(
                research_artifacts
            ),
            "raw_research_count": len(raw_research),
            "candidate_count": len(
                _candidate_rows(candidate_report)
            ),
            "candidate_review_count": len(
                candidate_reviews
            ),
            "governance": {
                "network_calls": 0,
                "model_calls": 0,
                "mutations": 0,
                "scoring_influence": False,
            },
        },
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name in sorted(payloads):
            archive.writestr(
                name,
                json.dumps(
                    payloads[name],
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )

        archive.writestr(
            "candidate_summary.csv",
            build_broad_mining_candidate_summary_csv(
                candidate_report,
                candidate_reviews,
                suggestions,
            ),
        )
        archive.writestr(
            "README.txt",
            (
                "TQ-D3 Broad Mining debug/export bundle\n"
                "======================================\n"
                "Contains persisted research, recomputed candidates, "
                "deterministic review suggestions, and human review state.\n\n"
                "Exporting this bundle makes no Tavily/Ollama/OpenAI call "
                "and performs no proposal, registry, taxonomy, or scoring "
                "mutation.\n"
            ),
        )

    return buffer.getvalue()
