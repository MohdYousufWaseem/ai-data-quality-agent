"""
Planner Agent.

In Phase 1 this looks almost too simple to justify being called an
"agent" — it just logs its decision and lets the graph run the fixed
Profiling -> Quality -> Report path. That's intentional.

The point of having this node at all is architectural: in Phase 2+,
THIS is where conditional logic will live -- e.g. "if row_count is
huge, sample instead of full-scan", or "if this is a scheduled rerun,
skip straight to drift comparison". By putting the decision point here
now, later phases only add branching logic in one place instead of
rewriting the graph.
"""

from src.state import GraphState


def planner_agent(state: GraphState) -> GraphState:
    state["log"] = [f"[PlannerAgent] Received '{state['source_name']}' "
                     f"({len(state['dataframe'])} rows) as of {state['as_of_date']}. "
                     f"Plan: profile -> drift_check -> quality_analysis -> report."]
    return state
