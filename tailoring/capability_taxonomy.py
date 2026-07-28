"""Versioned capability-taxonomy loader and deterministic matcher for Phase 6D."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "taxonomy" / "capability_taxonomy_v1.json"
ALLOWED_LABELS = {"direct", "transferable", "weak", "none"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def normalise(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("&", " and ")
    text = text.replace("row-level", "row level")
    text = text.replace("cross-functional", "cross functional")
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    return " ".join(text.split())


def _contains(text: str, phrase: str) -> bool:
    text_key = f" {normalise(text)} "
    phrase_key = normalise(phrase)
    if not phrase_key:
        return False
    if " " in phrase_key or any(ch in phrase_key for ch in "+#./"):
        return f" {phrase_key} " in text_key
    return bool(re.search(rf"\b{re.escape(phrase_key)}\b", normalise(text)))


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    return any(_contains(text, phrase) for phrase in phrases)


def _matches_groups(text: str, groups: list[list[str]]) -> bool:
    return all(_contains_any(text, group) for group in groups)


@dataclass(frozen=True)
class CapabilityTaxonomy:
    version: str
    capabilities: tuple[dict[str, Any], ...]

    def by_id(self) -> dict[str, dict[str, Any]]:
        return {
            str(item["capability_id"]): item
            for item in self.capabilities
        }


def _validate_capability(item: dict[str, Any], seen: set[str]) -> None:
    capability_id = _clean(item.get("capability_id"))
    if not capability_id:
        raise ValueError("Every capability requires capability_id.")
    if capability_id in seen:
        raise ValueError(f"Duplicate capability_id: {capability_id}")
    if not re.fullmatch(r"[a-z0-9_.-]+", capability_id):
        raise ValueError(f"Invalid capability_id: {capability_id}")
    seen.add(capability_id)

    if not _clean(item.get("label")):
        raise ValueError(f"{capability_id}: missing label")
    if not _clean(item.get("domain")):
        raise ValueError(f"{capability_id}: missing domain")
    if not isinstance(item.get("priority"), int):
        raise ValueError(f"{capability_id}: priority must be an integer")

    requirement = item.get("requirement")
    if not isinstance(requirement, dict):
        raise ValueError(f"{capability_id}: requirement must be an object")
    if not isinstance(requirement.get("any_terms", []), list):
        raise ValueError(f"{capability_id}: requirement.any_terms must be a list")
    if not isinstance(requirement.get("all_terms", []), list):
        raise ValueError(f"{capability_id}: requirement.all_terms must be a list")

    tiers = item.get("evidence_tiers")
    if not isinstance(tiers, list) or not tiers:
        raise ValueError(f"{capability_id}: evidence_tiers must be a non-empty list")
    for tier in tiers:
        label = _clean(tier.get("label"))
        if label not in ALLOWED_LABELS:
            raise ValueError(f"{capability_id}: invalid tier label {label!r}")
        if "all_groups" in tier and not isinstance(tier["all_groups"], list):
            raise ValueError(f"{capability_id}: all_groups must be a list")
        if "any_terms" in tier and not isinstance(tier["any_terms"], list):
            raise ValueError(f"{capability_id}: any_terms must be a list")

    if not isinstance(item.get("does_not_prove", []), list):
        raise ValueError(f"{capability_id}: does_not_prove must be a list")


def load_taxonomy(path: str | Path = TAXONOMY_PATH) -> CapabilityTaxonomy:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    version = _clean(data.get("taxonomy_version"))
    if not version:
        raise ValueError("Taxonomy requires taxonomy_version.")

    raw_capabilities = data.get("capabilities")
    if not isinstance(raw_capabilities, list) or not raw_capabilities:
        raise ValueError("Taxonomy requires a non-empty capabilities list.")

    seen: set[str] = set()
    for item in raw_capabilities:
        if not isinstance(item, dict):
            raise ValueError("Every capability must be an object.")
        _validate_capability(item, seen)

    ordered = tuple(
        sorted(
            raw_capabilities,
            key=lambda item: (
                int(item.get("priority", 999999)),
                str(item.get("capability_id", "")),
            ),
        )
    )
    return CapabilityTaxonomy(version=version, capabilities=ordered)


@lru_cache(maxsize=1)
def get_default_taxonomy() -> CapabilityTaxonomy:
    return load_taxonomy(TAXONOMY_PATH)


def capability_anchors(
    taxonomy: CapabilityTaxonomy | None = None,
) -> dict[str, set[str]]:
    taxonomy = taxonomy or get_default_taxonomy()
    anchors: dict[str, set[str]] = {}
    for item in taxonomy.capabilities:
        for name, values in (item.get("evidence_concepts") or {}).items():
            anchors.setdefault(str(name), set()).update(
                _clean(value) for value in values if _clean(value)
            )
    return anchors


def classify_requirement_record(
    requirement: dict[str, Any],
    taxonomy: CapabilityTaxonomy | None = None,
) -> dict[str, Any] | None:
    taxonomy = taxonomy or get_default_taxonomy()
    text = " ".join(
        [
            _clean(requirement.get("text")),
            _clean(requirement.get("atomic_focus")),
        ]
    )

    for item in taxonomy.capabilities:
        matcher = item.get("requirement") or {}
        any_terms = matcher.get("any_terms", []) or []
        all_terms = matcher.get("all_terms", []) or []
        if all_terms and not all(_contains(text, term) for term in all_terms):
            continue
        if any_terms and not _contains_any(text, any_terms):
            continue
        if not any_terms and not all_terms:
            continue
        return item
    return None


def classify_requirement(
    requirement: dict[str, Any],
    taxonomy: CapabilityTaxonomy | None = None,
) -> str | None:
    record = classify_requirement_record(requirement, taxonomy)
    return str(record["capability_id"]) if record else None


def evaluate_evidence(
    requirement: dict[str, Any],
    evidence_text: str,
    taxonomy: CapabilityTaxonomy | None = None,
) -> dict[str, Any]:
    taxonomy = taxonomy or get_default_taxonomy()
    capability = classify_requirement_record(requirement, taxonomy)
    if capability is None:
        return {
            "capability_id": None,
            "label": None,
            "reason": "unrecognised_capability",
            "concepts": [],
            "taxonomy_version": taxonomy.version,
            "does_not_prove": [],
        }

    if capability.get("explicit_only"):
        subjective_terms = (
            capability.get("evidence_concepts", {}).get("subjective", [])
        )
        if not _contains_any(evidence_text, subjective_terms):
            return {
                "capability_id": capability["capability_id"],
                "label": "none",
                "reason": "explicit_evidence_required",
                "concepts": [],
                "taxonomy_version": taxonomy.version,
                "does_not_prove": capability.get("does_not_prove", []),
            }

    for tier in capability.get("evidence_tiers", []):
        all_groups = tier.get("all_groups", []) or []
        any_terms = tier.get("any_terms", []) or []
        if all_groups and not _matches_groups(evidence_text, all_groups):
            continue
        if any_terms and not _contains_any(evidence_text, any_terms):
            continue
        if not all_groups and not any_terms and tier.get("label") != "none":
            continue
        return {
            "capability_id": capability["capability_id"],
            "label": tier.get("label", "none"),
            "reason": tier.get("reason", "taxonomy_rule"),
            "concepts": list(tier.get("concepts", []) or []),
            "taxonomy_version": taxonomy.version,
            "does_not_prove": capability.get("does_not_prove", []),
        }

    return {
        "capability_id": capability["capability_id"],
        "label": "none",
        "reason": "recognised_but_unsupported",
        "concepts": [],
        "taxonomy_version": taxonomy.version,
        "does_not_prove": capability.get("does_not_prove", []),
    }


def taxonomy_documents(
    taxonomy: CapabilityTaxonomy | None = None,
) -> list[dict[str, Any]]:
    taxonomy = taxonomy or get_default_taxonomy()
    documents = []
    for item in taxonomy.capabilities:
        requirement_terms = item.get("requirement", {}).get("any_terms", [])
        evidence_terms: list[str] = []
        for tier in item.get("evidence_tiers", []):
            evidence_terms.extend(tier.get("any_terms", []) or [])
            for group in tier.get("all_groups", []) or []:
                evidence_terms.extend(group)
        document = "\n".join(
            [
                f"Capability ID: {item['capability_id']}",
                f"Label: {item['label']}",
                f"Domain: {item['domain']}",
                "Requirement terms: " + ", ".join(requirement_terms),
                "Evidence terms: " + ", ".join(dict.fromkeys(evidence_terms)),
                "Does not prove: " + ", ".join(item.get("does_not_prove", [])),
            ]
        )
        documents.append(
            {
                "id": str(item["capability_id"]),
                "document": document,
                "metadata": {
                    "capability_id": str(item["capability_id"]),
                    "domain": str(item["domain"]),
                    "taxonomy_version": taxonomy.version,
                },
            }
        )
    return documents
