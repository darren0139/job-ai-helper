"""Deterministic source-authority assessment for discovery and focused verification."""

from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SOURCE_AUTHORITY_VERSION = "tqd3-source-authority-v1.2.0"
PRIMARY_OFFICIAL = "primary_official"
FIRST_PARTY_OTHER = "first_party_other_technology"
SECONDARY = "secondary"
UNCLASSIFIED = "unclassified"

_WS_RE = re.compile(r"\s+")


def _clean(value: Any) -> str:
    return _WS_RE.sub(" ", str(value or "")).strip()


def _key(value: Any) -> str:
    return unicodedata.normalize("NFKC", _clean(value)).casefold()


def default_source_authority_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "taxonomy"
        / "source_authority_registry_v1.json"
    )


def load_source_authority_registry(
    path: str | Path | None = None,
) -> dict[str, Any]:
    registry_path = (
        Path(path).expanduser().resolve()
        if path is not None
        else default_source_authority_registry_path()
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Source-authority registry must be an object")
    return payload


def _hostname(url: Any) -> str:
    value = _clean(url)
    if not value:
        return ""
    try:
        host = (urlsplit(value).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_matches(host: str, domain: str) -> bool:
    host = str(host or "").lower().rstrip(".")
    domain = str(domain or "").lower().strip().rstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def _normalise_scope(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        domain = _clean(raw).lower()
        prefixes: list[str] = []
    elif isinstance(raw, dict):
        domain = _clean(raw.get("domain")).lower()
        prefixes = [
            "/" + _clean(value).lstrip("/").lower()
            for value in raw.get("path_prefixes", []) or []
            if _clean(value)
        ]
    else:
        return None
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return None
    return {"domain": domain, "path_prefixes": sorted(set(prefixes))}


def _rule_scopes(rule: dict[str, Any]) -> list[dict[str, Any]]:
    raw = list(rule.get("official_domains", []) or []) + list(rule.get("official_sources", []) or [])
    scopes = [_normalise_scope(value) for value in raw]
    unique = {(row["domain"], tuple(row["path_prefixes"])): row for row in scopes if row}
    return [unique[key] for key in sorted(unique)]


def _scope_matches(host: str, path: str, scope: dict[str, Any]) -> bool:
    if not _domain_matches(host, scope.get("domain", "")):
        return False
    prefixes = scope.get("path_prefixes") or []
    path = "/" + str(path or "").lstrip("/").lower()
    return not prefixes or any(path.startswith(prefix.rstrip("/") + "/") or path == prefix.rstrip("/")
                               for prefix in prefixes)


def _candidate_official_sources(candidate: dict[str, Any], registry: dict[str, Any]) -> list[dict[str, Any]]:
    canonical = _key(candidate.get("canonical_name"))
    maintainers = {
        _key(value)
        for value in candidate.get("maintainers_vendors_or_standards_bodies", [])
        if _clean(value)
    }
    scopes: list[dict[str, Any]] = []
    for rule in registry.get("technology_domains", []) or []:
        if not isinstance(rule, dict):
            continue
        aliases = {_key(value) for value in rule.get("technology_aliases", []) or [] if _clean(value)}
        if canonical and canonical in aliases:
            scopes.extend(_rule_scopes(rule))
    for rule in registry.get("organization_domains", []) or []:
        if not isinstance(rule, dict):
            continue
        aliases = {_key(value) for value in rule.get("organization_aliases", []) or [] if _clean(value)}
        if maintainers.intersection(aliases):
            scopes.extend(_rule_scopes(rule))
    unique = {(row["domain"], tuple(row["path_prefixes"])): row for row in scopes}
    return [unique[key] for key in sorted(unique)]


def _candidate_official_domains(
    candidate: dict[str, Any],
    registry: dict[str, Any],
) -> set[str]:
    return {row["domain"] for row in _candidate_official_sources(candidate, registry)}


def _all_known_official_domains(
    registry: dict[str, Any],
) -> set[str]:
    domains: set[str] = set()
    for collection in ("technology_domains", "organization_domains"):
        for rule in registry.get(collection, []) or []:
            if not isinstance(rule, dict):
                continue
            domains.update(row["domain"] for row in _rule_scopes(rule))
    return domains


def candidate_official_domains(candidate, *, registry_path=None) -> list[str]:
    """Versioned routing hints only; never infer authority from provider claims."""
    return sorted(_candidate_official_domains(candidate, load_source_authority_registry(registry_path)))


def candidate_official_source_scopes(candidate, *, registry_path=None) -> list[dict[str, Any]]:
    """Return governed candidate-specific domain/path scopes for audits and diagnostics."""
    return deepcopy(_candidate_official_sources(candidate, load_source_authority_registry(registry_path)))


def _secondary_kind(
    host: str,
    registry: dict[str, Any],
) -> str | None:
    for rule in registry.get("secondary_domains", []) or []:
        if not isinstance(rule, dict):
            continue
        domain = _clean(rule.get("domain")).lower()
        if _domain_matches(host, domain):
            return _clean(rule.get("kind")) or "secondary"
    return None


def classify_candidate_source_url(
    candidate: dict[str, Any],
    url: str,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    registry = load_source_authority_registry(registry_path)
    host = _hostname(url)
    parsed = urlsplit(_clean(url))
    path = parsed.path or "/"

    candidate_scopes = _candidate_official_sources(candidate, registry)
    all_official_domains = _all_known_official_domains(registry)

    matched_candidate_scope = next(
        (
            scope
            for scope in candidate_scopes
            if _scope_matches(host, path, scope)
        ),
        None,
    )

    if matched_candidate_scope:
        authority = PRIMARY_OFFICIAL
        source_kind = "candidate_or_maintainer_primary"
        reason = (
            "source hostname matches a versioned official-domain rule "
            "for the exact candidate technology or declared maintainer"
        )
        matched_rule_domain = matched_candidate_scope["domain"]
    else:
        matched_other_domain = next(
            (
                domain
                for domain in sorted(all_official_domains)
                if _domain_matches(host, domain)
            ),
            "",
        )
        secondary_kind = _secondary_kind(host, registry)

        if matched_other_domain:
            authority = FIRST_PARTY_OTHER
            source_kind = "recognized_first_party_domain"
            reason = (
                "source hostname is recognized first-party, but not "
                "associated with this candidate"
            )
            matched_rule_domain = matched_other_domain
        elif secondary_kind:
            authority = SECONDARY
            source_kind = secondary_kind
            reason = "source hostname matches a versioned secondary-source rule"
            matched_rule_domain = host
        else:
            authority = UNCLASSIFIED
            source_kind = "unclassified"
            reason = (
                "no candidate-specific official-domain or secondary-source "
                "rule matched"
            )
            matched_rule_domain = ""

    return {
        "url": _clean(url),
        "hostname": host,
        "authority": authority,
        "source_kind": source_kind,
        "matched_rule_domain": matched_rule_domain,
        "reason": reason,
        "authority_version": SOURCE_AUTHORITY_VERSION,
    }


def assess_candidate_source_authority(
    candidate: dict[str, Any],
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    assessments = [
        classify_candidate_source_url(
            candidate,
            url,
            registry_path=registry_path,
        )
        for url in candidate.get("supporting_source_urls", [])
        if _clean(url)
    ]

    counts = {
        PRIMARY_OFFICIAL: 0,
        FIRST_PARTY_OTHER: 0,
        SECONDARY: 0,
        UNCLASSIFIED: 0,
    }
    kinds: dict[str, int] = {}
    for row in assessments:
        counts[row["authority"]] = counts.get(row["authority"], 0) + 1
        kind = row["source_kind"]
        kinds[kind] = kinds.get(kind, 0) + 1

    registry = load_source_authority_registry(registry_path)
    return {
        "authority_version": SOURCE_AUTHORITY_VERSION,
        "registry_version": _clean(registry.get("version")),
        "has_primary_official": counts[PRIMARY_OFFICIAL] > 0,
        "counts": counts,
        "source_kind_counts": kinds,
        "assessments": assessments,
        "contract": {
            "provider_authority_claim_trusted": False,
            "candidate_match": (
                "exact_candidate_or_maintainer_alias_plus_domain"
            ),
            "network_calls": 0,
            "model_calls": 0,
        },
    }


def enrich_candidates_with_source_authority(
    candidates: list[dict[str, Any]],
    *,
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    result = deepcopy(candidates)
    for candidate in result:
        candidate["source_authority"] = (
            assess_candidate_source_authority(
                candidate,
                registry_path=registry_path,
            )
        )
    return result
