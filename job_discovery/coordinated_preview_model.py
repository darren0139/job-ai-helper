"""Nullable presentation/export contract, independent of saved Job Match summaries."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import StrEnum
import json
import math

MODEL_VERSION = 'coordinated-comparison-view-v1'


class Label(StrEnum):
    DIRECT = 'DIRECT'
    TRANSFERABLE = 'TRANSFERABLE'
    WEAK = 'WEAK'
    NONE = 'NONE'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED'


@dataclass(frozen=True)
class RequirementView:
    requirement_id: str
    text: str
    label: Label
    native_label: str | None
    disposition: str
    allocation: float
    match_value: float | None
    contribution: float | None
    supported_actions: tuple[str, ...]
    missing_actions: tuple[str, ...]
    technical_scope: str
    evidence: tuple[dict, ...]
    conflict: dict | None
    receipt: dict

    def table_record(self):
        return {'Requirement ID': self.requirement_id, 'Requirement': self.text,
                'Label': self.label.value, 'Disposition': self.disposition, 'Allocation': self.allocation,
                'Credit': self.contribution, 'Credit display': 'Unavailable' if self.contribution is None else str(self.contribution),
                'Missing actions': ', '.join(self.missing_actions), 'Technical scope': self.technical_scope}


@dataclass(frozen=True)
class AnalysisView:
    scoring_version: str
    requirements: tuple[RequirementView, ...]
    review_count: int
    score_available: bool
    alignment: int | float | None
    required_core: int | float | None
    preferred: int | float | None
    evidence_strength: int | float | None
    rating_band: str | None
    ranking_eligible: bool = False

    def summary(self):
        return {**{key: getattr(self, key) for key in (
            'scoring_version', 'review_count', 'score_available', 'alignment', 'required_core',
            'preferred', 'evidence_strength', 'rating_band', 'ranking_eligible')},
            'counts': {label.value: sum(r.label == label for r in self.requirements) for label in Label}}


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid numeric preview field: '+field)
    return value


def analysis_view(analysis):
    rows = []
    ids = set()
    for row in analysis['canonical_requirements']:
        rid = row['requirement_id']
        if not rid or rid in ids:
            raise ValueError('Preview requirement identity is missing or duplicated')
        ids.add(rid)
        receipt = deepcopy(row.get('coordinated_action_receipt') or {})
        pending = (receipt.get('disposition') == 'REVIEW_REQUIRED' or row.get('match_label') is None
                   or str(row.get('match_label')).upper() == 'REVIEW_REQUIRED')
        if pending:
            if row.get('match_value') is not None or receipt.get('synthetic_parent_contribution') is not None:
                raise ValueError('REVIEW_REQUIRED credit must be null, never numeric zero')
            label, value, credit = Label.REVIEW_REQUIRED, None, None
        else:
            label = Label(str(row['match_label']).upper())
            value = _number(row['match_value'], 'match_value')
            if not 0 <= value <= 1:
                raise ValueError('Preview match value outside governed range')
            credit = value * row['group_weight_fraction']
            if receipt and receipt.get('synthetic_parent_contribution') != credit:
                raise ValueError('Preview contribution differs from the scorer receipt')
        allocation = _number(row['group_weight_fraction'], 'allocation')
        if not 0 <= allocation <= 1:
            raise ValueError('Preview parent allocation outside governed range')
        conflict = receipt.get('scoped_conflict')
        selected = (row.get('evidence') or
                    ([conflict['selected_positive']] if conflict and conflict.get('quarantine') else []))
        proof = next((item['proof'] for item in receipt.get('proofs', {}).values()
                      if selected and all(item['record'].get(k) == selected[0].get(k)
                                          for k in ('evidence_id', 'source', 'text', 'section'))), {})
        mandatory = tuple(a['action'] for a in receipt.get('obligation', {}).get('actions', []))
        rows.append(RequirementView(rid, row['text'], label, receipt.get('native_label', row.get('match_label')),
            receipt.get('disposition', 'PUBLISHED_NUMERIC'), allocation, value, credit,
            tuple(proof.get('supported_actions', [])), tuple(proof.get('missing_actions', mandatory)),
            proof.get('technical_scope', 'UNPROVEN'), tuple(deepcopy(selected)), deepcopy(conflict), receipt))
    count = sum(row.label == Label.REVIEW_REQUIRED for row in rows)
    fields = ('deterministic_alignment_score', 'required_core_coverage_score', 'preferred_coverage_score', 'evidence_strength_score')
    if count and (any(analysis.get(field) is not None for field in fields) or analysis.get('alignment_band') is not None):
        raise ValueError('Whole-JD review scores and bands must be null, never numeric zero')
    available = count == 0 and all(analysis.get(field) is not None for field in fields)
    metrics = [_number(analysis[field], field) for field in fields] if available else [None]*4
    return AnalysisView(analysis['scoring_version'], tuple(rows), count, available, *metrics,
                        analysis.get('alignment_band') if available else None)


def reject_preview_ranking(_preview):
    raise ValueError('Developer comparisons are never eligible for saved Job Match ranking')


def export_comparison(result):
    """A separate preview schema; public cache writers also see the gated receipt."""
    if analysis_view(result.gated_analysis) != result.gated or analysis_view(result.published_analysis) != result.published:
        raise ValueError('Preview receipt changed after presentation validation')
    payload = {'preview_namespace': result.namespace, 'view_version': MODEL_VERSION,
               'development_preview_only': True, 'input_identity': result.identity,
               'authority': result.authority, 'ranking_eligible': False,
               'published_off': deepcopy(result.published_analysis),
               'stable_analysis': deepcopy(result.gated_analysis),
               'published_view': asdict(result.published), 'gated_view': asdict(result.gated)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
