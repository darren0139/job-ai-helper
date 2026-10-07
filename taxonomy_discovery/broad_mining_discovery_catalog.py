from __future__ import annotations

import unicodedata
from typing import Any


DISCOVERY_CATALOG_VERSION = (
    "tqd3-broad-mining-discovery-catalog-v1.0.0"
)

CATALOG_ALREADY_HANDLED = "already_handled"
CATALOG_READY_TO_VERIFY = "ready_to_verify"
CATALOG_STRONG_SUGGESTION = "strong_suggestion"
CATALOG_SUGGESTED = "suggested"
CATALOG_OTHER_DISCOVERY = "other_discovery"
CATALOG_DISMISSED = "dismissed"


def normalize_discovery_name(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )
    return " ".join(text.split()).casefold()


def catalog_status_for_guided_bucket(
    bucket: str,
) -> str:
    bucket = str(bucket or "")
    return {
        "already_known": CATALOG_ALREADY_HANDLED,
        "confirmed": CATALOG_READY_TO_VERIFY,
        "recommended": CATALOG_STRONG_SUGGESTION,
        "needs_verification": CATALOG_SUGGESTED,
        "other_discoveries": CATALOG_OTHER_DISCOVERY,
        "parked": CATALOG_OTHER_DISCOVERY,
        "dismissed": CATALOG_DISMISSED,
    }.get(
        bucket,
        CATALOG_OTHER_DISCOVERY,
    )


def build_discovery_catalog(
    guided_summary: dict[str, Any],
) -> dict[str, Any]:
    items = guided_summary.get("items")
    items = items if isinstance(items, list) else []

    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        canonical_name = str(
            item.get("canonical_name") or ""
        ).strip()
        if not canonical_name:
            continue

        rows.append(
            {
                "candidate_id": str(
                    item.get("candidate_id") or ""
                ),
                "canonical_name": canonical_name,
                "normalized_name":
                    normalize_discovery_name(
                        canonical_name
                    ),
                "catalog_status":
                    catalog_status_for_guided_bucket(
                        str(
                            item.get("bucket") or ""
                        )
                    ),
                "guided_bucket": str(
                    item.get("bucket") or ""
                ),
                "friendly_reason": str(
                    item.get("friendly_reason") or ""
                ),
                "taxonomy_capabilities": list(
                    item.get(
                        "taxonomy_capabilities"
                    )
                    or []
                ),
                "supporting_sources": int(
                    item.get(
                        "supporting_sources",
                        0,
                    )
                    or 0
                ),
                "current_review": str(
                    item.get("current_review")
                    or "unreviewed"
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row["canonical_name"].casefold(),
            row["candidate_id"],
        )
    )

    return {
        "catalog_version":
            DISCOVERY_CATALOG_VERSION,
        "items": rows,
        "count": len(rows),
        "governance": {
            "recognition_only": True,
            "exact_name_lookup_only": True,
            "network_calls": 0,
            "model_calls": 0,
            "automatic_verification": False,
            "proposal_creation": False,
            "registry_mutations": 0,
            "taxonomy_mutations": 0,
            "scoring_influence": False,
        },
    }


def find_discovery_exact(
    name: str,
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return exact discovered-name matches for future escalation.

    This helper is recognition-only. An exact catalog hit must not be treated
    as a verified registry identity, capability relationship, or scoring fact.
    """
    normalized = normalize_discovery_name(name)
    if not normalized:
        return []

    items = catalog.get("items")
    items = items if isinstance(items, list) else []
    return [
        item
        for item in items
        if (
            isinstance(item, dict)
            and str(
                item.get("normalized_name")
                or ""
            )
            == normalized
        )
    ]
