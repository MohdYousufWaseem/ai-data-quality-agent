import pandas as pd
from src.tools.actions import apply_fixes
from src.tools.recommendations import build_recommendations
from src.tools.quality_checks import run_all_checks
from src.tools.validation import validate_fixes


def test_validation_shows_score_improvement_after_dedup():
    df = pd.DataFrame({
        "name": ["Alice", "Bob", "Alice"],
        "email": ["a@x.com", "b@x.com", "a@x.com"],
    })
    issues = run_all_checks(df)
    recs = build_recommendations("test.csv", issues)
    auto_fixable = [a for a in recs.actions if a.auto_fixable]

    fixed_df, applied = apply_fixes(df, auto_fixable)
    validation = validate_fixes(df, fixed_df, applied)

    assert validation.row_count_before == 3
    assert validation.row_count_after == 2
    assert validation.score_after > validation.score_before
    assert validation.issue_count_after < validation.issue_count_before
    assert len(validation.fixes_applied) == 1


def test_validation_with_no_fixes_applied_reports_unchanged():
    df = pd.DataFrame({"name": ["Alice", "Bob"]})
    validation = validate_fixes(df, df, [])
    assert validation.score_before == validation.score_after
    assert "No fixes were applied" in validation.summary
