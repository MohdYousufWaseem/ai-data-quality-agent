"""
Re-runs the same deterministic quality checks used in Phase 1 against the
data before and after fixes were applied, and builds a plain comparison.
This closes the loop: Recommend -> Approve -> Apply -> Validate. No LLM
involved -- "did the score actually improve" is a factual comparison, not
something that needs narrating to be true.
"""

import pandas as pd
from src.schemas import AppliedFix, ValidationReport
from src.tools.quality_checks import run_all_checks
from src.tools.scoring import compute_quality_score


def validate_fixes(
    original_df: pd.DataFrame,
    fixed_df: pd.DataFrame,
    applied_fixes: list[AppliedFix],
) -> ValidationReport:
    issues_before = run_all_checks(original_df)
    issues_after = run_all_checks(fixed_df)

    score_before = compute_quality_score(issues_before)
    score_after = compute_quality_score(issues_after)

    if score_after > score_before:
        verdict = f"Score improved from {score_before}/100 to {score_after}/100."
    elif score_after == score_before:
        verdict = f"Score stayed at {score_before}/100 -- the applied fixes " \
                  f"didn't change the remaining issue count."
    else:
        verdict = f"Score went from {score_before}/100 to {score_after}/100 -- " \
                  f"lower than before, which shouldn't normally happen from these " \
                  f"fixes; worth double-checking the input data."

    fix_summary = "; ".join(f.description for f in applied_fixes) if applied_fixes else "No fixes were applied."

    return ValidationReport(
        fixes_applied=applied_fixes,
        row_count_before=len(original_df),
        row_count_after=len(fixed_df),
        score_before=score_before,
        score_after=score_after,
        issue_count_before=len(issues_before),
        issue_count_after=len(issues_after),
        summary=f"{verdict} {fix_summary}",
    )
