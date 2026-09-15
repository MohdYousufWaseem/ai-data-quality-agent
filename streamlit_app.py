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
import re
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


def render_root_cause_section(root_cause_report):
    if not root_cause_report.triggered:
        return  # nothing to show -- no baseline yet, or no volume anomaly found

    st.subheader("\U0001F50D Root Cause Investigation")
    st.caption(f"Anomaly: {root_cause_report.anomaly_type} \u2022 "
               f"Total row-count change: {root_cause_report.total_row_change}")

    if root_cause_report.primary_suspect:
        s = root_cause_report.primary_suspect
        # Single-line HTML, no leading whitespace on any line -- Streamlit's
        # markdown renderer treats 4+ leading spaces as a literal code block,
        # which would break this card just like it did for the summary card.
        html = (
            f'<div style="background:linear-gradient(135deg,#8b1a1a33,#8b1a1a11);'
            f'border:1px solid #d7302733;border-left:6px solid #d73027;border-radius:14px;'
            f'padding:18px 24px;margin-bottom:0.6rem;">'
            f'<div style="font-weight:700;color:#d73027;font-size:0.8rem;'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">'
            f'\U0001F3AF Primary Suspect</div>'
            f'<div style="font-size:1.05rem;color:#f0f0f0;">'
            f"'{s.category}' in column '{s.column}'</div>"
            f'<div style="color:#ccc;margin-top:4px;">'
            f'{s.baseline_count} rows \u2192 {s.current_count} rows '
            f'&nbsp;\u2022&nbsp; <b style="color:#d73027;">{s.contribution_pct:.0f}%</b> '
            f'of the total change</div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.info(
            "No single category explains a majority of the change -- "
            "it looks broad-based rather than caused by one segment."
        )

    st.markdown(f"**Conclusion:** {root_cause_report.conclusion}")

    if root_cause_report.other_candidates:
        with st.expander("Other contributing segments"):
            for c in root_cause_report.other_candidates:
                st.markdown(f"- '{c.category}' in `{c.column}`: {c.baseline_count} \u2192 "
                            f"{c.current_count} ({c.contribution_pct:.0f}%)")


def render_summary(report):
    st.subheader("\U0001F4A1 Summary & Recommendation")

    summary = (report.generated_summary or "").strip()
    accent = score_color(report.overall_score)

    if not summary or summary.startswith("(Summary unavailable"):
        html = (
            f'<div style="background: linear-gradient(135deg, #2b2b2b, #1a1a1a); '
            f'border: 1px dashed #666; border-radius: 12px; padding: 18px 22px; '
            f'color: #ccc; font-style: italic;">'
            f'\u26a0\ufe0f {summary or "No summary was generated."}'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)
        return

    # Try to split the LLM's two intended parts: verdict + recommended action.
    # Uses regex (case-insensitive) so it survives the model wrapping the
    # phrase in markdown bold, numbering it ("2. Recommended Action:"), or
    # varying capitalization -- plain string slicing was leaving stray
    # "**" and list numbers stuck onto the verdict text.
    def clean(text: str) -> str:
        text = re.sub(r"^[\s\-\*\d\.\)]+", "", text)   # leading bullets/numbers/markdown
        text = re.sub(r"[\s\-\*\d\.\)]+$", "", text)   # trailing junk
        return text.strip()

    match = re.search(r"\**\s*recommended action\s*\**\s*:?", summary, flags=re.IGNORECASE)
    if match:
        verdict = clean(summary[:match.start()])
        action = clean(summary[match.end():])
    else:
        verdict = clean(summary)
        action = None

    # IMPORTANT: every line below is built with zero leading whitespace on
    # purpose. Streamlit's markdown renderer treats any line indented 4+
    # spaces as a literal code block (standard Markdown behavior), which
    # would make this HTML show up as raw text instead of rendering --
    # that's exactly what a nicely-indented multi-line f-string does.
    action_html = ""
    if action:
        action_html = (
            f'<div style="margin-top:14px;padding-top:14px;border-top:1px solid {accent}33;'
            f'display:flex;align-items:flex-start;gap:10px;">'
            f'<div style="font-size:1.3rem;line-height:1;">\U0001F3AF</div>'
            f'<div>'
            f'<div style="font-weight:700;color:{accent};font-size:0.8rem;'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">'
            f'Recommended Action</div>'
            f'<div style="color:#f0f0f0;line-height:1.5;">{action}</div>'
            f'</div>'
            f'</div>'
        )

    card_html = (
        f'<div style="background: linear-gradient(135deg, {accent}22, {accent}0d);'
        f'border:1px solid {accent}55;border-left:6px solid {accent};border-radius:14px;'
        f'padding:20px 26px;box-shadow:0 4px 14px rgba(0,0,0,0.25);margin-bottom:0.5rem;">'
        f'<div style="font-size:1.02rem;line-height:1.55;color:#f0f0f0;">{verdict}</div>'
        f'{action_html}'
        f'</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)
    st.caption("Generated by Llama/GPT-OSS via Groq \u2014 constrained to only the computed facts above.")


def render_trace(log: list[str]):
    with st.expander("Agent trace (what each agent did, in order)"):
        for line in log:
            st.text(line)


def main():
    st.title("\U0001F9EA AI Data Quality & Analytics Agent")
    st.caption(
        "Multi-agent pipeline: Planner \u2192 Profiling \u2192 Drift \u2192 "
        "Root Cause \u2192 Quality Analysis \u2192 Report, built with LangGraph."
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
            "baseline_profile": None,
            "quality_report": None,
            "drift_report": None,
            "root_cause_report": None,
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
    render_root_cause_section(result["root_cause_report"])
    if result["root_cause_report"].triggered:
        st.divider()
    render_summary(result["quality_report"])
    render_trace(result["log"])


if __name__ == "__main__":
    main()
