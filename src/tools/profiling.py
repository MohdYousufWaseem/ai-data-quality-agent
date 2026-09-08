"""
Deterministic data profiling — no LLM calls in this file, on purpose.

This is a "tool" that an agent calls, not an agent itself. It takes a
pandas DataFrame and returns a DataProfile. Keeping this LLM-free keeps
it fast, cheap, and testable with plain unit tests.
"""

import pandas as pd
import numpy as np
from src.schemas import DataProfile, ColumnProfile


def profile_dataframe(df: pd.DataFrame, source_name: str) -> DataProfile:
    columns: list[ColumnProfile] = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        col_profile = ColumnProfile(
            name=col,
            dtype=str(series.dtype),
            null_count=null_count,
            null_pct=round(null_count / len(df) * 100, 2) if len(df) else 0.0,
            unique_count=int(series.nunique(dropna=True)),
            sample_values=[str(v) for v in series.dropna().unique()[:5]],
        )

        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) > 0:
                col_profile.min_value = float(clean.min())
                col_profile.max_value = float(clean.max())
                col_profile.mean_value = round(float(clean.mean()), 2)
                col_profile.std_value = round(float(clean.std()), 2) if len(clean) > 1 else 0.0

        columns.append(col_profile)

    duplicate_row_count = int(df.duplicated().sum())

    return DataProfile(
        source_name=source_name,
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        duplicate_row_count=duplicate_row_count,
    )
