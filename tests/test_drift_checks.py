"""
Known-answer tests for the pure drift comparison logic. We hand-build
two DataProfile objects with known differences instead of going through
the CSVs or the database, so these tests are fast and don't depend on
storage state.
"""

from src.schemas import DataProfile, ColumnProfile
from src.tools.drift_checks import compare_profiles


def make_profile(row_count, columns: list[ColumnProfile]) -> DataProfile:
    return DataProfile(
        source_name="test_source",
        row_count=row_count,
        column_count=len(columns),
        columns=columns,
        duplicate_row_count=0,
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
    current = make_profile(101, [col])  # tiny, insignificant change
    findings = compare_profiles(baseline, current)
    assert findings == []
