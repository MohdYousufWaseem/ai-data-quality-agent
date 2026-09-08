"""
Builds the LangGraph state graph for Phase 2:

    Planner -> Profiling -> Drift -> Quality Analysis -> Report -> END

Each box is a Python function (an "agent node") that takes GraphState
and returns GraphState. LangGraph handles passing state between them.
"""

from langgraph.graph import StateGraph, END
from src.state import GraphState
from src.agents.planner_agent import planner_agent
from src.agents.profiling_agent import profiling_agent
from src.agents.drift_agent import drift_agent
from src.agents.quality_agent import quality_agent
from src.agents.report_agent import report_agent


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("planner", planner_agent)
    graph.add_node("profiling", profiling_agent)
    graph.add_node("drift", drift_agent)
    graph.add_node("quality_analysis", quality_agent)
    graph.add_node("report", report_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "profiling")
    graph.add_edge("profiling", "drift")
    graph.add_edge("drift", "quality_analysis")
    graph.add_edge("quality_analysis", "report")
    graph.add_edge("report", END)

    return graph.compile()
