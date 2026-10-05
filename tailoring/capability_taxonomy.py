"""Versioned capability-taxonomy loader and deterministic matcher for Phase 6D."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "taxonomy" / "capability_taxonomy_v1.json"
ALLOWED_LABELS = {"direct", "transferable", "weak", "none"}
PRODUCT_CONTEXT_GUARD_VERSION = "native-product-context-guard-v1"


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



# v1.4 evidence policies are local predicates, not research relationships.
V14_EVIDENCE_POLICIES = {
    "c_cpp_v1", "android_v1", "graphics_api_v1", "memory_cache_v1",
    "data_oriented_v1", "algorithms_v1", "client_integration_v1", "realtime_v1",
}
_V14_ACTIONS = ["built", "implemented", "developed", "shipped", "published", "programmed", "created", "integrated", "deployed"]


def _v14_label(policy: str, requirement: str, evidence: str) -> tuple[str, str]:
    """Conservative caps. No weights, evidence joining, or preliminary upgrades.

    Existing v1.3 capabilities never enter this function. Input evidence may be
    one cited row; do not source facts from the profile, title, or other rows.
    """
    r, e = requirement, evidence
    has = lambda text, terms: _contains_any(text, terms)
    action = has(e, _V14_ACTIONS)
    if has(e, ["no experience", "not implemented", "never used", "not used", "not familiar", "without experience"]):
        return "none", "explicit_negative_evidence"
    if has(e, ["tutorial", "tutorials", "course", "courses", "installed", "installation"]) and not action:
        return "none", "tool_or_learning_only"

    if policy == "c_cpp_v1":
        # Technical token boundaries deliberately do not treat C# or C++ as C.
        cpp = lambda t: bool(re.search(r"(?<![a-z0-9+#])c\+\+(?:11|14|17|20|23|26)?(?![a-z0-9+#])", t.lower()))
        c = lambda t: bool(re.search(r"(?<![a-z0-9+#])c(?:11|17|23)?(?![a-z0-9+#])", t.lower()))
        rc, rp = c(r), cpp(r)
        ec, ep = c(e), cpp(e)
        alternative = bool(re.search(r"c\s*/\s*c\+\+|c\s+(?:or|and/or)\s+c\+\+", r, re.I))
        supported = ((ec or ep) if alternative else ((not rc or ec) and (not rp or ep))) and (rc or rp)
        if not supported:
            return "none", "requested_language_not_evidenced"
        modern = has(r, ["modern", "c++11", "c++14", "c++17", "c++20", "c++23", "c11", "c17", "c23"])
        modern_e = ((ep and has(e, ["modern c++", "c++11", "c++14", "c++17", "c++20", "c++23", "c++26"])) or
                    (ec and has(e, ["modern c", "c11", "c17", "c23"])))
        if modern and not modern_e:
            return "transferable", "language_present_modern_proficiency_not_established"

        # A bare language token can prove a narrow knowledge/familiarity claim,
        # but it must not prove stronger implementation/experience/proficiency
        # claims. Keep this deliberately narrower than generic "skills".
        knowledge_only = bool(
            re.search(r"\b(?:knowledge\s+of|familiarity\s+with)\b", r, re.I)
        ) and not has(
            r,
            [
                "strong knowledge",
                "solid knowledge",
                "proficiency",
                "experience",
                "programming experience",
                "production",
                "develop",
                "build",
                "implement",
            ],
        )
        if knowledge_only:
            return "direct", "explicit_language_knowledge"

        # Structured project headings can be concrete implementation evidence
        # even when they contain no action verb, e.g. "C++ Custom Engine".
        # Require a conservative software-artifact noun so a bare "C++" skill
        # still receives only transferable credit for experience claims.
        artifact = has(
            e,
            [
                "engine",
                "application",
                "app",
                "system",
                "service",
                "library",
                "tool",
                "manager",
                "pipeline",
                "interface",
                "component",
                "module",
            ],
        )
        # Concrete C/C++ implementation proves language implementation, but
        # it must not silently prove extra qualifiers carried by the JD. In
        # particular, "high-performance" and "native" describe properties of
        # the requested work, not merely the implementation language.
        requires_performance = has(
            r,
            [
                "high-performance",
                "high performance",
                "performance-critical",
                "performance critical",
            ],
        )
        evidence_performance = has(
            e,
            [
                "high-performance",
                "high performance",
                "performance-critical",
                "performance critical",
                "optimized",
                "optimised",
                "profiled",
                "tuned",
                "latency",
                "throughput",
            ],
        )
        requires_native = bool(re.search(r"\bnative\b", r, re.I))
        evidence_native = bool(re.search(r"\bnative\b", e, re.I))
        if (
            (requires_performance and not evidence_performance)
            or (requires_native and not evidence_native)
        ):
            return (
                "transferable",
                "language_implementation_without_required_context",
            )

        if action or modern_e or artifact:
            return "direct", "explicit_requested_language_implementation"
        return "transferable", "language_skill_only"

    if policy == "android_v1":
        # Android Studio is a tool, not evidence of the target platform itself.
        platform_text = re.sub(r"\bandroid\s+studio\b", "", e, flags=re.I)
        platform = has(platform_text, ["android"])
        if not platform or (has(e, ["android studio"]) and not action):
            return "none", "android_implementation_not_evidenced"
        if has(r, ["kotlin"]) and not has(e, ["kotlin"]):
            return "none", "requested_kotlin_missing"
        implementation = re.search(
            r"\b(?:built|implemented|developed|shipped|published|programmed|created|implementation|development)\b"
            r"[^.;\n]{0,80}\bandroid\s+(?:[a-z-]+\s+){0,3}(?:applications?|apps?|features?|software|frontend)\b",
            platform_text, re.I,
        ) or re.search(
            r"\b(?:built|implemented|developed|shipped|published|programmed|created)\b"
            r"[^.;\n]{0,60}\b(?:applications?|apps?|features?|software|frontend)\b[^.;\n]{0,40}\b(?:for|on)\s+android\b",
            platform_text, re.I,
        )
        if implementation:
            return "direct", "android_application_implementation"
        if has(e, ["android sdk", "jetpack compose"]) and has(e, ["kotlin", "java"]):
            return "transferable", "android_platform_without_delivery_evidence"
        return "none", "android_implementation_not_evidenced"

    if policy == "graphics_api_v1":
        requested = [api for api in ("opengl", "vulkan") if has(r, [api])]
        present = [api for api in requested if has(e, [api])]
        alternative = bool(re.search(r"\bopengl\s*(?:and/or|or|/)\s*vulkan\b|\bvulkan\s*(?:and/or|or|/)\s*opengl\b", r, re.I))
        if requested and (len(present) == len(requested) or (alternative and present)):
            return "direct", "requested_graphics_api_explicit"
        return "none", "requested_graphics_api_missing"

    if policy == "memory_cache_v1":
        memory = ["memory allocation", "memory management", "memory allocator", "memory performance"]
        cache = ["cache performance", "cache locality", "cache optimization", "cache optimisation"]
        groups = [g for g in (memory, cache) if has(r, g)]
        if not groups or not all(has(e, g) for g in groups):
            return "none", "requested_memory_cache_concept_missing"
        optimization = ["optimize", "optimise", "optimization", "optimisation", "profile", "profiling", "tune"]
        optimized = has(e, ["optimized", "optimised", "profiled", "tuned", "reduced allocations", "improved cache locality"])
        if has(r, optimization):
            return ("direct", "explicit_memory_cache_optimization") if optimized else ("transferable", "concept_without_requested_optimization")
        if has(r, ["implement", "build", "develop"]):
            return ("direct", "memory_cache_implementation") if action else ("transferable", "concept_without_requested_implementation")
        return "direct", "explicit_memory_cache_knowledge"

    if policy == "data_oriented_v1":
        if not has(e, ["data oriented programming", "data-oriented programming", "data oriented design", "data-oriented design"]):
            return "none", "data_oriented_semantics_missing"
        if has(r, ["implement", "build", "develop"]) and not action:
            return "transferable", "data_oriented_knowledge_without_implementation"
        return "direct", "explicit_data_oriented_semantics"

    if policy == "algorithms_v1":
        named = ["a* pathfinding", "dijkstra", "breadth first search", "depth first search", "binary search", "dynamic programming"]
        complexity = ["algorithmic complexity", "runtime analysis", "running time of algorithms", "big o", "time complexity"]
        broad = has(e, ["data structures"]) and has(e, ["algorithms"])
        concrete = action and has(e, named)
        if has(r, complexity):
            return ("direct", "explicit_complexity_analysis") if has(e, complexity) else (("transferable", "algorithm_without_complexity_analysis") if concrete or broad else ("none", "complexity_evidence_missing"))
        if has(r, ["data structures"]):
            if (not has(r, ["algorithms"]) and has(e, ["data structures"])) or broad:
                return "direct", "explicit_requested_dsa_foundation"
            return ("transferable", "concrete_algorithm_not_broad_dsa") if concrete else ("none", "dsa_evidence_missing")
        requested_named = [n for n in named if has(r, [n])]
        if requested_named and all(has(e, [n]) for n in requested_named) and action:
            return "direct", "requested_algorithm_implemented"
        if broad:
            return "direct", "explicit_algorithm_foundation"
        return ("transferable", "concrete_algorithm_limited_breadth") if concrete else ("none", "algorithm_evidence_missing")

    if policy == "client_integration_v1":
        technical = has(e, ["software", "system", "systems", "api", "apis", "service", "services", "software stack"])
        integrated = has(e, ["integrated", "integrating", "implemented integration", "built integration"])
        if not technical or not integrated:
            return "none", "technical_integration_behavior_missing"
        if has(e, ["client", "clients", "customer", "customers"]):
            return "direct", "client_software_integration_behavior"
        return "transferable", "software_integration_without_client_context"

    if policy == "realtime_v1":
        transports = ["udp", "mqtt", "websocket", "websockets", "kafka", "grpc"]
        required_transports = [t for t in transports if has(r, [t])]
        if required_transports and not all(has(e, [t]) for t in required_transports):
            return "none", "requested_transport_missing"
        if has(r, ["streaming"]) and not has(e, ["streaming"]):
            return "none", "requested_streaming_behavior_missing"
        if has(r, ["telemetry"]) and not has(e, ["telemetry"]):
            return "none", "requested_telemetry_behavior_missing"
        behavior = has(e, ["real-time", "real time", "event-driven", "streaming", "telemetry", "messaging"])
        transport = has(e, transports)
        if action and behavior and (transport or has(e, ["message delivery", "streaming pipeline", "streaming system"])):
            return "direct", "implemented_messaging_streaming_behavior"
        if transport:
            return "transferable", "transport_without_requested_delivery_evidence"
        return "none", "messaging_streaming_evidence_missing"
    raise ValueError("Unknown v1.4 evidence policy")


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

    if "allow_stronger_single_row_reselection" in item and not isinstance(
        item.get("allow_stronger_single_row_reselection"), bool
    ):
        raise ValueError(
            f"{capability_id}: allow_stronger_single_row_reselection "
            "must be a boolean"
        )

    requirement = item.get("requirement")
    if not isinstance(requirement, dict):
        raise ValueError(f"{capability_id}: requirement must be an object")
    if not isinstance(requirement.get("any_terms", []), list):
        raise ValueError(f"{capability_id}: requirement.any_terms must be a list")
    if not isinstance(requirement.get("all_terms", []), list):
        raise ValueError(f"{capability_id}: requirement.all_terms must be a list")
    variants = requirement.get("contextual_phrase_variants", [])
    if not isinstance(variants,list) or any(not isinstance(v,dict)
        or not isinstance(v.get("phrase"),str) or len(normalise(v["phrase"]).split()) < 2
        or v.get("product_context_guard") != "exclude_recognized_multiword_technology_spans" for v in variants):
        raise ValueError(f"{capability_id}: invalid guarded contextual phrase variant")
    if len({normalise(v["phrase"]) for v in variants}) != len(variants):
        raise ValueError(f"{capability_id}: duplicate contextual phrase variants")
    for variant in variants:
        names = variant.get("excluded_product_names")
        if names is not None and (not isinstance(names,list) or any(not isinstance(n,str) or len(normalise(n).split()) < 2 for n in names)):
            raise ValueError(f"{capability_id}: invalid frozen product-context names")
        if names is not None and variant.get("guard_contract_version") != PRODUCT_CONTEXT_GUARD_VERSION:
            raise ValueError(f"{capability_id}: unsupported product-context guard contract")

    if "evidence_policy" in item and item["evidence_policy"] not in V14_EVIDENCE_POLICIES:
        raise ValueError(f"{capability_id}: unknown evidence policy")
    groups = requirement.get("all_groups", [])
    if not isinstance(groups, list) or any(
        not isinstance(g, list) or not g or any(not isinstance(t, str) or not t.strip() for t in g)
        for g in groups
    ):
        raise ValueError(f"{capability_id}: invalid requirement groups")

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
def _taxonomy_at_signature(path, signature) -> CapabilityTaxonomy:
    return load_taxonomy(path)


def _production_taxonomy() -> CapabilityTaxonomy:
    # Publication in another session/process must advance currentness without
    # an arbitrary UI cache purge. Mirror the native registry file identity.
    path = Path(TAXONOMY_PATH).resolve()
    stat = path.stat()
    return _taxonomy_at_signature(str(path), (stat.st_mtime_ns, stat.st_size, stat.st_ino))


# Offline review scopes are context-local: never replace the production cache or
# leak temporary knowledge to another Streamlit session/thread.
_review_taxonomy = ContextVar("temporary_review_taxonomy", default=None)


def get_default_taxonomy() -> CapabilityTaxonomy:
    return _review_taxonomy.get() or _production_taxonomy()


get_default_taxonomy.cache_clear = _taxonomy_at_signature.cache_clear
get_default_taxonomy.cache_info = _taxonomy_at_signature.cache_info


@contextmanager
def temporary_taxonomy_scope(taxonomy: CapabilityTaxonomy):
    """Explicit offline test/review only; no file, cache or scoring mutation."""
    token = _review_taxonomy.set(taxonomy)
    try:
        yield taxonomy
    finally:
        _review_taxonomy.reset(token)


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
    """Return the production taxonomy record selected for a requirement."""
    return classify_requirement_diagnostics(requirement, taxonomy)["capability_record"]


def classify_requirement_diagnostics(
    requirement: dict[str, Any],
    taxonomy: CapabilityTaxonomy | None = None,
) -> dict[str, Any]:
    """Run the production matcher once and expose its deterministic decisions.

    The returned ``capability_record`` is for internal callers.  The other
    fields are safe, read-only diagnostics derived while applying the exact
    same rules used by :func:`classify_requirement_record`.
    """
    taxonomy = taxonomy or get_default_taxonomy()
    text = " ".join(
        [
            _clean(requirement.get("text")),
            _clean(requirement.get("atomic_focus")),
        ]
    )
    original = _clean(requirement.get("text")) or _clean(
        requirement.get("atomic_focus")
    )
    rejected_rules: list[dict[str, Any]] = []

    for item in taxonomy.capabilities:
        matcher = item.get("requirement") or {}
        any_terms = matcher.get("any_terms", []) or []
        all_terms = matcher.get("all_terms", []) or []
        if all_terms and not all(_contains(text, term) for term in all_terms):
            continue
        variants = matcher.get("contextual_phrase_variants", [])
        variant_match = False
        matched_variant: dict[str, Any] | None = None
        if variants:
            # Only governed temporary variants opt in. Native production terms
            # and all evidence/scoring predicates retain their existing contract.
            from taxonomy_discovery.candidate_refinement import capability_context
            # A shortened atomic focus cannot strip the product's identity and
            # turn a fragment of its name into independent capability evidence.
            def variant_result(v):
                names = v.get("excluded_product_names")
                context = capability_context(
                    original,
                    include_research_aliases=names is None,
                    extra_product_names=names or (),
                    product_span_replacement=" tqd3_product_span ",
                )
                excluded = [
                    normalise(name)
                    for name in names or ()
                    if _contains(original, name)
                ]
                raw_match = _contains(original, v.get("phrase", ""))
                guarded_match = bool(
                    v.get("product_context_guard")
                    == "exclude_recognized_multiword_technology_spans"
                    and _contains(context, v.get("phrase", ""))
                )
                detail = {
                    "capability_id": str(item.get("capability_id") or ""),
                    "phrase": str(v.get("phrase") or ""),
                    "product_context_guard": v.get("product_context_guard"),
                    "guard_contract_version": v.get("guard_contract_version"),
                    "raw_phrase_matched": raw_match,
                    "guarded_phrase_matched": guarded_match,
                    "excluded_product_spans": excluded,
                }
                if raw_match and not guarded_match:
                    rejected_rules.append(
                        {
                            **detail,
                            "reason": "product_context_guard_excluded_phrase",
                        }
                    )
                return guarded_match, detail

            for variant in variants:
                present, detail = variant_result(variant)
                if present and matched_variant is None:
                    matched_variant = detail
            variant_match = matched_variant is not None
        matched_any_terms = [term for term in any_terms if _contains(text, term)]
        if (any_terms or variants) and not (matched_any_terms or variant_match):
            continue
        if not _matches_groups(text, matcher.get("all_groups", [])):
            continue
        if item.get("evidence_policy") == "c_cpp_v1" and not re.search(r"(?<![a-z0-9+#])c(?:\+\+(?:11|14|17|20|23|26)?|11|17|23)?(?![a-z0-9+#])", text.lower()):
            continue
        if not any_terms and not all_terms and not variants:
            continue
        matched_phrase = (
            str(matched_any_terms[0])
            if matched_any_terms
            else str((matched_variant or {}).get("phrase") or "")
        )
        return {
            "normalized_requirement_text": normalise(original),
            "taxonomy_version": taxonomy.version,
            "capability_record": item,
            "capability_id": str(item.get("capability_id") or ""),
            "capability_label": str(item.get("label") or ""),
            "matched_phrase": matched_phrase,
            "matched_taxonomy_rule_type": (
                "native_any_term" if matched_any_terms else "contextual_phrase_variant"
            ),
            "contextual_phrase_rule": (
                str((matched_variant or {}).get("phrase") or "") or None
            ),
            "product_context_guard": (matched_variant or {}).get(
                "product_context_guard"
            ),
            "guard_contract_version": (matched_variant or {}).get(
                "guard_contract_version"
            ),
            "excluded_product_spans": list(
                (matched_variant or {}).get("excluded_product_spans") or []
            ),
            "rejected_candidate_rules": rejected_rules,
            "reason": "taxonomy_requirement_rule_matched",
        }
    return {
        "normalized_requirement_text": normalise(original),
        "taxonomy_version": taxonomy.version,
        "capability_record": None,
        "capability_id": None,
        "capability_label": None,
        "matched_phrase": None,
        "matched_taxonomy_rule_type": None,
        "contextual_phrase_rule": None,
        "product_context_guard": None,
        "guard_contract_version": None,
        "excluded_product_spans": sorted(
            {
                span
                for row in rejected_rules
                for span in row.get("excluded_product_spans", [])
            }
        ),
        "rejected_candidate_rules": rejected_rules,
        "reason": "no_taxonomy_requirement_rule_matched",
    }


def classify_requirement(
    requirement: dict[str, Any],
    taxonomy: CapabilityTaxonomy | None = None,
) -> str | None:
    record = classify_requirement_record(requirement, taxonomy)
    return str(record["capability_id"]) if record else None


def _evaluate_capability_record(
    *,
    capability: dict[str, Any],
    requirement: dict[str, Any],
    evidence_text: str,
    taxonomy_version: str,
) -> dict[str, Any]:
    """Evaluate evidence against one already-resolved capability record."""
    if capability.get("evidence_policy"):
        focus = _clean(requirement.get("atomic_focus") or requirement.get("text"))
        decisions = [
            _v14_label(capability["evidence_policy"], focus, row)
            for row in evidence_text.splitlines()
            if row.strip()
        ]
        order = {"none": 0, "weak": 1, "transferable": 2, "direct": 3}
        label, reason = (
            max(decisions, key=lambda d: order[d[0]])
            if decisions
            else ("none", "no_evidence")
        )
        return {
            "capability_id": capability["capability_id"],
            "label": label,
            "reason": reason,
            "concepts": [capability["evidence_policy"]],
            "taxonomy_version": taxonomy_version,
            "does_not_prove": capability.get("does_not_prove", []),
        }

    if capability.get("explicit_only"):
        subjective_terms = capability.get("evidence_concepts", {}).get("subjective", [])
        if not _contains_any(evidence_text, subjective_terms):
            return {
                "capability_id": capability["capability_id"],
                "label": "none",
                "reason": "explicit_evidence_required",
                "concepts": [],
                "taxonomy_version": taxonomy_version,
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
            "taxonomy_version": taxonomy_version,
            "does_not_prove": capability.get("does_not_prove", []),
        }

    return {
        "capability_id": capability["capability_id"],
        "label": "none",
        "reason": "recognised_but_unsupported",
        "concepts": [],
        "taxonomy_version": taxonomy_version,
        "does_not_prove": capability.get("does_not_prove", []),
    }


def evaluate_capability_evidence(
    capability_id: str,
    requirement: dict[str, Any],
    evidence_text: str,
    taxonomy: CapabilityTaxonomy | None = None,
) -> dict[str, Any]:
    """Evaluate evidence for an already-approved deterministic capability ID."""
    taxonomy = taxonomy or get_default_taxonomy()
    capability = taxonomy.by_id().get(_clean(capability_id))
    if capability is None:
        return {
            "capability_id": None,
            "label": None,
            "reason": "unknown_capability_id",
            "concepts": [],
            "taxonomy_version": taxonomy.version,
            "does_not_prove": [],
        }
    return _evaluate_capability_record(
        capability=capability,
        requirement=requirement,
        evidence_text=evidence_text,
        taxonomy_version=taxonomy.version,
    )


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
    return _evaluate_capability_record(
        capability=capability,
        requirement=requirement,
        evidence_text=evidence_text,
        taxonomy_version=taxonomy.version,
    )

def taxonomy_documents(
    taxonomy: CapabilityTaxonomy | None = None,
) -> list[dict[str, Any]]:
    taxonomy = taxonomy or get_default_taxonomy()
    documents = []
    for item in taxonomy.capabilities:
        requirement_terms = item.get("requirement", {}).get("any_terms", [])
        evidence_terms: list[str] = []
        if item.get("evidence_policy"):
            for terms in (item.get("evidence_concepts") or {}).values():
                evidence_terms.extend(terms)
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
