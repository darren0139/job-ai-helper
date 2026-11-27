"""B1.21.3 test-only policy identities; never import this from application code."""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch

POLICY_ENV = "JOB_AI_HELPER_V312A17_NATIVE_FULLSTACK_POLICY"
TOKEN = "v312a17_fullstack_single_row"
LEGACY = "stable-evidence-v1.16-phase6d20"
ACTIVE = LEGACY + "-v312b215-jd-eligibility-v312a17-fullstack-single-row"
# Frozen historical names above deliberately retain their original meaning.
# These successors may open *read-only* V1.16 fixture scopes; they are not
# interchangeable scoring identities and cannot be used for native replay.
ROLLBACK_B219A = LEGACY + "-v312b219a-software-testing-v1"
ACTIVE_B219A = ACTIVE + "-v312b219a-software-testing-v1"
ACTIVE_B219B = ACTIVE_B219A + "-v312b219b-technology-database-v1"
HISTORICAL_FIXTURE_HOST_POLICIES = frozenset((
    LEGACY, ACTIVE, ROLLBACK_B219A, ACTIVE_B219A, ACTIVE_B219B,
))

EXPECTED_SCORING_VERSION = ACTIVE_B219B if os.environ.get(POLICY_ENV, TOKEN).strip() == TOKEN else ROLLBACK_B219A
EXPECTED_JD_INPUT_FINGERPRINT = {
    LEGACY: "3b9ce38aea8345b847b486c710fa8f0c1dda3cc51d8b70cd6657503a25e0379c",
    ACTIVE: "57057947f0f70cdcca92754722faeb5911ede61a3eb4997d0b1df085d834a101",
    ROLLBACK_B219A: "153d023c949ccadf352bde355b3a1cb45c71d4c6b50880d9f1e3fea07c1b32ab",
    ACTIVE_B219B: "6728e21247e4f10b4e27b39696233ae72a38051b30e0fc194f2e89c77e45d17b",
}[EXPECTED_SCORING_VERSION]

@contextmanager
def historical_receipt_policy(bundle):
    """Read-only frozen-receipt presentation/arithmetic tests, NOT native replay.

    Keep the real JD/taxonomy/registry/currentness validators and exact receipt
    bytes. Model only the historical scoring-version authority in this scope.
    Only under the original V1.16 identity is no override necessary. Do not use this
    scope for newly scored analyses or real application operations.
    """
    from job_discovery import matching
    from tailoring import job_match_ab_analysis, initial_analysis_explainer
    jobs = bundle["snapshot"]["audit"]["corpus"]["jobs"]
    if not jobs or any(j["baseline_stable_analysis"]["scoring_version"] != LEGACY for j in jobs):
        raise AssertionError("Historical fixture must retain the exact V1.16 legacy policy")
    original = matching.current_match_versions
    actual = original()["scoring_version"]
    if actual not in HISTORICAL_FIXTURE_HOST_POLICIES:
        raise AssertionError("Unknown current scoring policy: " + str(actual))
    if actual == LEGACY:
        yield
        return
    def fixture_versions():
        versions = dict(original())
        versions["scoring_version"] = LEGACY
        return versions
    with ExitStack() as stack:
        for module in (matching, job_match_ab_analysis, initial_analysis_explainer):
            stack.enter_context(patch.object(module, "current_match_versions", fixture_versions))
        yield


def run_exact_legacy_case(test):
    """Execute the original exact pin in a genuinely fresh legacy process."""
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION
    test.assertEqual(SCORING_VERSION, ACTIVE)
    module = test.__class__.__module__.rsplit(".", 1)[-1]
    case = "tests." + module + "." + test.__class__.__name__ + "." + test._testMethodName
    env = os.environ.copy(); env[POLICY_ENV] = "legacy"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run([sys.executable, "-m", "unittest", case, "-v"],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    output = result.stdout + "\n" + result.stderr
    test.assertEqual(result.returncode, 0, output)
    test.assertRegex(output, r"Ran 1 test in ")
    test.assertRegex(output, r"(?m)^OK\s*$")
