"""
Recommendation Agent.

Unlike the Action Agent (which requires human approval before running),
this agent always runs automatically -- proposing a fix is safe, since
nothing gets executed here. It just turns the QualityReport's issues
into structured FixAction proposals.
"""

from src.state import GraphState
from src.tools.recommendations import build_recommendations


def recommendation_agent(state: GraphState) -> GraphState:
    quality_report = state["quality_report"]
    report = build_recommendations(state["source_name"], quality_report.issues)

    state["recommendation_report"] = report
    auto_fixable = sum(1 for a in report.actions if a.auto_fixable)
    state["log"].append(f"[RecommendationAgent] Proposed {len(report.actions)} action(s), "
                         f"{auto_fixable} auto-fixable.")
    return state
