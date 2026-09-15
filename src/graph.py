"""
Builds the LangGraph state graph for Phase 4:

    Planner -> Profiling -> Drift -> Root Cause -> Quality Analysis
             -> Recommendation -> Report -> END

Each box is a Python function (an "agent node") that takes GraphState
and returns GraphState. LangGraph handles passing state between them.

Note: this graph only PROPOSES fixes (RecommendationAgent) -- it never
applies them. Applying a fix requires human approval and happens outside
this automatic graph, via tools/actions.py, triggered from the UI/CLI
after the person reviews the proposals.
"""

from langgraph.graph import StateGraph, END
from src.state import GraphState
from src.agents.planner_agent import planner_agent
from src.agents.profiling_agent import profiling_agent
from src.agents.drift_agent import drift_agent
from src.agents.root_cause_agent import root_cause_agent
from src.agents.quality_agent import quality_agent
from src.agents.recommendation_agent import recommendation_agent
from src.agents.report_agent import report_agent


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("planner", planner_agent)
    graph.add_node("profiling", profiling_agent)
    graph.add_node("drift", drift_agent)
    graph.add_node("root_cause", root_cause_agent)
    graph.add_node("quality_analysis", quality_agent)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("report", report_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "profiling")
    graph.add_edge("profiling", "drift")
    graph.add_edge("drift", "root_cause")
    graph.add_edge("root_cause", "quality_analysis")
    graph.add_edge("quality_analysis", "recommendation")
    graph.add_edge("recommendation", "report")
    graph.add_edge("report", END)

    return graph.compile()
