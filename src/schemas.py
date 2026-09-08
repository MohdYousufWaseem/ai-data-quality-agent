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
