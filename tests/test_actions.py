import pandas as pd
from src.schemas import FixAction
from src.tools.actions import apply_deduplication, apply_missing_value_imputation, apply_fixes


def test_deduplication_removes_duplicates_and_preserves_original():
    df = pd.DataFrame({
        "name": ["Alice", "Bob", "Alice"],
        "email": ["a@x.com", "b@x.com", "a@x.com"],
    })
    original_len = len(df)
    action = FixAction(action_id="a1", issue_type="duplicate_records",
                        action_type="deduplicate", description="dedup",
                        affected_row_count=1, auto_fixable=True)

    fixed_df, applied_fix = apply_deduplication(df, action)

    assert len(fixed_df) == 2
    assert applied_fix.rows_affected == 1
    # Original DataFrame must be untouched.
    assert len(df) == original_len


def test_missing_value_imputation_numeric_uses_median():
    df = pd.DataFrame({"age": [20.0, 30.0, None, 40.0]})
    action = FixAction(action_id="a1", issue_type="missing_values", column="age",
                        action_type="impute_missing", description="impute",
                        affected_row_count=1, auto_fixable=True)

    fixed_df, applied_fix = apply_missing_value_imputation(df, action)

    assert fixed_df["age"].isna().sum() == 0
    assert fixed_df["age"].iloc[2] == 30.0  # median of 20, 30, 40
    assert applied_fix.rows_affected == 1
    # Original untouched.
    assert df["age"].isna().sum() == 1


def test_missing_value_imputation_categorical_uses_mode():
    df = pd.DataFrame({"status": ["Active", "Active", None, "Inactive"]})
    action = FixAction(action_id="a1", issue_type="missing_values", column="status",
                        action_type="impute_missing", description="impute",
                        affected_row_count=1, auto_fixable=True)

    fixed_df, applied_fix = apply_missing_value_imputation(df, action)

    assert fixed_df["status"].isna().sum() == 0
    assert fixed_df["status"].iloc[2] == "Active"  # most common value


def test_apply_fixes_skips_manual_review_only_actions():
    df = pd.DataFrame({"name": ["Alice", "Alice"], "email": ["bad-email", "bad-email"]})
    dedup_action = FixAction(action_id="a1", issue_type="duplicate_records",
                              action_type="deduplicate", description="dedup",
                              affected_row_count=1, auto_fixable=True)
    manual_action = FixAction(action_id="a2", issue_type="invalid_email", column="email",
                               action_type="manual_review_only", description="review",
                               affected_row_count=2, auto_fixable=False)

    fixed_df, applied = apply_fixes(df, [dedup_action, manual_action])

    assert len(fixed_df) == 1  # dedup applied
    assert len(applied) == 1   # only the auto-fixable one ran
    assert applied[0].action_type == "deduplicate"


def test_apply_fixes_applies_multiple_actions_in_sequence():
    df = pd.DataFrame({
        "name": ["Alice", "Alice", "Bob"],
        "age": [25.0, 25.0, None],
    })
    dedup = FixAction(action_id="a1", issue_type="duplicate_records",
                       action_type="deduplicate", description="dedup",
                       affected_row_count=1, auto_fixable=True)
    impute = FixAction(action_id="a2", issue_type="missing_values", column="age",
                        action_type="impute_missing", description="impute",
                        affected_row_count=1, auto_fixable=True)

    fixed_df, applied = apply_fixes(df, [dedup, impute])

    assert len(fixed_df) == 2          # dedup ran first
    assert fixed_df["age"].isna().sum() == 0  # then imputation ran on the deduped data
    assert len(applied) == 2
