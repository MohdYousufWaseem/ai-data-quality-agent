"""
Turns already-detected QualityIssues into proposed fix actions. Pure and
deterministic -- no LLM, no execution. This only *proposes*; nothing here
ever touches the data. See tools/actions.py for the code that actually
applies an approved fix.

Deliberately conservative about what's "auto_fixable": duplicates and
missing values have safe, well-understood default strategies (drop
duplicates keeping the first row; impute with median/mode). Invalid
formats and statistical outliers do NOT get an automated fix proposed --
correcting a malformed email or deciding an outlier is wrong both require
business judgment a script shouldn't assume, so those are flagged for
manual review only.
"""

from src.schemas import QualityIssue, FixAction, RecommendationReport

AUTO_FIXABLE_ISSUE_TYPES = {"duplicate_records", "missing_values"}


def build_recommendations(source_name: str, issues: list[QualityIssue]) -> RecommendationReport:
    actions: list[FixAction] = []

    for i, issue in enumerate(issues):
        action_id = f"action_{i}"

        if issue.issue_type == "duplicate_records":
            actions.append(FixAction(
                action_id=action_id,
                issue_type=issue.issue_type,
                action_type="deduplicate",
                description=f"Remove {issue.affected_row_count} duplicate row(s), "
                             f"keeping the first occurrence of each.",
                affected_row_count=issue.affected_row_count,
                auto_fixable=True,
            ))

        elif issue.issue_type == "missing_values":
            actions.append(FixAction(
                action_id=action_id,
                issue_type=issue.issue_type,
                action_type="impute_missing",
                column=issue.column,
                description=f"Fill {issue.affected_row_count} missing value(s) in "
                             f"'{issue.column}' (median for numeric columns, most "
                             f"common value for text columns).",
                affected_row_count=issue.affected_row_count,
                auto_fixable=True,
            ))

        else:
            actions.append(FixAction(
                action_id=action_id,
                issue_type=issue.issue_type,
                action_type="manual_review_only",
                column=issue.column,
                description=f"{issue.description} -- requires manual judgment, "
                             f"no automated fix proposed.",
                affected_row_count=issue.affected_row_count,
                auto_fixable=False,
            ))

    return RecommendationReport(source_name=source_name, actions=actions)
