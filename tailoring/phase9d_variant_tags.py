"""Deterministic Phase 9D Blueprint variant-tag and lane suggestions.

This module is deliberately local-only. It scores persisted Phase 9B source-JD
requirement evidence, allows an explicit user-confirmed tag override, and compares
that specialization with existing Blueprint lane labels. It never calls a model,
embeddings, or Chroma, and it never mutates Blueprint lifecycle state.
"""

from __future__ import annotations

import re
from typing import Any


PHASE9D_VARIANT_TAG_POLICY_VERSION = "phase9d-variant-tags-v3.1-lane-metadata"

AVAILABLE_VARIANT_TAGS = (
    "Backend",
    "AI",
    "Frontend",
    "Data",
    "DevOps",
    "QA",
    "Game Ops",
    "Mobile",
    "Graphics",
)

_IMPORTANCE_WEIGHT = {
    "core": 1.50,
    "required": 1.25,
    "preferred": 0.80,
}
_MATCH_WEIGHT = {
    "direct": 1.00,
    "transferable": 0.70,
}

_TAG_RULES: dict[str, dict[str, Any]] = {
    "Backend": {
        "capability_prefixes": ("backend.", "api.", "services."),
        "phrases": {
            "backend": 5.0,
            "back-end": 5.0,
            "fastapi": 5.0,
            "flask": 4.0,
            "django": 4.0,
            "rest api": 4.0,
            "rest apis": 5.0,
            "restful api": 4.0,
            "restful apis": 5.0,
            "web api": 4.0,
            "web apis": 4.0,
            "api service": 4.0,
            "api services": 4.0,
            "api development": 4.0,
            "server-side": 4.0,
            "server side": 4.0,
            "microservice": 3.0,
            "web service": 3.0,
            "crud": 3.0,
            "postgrest": 3.0,
        },
    },
    "AI": {
        "capability_prefixes": ("ai.", "ml.", "machine_learning."),
        "phrases": {
            "rag": 5.0,
            "retrieval-augmented generation": 5.0,
            "retrieval augmented generation": 5.0,
            "llm": 5.0,
            "large language model": 4.0,
            "vector search": 4.0,
            "embedding": 3.0,
            "embeddings": 3.0,
            "openai": 3.0,
            "chromadb": 4.0,
            "pgvector": 4.0,
            "prompt engineering": 3.0,
            "machine learning": 3.0,
            "artificial intelligence": 3.0,
        },
    },
    "Frontend": {
        "capability_prefixes": ("frontend.", "ui."),
        "phrases": {
            "frontend": 5.0,
            "front-end": 5.0,
            "react": 4.0,
            "typescript": 3.0,
            "javascript": 2.0,
            "user interface": 3.0,
            "ui": 2.0,
            "css": 2.0,
            "html": 2.0,
            "web interface": 3.0,
        },
    },
    "Data": {
        "capability_prefixes": ("database.", "data."),
        "phrases": {
            "postgresql": 4.0,
            "postgres": 4.0,
            "sqlite": 3.0,
            "supabase": 3.0,
            "database": 3.0,
            "sql": 2.0,
            "data model": 3.0,
            "data modelling": 3.0,
            "row-level security": 3.0,
            "row level security": 3.0,
        },
    },
    "DevOps": {
        "capability_prefixes": ("devops.", "cloud.", "ci.", "deployment."),
        "phrases": {
            "docker": 5.0,
            "kubernetes": 5.0,
            "aws": 4.0,
            "azure": 4.0,
            "gcp": 4.0,
            "ci/cd": 5.0,
            "continuous integration": 4.0,
            "github actions": 4.0,
            "cloud": 3.0,
            "container": 3.0,
            "containers": 3.0,
            "deployment": 2.0,
        },
    },
    "QA": {
        "capability_prefixes": ("qa.", "testing.", "quality."),
        "phrases": {
            "quality assurance": 5.0,
            "qa": 5.0,
            "automated testing": 4.0,
            "test automation": 4.0,
            "pytest": 4.0,
            "regression testing": 3.0,
            "regression": 2.0,
            "testing": 2.0,
        },
    },
    "Game Ops": {
        "capability_prefixes": ("game_ops.", "live_ops.", "configuration."),
        "phrases": {
            "game operations": 5.0,
            "game ops": 5.0,
            "live ops": 5.0,
            "liveops": 5.0,
            "configuration": 3.0,
            "content operations": 3.0,
        },
    },
    "Mobile": {
        "capability_prefixes": ("mobile.",),
        "phrases": {
            "android": 4.0,
            "ios": 4.0,
            "react native": 5.0,
            "flutter": 5.0,
            "jetpack compose": 5.0,
            "kotlin": 2.0,
        },
    },
    "Graphics": {
        "capability_prefixes": ("graphics.", "engine."),
        "phrases": {
            "unity": 4.0,
            "unreal": 4.0,
            "opengl": 5.0,
            "shader": 4.0,
            "graphics": 4.0,
            "game engine": 4.0,
            "game-engine": 4.0,
        },
    },
}

