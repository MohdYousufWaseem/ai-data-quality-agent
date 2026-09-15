"""
Deterministic root-cause investigation for volume anomalies. No LLM call,
no raw SQL, no live queries against a database -- it works entirely off
the value_counts already captured in two DataProfile snapshots (see
tools/profiling.py). This is the same principle as the rest of the
pipeline: compute the facts in plain code, let the LLM only narrate them.

The core idea: if total row count dropped by N rows, and one category in
some categorical column also dropped by roughly N rows while other
categories stayed flat, that category is very likely the cause -- e.g.
"North region rows vanished" rather than "everything shrank evenly."
"""

from src.schemas import DataProfile, DriftFinding, RootCauseCandidate, RootCauseReport

# If the single best candidate explains at least this % of the total
# row-count change, we call it out as a "primary suspect" rather than
# just listing it as one of several partial contributors.
PRIMARY_SUSPECT_THRESHOLD_PCT = 50.0


def investigate_volume_anomaly(
    baseline_profile: DataProfile,
    current_profile: DataProfile,
    volume_finding: DriftFinding,
) -> RootCauseReport:
    total_change = current_profile.row_count - baseline_profile.row_count
    is_drop = volume_finding.finding_type == "volume_drop"

    candidates = _find_candidates(baseline_profile, current_profile, is_drop)

    if not candidates:
        return RootCauseReport(
            triggered=True,
            anomaly_type=volume_finding.finding_type,
            total_row_change=total_change,
            conclusion=(
                f"Row count changed by {total_change} but no single category in "
                f"any tracked categorical column explains it -- the change looks "
                f"broad-based rather than concentrated in one segment."
            ),
        )

    top = candidates[0]
    others = candidates[1:4]  # keep a few runners-up for transparency

    if top.contribution_pct >= PRIMARY_SUSPECT_THRESHOLD_PCT:
        cause_phrase = (
            f"its disappearance from the dataset" if is_drop and top.current_count == 0
            else f"its decline" if is_drop
            else f"its surge"
        )
        conclusion = (
            f"{top.contribution_pct:.0f}% of the row-count change is attributable to "
            f"'{top.category}' in column '{top.column}': it went from "
            f"{top.baseline_count} rows to {top.current_count} rows. "
            f"{cause_phrase.capitalize()} largely explains the overall "
            f"{'drop' if is_drop else 'spike'}."
        )
        return RootCauseReport(
            triggered=True,
            anomaly_type=volume_finding.finding_type,
            total_row_change=total_change,
            primary_suspect=top,
            other_candidates=others,
            conclusion=conclusion,
        )

    conclusion = (
        f"Row count changed by {total_change}, but no single category explains a "
        f"majority of it -- the closest contributor is '{top.category}' in "
        f"'{top.column}' at {top.contribution_pct:.0f}%. The change appears "
        f"spread across multiple segments rather than caused by one."
    )
    return RootCauseReport(
        triggered=True,
        anomaly_type=volume_finding.finding_type,
        total_row_change=total_change,
        other_candidates=[top] + others,
        conclusion=conclusion,
    )


def _find_candidates(
    baseline_profile: DataProfile, current_profile: DataProfile, is_drop: bool
) -> list[RootCauseCandidate]:
    baseline_cols = {c.name: c for c in baseline_profile.columns}
    current_cols = {c.name: c for c in current_profile.columns}
    shared = baseline_cols.keys() & current_cols.keys()

    total_change = abs(current_profile.row_count - baseline_profile.row_count)
    candidates: list[RootCauseCandidate] = []

    for name in shared:
        b, c = baseline_cols[name], current_cols[name]
        if not b.value_counts or not c.value_counts:
            continue  # column wasn't tracked as low-cardinality categorical

        all_categories = set(b.value_counts) | set(c.value_counts)
        for category in all_categories:
            b_count = b.value_counts.get(category, 0)
            c_count = c.value_counts.get(category, 0)
            delta = b_count - c_count  # positive = this category shrank

            # For a drop we care about categories that shrank; for a spike,
            # categories that grew. Ignore the opposite direction as noise.
            relevant_delta = delta if is_drop else -delta
            if relevant_delta <= 0:
                continue

            contribution_pct = (relevant_delta / total_change * 100) if total_change > 0 else 0.0
            candidates.append(RootCauseCandidate(
                column=name, category=category,
                baseline_count=b_count, current_count=c_count,
                delta=delta, contribution_pct=round(contribution_pct, 1),
            ))

    candidates.sort(key=lambda cand: cand.contribution_pct, reverse=True)
    return candidates
