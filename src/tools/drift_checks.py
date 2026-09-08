from src.schemas import DataProfile, DriftFinding

VOLUME_CHANGE_THRESHOLD = 0.15
MISSING_RATE_WARN_PTS = 5.0
MISSING_RATE_CRITICAL_PTS = 15.0
MEAN_SHIFT_Z = 1.5
CATEGORICAL_SHIFT_PCT = 10.0
NUMERIC_QUANTILE_SHIFT_PCT = 20.0
QUANTILE_LABELS = ("p10", "p25", "p50", "p75", "p90")


def compare_profiles(baseline: DataProfile, current: DataProfile) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    findings += _check_volume(baseline, current)
    baseline_cols = {c.name: c for c in baseline.columns}
    current_cols = {c.name: c for c in current.columns}
    findings += _check_schema_changes(baseline_cols, current_cols)
    findings += _check_column_level_drift(baseline_cols, current_cols)
    return findings


def _check_volume(baseline, current):
    if baseline.row_count == 0:
        return []
    pct_change = (current.row_count - baseline.row_count) / baseline.row_count
    if pct_change <= -VOLUME_CHANGE_THRESHOLD:
        return [DriftFinding(
            finding_type="volume_drop", severity="critical",
            description=f"Row count dropped {abs(pct_change) * 100:.1f}% "
                         f"({baseline.row_count} -> {current.row_count}).",
            previous_value=str(baseline.row_count), current_value=str(current.row_count),
        )]
    if pct_change >= VOLUME_CHANGE_THRESHOLD:
        return [DriftFinding(
            finding_type="volume_spike", severity="warning",
            description=f"Row count increased {pct_change * 100:.1f}% "
                         f"({baseline.row_count} -> {current.row_count}).",
            previous_value=str(baseline.row_count), current_value=str(current.row_count),
        )]
    return []


def _check_schema_changes(baseline_cols, current_cols):
    findings = []
    for name in baseline_cols:
        if name not in current_cols:
            findings.append(DriftFinding(
                finding_type="schema_column_removed", severity="critical", column=name,
                description=f"Column '{name}' was present before but is missing now.",
            ))
    for name in current_cols:
        if name not in baseline_cols:
            findings.append(DriftFinding(
                finding_type="schema_column_added", severity="warning", column=name,
                description=f"New column '{name}' appeared that wasn't present before.",
            ))
    return findings


def _check_column_level_drift(baseline_cols, current_cols):
    findings = []
    shared = baseline_cols.keys() & current_cols.keys()
    for name in shared:
        b, c = baseline_cols[name], current_cols[name]

        if b.dtype != c.dtype:
            findings.append(DriftFinding(
                finding_type="dtype_changed", severity="warning", column=name,
                description=f"Column '{name}' changed type from {b.dtype} to {c.dtype}.",
                previous_value=b.dtype, current_value=c.dtype,
            ))

        null_diff = round(c.null_pct - b.null_pct, 2)
        if abs(null_diff) >= MISSING_RATE_WARN_PTS:
            severity = "critical" if abs(null_diff) >= MISSING_RATE_CRITICAL_PTS else "warning"
            direction = "jumped" if null_diff > 0 else "dropped"
            findings.append(DriftFinding(
                finding_type="missing_rate_shift", severity=severity, column=name,
                description=f"Missing-value rate on '{name}' {direction} from "
                             f"{b.null_pct}% to {c.null_pct}%.",
                previous_value=f"{b.null_pct}%", current_value=f"{c.null_pct}%",
            ))

        findings += _check_mean_shift(b, c, name)
        findings += _check_quantile_shift(b, c, name)
        findings += _check_categorical_shift(b, c, name)

    return findings


def _check_mean_shift(b, c, name) -> list[DriftFinding]:
    """Original mean/std-based numeric drift check, kept as-is. This alone
    can miss shifts where the mean stays flat but the shape of the
    distribution changes (e.g. a bimodal split) -- that's what the
    quantile check below is for; this one stays for continuity."""
    if b.std_value and b.std_value > 0 and b.mean_value is not None and c.mean_value is not None:
        z = abs(c.mean_value - b.mean_value) / b.std_value
        if z >= MEAN_SHIFT_Z:
            return [DriftFinding(
                finding_type="distribution_shift", severity="warning", column=name,
                description=f"Mean shift: average '{name}' moved from {b.mean_value} to "
                             f"{c.mean_value} -- a notable change relative to its "
                             f"historical spread.",
                previous_value=str(b.mean_value), current_value=str(c.mean_value),
            )]
    return []


def _check_quantile_shift(b, c, name) -> list[DriftFinding]:
    """Compares stored quantiles (p10/p25/p50/p75/p90) rather than just the
    mean, so shifts in the shape of a numeric distribution show up even
    when the average doesn't move much."""
    findings = []
    if not b.quantiles or not c.quantiles:
        return findings

    for label in QUANTILE_LABELS:
        if label not in b.quantiles or label not in c.quantiles:
            continue
        baseline_q = b.quantiles[label]
        current_q = c.quantiles[label]

        if baseline_q == 0:
            # Avoid division by zero; only flag if current is meaningfully
            # non-zero, since 0 -> 0 is not drift.
            if current_q != 0:
                findings.append(DriftFinding(
                    finding_type="numeric_quantile_shift", severity="warning", column=name,
                    description=f"'{name}' {label} shifted from {baseline_q} to {current_q}.",
                    previous_value=str(baseline_q), current_value=str(current_q),
                ))
            continue

        pct_change = abs(current_q - baseline_q) / abs(baseline_q) * 100
        if pct_change >= NUMERIC_QUANTILE_SHIFT_PCT:
            findings.append(DriftFinding(
                finding_type="numeric_quantile_shift", severity="warning", column=name,
                description=f"'{name}' {label} shifted from {baseline_q} to {current_q} "
                             f"({pct_change:.1f}% change).",
                previous_value=str(baseline_q), current_value=str(current_q),
            ))
    return findings


def _check_categorical_shift(b, c, name) -> list[DriftFinding]:
    """Compares category frequency shares between baseline and current.
    Only runs when both snapshots actually captured value_counts for this
    column (low-cardinality columns only -- see profiling.py). Old
    snapshots saved before this feature existed will simply have an empty
    value_counts dict, so this safely no-ops for them rather than erroring."""
    findings = []
    if not b.value_counts or not c.value_counts:
        return findings

    b_total = sum(b.value_counts.values()) or 1
    c_total = sum(c.value_counts.values()) or 1
    all_categories = set(b.value_counts) | set(c.value_counts)

    for category in sorted(all_categories):
        baseline_pct = b.value_counts.get(category, 0) / b_total * 100
        current_pct = c.value_counts.get(category, 0) / c_total * 100
        diff = abs(current_pct - baseline_pct)

        if diff >= CATEGORICAL_SHIFT_PCT:
            if category not in b.value_counts:
                desc = (f"New category '{category}' in '{name}' appeared, now "
                        f"{current_pct:.1f}% of rows.")
            elif category not in c.value_counts:
                desc = (f"Category '{category}' in '{name}' disappeared "
                        f"(was {baseline_pct:.1f}% of rows).")
            else:
                direction = "increased" if current_pct > baseline_pct else "decreased"
                desc = (f"Category '{category}' in '{name}' {direction} from "
                        f"{baseline_pct:.1f}% to {current_pct:.1f}%.")

            findings.append(DriftFinding(
                finding_type="categorical_distribution_shift", severity="warning", column=name,
                description=desc,
                previous_value=f"{baseline_pct:.1f}%", current_value=f"{current_pct:.1f}%",
            ))

    return findings

