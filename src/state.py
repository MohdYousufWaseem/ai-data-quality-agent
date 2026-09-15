from typing import TypedDict, Any
import pandas as pd
from src.schemas import DataProfile, QualityReport, DriftReport, RootCauseReport


class GraphState(TypedDict):
    source_name: str
    as_of_date: str
    dataframe: pd.DataFrame
    data_profile: DataProfile | None
    baseline_profile: DataProfile | None    # set by DriftAgent when a baseline exists
    quality_report: QualityReport | None
    drift_report: DriftReport | None
    root_cause_report: RootCauseReport | None
    log: list[str]
