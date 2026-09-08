"""
Rule-based and statistical quality checks. Each function inspects a
DataFrame and returns zero or more QualityIssue objects. This is where
you'd add more checks over time (referential integrity, schema drift,
custom business rules) without touching the agent orchestration code.
"""

import re
import pandas as pd
from src.schemas import QualityIssue

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def check_duplicates(df: pd.DataFrame, subset: list[str] | None = None) -> list[QualityIssue]:
    """
    Flags duplicate records. By default this ignores obvious surrogate-key
    columns (e.g. 'id', 'customer_id') since two rows with the same name,
    email, and phone but different auto-generated IDs are still the same
    real-world duplicate customer -- comparing on every raw column would
    miss exactly that case.
    """
    if subset is None:
        subset = [c for c in df.columns if not c.lower().endswith("id") and c.lower() != "id"]

    dup_mask = df.duplicated(subset=subset, keep="first")
    count = int(dup_mask.sum())
    if count == 0:
        return []
    return [QualityIssue(
        issue_type="duplicate_records",
        severity="critical",
        affected_row_count=count,
        affected_pct=round(count / len(df) * 100, 2),
        description=f"{count} rows are duplicates of an earlier row "
                     f"(matched on {', '.join(subset)}).",
        sample_row_indices=df[dup_mask].index[:10].tolist(),
    )]


def check_invalid_emails(df: pd.DataFrame, column: str = "email") -> list[QualityIssue]:
    if column not in df.columns:
        return []
    non_null = df[column].dropna()
    invalid_mask = ~non_null.astype(str).str.match(EMAIL_REGEX)
    count = int(invalid_mask.sum())
    if count == 0:
        return []
    bad_indices = non_null[invalid_mask].index[:10].tolist()
    return [QualityIssue(
        issue_type="invalid_email",
        severity="warning",
        column=column,
        affected_row_count=count,
        affected_pct=round(count / len(df) * 100, 2),
        description=f"{count} rows have an email that doesn't match a valid email pattern.",
        sample_row_indices=bad_indices,
    )]


def check_missing_values(df: pd.DataFrame, warn_threshold_pct: float = 3.0) -> list[QualityIssue]:
    issues = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count == 0:
            continue
        pct = round(null_count / len(df) * 100, 2)
        severity = "warning" if pct >= warn_threshold_pct else "info"
        issues.append(QualityIssue(
            issue_type="missing_values",
            severity=severity,
            column=col,
            affected_row_count=null_count,
            affected_pct=pct,
            description=f"Column '{col}' is missing {pct}% of values.",
            sample_row_indices=df[df[col].isna()].index[:10].tolist(),
        ))
    return issues


def check_outliers_iqr(df: pd.DataFrame, columns: list[str] | None = None) -> list[QualityIssue]:
    """Flags numeric outliers using the 1.5*IQR rule."""
    issues = []
    numeric_cols = columns or df.select_dtypes(include="number").columns.tolist()

    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if len(series) < 4:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_mask = (series < lower) | (series > upper)
        count = int(outlier_mask.sum())
        if count == 0:
            continue
        issues.append(QualityIssue(
            issue_type="statistical_outlier",
            severity="warning",
            column=col,
            affected_row_count=count,
            affected_pct=round(count / len(df) * 100, 2),
            description=(
                f"Column '{col}' has {count} outlier(s) outside the expected "
                f"range [{round(lower,1)}, {round(upper,1)}]."
            ),
            sample_row_indices=series[outlier_mask].index[:10].tolist(),
        ))
    return issues


def run_all_checks(df: pd.DataFrame) -> list[QualityIssue]:
    """Convenience function the Quality Analysis Agent calls."""
    issues: list[QualityIssue] = []
    issues += check_duplicates(df)
    issues += check_invalid_emails(df)
    issues += check_missing_values(df)
    issues += check_outliers_iqr(df)
    return issues
