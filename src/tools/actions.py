"""
Executes approved fixes. Every function here takes a DataFrame and
returns a NEW DataFrame plus an AppliedFix record -- the original
DataFrame (and the original uploaded file) is never mutated in place.
This is the "always write to staging, never overwrite source data"
principle from the project plan, adapted to a file-based tool: the
"staging" output is a new in-memory DataFrame / new CSV, not an edit to
the input file.

Only called after a human has approved the specific action -- see
agents/recommendation_agent.py for where actions are proposed, and the
UI/CLI for where the human approval gate lives.
"""

import pandas as pd
from src.schemas import FixAction, AppliedFix


def apply_deduplication(df: pd.DataFrame, action: FixAction) -> tuple[pd.DataFrame, AppliedFix]:
    # Mirrors the subset logic in tools/quality_checks.check_duplicates so
    # the fix removes exactly what the check flagged -- fixing more or
    # fewer rows than were reported would be confusing.
    subset = [c for c in df.columns if not c.lower().endswith("id") and c.lower() != "id"]
    before = len(df)
    deduped = df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
    removed = before - len(deduped)

    fix = AppliedFix(
        action_id=action.action_id, action_type="deduplicate",
        rows_affected=removed,
        description=f"Removed {removed} duplicate row(s), kept the first occurrence of each.",
    )
    return deduped, fix


def apply_missing_value_imputation(df: pd.DataFrame, action: FixAction) -> tuple[pd.DataFrame, AppliedFix]:
    column = action.column
    df = df.copy()
    null_count_before = int(df[column].isna().sum())

    if pd.api.types.is_numeric_dtype(df[column]):
        fill_value = df[column].median()
        strategy_desc = f"median ({fill_value})"
    else:
        mode = df[column].mode(dropna=True)
        fill_value = mode.iloc[0] if not mode.empty else "Unknown"
        strategy_desc = f"most common value ('{fill_value}')"

    df[column] = df[column].fillna(fill_value)

    fix = AppliedFix(
        action_id=action.action_id, action_type="impute_missing", column=column,
        rows_affected=null_count_before,
        description=f"Filled {null_count_before} missing value(s) in '{column}' "
                     f"using the {strategy_desc}.",
    )
    return df, fix


def apply_fixes(df: pd.DataFrame, actions: list[FixAction]) -> tuple[pd.DataFrame, list[AppliedFix]]:
    """Applies a list of approved, auto-fixable actions in sequence and
    returns the resulting DataFrame plus a log of what was actually done.
    Non-auto-fixable actions (manual_review_only) are silently skipped --
    the caller should only pass actions the human explicitly approved."""
    current_df = df.copy()
    applied: list[AppliedFix] = []

    for action in actions:
        if not action.auto_fixable:
            continue
        if action.action_type == "deduplicate":
            current_df, fix = apply_deduplication(current_df, action)
        elif action.action_type == "impute_missing":
            current_df, fix = apply_missing_value_imputation(current_df, action)
        else:
            continue
        applied.append(fix)

    return current_df, applied
