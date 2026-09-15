"""
Unit tests for investigate_volume_anomaly() -- hand-built profiles with
known, deliberate causes, so we can assert the agent actually finds the
right answer rather than just "runs without crashing."
"""

from src.schemas import DataProfile, ColumnProfile, DriftFinding
from src.tools.root_cause import investigate_volume_anomaly


def make_profile(row_count, columns):
    return DataProfile(
        source_name="test_source", row_count=row_count,
        column_count=len(columns), columns=columns, duplicate_row_count=0,
    )


def test_identifies_primary_suspect_for_volume_drop():
    # Baseline: 40 rows, 10 each across 4 regions.
    baseline_region = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=4,
        value_counts={"North": 10, "South": 10, "East": 10, "West": 10},
    )
    # Current: North vanished entirely, other regions unchanged -- classic
    # "North region has been missing" scenario.
    current_region = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=3,
        value_counts={"South": 10, "East": 10, "West": 10},
    )
    baseline = make_profile(40, [baseline_region])
    current = make_profile(30, [current_region])

    volume_finding = DriftFinding(
        finding_type="volume_drop", severity="critical",
        description="Row count dropped 25%.",
    )

    report = investigate_volume_anomaly(baseline, current, volume_finding)

    assert report.triggered is True
    assert report.total_row_change == -10
    assert report.primary_suspect is not None
    assert report.primary_suspect.category == "North"
    assert report.primary_suspect.column == "region"
    assert report.primary_suspect.contribution_pct == 100.0
    assert "North" in report.conclusion


def test_no_dominant_cause_when_drop_is_broad_based():
    # Every region shrinks by roughly the same amount -- no single segment
    # should be blamed; the conclusion should say so.
    baseline_region = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=4,
        value_counts={"North": 10, "South": 10, "East": 10, "West": 10},
    )
    current_region = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=4,
        value_counts={"North": 8, "South": 8, "East": 7, "West": 7},
    )
    baseline = make_profile(40, [baseline_region])
    current = make_profile(30, [current_region])

    volume_finding = DriftFinding(
        finding_type="volume_drop", severity="critical",
        description="Row count dropped 25%.",
    )

    report = investigate_volume_anomaly(baseline, current, volume_finding)

    assert report.triggered is True
    assert report.primary_suspect is None
    assert "spread across" in report.conclusion or "broad-based" in report.conclusion


def test_no_categorical_columns_available_gives_broad_based_conclusion():
    # No value_counts on any shared column -- e.g. high-cardinality columns
    # only, or old snapshots without this feature. Should not crash.
    baseline_col = ColumnProfile(name="customer_id", dtype="object", null_count=0,
                                  null_pct=0.0, unique_count=40)
    current_col = ColumnProfile(name="customer_id", dtype="object", null_count=0,
                                 null_pct=0.0, unique_count=30)
    baseline = make_profile(40, [baseline_col])
    current = make_profile(30, [current_col])

    volume_finding = DriftFinding(finding_type="volume_drop", severity="critical",
                                   description="Row count dropped 25%.")

    report = investigate_volume_anomaly(baseline, current, volume_finding)
    assert report.triggered is True
    assert report.primary_suspect is None
    assert "no single category" in report.conclusion.lower()


def test_volume_spike_attributes_growth_correctly():
    baseline_region = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=3,
        value_counts={"North": 10, "South": 10, "East": 10},
    )
    current_region = ColumnProfile(
        name="region", dtype="object", null_count=0, null_pct=0.0, unique_count=3,
        value_counts={"North": 10, "South": 10, "East": 40},
    )
    baseline = make_profile(30, [baseline_region])
    current = make_profile(60, [current_region])

    volume_finding = DriftFinding(finding_type="volume_spike", severity="warning",
                                   description="Row count increased 100%.")

    report = investigate_volume_anomaly(baseline, current, volume_finding)
    assert report.primary_suspect is not None
    assert report.primary_suspect.category == "East"
    assert report.primary_suspect.contribution_pct == 100.0
