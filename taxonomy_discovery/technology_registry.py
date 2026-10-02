"""Deterministic technology/terminology registry for TQ-D2.6."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from tailoring.capability_taxonomy import get_default_taxonomy

REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "taxonomy"
    / "technology_registry_v1.json"
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def normalise(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class TechnologyRegistry:
    version: str
    entries: tuple[dict[str, Any], ...]

    def by_id(self) -> dict[str, dict[str, Any]]:
        return {
            str(entry["technology_id"]): entry
            for entry in self.entries
        }


def _validate_registry(data: dict[str, Any]) -> None:
    version = _clean(data.get("registry_version"))
    if not version:
        raise ValueError("Technology registry requires registry_version.")

    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Technology registry entries must be a list.")

    taxonomy_ids = set(get_default_taxonomy().by_id())
    seen_ids: set[str] = set()
    seen_aliases: dict[str, str] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each technology registry entry must be an object.")

        technology_id = _clean(entry.get("technology_id"))
        if not technology_id:
            raise ValueError("Technology registry entry missing technology_id.")
        if technology_id in seen_ids:
            raise ValueError(f"Duplicate technology_id: {technology_id}")
        if not re.fullmatch(r"[a-z0-9_.-]+", technology_id):
            raise ValueError(f"Invalid technology_id: {technology_id}")
        seen_ids.add(technology_id)

        aliases = entry.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"{technology_id}: aliases must be a non-empty list.")

        for alias in aliases:
            key = normalise(alias)
            if not key:
                raise ValueError(f"{technology_id}: blank alias.")
            owner = seen_aliases.get(key)
            if owner and owner != technology_id:
                raise ValueError(
                    f"Alias {alias!r} is shared by {owner} and {technology_id}."
                )
            seen_aliases[key] = technology_id

        relationships = entry.get("capability_relationships", [])
        if not isinstance(relationships, list):
            raise ValueError(
                f"{technology_id}: capability_relationships must be a list."
            )

        approved_mappings = 0
        for relationship in relationships:
            if not isinstance(relationship, dict):
                raise ValueError(
                    f"{technology_id}: relationship must be an object."
                )
            capability_id = _clean(relationship.get("capability_id"))
            if capability_id not in taxonomy_ids:
                raise ValueError(
                    f"{technology_id}: unknown capability_id {capability_id!r}."
                )
            if (
                relationship.get("relationship_type") == "maps_to_capability"
                and relationship.get("status") == "approved"
            ):
                approved_mappings += 1

        if approved_mappings > 1:
            raise ValueError(
                f"{technology_id}: at most one approved maps_to_capability "
                "relationship is allowed in v1."
            )


def load_registry(
    path: str | Path = REGISTRY_PATH,
) -> TechnologyRegistry:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Technology registry root must be an object.")
    _validate_registry(data)
    return TechnologyRegistry(
        version=_clean(data.get("registry_version")),
        entries=tuple(data.get("entries", [])),
    )


@lru_cache(maxsize=1)
def _registry_at_file_signature(path: str, signature: tuple[int, int, int]) -> TechnologyRegistry:
    return load_registry(path)


def get_default_registry() -> TechnologyRegistry:
    # Atomic publication replaces the file. Other app processes also observe
    # the new knowledge before checking versions or resolving requirements.
    path = Path(REGISTRY_PATH).resolve()
    stat = path.stat()
    return _registry_at_file_signature(str(path), (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))


get_default_registry.cache_clear = _registry_at_file_signature.cache_clear


def _alias_index(
    registry: TechnologyRegistry,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in registry.entries:
        for alias in entry.get("aliases", []) or []:
            index[normalise(alias)] = entry
    return index


_WRAPPERS = (
    r"^(?:hands[- ]on\s+)?experience\s+(?:with|in|using)\s+",
    r"^(?:strong\s+)?proficiency\s+(?:with|in)\s+",
    r"^(?:working\s+)?knowledge\s+(?:of|with|in)\s+",
    r"^familiarity\s+(?:with|in)\s+",
)


def _candidate_terms(text: str) -> list[str]:
    raw = _clean(text)
    values: list[str] = [raw]

    stripped = raw
    for pattern in _WRAPPERS:
        new_value = re.sub(pattern, "", stripped, flags=re.I).strip()
        if new_value != stripped:
            values.append(new_value)
            stripped = new_value
            break

    such_as = re.search(r"\bsuch\s+as\s+(.+)$", raw, flags=re.I)
    if such_as:
        values.append(such_as.group(1).strip())

    # Do not split comma/and lists here. Atomicisation should already have
    # produced one candidate per requirement, and guessing list boundaries at
    # this layer could create false positives.
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalise(value)
        if key and key not in seen:
            unique.append(value)
            seen.add(key)
    return unique


def _approved_mapping(
    entry: dict[str, Any],
) -> dict[str, Any] | None:
    rows = [
        relationship
        for relationship in entry.get("capability_relationships", []) or []
        if isinstance(relationship, dict)
        and relationship.get("relationship_type") == "maps_to_capability"
        and relationship.get("status") == "approved"
    ]
    return rows[0] if len(rows) == 1 else None


def resolve_requirement_text(
    text: str,
    *,
    registry: TechnologyRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or get_default_registry()
    index = _alias_index(registry)

    matched_entry: dict[str, Any] | None = None
    matched_alias: str | None = None
    matched_term: str | None = None

    for candidate_term in _candidate_terms(text):
        key = normalise(candidate_term)
        entry = index.get(key)
        if entry is None:
            continue
        if matched_entry is not None and (
            matched_entry.get("technology_id") != entry.get("technology_id")
        ):
            return {
                "status": "ambiguous",
                "registry_version": registry.version,
                "technology_id": None,
                "technology_label": None,
                "matched_alias": None,
                "matched_term": None,
                "capability_id": None,
                "relationship_type": None,
                "reason": "multiple_registry_entries_matched",
            }
        matched_entry = entry
        matched_alias = candidate_term
        matched_term = candidate_term

    if matched_entry is None:
        return {
            "status": "unresolved",
            "registry_version": registry.version,
            "technology_id": None,
            "technology_label": None,
            "matched_alias": None,
            "matched_term": None,
            "capability_id": None,
            "relationship_type": None,
            "reason": "no_exact_registry_alias_match",
        }

    mapping = _approved_mapping(matched_entry)
    if mapping is None:
        return {
            "status": "recognized_unmapped",
            "registry_version": registry.version,
            "technology_id": _clean(matched_entry.get("technology_id")),
            "technology_label": _clean(matched_entry.get("label")),
            "matched_alias": matched_alias,
            "matched_term": matched_term,
            "capability_id": None,
            "relationship_type": None,
            "reason": "registry_entry_has_no_approved_capability_mapping",
        }

    return {
        "status": "resolved",
        "registry_version": registry.version,
        "technology_id": _clean(matched_entry.get("technology_id")),
        "technology_label": _clean(matched_entry.get("label")),
        "matched_alias": matched_alias,
        "matched_term": matched_term,
        "capability_id": _clean(mapping.get("capability_id")),
        "relationship_type": _clean(mapping.get("relationship_type")),
        "reason": "approved_exact_alias_registry_mapping",
    }


def resolve_candidate(
    candidate: dict[str, Any],
    *,
    registry: TechnologyRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or get_default_registry()
    observations = [
        row
        for row in candidate.get("observations", []) or []
        if isinstance(row, dict)
    ]

    resolutions = [
        resolve_requirement_text(
            str(row.get("requirement_text") or ""),
            registry=registry,
        )
        for row in observations
    ]

    meaningful = [
        row
        for row in resolutions
        if row.get("status") != "unresolved"
    ]
    if not meaningful:
        result = resolve_requirement_text(
            str(
                (candidate.get("observed_terms") or [""])[0]
                if candidate.get("observed_terms")
                else candidate.get("normalised_observed_text") or ""
            ),
            registry=registry,
        )
        result["observation_resolutions"] = resolutions
        return result

    identities = {
        (
            row.get("status"),
            row.get("technology_id"),
            row.get("capability_id"),
        )
        for row in meaningful
    }
    if len(identities) > 1:
        return {
            "status": "ambiguous",
            "registry_version": registry.version,
            "technology_id": None,
            "technology_label": None,
            "matched_alias": None,
            "matched_term": None,
            "capability_id": None,
            "relationship_type": None,
            "reason": "candidate_observations_have_conflicting_registry_matches",
            "observation_resolutions": resolutions,
        }

    result = dict(meaningful[0])
    result["observation_resolutions"] = resolutions
    return result


def registry_rows(
    registry: TechnologyRegistry | None = None,
) -> list[dict[str, Any]]:
    registry = registry or get_default_registry()
    rows: list[dict[str, Any]] = []
    for entry in registry.entries:
        mapping = _approved_mapping(entry)
        rows.append(
            {
                "technology_id": _clean(entry.get("technology_id")),
                "label": _clean(entry.get("label")),
                "entry_kind": _clean(entry.get("entry_kind")),
                "aliases": list(entry.get("aliases", []) or []),
                "mapping_status": (
                    "mapped" if mapping is not None else "recognized_unmapped"
                ),
                "capability_id": (
                    _clean(mapping.get("capability_id"))
                    if mapping is not None
                    else None
                ),
                "relationship_type": (
                    _clean(mapping.get("relationship_type"))
                    if mapping is not None
                    else None
                ),
                "notes": _clean(entry.get("notes")),
            }
        )
    return rows
