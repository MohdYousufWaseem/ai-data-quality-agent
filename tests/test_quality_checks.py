"""
'Known-answer' tests: sample_customers.csv was seeded with exact,
known issues (see data/sample_customers.csv). These tests confirm the
deterministic checks actually catch them -- this is how you validate
an agentic pipeline's building blocks before trusting the LLM layer
on top of them.

Run with: pytest tests/
"""

import pandas as pd
import os
from src.tools.quality_checks import (
    check_duplicates,
    check_invalid_emails,
    check_missing_values,
    check_outliers_iqr,
)

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample_customers.csv")


def load_df():
    return pd.read_csv(DATA_PATH)


def test_duplicates_detected():
    df = load_df()
    issues = check_duplicates(df)
    assert len(issues) == 1
    # Rows 5 and 10 (0-indexed: 4, 9) are duplicates of row 1
    assert issues[0].affected_row_count == 2


def test_invalid_emails_detected():
    df = load_df()
    issues = check_invalid_emails(df)
    assert len(issues) == 1
    # vikram.singh#gmail.com and manoj.tiwari@ are malformed
    assert issues[0].affected_row_count == 2


def test_missing_values_detected():
    df = load_df()
    issues = check_missing_values(df)
    phone_issue = next(i for i in issues if i.column == "phone")
    age_issue = next(i for i in issues if i.column == "age")
    assert phone_issue.affected_row_count == 3
    assert age_issue.affected_row_count == 1


def test_age_outliers_detected():
    df = load_df()
    issues = check_outliers_iqr(df, columns=["age"])
    assert len(issues) == 1
    # age=150 and age=-5 are both outside the IQR fence
    assert issues[0].affected_row_count == 2
