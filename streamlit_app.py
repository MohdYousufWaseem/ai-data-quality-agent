"""
Streamlit UI for the AI Data Quality & Analytics Agent.

Run with:
    streamlit run streamlit_app.py

This is a thin presentation layer only -- it calls the exact same
LangGraph pipeline (src/graph.py) that the CLI (src/main.py) uses.
No agent logic lives in this file on purpose: if the pipeline changes,
both the CLI and this UI pick it up automatically.
"""

import os
from datetime import date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.graph import build_graph

st.set_page_config(
    page_title="AI Data Quality & Analytics Agent",
    page_icon="\U0001F9EA",
    layout="wide",
)

SEVERITY_COLOR = {"critical": "\U0001F534", "warning": "\U0001F7E1", "info": "\U0001F535"}


@st.cache_resource
def get_app():
    return build_graph()


def score_color(score: int) -> str:
    if score >= 80:
        return "#1a9850"
    if score >= 50:
        return "#f4a300"
    return "#d73027"


def render_quality_section(report):
    st.subheader("Data Quality Report")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.metric("Overall Score", f"{report.overall_score}/100")
    with col2:
        st.metric("Rows Analyzed", report.row_count)
    with col3:
        if report.most_critical_issue:
            st.metric("Most Critical Issue", report.most_critical_issue.replace("_", " ").title())

    st.markdown(
        f"""
        <div style="background-color:{score_color(report.overall_score)}22;
                    border-left: 5px solid {score_color(report.overall_score)};
                    padding: 10px 16px; border-radius: 4px; margin-bottom: 1rem;">
        <b>Score interpretation:</b> {"Looks healthy." if report.overall_score >= 80 else
        "Some real issues worth addressing." if report.overall_score >= 50 else
        "Significant quality problems -- recommend investigating before using this data downstream."}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not report.issues:
        st.success("No issues found. Dataset looks clean.")
    else:
        for issue in report.issues:
            icon = SEVERITY_COLOR.get(issue.severity, "\u26aa")
            col_tag = f" `{issue.column}`" if issue.column else ""
            st.markdown(f"{icon} **{issue.severity.upper()}** -- {issue.description}{col_tag}")


def render_drift_section(drift_report):
    st.subheader("Drift Report")

    if not drift_report.has_baseline:
        st.info(
            f"No historical baseline found for **{drift_report.source_name}**. "
            f"This snapshot ({drift_report.current_date}) has been saved as the "
            f"starting point -- run this source again later (with a different "
            f"`--as-of` date) to see drift detection in action."
        )
        return

    st.caption(f"Comparing **{drift_report.baseline_date}** \u2192 **{drift_report.current_date}**")

    if not drift_report.findings:
        st.success("No significant drift detected since the last snapshot.")
    else:
        for finding in drift_report.findings:
            icon = SEVERITY_COLOR.get(finding.severity, "\u26aa")
            col_tag = f" `{finding.column}`" if finding.column else ""
            st.markdown(f"{icon} **{finding.severity.upper()}** -- {finding.description}{col_tag}")


def render_summary(report):
    st.subheader("Summary & Recommendation")
    st.info(report.generated_summary)


def render_trace(log: list[str]):
    with st.expander("Agent trace (what each agent did, in order)"):
        for line in log:
            st.text(line)


def main():
    st.title("\U0001F9EA AI Data Quality & Analytics Agent")
    st.caption(
        "Multi-agent pipeline: Planner \u2192 Profiling \u2192 Drift \u2192 "
        "Quality Analysis \u2192 Report, built with LangGraph."
    )

    with st.sidebar:
        st.header("Run an analysis")
        uploaded_file = st.file_uploader("Upload a CSV", type=["csv"])
        source_name_override = st.text_input(
            "Source name (optional)",
            help="Use the same source name across runs to enable drift detection "
                 "against a prior snapshot, even if the filename changes.",
        )
        as_of = st.date_input("As-of date", value=date.today())
        run_clicked = st.button("Run Analysis", type="primary", use_container_width=True)

        st.divider()
        if not os.environ.get("GROQ_API_KEY"):
            st.warning(
                "No GROQ_API_KEY found. The structured report will still work, "
                "but the LLM-written summary will be skipped. Add a free key "
                "in your .env file -- see console.groq.com/keys."
            )

    if run_clicked:
        if uploaded_file is None:
            st.error("Please upload a CSV file first.")
            return

        df = pd.read_csv(uploaded_file)
        source_name = source_name_override.strip() or uploaded_file.name
        as_of_str = as_of.isoformat()

        app = get_app()
        initial_state = {
            "source_name": source_name,
            "as_of_date": as_of_str,
            "dataframe": df,
            "data_profile": None,
            "quality_report": None,
            "drift_report": None,
            "log": [],
        }

        with st.spinner("Running the agent pipeline..."):
            final_state = app.invoke(initial_state)

        st.session_state["result"] = final_state

    result = st.session_state.get("result")
    if result is None:
        st.markdown(
            "Upload a CSV in the sidebar and click **Run Analysis** to get started. "
            "Try running the same source name twice with different `--as-of` dates "
            "(or two different files) to see the Drift Agent detect real changes."
        )
        return

    render_quality_section(result["quality_report"])
    st.divider()
    render_drift_section(result["drift_report"])
    st.divider()
    render_summary(result["quality_report"])
    render_trace(result["log"])


if __name__ == "__main__":
    main()
