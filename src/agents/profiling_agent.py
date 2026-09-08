"""
Profiling Agent.

In this phase it's a thin wrapper around the deterministic profiling
tool. It earns the name "agent" (rather than just "function") because
it participates in the LangGraph state machine and could later decide
*how* to profile (e.g. sample a huge file instead of scanning it all,
or pick which columns matter) based on context. For now, keep it simple
and honest about what it does.
"""

from src.state import GraphState
from src.tools.profiling import profile_dataframe


def profiling_agent(state: GraphState) -> GraphState:
    df = state["dataframe"]
    source_name = state["source_name"]

    profile = profile_dataframe(df, source_name)

    state["data_profile"] = profile
    state["log"].append(f"[ProfilingAgent] Profiled {profile.row_count} rows, "
                         f"{profile.column_count} columns.")
    return state
