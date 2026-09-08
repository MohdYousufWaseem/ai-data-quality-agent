"""
Tests for the enhanced profile_dataframe(): quantiles for numeric columns,
and capped value_counts for low-cardinality categorical columns only.
"""

import pandas as pd
from src.tools.profiling import profile_dataframe, MAX_DISTRIBUTION_CATEGORIES


def test_numeric_column_gets_quantiles():
    df = pd.DataFrame({"age": list(range(1, 101))})  # 1..100
    profile = profile_dataframe(df, "test.csv")
    col = profile.columns[0]
    assert set(col.quantiles.keys()) == {"p10", "p25", "p50", "p75", "p90"}
    # For 1..100, p50 (median) should land right around 50-51.
    assert 49 <= col.quantiles["p50"] <= 52


def test_low_cardinality_categorical_gets_value_counts():
    df = pd.DataFrame({"region": ["North"] * 60 + ["South"] * 40})
    profile = profile_dataframe(df, "test.csv")
    col = profile.columns[0]
    assert col.value_counts == {"North": 60, "South": 40}


def test_high_cardinality_column_does_not_get_value_counts():
    # One unique value per row -- like a customer_id or UUID column.
    df = pd.DataFrame({"customer_id": [f"C{i}" for i in range(500)]})
    profile = profile_dataframe(df, "test.csv")
    col = profile.columns[0]
    assert col.value_counts == {}
    assert col.unique_count == 500
    # sample_values should still be populated even without full value_counts.
    assert len(col.sample_values) > 0


def test_value_counts_excludes_nulls():
    df = pd.DataFrame({"status": ["Active", "Active", None, "Inactive"]})
    profile = profile_dataframe(df, "test.csv")
    col = profile.columns[0]
    assert "None" not in col.value_counts
    assert sum(col.value_counts.values()) == 3  # nulls excluded from the count


def test_cardinality_boundary_is_configurable_constant():
    # A column with exactly MAX_DISTRIBUTION_CATEGORIES uniques should still
    # get value_counts; one above should not. This locks in the boundary
    # behavior described in the spec ("<=100 gets stored").
    at_limit = pd.DataFrame({"c": [f"v{i}" for i in range(MAX_DISTRIBUTION_CATEGORIES)]})
    over_limit = pd.DataFrame({"c": [f"v{i}" for i in range(MAX_DISTRIBUTION_CATEGORIES + 1)]})

    profile_at = profile_dataframe(at_limit, "test.csv")
    profile_over = profile_dataframe(over_limit, "test.csv")

    assert len(profile_at.columns[0].value_counts) == MAX_DISTRIBUTION_CATEGORIES
    assert profile_over.columns[0].value_counts == {}
