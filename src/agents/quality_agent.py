"""
Quality Analysis Agent.

Runs the deterministic checks, scores the dataset, and produces a
QualityReport. Still no LLM call here — the report's narrative summary
gets filled in later by the Report Agent, which is the one place we
actually spend an LLM call in Phase 1.
"""

from src.state import GraphState
from src.tools.quality_checks import run_all_checks
from src.tools.scoring import compute_quality_score, most_critical_issue
from src.schemas import QualityReport


def quality_agent(state: GraphState) -> GraphState:
    df = state["dataframe"]
    source_name = state["source_name"]

    issues = run_all_checks(df)
    score = compute_quality_score(issues)
    critical = most_critical_issue(issues)

    report = QualityReport(
        source_name=source_name,
        overall_score=score,
        row_count=len(df),
        issues=issues,
        most_critical_issue=critical,
    )

    state["quality_report"] = report
    state["log"].append(f"[QualityAgent] Found {len(issues)} issue types, "
                         f"score={score}/100.")
    return state
