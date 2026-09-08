from src.schemas import DataProfile, ColumnProfile
from src.tools.drift_checks import compare_profiles


def make_profile(row_count, columns):
    return DataProfile(
        source_name="test_source", row_count=row_count,
        column_count=len(columns), columns=columns, duplicate_row_count=0,
    )


def test_volume_drop_detected():
    baseline = make_profile(100, [ColumnProfile(name="x", dtype="int64", null_count=0,
                                                  null_pct=0.0, unique_count=100)])
    current = make_profile(70, [ColumnProfile(name="x", dtype="int64", null_count=0,
                                                null_pct=0.0, unique_count=70)])
    findings = compare_profiles(baseline, current)
    volume_findings = [f for f in findings if f.finding_type == "volume_drop"]
    assert len(volume_findings) == 1
    assert volume_findings[0].severity == "critical"


def test_missing_rate_spike_detected():
    baseline = make_profile(100, [ColumnProfile(name="phone", dtype="object", null_count=2,
                                                  null_pct=2.0, unique_count=98)])
    current = make_profile(100, [ColumnProfile(name="phone", dtype="object", null_count=12,
                                                 null_pct=12.0, unique_count=88)])
    findings = compare_profiles(baseline, current)
    missing_findings = [f for f in findings if f.finding_type == "missing_rate_shift"]
    assert len(missing_findings) == 1
    assert missing_findings[0].column == "phone"


def test_schema_column_removed_and_added():
    baseline = make_profile(50, [
        ColumnProfile(name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=4),
    ])
    current = make_profile(50, [
        ColumnProfile(name="loyalty_tier", dtype="object", null_count=0, null_pct=0.0, unique_count=3),
    ])
    findings = compare_profiles(baseline, current)
    removed = [f for f in findings if f.finding_type == "schema_column_removed"]
    added = [f for f in findings if f.finding_type == "schema_column_added"]
    assert len(removed) == 1 and removed[0].column == "region"
    assert len(added) == 1 and added[0].column == "loyalty_tier"


def test_no_drift_when_stable():
    col = ColumnProfile(name="x", dtype="int64", null_count=5, null_pct=5.0,
                         unique_count=95, mean_value=10.0, std_value=2.0)
    baseline = make_profile(100, [col])
    current = make_profile(101, [col])
    findings = compare_profiles(baseline, current)
    assert findings == []


def test_volume_spike_detected():
    baseline = make_profile(100, [ColumnProfile(name="x", dtype="int64", null_count=0,
                                                  null_pct=0.0, unique_count=100)])
    current = make_profile(140, [ColumnProfile(name="x", dtype="int64", null_count=0,
                                                 null_pct=0.0, unique_count=140)])
    findings = compare_profiles(baseline, current)
    spike_findings = [f for f in findings if f.finding_type == "volume_spike"]
    assert len(spike_findings) == 1
    assert spike_findings[0].severity == "warning"


def test_dtype_change_detected():
    baseline = make_profile(50, [ColumnProfile(name="age", dtype="float64", null_count=0,
                                                 null_pct=0.0, unique_count=40)])
    current = make_profile(50, [ColumnProfile(name="age", dtype="int64", null_count=0,
                                                null_pct=0.0, unique_count=40)])
    findings = compare_profiles(baseline, current)
    dtype_findings = [f for f in findings if f.finding_type == "dtype_changed"]
    assert len(dtype_findings) == 1
    assert dtype_findings[0].previous_value == "float64"
    assert dtype_findings[0].current_value == "int64"


def test_numeric_mean_shift_detected():
    baseline = make_profile(100, [ColumnProfile(name="income", dtype="float64", null_count=0,
                                                  null_pct=0.0, unique_count=90,
                                                  mean_value=50000.0, std_value=5000.0)])
    current = make_profile(100, [ColumnProfile(name="income", dtype="float64", null_count=0,
                                                 null_pct=0.0, unique_count=90,
                                                 mean_value=65000.0, std_value=5000.0)])
    findings = compare_profiles(baseline, current)
    mean_findings = [f for f in findings if f.finding_type == "distribution_shift"]
    assert len(mean_findings) == 1
    assert "Mean shift" in mean_findings[0].description


