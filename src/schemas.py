from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: list[str] = Field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    std_value: Optional[float] = None
    # Category -> count, only populated for low-cardinality categorical
    # columns (see MAX_DISTRIBUTION_CATEGORIES in tools/profiling.py).
    # default_factory=dict keeps old snapshots (saved before this field
    # existed) loadable -- they just deserialize with an empty dict here.
    value_counts: dict[str, int] = Field(default_factory=dict)
    # Numeric quantiles: keys "p10", "p25", "p50", "p75", "p90".
    # Same backward-compatibility reasoning as value_counts.
    quantiles: dict[str, float] = Field(default_factory=dict)


class DataProfile(BaseModel):
    source_name: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    duplicate_row_count: int


Severity = Literal["critical", "warning", "info"]


class QualityIssue(BaseModel):
    issue_type: str
    severity: Severity
    column: Optional[str] = None
    affected_row_count: int
    affected_pct: float
    description: str
    sample_row_indices: list[int] = Field(default_factory=list)


class QualityReport(BaseModel):
    source_name: str
    overall_score: int
    row_count: int
    issues: list[QualityIssue]
    most_critical_issue: Optional[str] = None
    generated_summary: Optional[str] = None


class DriftFinding(BaseModel):
    finding_type: str
    severity: Severity
    column: Optional[str] = None
    description: str
    previous_value: Optional[str] = None
    current_value: Optional[str] = None


class DriftReport(BaseModel):
    source_name: str
    has_baseline: bool
    baseline_date: Optional[str] = None
    current_date: str
    findings: list[DriftFinding]


# ---------------------------------------------------------------------------
# 4. Output of the Root Cause Agent (explains WHY a volume anomaly happened)
# ---------------------------------------------------------------------------

class RootCauseCandidate(BaseModel):
    column: str
    category: str
    baseline_count: int
    current_count: int
    delta: int              # positive = this category's rows decreased
    contribution_pct: float # % of the total row-count change this category explains


class RootCauseReport(BaseModel):
    triggered: bool                              # did an investigation actually run?
    anomaly_type: Optional[str] = None            # "volume_drop" or "volume_spike"
    total_row_change: Optional[int] = None
    primary_suspect: Optional[RootCauseCandidate] = None
    other_candidates: list[RootCauseCandidate] = Field(default_factory=list)
    conclusion: str = ""                          # deterministic, plain-English fact
    reason_not_triggered: Optional[str] = None


# ---------------------------------------------------------------------------
# 5. Output of the Recommendation Agent (proposed fixes -- not yet applied)
# ---------------------------------------------------------------------------

ActionType = Literal["deduplicate", "impute_missing", "manual_review_only"]


class FixAction(BaseModel):
    # A stable id so the UI/CLI can reference "apply this specific action"
    # without re-matching on free text.
    action_id: str
    issue_type: str
    action_type: ActionType
    column: Optional[str] = None
    description: str
    affected_row_count: int
    auto_fixable: bool


class RecommendationReport(BaseModel):
    source_name: str
    actions: list[FixAction]


# ---------------------------------------------------------------------------
# 6. Output of applying fixes (Action Agent) and re-validating (Validation Agent)
# ---------------------------------------------------------------------------

class AppliedFix(BaseModel):
    action_id: str
    action_type: str
    column: Optional[str] = None
    rows_affected: int
    description: str


class ValidationReport(BaseModel):
    fixes_applied: list[AppliedFix]
    row_count_before: int
    row_count_after: int
    score_before: int
    score_after: int
    issue_count_before: int
    issue_count_after: int
    summary: str  # deterministic, plain-English comparison
