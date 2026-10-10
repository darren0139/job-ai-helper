"""Test-only, context-local requirement hypothesis using the native matcher.

No production rule, taxonomy entry, registry mapping or evidence tier is changed.
The complete-scope predicate is the existing Addressability V2 diagnostic.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from threading import RLock
from unittest.mock import patch

from tailoring import capability_taxonomy as taxonomy, production_requirement_resolver as resolver
from taxonomy_discovery.taxonomy_addressability import manual_triage, SUPPORTED

_active = ContextVar("cross_functional_test_rule", default=False)
_lock = RLock()
CAPABILITY_ID = "collaboration.cross_functional"
NEGATIVES = (
    "Work with the engineering team", "Collaborate with developers", "Team player", "Work with stakeholders",
    "Work closely with software engineers and engineers", "Work with different teams",
    "Collaborate with product and engineering teams to build and deploy APIs",
    "Work closely with policy officers and software engineers to implement APIs",
    "Work closely with policy officers or software engineers",
    "Work closely with stakeholders such as policy officers and software engineers",
    "Experience with Python, SQL and AWS", "Do not work closely with policy officers and software engineers",
)


def eligible(requirement):
    result = manual_triage(requirement, set())
    return result["decision"] == SUPPORTED and result.get("capability_id") == CAPABILITY_ID


@contextmanager
def temporary_rule(requirements=None):
    # Full-corpus previews bind admission to complete frozen provenance. Native
    # audit adapters sometimes pass only text/focus: a stripped fragment cannot
    # bypass the source-scope guard. This is scope admission, not an ID allowlist.
    def key(row):
        return str(row.get("atomic_focus") or row.get("text", "")).replace("\u200b", "").strip().rstrip(". ").casefold()
    admitted = None
    if requirements is not None:
        records = list(requirements)
        admitted = {key(r) for r in records if eligible(r)} - {key(r) for r in records if not eligible(r)}
    # Serializes preview instrumentation; ContextVar keeps other threads native.
    # Both native aliases must be instrumented, because the resolver imports the
    # diagnostic function directly while evidence evaluation uses its module.
    with _lock:
        original = taxonomy.classify_requirement_diagnostics
        module = taxonomy
        def diagnostic(requirement, taxonomy=None):
            if not _active.get() or (admitted is not None and key(requirement) not in admitted) or not eligible(requirement):
                return original(requirement, taxonomy)
            current = taxonomy or module.get_default_taxonomy()
            records = deepcopy(list(current.capabilities))
            record = next(c for c in records if c["capability_id"] == CAPABILITY_ID)
            focus = requirement.get("atomic_focus") or requirement.get("text", "")
            record["requirement"]["any_terms"] = list(dict.fromkeys(record["requirement"]["any_terms"] + [focus]))
            shadow = module.CapabilityTaxonomy(current.version, tuple(records))
            return original(requirement, shadow)
        with patch.object(taxonomy, "classify_requirement_diagnostics", diagnostic), patch.object(resolver, "classify_requirement_diagnostics", diagnostic):
            token = _active.set(True)
            try:
                yield
            finally:
                _active.reset(token)
