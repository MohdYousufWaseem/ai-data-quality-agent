"""
Deterministic data profiling -- no LLM calls in this file, on purpose.

This is a "tool" that an agent calls, not an agent itself. It takes a
pandas DataFrame and returns a DataProfile. Keeping this LLM-free keeps
it fast, cheap, and testable with plain unit tests.
"""

import pandas as pd
import numpy as np
from src.schemas import DataProfile, ColumnProfile

# Columns with more distinct values than this are treated as high-cardinality
# (e.g. customer_id, transaction_id, UUIDs) and do NOT get a value_counts
# dictionary stored -- doing so for a million-row ID column would mean
# storing up to a million entries per snapshot, which is both wasteful and
# useless for drift detection (an ID column isn't a "distribution").
MAX_DISTRIBUTION_CATEGORIES = 100

QUANTILE_LEVELS = {"p10": 0.10, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90}


def profile_dataframe(df: pd.DataFrame, source_name: str) -> DataProfile:
    columns: list[ColumnProfile] = []
    row_count = len(df)

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))

        col_profile = ColumnProfile(
            name=col,
            dtype=str(series.dtype),
            null_count=null_count,
            null_pct=round(null_count / row_count * 100, 2) if row_count else 0.0,
            unique_count=unique_count,
            sample_values=[str(v) for v in series.dropna().unique()[:5]],
        )

        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) > 0:
                col_profile.min_value = float(clean.min())
                col_profile.max_value = float(clean.max())
                col_profile.mean_value = round(float(clean.mean()), 2)
                col_profile.std_value = round(float(clean.std()), 2) if len(clean) > 1 else 0.0

                # A single vectorized call for all five quantiles, rather
                # than calling .quantile() five separate times -- matters
                # once this runs against million-row columns.
                q = clean.quantile(list(QUANTILE_LEVELS.values()))
                col_profile.quantiles = {
                    label: round(float(q.loc[level]), 4)
                    for label, level in QUANTILE_LEVELS.items()
                }
        else:
            # Categorical/text column: only store the full frequency table
            # for low-cardinality columns. value_counts() itself is a single
            # vectorized, hash-based pass over the column (cheap even at
            # millions of rows) -- what we guard here is how much of that
            # result we keep and serialize, not whether we compute it.
            if 0 < unique_count <= MAX_DISTRIBUTION_CATEGORIES:
                counts = series.dropna().astype(str).value_counts()
                col_profile.value_counts = {str(k): int(v) for k, v in counts.items()}

        columns.append(col_profile)

    duplicate_row_count = int(df.duplicated().sum())

    return DataProfile(
        source_name=source_name,
        row_count=row_count,
        column_count=len(df.columns),
        columns=columns,
        duplicate_row_count=duplicate_row_count,
    )

