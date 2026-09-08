"""
Turns a list of QualityIssues into a single 0-100 score.

This is intentionally simple and transparent (not an LLM call) so the
score is explainable: "you lost points because of X, Y, Z" rather than
a black box. Tune the weights as you learn what matters for your data.
"""

from src.schemas import QualityIssue

SEVERITY_WEIGHTS = {
    "critical": 15,
    "warning": 5,
    "info": 1,
}


def compute_quality_score(issues: list[QualityIssue]) -> int:
    score = 100
    for issue in issues:
        weight = SEVERITY_WEIGHTS.get(issue.severity, 1)
        # Scale the penalty a bit by how much of the dataset is affected,
        # so a 0.5%-affecting warning costs less than a 40%-affecting one.
        impact_multiplier = min(1.0 + issue.affected_pct / 25, 3.0)
        score -= weight * impact_multiplier
    return max(0, round(score))


def most_critical_issue(issues: list[QualityIssue]) -> str | None:
    if not issues:
        return None
    ranked = sorted(
        issues,
        key=lambda i: (SEVERITY_WEIGHTS.get(i.severity, 0), i.affected_pct),
        reverse=True,
    )
    return ranked[0].issue_type