def test_numeric_quantile_shift_detected():
    baseline_col = ColumnProfile(
        name="annual_income", dtype="float64", null_count=0, null_pct=0.0, unique_count=90,
        quantiles={"p10": 200000.0, "p25": 400000.0, "p50": 1800000.0,
                   "p75": 2200000.0, "p90": 2800000.0},
    )
    current_col = ColumnProfile(
        name="annual_income", dtype="float64", null_count=0, null_pct=0.0, unique_count=90,
        quantiles={"p10": 200000.0, "p25": 400000.0, "p50": 3200000.0,
                   "p75": 2200000.0, "p90": 2800000.0},
    )
    baseline = make_profile(100, [baseline_col])
    current = make_profile(100, [current_col])
    findings = compare_profiles(baseline, current)
    quantile_findings = [f for f in findings if f.finding_type == "numeric_quantile_shift"]
    assert len(quantile_findings) == 1
    assert "p50" in quantile_findings[0].description


def test_numeric_quantile_shift_ignores_small_changes():
    col = ColumnProfile(
        name="age", dtype="float64", null_count=0, null_pct=0.0, unique_count=90,
        quantiles={"p10": 20.0, "p25": 30.0, "p50": 40.0, "p75": 50.0, "p90": 60.0},
    )
    slightly_shifted = ColumnProfile(
        name="age", dtype="float64", null_count=0, null_pct=0.0, unique_count=90,
        quantiles={"p10": 20.0, "p25": 31.0, "p50": 41.0, "p75": 51.0, "p90": 62.0},
    )
    baseline = make_profile(100, [col])
    current = make_profile(100, [slightly_shifted])
    findings = compare_profiles(baseline, current)
    assert [f for f in findings if f.finding_type == "numeric_quantile_shift"] == []


def test_numeric_quantile_shift_handles_zero_baseline():
    baseline_col = ColumnProfile(
        name="balance", dtype="float64", null_count=0, null_pct=0.0, unique_count=50,
        quantiles={"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 10.0, "p90": 20.0},
    )
    current_col = ColumnProfile(
        name="balance", dtype="float64", null_count=0, null_pct=0.0, unique_count=50,
        quantiles={"p10": 5.0, "p25": 0.0, "p50": 0.0, "p75": 10.0, "p90": 20.0},
    )
    baseline = make_profile(100, [baseline_col])
    current = make_profile(100, [current_col])
    # Should not raise a ZeroDivisionError, and should flag the 0 -> 5 shift on p10.
    findings = compare_profiles(baseline, current)
    p10_findings = [f for f in findings if f.finding_type == "numeric_quantile_shift"
                    and "p10" in f.description]
    assert len(p10_findings) == 1


def test_categorical_distribution_shift_detected():
    baseline_col = ColumnProfile(
        name="city", dtype="object", null_count=0, null_pct=0.0, unique_count=2,
        value_counts={"Hyderabad": 12, "Mumbai": 88},
    )
    current_col = ColumnProfile(
        name="city", dtype="object", null_count=0, null_pct=0.0, unique_count=2,
        value_counts={"Hyderabad": 43, "Mumbai": 57},
    )
    baseline = make_profile(100, [baseline_col])
    current = make_profile(100, [current_col])
    findings = compare_profiles(baseline, current)
    cat_findings = [f for f in findings if f.finding_type == "categorical_distribution_shift"]
    hyderabad_findings = [f for f in cat_findings if "Hyderabad" in f.description]
    assert len(hyderabad_findings) == 1
    assert "increased" in hyderabad_findings[0].description


def test_new_categorical_category_detected():
    baseline_col = ColumnProfile(
        name="status", dtype="object", null_count=0, null_pct=0.0, unique_count=1,
        value_counts={"Active": 100},
    )
    current_col = ColumnProfile(
        name="status", dtype="object", null_count=0, null_pct=0.0, unique_count=2,
        value_counts={"Active": 85, "Suspended": 15},
    )
    baseline = make_profile(100, [baseline_col])
    current = make_profile(100, [current_col])
    findings = compare_profiles(baseline, current)
    new_cat = [f for f in findings if f.finding_type == "categorical_distribution_shift"
               and "Suspended" in f.description]
    assert len(new_cat) == 1
    assert "New category" in new_cat[0].description


def test_disappearing_categorical_category_detected():
    baseline_col = ColumnProfile(
        name="status", dtype="object", null_count=0, null_pct=0.0, unique_count=2,
        value_counts={"Active": 85, "Trial": 15},
    )
    current_col = ColumnProfile(
        name="status", dtype="object", null_count=0, null_pct=0.0, unique_count=1,
        value_counts={"Active": 100},
    )
    baseline = make_profile(100, [baseline_col])
    current = make_profile(100, [current_col])
    findings = compare_profiles(baseline, current)
    disappeared = [f for f in findings if f.finding_type == "categorical_distribution_shift"
                   and "Trial" in f.description]
    assert len(disappeared) == 1
    assert "disappeared" in disappeared[0].description


def test_categorical_shift_ignores_small_changes():
    baseline_col = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=2,
        value_counts={"North": 50, "South": 50},
    )
    current_col = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=2,
        value_counts={"North": 53, "South": 47},
    )
    baseline = make_profile(100, [baseline_col])
    current = make_profile(100, [current_col])
    findings = compare_profiles(baseline, current)
    assert [f for f in findings if f.finding_type == "categorical_distribution_shift"] == []


