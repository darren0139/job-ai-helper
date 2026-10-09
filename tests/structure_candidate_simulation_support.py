"""Test-only, scoped hypotheses. No production entry point or persistence."""
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import re
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as scorer
from tailoring import phase6d6_structured_matching as structure
from taxonomy_discovery import regression_corpus as corpus
from taxonomy_discovery.technology_registry import resolve_requirement_text


@contextmanager
def simulation(candidate):
    """Restore every patched callable even if a frozen replay fails."""
    with ExitStack() as stack:
        if candidate == "presentation":
            native = structure.technology_requirement_structure

            def presentation(row):
                copied = deepcopy(row)
                text = copied.get("atomic_focus") or copied.get("text", "")
                copied["atomic_focus"] = re.sub(r"^[\u00b7\u2022]\s*", "", text)
                return native(copied)

            stack.enter_context(patch.object(structure, "technology_requirement_structure", presentation))
        elif candidate == "dotnet":
            # A hypothesis, NOT an existing production technical-token guard.
            # Protect only the exact dotted registry spelling. Bare NET is
            # deliberately untouched. Existing segmentation/decomposition runs.
            native_surface = scorer._normalise_requirement_surface
            native_sentences = scorer._split_requirement_sentences
            native_record = scorer._clause_record
            token = "TQTemporaryDottedNetToken"
            dotted = re.compile(r"(?<![\w.])\.NET\b", re.I)

            def surface(value):
                text = str(value or "")
                if token in text:
                    raise ValueError("Temporary token collision")
                return native_surface(dotted.sub(token, text)).replace(token, ".NET")

            def sentences(value):
                # The native sentence helper trims leading dots separately.
                text = str(value or "")
                if token in text:
                    raise ValueError("Temporary token collision")
                with patch.object(scorer, "_normalise_requirement_surface", native_surface):
                    parts = native_sentences(dotted.sub(token, text))
                return [p.replace(token, ".NET") for p in parts]

            def record(**kwargs):
                result = native_record(**kwargs)
                for key, source in (("text", kwargs["text"]), ("atomic_focus", kwargs.get("focus_text") or kwargs["text"])):
                    if re.match(r"^\s*\.NET\b", str(source), re.I) and result[key].lower().startswith("net"):
                        result[key] = "." + result[key]
                return result

            stack.enter_context(patch.object(scorer, "_normalise_requirement_surface", surface))
            stack.enter_context(patch.object(scorer, "_split_requirement_sentences", sentences))
            stack.enter_context(patch.object(scorer, "_clause_record", record))
        elif candidate == "parent_scope":
            native_canonical = scorer.canonicalise_requirements

            def canonical(*args, **kwargs):
                result = native_canonical(*args, **kwargs)
                for row in result["requirements"]:
                    parents = [p for p in row.get("source_provenance", [])
                        if scorer._preserves_coherent_parent(p.get("raw_parent_text", ""))]
                    if parents and not scorer._preserves_coherent_parent(row["atomic_focus"]):
                        # Inspection metadata only; never create scoring terms,
                        # force group mode, change text, or suppress evidence.
                        row["simulation_parent_scope"] = {
                            "source_provenance": deepcopy(parents),
                            "native_coherent_parent": True,
                            "mandatory_children_inferred": False,
                            "scoring_effect": False,
                        }
                return result

            stack.enter_context(patch.object(scorer, "canonicalise_requirements", canonical))
        else:
            raise ValueError("Unknown bounded simulation")
        yield


def view(job):
    """Use native weighted coverage to measure actual per-row contributions."""
    rows = job["baseline_stable_analysis"]["canonical_requirements"]
    output = []
    for row in rows:
        accepted = {"required", "core", "deal_breaker"} if row["importance"] in {"required", "core", "deal_breaker"} else {"preferred"}
        only = deepcopy(rows)
        for r in only:
            r["match_value"] = 1.0 if r["requirement_id"] == row["requirement_id"] else 0.0
        _, weight, _ = scorer._weighted_coverage(only, accepted)
        native = structure.technology_requirement_structure(row)
        output.append({"requirement_id": row["requirement_id"], "canonical_text": row["text"],
            "structure_kind": native["source"], "group_mode": native["mode"],
            "component_identities": [{"text": c["atomic_focus"], "registry": resolve_requirement_text(c["atomic_focus"])} for c in native["components"]],
            "parent_registry": deepcopy(row.get("technology_registry_resolution")),
            "parent_capability_id": row.get("capability_id"), "parent_taxonomy_status": row.get("capability_taxonomy_cap_status"),
            "weight": weight, "group_weight_fraction": row.get("group_weight_fraction"),
            "atomic_group_id": row.get("atomic_group_id"), "importance": row["importance"],
            "evidence_label": row.get("match_label"), "evidence": deepcopy(row.get("evidence")),
            "score_contribution": weight * row.get("match_value", 0),
            "job_score": job["metrics"]["deterministic_alignment_score"],
            "provenance": deepcopy(row.get("source_provenance")),
            "simulation_parent_scope": deepcopy(row.get("simulation_parent_scope"))})
    return output


def replay(frozen, candidate=None):
    if candidate is None:
        result = corpus.replay_current_corpus(frozen)
        return result, {j["job_id"]: view(j) for j in result["jobs"]}
    with simulation(candidate):
        result = corpus.replay_current_corpus(frozen)
        return result, {j["job_id"]: view(j) for j in result["jobs"]}
