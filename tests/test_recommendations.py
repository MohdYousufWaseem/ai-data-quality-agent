from src.schemas import QualityIssue
from src.tools.recommendations import build_recommendations


def make_issue(issue_type, column=None, affected=5):
    return QualityIssue(
        issue_type=issue_type, severity="warning", column=column,
        affected_row_count=affected, affected_pct=10.0,
        description=f"{affected} problem rows in {issue_type}.",
    )


def test_duplicate_records_get_auto_fixable_action():
    report = build_recommendations("test.csv", [make_issue("duplicate_records", affected=3)])
    assert len(report.actions) == 1
    assert report.actions[0].action_type == "deduplicate"
    assert report.actions[0].auto_fixable is True


def test_missing_values_get_auto_fixable_action():
    report = build_recommendations("test.csv", [make_issue("missing_values", column="phone")])
    assert len(report.actions) == 1
    assert report.actions[0].action_type == "impute_missing"
    assert report.actions[0].column == "phone"
    assert report.actions[0].auto_fixable is True


def test_invalid_email_is_manual_review_only():
    report = build_recommendations("test.csv", [make_issue("invalid_email", column="email")])
    assert report.actions[0].action_type == "manual_review_only"
    assert report.actions[0].auto_fixable is False


def test_statistical_outlier_is_manual_review_only():
    report = build_recommendations("test.csv", [make_issue("statistical_outlier", column="age")])
    assert report.actions[0].action_type == "manual_review_only"
    assert report.actions[0].auto_fixable is False


def test_action_ids_are_unique():
    issues = [make_issue("duplicate_records"), make_issue("missing_values", column="age"),
              make_issue("invalid_email", column="email")]
    report = build_recommendations("test.csv", issues)
    ids = [a.action_id for a in report.actions]
    assert len(ids) == len(set(ids))