def test_missing_value_counts_does_not_crash_or_flag():
    """Columns without value_counts (e.g. high-cardinality columns, or old
    snapshots saved before this field existed) must be safely skipped by
    the categorical check rather than raising or producing false findings."""
    baseline_col = ColumnProfile(name="customer_id", dtype="object", null_count=0,
                                  null_pct=0.0, unique_count=100000)
    current_col = ColumnProfile(name="customer_id", dtype="object", null_count=0,
                                 null_pct=0.0, unique_count=120000)
    baseline = make_profile(100000, [baseline_col])
    current = make_profile(120000, [current_col])
    findings = compare_profiles(baseline, current)
    assert [f for f in findings if f.finding_type == "categorical_distribution_shift"] == []


def test_old_snapshot_json_without_new_fields_is_still_loadable():
    """Simulates a DataProfile saved to DuckDB before value_counts/quantiles
    existed -- the JSON simply won't have those keys. Confirms backward
    compatibility via Field(default_factory=dict)."""
    old_json = """
    {
        "source_name": "legacy.csv",
        "row_count": 10,
        "column_count": 1,
        "duplicate_row_count": 0,
        "columns": [
            {
                "name": "age", "dtype": "int64", "null_count": 0, "null_pct": 0.0,
                "unique_count": 8, "sample_values": ["25", "30"],
                "min_value": 20.0, "max_value": 60.0, "mean_value": 35.0, "std_value": 8.0
            }
        ]
    }
    """
    profile = DataProfile.model_validate_json(old_json)
    assert profile.columns[0].value_counts == {}
    assert profile.columns[0].quantiles == {}

    # And it should compare cleanly against a "new" profile without erroring.
    new_col = ColumnProfile(name="age", dtype="int64", null_count=0, null_pct=0.0,
                             unique_count=8, mean_value=35.0, std_value=8.0,
                             quantiles={"p10": 22.0, "p25": 28.0, "p50": 35.0,
                                        "p75": 42.0, "p90": 55.0})
    current = make_profile(10, [new_col])
    findings = compare_profiles(profile, current)
    # No quantile finding should appear since the baseline had none to compare.
    assert [f for f in findings if f.finding_type == "numeric_quantile_shift"] == []
