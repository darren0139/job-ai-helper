"""Explicitly registered document scoring upgrades; never a prefix-based trust rule.

Registration is not activation. Future releases add a reviewed exact edge and tests.
The historical B2.15 event shape remains unchanged.
"""
LEGACY = frozenset({'stable-evidence-v1.16-phase6d20', 'stable-evidence-v1.16-phase6d20-v312a17-fullstack-single-row'})
B215 = 'stable-evidence-v1.16-phase6d20-v312b215-jd-eligibility-v312a17-fullstack-single-row'
B219A = B215 + '-v312b219a-software-testing-v1'
# Policy-only edges are exact and scope-preserving. Legacy eligibility correction
# is a separately reviewed removal-only edge. An unused registration is inert.
B219B = B219A + '-v312b219b-technology-database-v1'
POLICY_ONLY_EDGES = frozenset({(B215, B219A), (B219A, B219B)})

def policy_path(old, new):
    if not isinstance(old,str) or not isinstance(new,str) or old == new:
        return None
    edges = POLICY_ONLY_EDGES | frozenset((x,B215) for x in LEGACY)
    queue = [(old,)]
    while queue:
        path = queue.pop(0)
        for a,b in sorted(edges):
            if a != path[-1] or b in path:
                continue
            extended = path + (b,)
            if b == new:
                return extended
            queue.append(extended)
    return None

def needs_exact_recheck(decision, active):
    stable = (decision.get('effective_starting_comparison') or decision.get('comparison') or {}).get('stable_analysis_snapshot') or {}
    old = stable.get('scoring_version')
    # Preserve the existing B2.15 runtime semantics. Subsequent upgrades must
    # not silently use a historical frozen score, even if the JD IDs agree.
    scoped_identity = stable.get('matching_policy_identity')
    same_runtime = old == active or (isinstance(scoped_identity,str) and bool(scoped_identity) and old == active + '+' + scoped_identity)
    return bool(not same_runtime and active not in LEGACY | {B215})

def enforce_fresh_receipt(active):
    # Keep the explicit pre-A1.7 legacy rollback behaviour only for its exact
    # original version; known and future nonlegacy versions require freshness.
    return active != 'stable-evidence-v1.16-phase6d20'
