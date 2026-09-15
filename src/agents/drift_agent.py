from src.state import GraphState
from src.schemas import DriftReport
from src.tools.snapshot_store import load_latest_before, save_snapshot
from src.tools.drift_checks import compare_profiles


def drift_agent(state: GraphState) -> GraphState:
    profile = state["data_profile"]
    source_name = state["source_name"]
    as_of_date = state["as_of_date"]

    baseline_date, baseline_profile = load_latest_before(source_name, as_of_date)
    state["baseline_profile"] = baseline_profile  # exposed for RootCauseAgent to reuse

    if baseline_profile is None:
        report = DriftReport(
            source_name=source_name, has_baseline=False,
            baseline_date=None, current_date=as_of_date, findings=[],
        )
        state["log"].append("[DriftAgent] No historical snapshot found -- "
                             "this is the first run for this source.")
    else:
        findings = compare_profiles(baseline_profile, profile)
        report = DriftReport(
            source_name=source_name, has_baseline=True,
            baseline_date=baseline_date, current_date=as_of_date, findings=findings,
        )
        state["log"].append(f"[DriftAgent] Compared against baseline from "
                             f"{baseline_date}; found {len(findings)} drift finding(s).")

    state["drift_report"] = report
    save_snapshot(profile, as_of_date)
    state["log"].append(f"[DriftAgent] Saved snapshot for {as_of_date}.")
    return state
