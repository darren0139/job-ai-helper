"""Job discovery ingestion for Job AI Helper.

This package deliberately stops at normalized job discovery. Selected jobs are
handed to the existing Application Session JD-analysis pipeline, which remains
responsible for taxonomy, evidence scoring, blueprint selection, and tailoring.
"""

from .models import NormalizedJob, SearchSpec

__all__ = ["NormalizedJob", "SearchSpec"]
