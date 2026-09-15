from src.state import GraphState


def planner_agent(state: GraphState) -> GraphState:
    state["log"] = [f"[PlannerAgent] Received '{state['source_name']}' "
                     f"({len(state['dataframe'])} rows) as of {state['as_of_date']}. "
                     f"Plan: profile -> drift_check -> root_cause -> quality_analysis -> report."]
    return state
