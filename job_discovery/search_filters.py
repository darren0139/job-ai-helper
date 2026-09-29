"""Pure helpers for Job Finder source/company search scoping."""

from __future__ import annotations

from typing import Any, Iterable


ATS_PROVIDERS = {"greenhouse", "lever", "ashby", "smartrecruiters"}


def target_key(target: dict[str, Any]) -> str:
    provider = str(target.get("ats_provider") or "").strip().lower()
    identifier = str(target.get("ats_identifier") or "").strip()
    if not provider or not identifier:
        return ""
    return f"{provider}:{identifier}"


def targets_for_sources(
    targets: Iterable[dict[str, Any]],
    selected_sources: Iterable[str],
) -> list[dict[str, Any]]:
    selected = {str(source or "").strip().lower() for source in selected_sources}
    return [
        dict(target)
        for target in targets
        if str(target.get("ats_provider") or "").strip().lower() in selected
        and target_key(target)
    ]


def filter_jobs_by_target_companies(
    jobs: Iterable[dict[str, Any]],
    selected_targets: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply optional per-ATS-company filters without affecting broad sources.

    If no target companies were selected, every job passes.

    If targets were selected for SmartRecruiters, for example, only matching
    SmartRecruiters target scopes pass, while MyCareersFuture/Careers@Gov and
    other ATS providers without an explicit target selection remain unaffected.

    V1/V1.1 rows that predate ``source_scope`` get a conservative fallback:
    exact normalized company-name or identifier matching.
    """
    selected = [dict(target) for target in selected_targets if target_key(target)]
    if not selected:
        return [dict(job) for job in jobs]

    selected_by_provider: dict[str, list[dict[str, Any]]] = {}
    for target in selected:
        provider = str(target.get("ats_provider") or "").strip().lower()
        selected_by_provider.setdefault(provider, []).append(target)

    output: list[dict[str, Any]] = []
    for raw_job in jobs:
        job = dict(raw_job)
        source = str(job.get("source") or "").strip().lower()
        provider_targets = selected_by_provider.get(source)

        # A target-company filter applies only to the provider(s) for which the
        # user explicitly selected companies.
        if not provider_targets:
            output.append(job)
            continue

        scope = str(job.get("source_scope") or "").strip().casefold()
        accepted_scopes = {
            target_key(target).casefold()
            for target in provider_targets
            if target_key(target)
        }
        if scope and scope in accepted_scopes:
            output.append(job)
            continue

        # Migration fallback for older discovered rows without source_scope.
        if not scope:
            company = str(job.get("company") or "").strip().casefold()
            accepted_names = {
                str(target.get("company_name") or "").strip().casefold()
                for target in provider_targets
                if str(target.get("company_name") or "").strip()
            }
            accepted_identifiers = {
                str(target.get("ats_identifier") or "").strip().casefold()
                for target in provider_targets
                if str(target.get("ats_identifier") or "").strip()
            }
            if company and company in (accepted_names | accepted_identifiers):
                output.append(job)

    return output
