"""
CLI entry point.

Usage:
    python -m src.main data/sample_customers.csv
    python -m src.main data/sample_customers.csv --as-of 2026-08-05
    python -m src.main data/sample_customers_week2.csv --as-of 2026-08-12 --source-name sample_customers.csv

--as-of lets you simulate "today" for demo purposes, so you can build up
a fake history without waiting for real days to pass.

--source-name lets two different files be treated as the same logical
source over time (e.g. a daily export that gets a new filename each day)
so the DriftAgent knows to compare them against each other.
"""

import argparse
import os
import pandas as pd
from datetime import date
from dotenv import load_dotenv

load_dotenv()  # reads .env and sets GROQ_API_KEY as an env var

from src.graph import build_graph
from src.state import GraphState


SEVERITY_ICON = {"critical": "\u274c", "warning": "\u26a0\ufe0f", "info": "\u2139\ufe0f"}


def print_quality_section(report):
    print("=" * 60)
    print("DATA QUALITY REPORT")
    print("=" * 60)
    print(f"Source: {report.source_name}")
    print(f"Rows analyzed: {report.row_count}")
    print(f"Overall Score: {report.overall_score}/100\n")

    if not report.issues:
        print("No issues found. Dataset looks clean.")
    else:
        print("Issues Found:")
        for issue in report.issues:
            icon = SEVERITY_ICON.get(issue.severity, "-")
            col = f" ({issue.column})" if issue.column else ""
            print(f"  {icon} {issue.description}{col}")

    if report.most_critical_issue:
        print(f"\nMost Critical Issue: {report.most_critical_issue}")


def print_drift_section(drift_report):
    print("\n" + "=" * 60)
    print("DRIFT REPORT")
    print("=" * 60)

    if not drift_report.has_baseline:
        print(f"No historical baseline found for '{drift_report.source_name}' -- "
              f"this snapshot ({drift_report.current_date}) has been saved as the "
              f"starting point for future comparisons.")
        return

    print(f"Comparing {drift_report.baseline_date}  ->  {drift_report.current_date}\n")

    if not drift_report.findings:
        print("No significant drift detected since the last snapshot.")
    else:
        for finding in drift_report.findings:
            icon = SEVERITY_ICON.get(finding.severity, "-")
            print(f"  {icon} {finding.description}")


def main():
    parser = argparse.ArgumentParser(description="AI Data Quality & Analytics Agent")
    parser.add_argument("csv_path", help="Path to the CSV file to analyze")
    parser.add_argument("--as-of", dest="as_of", default=None,
                         help="Date this run represents, YYYY-MM-DD (default: today)")
    parser.add_argument("--source-name", dest="source_name", default=None,
                         help="Logical source name to key history by "
                              "(default: the CSV filename)")
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"File not found: {args.csv_path}")
        return

    df = pd.read_csv(args.csv_path)
    source_name = args.source_name or os.path.basename(args.csv_path)
    as_of_date = args.as_of or date.today().isoformat()

    app = build_graph()

    initial_state: GraphState = {
        "source_name": source_name,
        "as_of_date": as_of_date,
        "dataframe": df,
        "data_profile": None,
        "quality_report": None,
        "drift_report": None,
        "log": [],
    }

    final_state = app.invoke(initial_state)

    print_quality_section(final_state["quality_report"])
    print_drift_section(final_state["drift_report"])

    if final_state["quality_report"].generated_summary:
        print(f"\nSummary & Recommendation:\n{final_state['quality_report'].generated_summary}")

    print("\n--- Agent Trace ---")
    for line in final_state["log"]:
        print(line)
    print("=" * 60)


if __name__ == "__main__":
    main()
