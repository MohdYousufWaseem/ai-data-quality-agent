"""
Shared data contracts for the AI Data Quality & Analytics Agent.

WHY THIS FILE MATTERS:
In an agentic system, agents pass structured data to each other, not just
chat messages. If the Profiling Agent hands the Quality Agent a loose
dictionary, small key-name typos silently break the pipeline. Pydantic
models catch that at runtime and give you auto-generated validation.

Every agent in this project reads/writes one of these models.
"""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Output of the Profiling Agent (pure statistics, no judgment calls yet)
# ---------------------------------------------------------------------------

class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: list[str] = Field(default_factory=list)
    # Only populated for numeric columns
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    std_value: Optional[float] = None


class DataProfile(BaseModel):
    """The raw, deterministic profile of a dataset. No LLM involved here."""
    source_name: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    duplicate_row_count: int


# ---------------------------------------------------------------------------
# 2. Output of the Quality Analysis Agent (judgment applied to the profile)
# ---------------------------------------------------------------------------

Severity = Literal["critical", "warning", "info"]


class QualityIssue(BaseModel):
    issue_type: str            # e.g. "duplicate_records", "invalid_email"
    severity: Severity
    column: Optional[str] = None
    affected_row_count: int
    affected_pct: float
    description: str
    sample_row_indices: list[int] = Field(default_factory=list)


class QualityReport(BaseModel):
    source_name: str
    overall_score: int         # 0-100
    row_count: int
    issues: list[QualityIssue]
    most_critical_issue: Optional[str] = None
    generated_summary: Optional[str] = None  # filled in by the LLM report writer


# ---------------------------------------------------------------------------
# 3. Output of the Drift Agent (compares today's profile to a past baseline)
# ---------------------------------------------------------------------------

class DriftFinding(BaseModel):
    finding_type: str          # e.g. "volume_drop", "missing_rate_shift", "schema_column_removed"
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
