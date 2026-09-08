"""
The shared state that flows through every node in the LangGraph graph.

LangGraph passes this dict between agent nodes. Each agent reads what
it needs and writes its output back into the same dict. Think of it as
the "shared whiteboard" all agents write on.
"""

from typing import TypedDict, Any
import pandas as pd
from src.schemas import DataProfile, QualityReport, DriftReport


class GraphState(TypedDict):
    source_name: str
    as_of_date: str          # the date this run represents, e.g. "2026-08-12"
    dataframe: pd.DataFrame
    data_profile: DataProfile | None
    quality_report: QualityReport | None
    drift_report: DriftReport | None
    log: list[str]           # human-readable trace of what each agent did