_LABEL_ALIASES = {
    "backend": "Backend",
    "api": "Backend",
    "ai": "AI",
    "applied ai": "AI",
    "frontend": "Frontend",
    "front end": "Frontend",
    "data": "Data",
    "database": "Data",
    "cloud": "DevOps",
    "devops": "DevOps",
    "qa": "QA",
    "automation": "QA",
    "game ops": "Game Ops",
    "game operations": "Game Ops",
    "mobile": "Mobile",
    "graphics": "Graphics",
    "engine": "Graphics",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _phrase_count(text: str, phrase: str) -> int:
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return len(re.findall(pattern, text))


def _requirement_summary(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = candidate.get("evaluation_metadata") or {}
    rows = metadata.get("source_jd_requirement_summary") or []
    return [row for row in rows if isinstance(row, dict)]


def derive_candidate_variant_tag_scores(
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return every deterministic tag score plus the evidence signals behind it."""
    scores = {tag: 0.0 for tag in AVAILABLE_VARIANT_TAGS}
    signals: dict[str, list[str]] = {tag: [] for tag in AVAILABLE_VARIANT_TAGS}

    for row in _requirement_summary(candidate):
        match_label = _clean(row.get("match_label")).lower()
        if match_label not in _MATCH_WEIGHT:
            continue
        importance = _clean(row.get("importance")).lower()
        importance_weight = _IMPORTANCE_WEIGHT.get(importance, 1.0)
        try:
            evidence_strength = float(row.get("evidence_strength") or 0)
        except (TypeError, ValueError):
            evidence_strength = 0.0
        evidence_weight = max(0.20, min(1.0, evidence_strength / 5.0))
        base_weight = (
            importance_weight
            * _MATCH_WEIGHT[match_label]
            * evidence_weight
        )
        capability_id = _clean(row.get("capability_id")).lower()
        text = " ".join(
            _clean(row.get(field))
            for field in ("text", "requirement", "description")
            if _clean(row.get(field))
        ).lower()

        for tag, rule in _TAG_RULES.items():
            for prefix in rule["capability_prefixes"]:
                if capability_id.startswith(prefix):
                    scores[tag] += 4.0 * base_weight
                    signal = f"capability:{capability_id}"
                    if signal not in signals[tag]:
                        signals[tag].append(signal)
                    break
            for phrase, phrase_weight in rule["phrases"].items():
                count = _phrase_count(text, phrase)
                if not count:
                    continue
                scores[tag] += phrase_weight * base_weight * min(count, 2)
                if phrase not in signals[tag]:
                    signals[tag].append(phrase)

    output = [
        {
            "tag": tag,
            "score": round(scores[tag], 2),
            "signals": sorted(signals[tag])[:6],
        }
        for tag in AVAILABLE_VARIANT_TAGS
    ]
    output.sort(key=lambda row: (-float(row["score"]), str(row["tag"])))
    return output


def derive_candidate_variant_tags(
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return automatically selected tags from the scored source-JD evidence."""
    scored = derive_candidate_variant_tag_scores(candidate)
    maximum = max((float(row["score"]) for row in scored), default=0.0)
    if maximum <= 0:
        return []

    # v2.1 uses an absolute strong-evidence floor rather than a relative
    # percentage of the highest-scoring tag. Repeated AI/DevOps phrases should
    # not suppress a separately strong Backend signal such as one direct
    # required REST-API requirement. Manual confirmation remains available.
    cutoff = 5.0
    return [
        row
        for row in scored
        if float(row["score"]) >= cutoff
    ][:5]


def variant_tags_from_label(label: Any) -> list[str]:
    """Infer stable comparison tags from an existing human lane label."""
    cleaned = _clean(label).lower()
    if not cleaned or cleaned == "primary":
        return []
    found: list[str] = []
    for alias, tag in _LABEL_ALIASES.items():
        if _phrase_count(cleaned, alias) and tag not in found:
            found.append(tag)
    return found


def _normalise_selected_tags(
    values: list[str] | tuple[str, ...] | None,
) -> list[str]:
    """Normalise user-confirmed tags, including custom Tag Library labels."""
    if values is None:
        return []
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = _clean(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)
    return output


def _effective_tag_rows(
    *,
    candidate: dict[str, Any],
    selected_tags: list[str] | tuple[str, ...] | None,
) -> tuple[list[dict[str, Any]], str]:
    automatic = derive_candidate_variant_tags(candidate)
    if selected_tags is None:
        return automatic, "automatic"

    selected = _normalise_selected_tags(selected_tags)
    by_name = {
        str(row.get("tag") or ""): row
        for row in derive_candidate_variant_tag_scores(candidate)
    }
    rows: list[dict[str, Any]] = []
    for tag in selected:
        source = by_name.get(tag) or {
            "tag": tag,
            "score": 0.0,
            "signals": [],
        }
        rows.append(
            {
                "tag": tag,
                "score": float(source.get("score") or 0.0),
                "signals": list(source.get("signals") or []),
                "confirmed": True,
            }
        )
    rows.sort(key=lambda row: (-float(row["score"]), str(row["tag"])))
    return rows, "user_confirmed"


def _suggested_label(tags: list[dict[str, Any]]) -> str:
    names = [
        _clean(row.get("tag"))
        for row in tags
        if _clean(row.get("tag")) and _clean(row.get("tag")) != "Generalist"
    ]
    present = set(names)
    pair_rules = (
        (("Backend", "AI"), "Backend / AI"),
        (("Frontend", "AI"), "Frontend / AI"),
        (("Game Ops", "QA"), "Game Ops / QA"),
        (("Backend", "DevOps"), "Backend / Cloud"),
    )
    for required, label in pair_rules:
        if set(required).issubset(present):
            return label

    if "Backend" in present and "Frontend" in present:
        return ""

    builtin = set(AVAILABLE_VARIANT_TAGS)
    custom = [name for name in names if name not in builtin]
    if custom:
        return " / ".join(names[:2])

    singles = {
        "Backend": "Backend",
        "Frontend": "Frontend",
        "AI": "Applied AI",
        "QA": "QA / Automation",
        "Game Ops": "Game Operations",
        "Mobile": "Mobile",
        "Graphics": "Graphics / Engine",
        "Data": "Data / Database",
        "DevOps": "Cloud / DevOps",
    }
    for row in tags:
        tag = _clean(row.get("tag"))
        if tag in singles:
            return singles[tag]
    return ""


def _lane_tag_set(lane: dict[str, Any]) -> set[str]:
    """Prefer persisted lane metadata; fall back to legacy label inference."""
    if _clean(lane.get("variant_id")).lower() == "primary":
        return set()
    persisted = lane.get("persisted_tags")
    if isinstance(persisted, (list, tuple, set)):
        cleaned = {
            _clean(value)
            for value in persisted
            if _clean(value) and _clean(value) != "Generalist"
        }
        if cleaned:
            return cleaned
    return set(variant_tags_from_label(lane.get("variant_label")))


def suggest_blueprint_variant_lane(
    *,
    candidate: dict[str, Any],
    active_family_lanes: list[dict[str, Any]],
    selected_tags: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Suggest a label/action; selected_tags explicitly overrides auto tags."""
    automatic_tags = derive_candidate_variant_tags(candidate)
    tags, tag_source = _effective_tag_rows(
        candidate=candidate,
        selected_tags=selected_tags,
    )
    label = _suggested_label(tags)
    active = [row for row in active_family_lanes if isinstance(row, dict)]

    base = {
        "policy_version": PHASE9D_VARIANT_TAG_POLICY_VERSION,
        "automatic_tags": automatic_tags,
        "tags": tags,
        "tag_source": tag_source,
        "tag_scores": derive_candidate_variant_tag_scores(candidate),
        "suggested_label": label,
    }

    if not active:
        return {
            **base,
            "recommendation": {
                "intent": "initial_primary",
                "variant_id": "primary",
                "variant_label": "Primary",
                "reason": "No active lane exists; the first lane remains Primary.",
            },
        }

    primary = next(
        (
            row
            for row in active
            if _clean(row.get("variant_id")).lower() == "primary"
        ),
        None,
    )
    if not label:
        if primary is not None:
            return {
                **base,
                "recommendation": {
                    "intent": "update_existing_variant",
                    "variant_id": _clean(primary.get("variant_id")) or "primary",
                    "variant_label": (
                        _clean(primary.get("variant_label")) or "Primary"
                    ),
                    "reason": (
                        "No clear specialization dominates; Primary is the "
                        "closest generalist lane."
                    ),
                },
            }
        return {
            **base,
            "recommendation": {
                "intent": "create_new_variant",
                "variant_id": "",
                "variant_label": "",
                "reason": "No stable specialization label could be derived.",
            },
        }

    candidate_tags = {
        _clean(row.get("tag"))
        for row in tags
        if _clean(row.get("tag")) and _clean(row.get("tag")) != "Generalist"
    }
    lane_matches: list[tuple[int, float, int, str, dict[str, Any]]] = []
    for lane in active:
        if _clean(lane.get("variant_id")).lower() == "primary":
            continue
        lane_tags = _lane_tag_set(lane)
        if not lane_tags or not candidate_tags:
            continue
        intersection = candidate_tags & lane_tags
        exact = int(candidate_tags == lane_tags)
        minimum_size = min(len(candidate_tags), len(lane_tags))
        overlap = (
            len(intersection) / minimum_size
            if minimum_size
            else 0.0
        )
        strong_containment = (
            minimum_size >= 2
            and len(intersection) >= 2
            and len(intersection) * 3 >= minimum_size * 2
        )
        if exact or strong_containment:
            lane_matches.append(
                (
                    exact,
                    overlap,
                    len(intersection),
                    _clean(lane.get("variant_id")),
                    lane,
                )
            )

    if lane_matches:
        lane_matches.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                -item[2],
                item[3],
            )
        )
        exact, overlap, intersection_count, _, lane = lane_matches[0]
        return {
            **base,
            "recommendation": {
                "intent": "update_existing_variant",
                "variant_id": _clean(lane.get("variant_id")),
                "variant_label": _clean(lane.get("variant_label")),
                "reason": (
                    "The confirmed specialization exactly matches the "
                    "persisted lane tags."
                    if exact
                    else (
                        "The confirmed specialization strongly overlaps the "
                        "persisted lane tags "
                        f"({intersection_count} shared tags; "
                        f"{overlap:.0%} containment)."
                    )
                ),
            },
        }

    return {
        **base,
        "recommendation": {
            "intent": "create_new_variant",
            "variant_id": "",
            "variant_label": label,
            "reason": (
                "No existing active lane matches the confirmed specialization."
            ),
        },
    }
