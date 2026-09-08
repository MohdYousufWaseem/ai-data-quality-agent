"""
Pure drift comparison logic. Takes two DataProfile snapshots and returns
DriftFindings. Deliberately has zero storage or LLM code in it, so it's
trivially unit-testable with two hand-built DataProfile objects -- same
principle as tools/quality_checks.py in Phase 1.

Thresholds below are simple and explainable on purpose. Tune them once
you see how noisy/quiet they are on your real data.
"""

from src.schemas import DataProfile, DriftFinding

VOLUME_CHANGE_THRESHOLD = 0.15       # 15% row-count change triggers a finding
MISSING_RATE_WARN_PTS = 5.0          # percentage-point shift in null rate
MISSING_RATE_CRITICAL_PTS = 15.0
DISTRIBUTION_SHIFT_Z = 1.5           # mean shift, in units of baseline std dev


def compare_profiles(baseline: DataProfile, current: DataProfile) -> list[DriftFinding]:
    findings: list[DriftFinding] = []

    findings += _check_volume(baseline, current)

    baseline_cols = {c.name: c for c in baseline.columns}
    current_cols = {c.name: c for c in current.columns}

    findings += _check_schema_changes(baseline_cols, current_cols)
    findings += _check_column_level_drift(baseline_cols, current_cols)

    return findings


def _check_volume(baseline: DataProfile, current: DataProfile) -> list[DriftFinding]:
    if baseline.row_count == 0:
        return []
    pct_change = (current.row_count - baseline.row_count) / baseline.row_count

    if pct_change <= -VOLUME_CHANGE_THRESHOLD:
        return [DriftFinding(
            finding_type="volume_drop",
            severity="critical",
            description=f"Row count dropped {abs(pct_change) * 100:.1f}% "
                         f"({baseline.row_count} -> {current.row_count}).",
            previous_value=str(baseline.row_count),
            current_value=str(current.row_count),
        )]
    if pct_change >= VOLUME_CHANGE_THRESHOLD:
        return [DriftFinding(
            finding_type="volume_spike",
            severity="warning",
            description=f"Row count increased {pct_change * 100:.1f}% "
                         f"({baseline.row_count} -> {current.row_count}).",
            previous_value=str(baseline.row_count),
            current_value=str(current.row_count),
        )]
    return []


def _check_schema_changes(baseline_cols: dict, current_cols: dict) -> list[DriftFinding]:
    findings = []
    for name in baseline_cols:
        if name not in current_cols:
            findings.append(DriftFinding(
                finding_type="schema_column_removed",
                severity="critical",
                column=name,
                description=f"Column '{name}' was present before but is missing now.",
            ))
    for name in current_cols:
        if name not in baseline_cols:
            findings.append(DriftFinding(
                finding_type="schema_column_added",
                severity="warning",
                column=name,
                description=f"New column '{name}' appeared that wasn't present before.",
            ))
    return findings


def _check_column_level_drift(baseline_cols: dict, current_cols: dict) -> list[DriftFinding]:
    findings = []
    shared = baseline_cols.keys() & current_cols.keys()

    for name in shared:
        b, c = baseline_cols[name], current_cols[name]

        if b.dtype != c.dtype:
            findings.append(DriftFinding(
                finding_type="dtype_changed",
                severity="warning",
                column=name,
                description=f"Column '{name}' changed type from {b.dtype} to {c.dtype}.",
                previous_value=b.dtype,
                current_value=c.dtype,
            ))

        null_diff = round(c.null_pct - b.null_pct, 2)
        if abs(null_diff) >= MISSING_RATE_WARN_PTS:
            severity = "critical" if abs(null_diff) >= MISSING_RATE_CRITICAL_PTS else "warning"
            direction = "jumped" if null_diff > 0 else "dropped"
            findings.append(DriftFinding(
                finding_type="missing_rate_shift",
                severity=severity,
                column=name,
                description=f"Missing-value rate on '{name}' {direction} from "
                             f"{b.null_pct}% to {c.null_pct}%.",
                previous_value=f"{b.null_pct}%",
                current_value=f"{c.null_pct}%",
            ))

        if b.std_value and b.std_value > 0 and b.mean_value is not None and c.mean_value is not None:
            z = abs(c.mean_value - b.mean_value) / b.std_value
            if z >= DISTRIBUTION_SHIFT_Z:
                findings.append(DriftFinding(
                    finding_type="distribution_shift",
                    severity="warning",
                    column=name,
                    description=f"Average '{name}' shifted from {b.mean_value} to "
                                 f"{c.mean_value} -- a notable change relative to its "
                                 f"historical spread.",
                    previous_value=str(b.mean_value),
                    current_value=str(c.mean_value),
                ))

    return findings
