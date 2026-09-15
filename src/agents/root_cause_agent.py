"""
Root Cause Agent.

Only runs an investigation when there's something worth investigating:
a real historical baseline AND a volume anomaly (drop or spike) flagged
by the Drift Agent. Otherwise it short-circuits with a clear reason why
it didn't trigger, rather than always forcing an (empty) investigation.

No LLM call here either -- see tools/root_cause.py for why. This agent
is just the orchestration glue: pull the right inputs out of state, call
the pure investigation function, put the result back in state.
"""

from src.state import GraphState
from src.schemas import RootCauseReport
from src.tools.root_cause import investigate_volume_anomaly


def root_cause_agent(state: GraphState) -> GraphState:
    drift_report = state["drift_report"]
    baseline_profile = state.get("baseline_profile")
    current_profile = state["data_profile"]

    if not drift_report.has_baseline or baseline_profile is None:
        state["root_cause_report"] = RootCauseReport(
            triggered=False,
            reason_not_triggered="No historical baseline available yet -- "
                                  "nothing to investigate against.",
        )
        state["log"].append("[RootCauseAgent] Skipped -- no baseline.")
        return state

    volume_finding = next(
        (f for f in drift_report.findings if f.finding_type in ("volume_drop", "volume_spike")),
        None,
    )

    if volume_finding is None:
        state["root_cause_report"] = RootCauseReport(
            triggered=False,
            reason_not_triggered="No volume anomaly detected -- nothing to investigate.",
        )
        state["log"].append("[RootCauseAgent] Skipped -- no volume anomaly to investigate.")
        return state

    report = investigate_volume_anomaly(baseline_profile, current_profile, volume_finding)
    state["root_cause_report"] = report
    state["log"].append(f"[RootCauseAgent] Investigated {report.anomaly_type}. "
                         f"Conclusion: {report.conclusion}")
    return state
