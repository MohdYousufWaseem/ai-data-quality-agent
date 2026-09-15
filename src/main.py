"""
CLI entry point.

Usage:
    python -m src.main data/sample_customers.csv
    python -m src.main data/sample_customers.csv --as-of 2026-08-05
    python -m src.main data/sample_customers_week2.csv --as-of 2026-08-12 --source-name sample_customers.csv
    python -m src.main data/sample_customers.csv --apply-fixes --output cleaned.csv
"""

import argparse
import os
import pandas as pd
from datetime import date
from dotenv import load_dotenv

load_dotenv()

from src.graph import build_graph
from src.state import GraphState
from src.tools.actions import apply_fixes
from src.tools.validation import validate_fixes


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


def print_root_cause_section(root_cause_report):
    if not root_cause_report.triggered:
        return  # nothing to show -- no baseline or no volume anomaly to investigate

    print("\n" + "=" * 60)
    print("ROOT CAUSE INVESTIGATION")
    print("=" * 60)
    print(f"Anomaly type: {root_cause_report.anomaly_type}")
    print(f"Total row-count change: {root_cause_report.total_row_change}\n")

    if root_cause_report.primary_suspect:
        s = root_cause_report.primary_suspect
        print(f"\U0001F3AF PRIMARY SUSPECT: '{s.category}' in column '{s.column}'")
        print(f"   {s.baseline_count} rows -> {s.current_count} rows "
              f"({s.contribution_pct:.0f}% of the total change)")

    print(f"\nConclusion: {root_cause_report.conclusion}")

    if root_cause_report.other_candidates:
        print("\nOther contributing segments:")
        for c in root_cause_report.other_candidates:
            print(f"  - '{c.category}' in '{c.column}': {c.baseline_count} -> "
                  f"{c.current_count} ({c.contribution_pct:.0f}%)")


def print_recommendation_section(recommendation_report):
    print("\n" + "=" * 60)
    print("RECOMMENDED FIXES")
    print("=" * 60)

    if not recommendation_report.actions:
        print("No issues to fix.")
        return

    for action in recommendation_report.actions:
        tag = "[AUTO-FIXABLE]" if action.auto_fixable else "[MANUAL REVIEW]"
        print(f"  {tag} ({action.action_id}) {action.description}")


def run_apply_fixes_flow(df: pd.DataFrame, recommendation_report, output_path: str):
    """Interactive human-approval loop: ask about each auto-fixable action
    one at a time, apply only the ones approved, then re-validate."""
    auto_fixable = [a for a in recommendation_report.actions if a.auto_fixable]

    if not auto_fixable:
        print("\nNo auto-fixable actions available -- nothing to apply.")
        return

    print("\n" + "=" * 60)
    print("APPROVE FIXES")
    print("=" * 60)
    approved = []
    for action in auto_fixable:
        answer = input(f"Apply fix: {action.description}\n  Apply? [y/N]: ").strip().lower()
        if answer == "y":
            approved.append(action)

    if not approved:
        print("\nNo fixes approved -- nothing applied.")
        return

    fixed_df, applied = apply_fixes(df, approved)
    validation = validate_fixes(df, fixed_df, applied)

    print("\n" + "=" * 60)
    print("VALIDATION RESULT")
    print("=" * 60)
    print(f"Rows: {validation.row_count_before} -> {validation.row_count_after}")
    print(f"Score: {validation.score_before}/100 -> {validation.score_after}/100")
    print(f"Remaining issues: {validation.issue_count_before} -> {validation.issue_count_after}")
    print(f"\n{validation.summary}")

    fixed_df.to_csv(output_path, index=False)
    print(f"\nCleaned data written to: {output_path}")
    print("(The original input file was not modified.)")


def main():
    parser = argparse.ArgumentParser(description="AI Data Quality & Analytics Agent")
    parser.add_argument("csv_path", help="Path to the CSV file to analyze")
    parser.add_argument("--as-of", dest="as_of", default=None,
                         help="Date this run represents, YYYY-MM-DD (default: today)")
    parser.add_argument("--source-name", dest="source_name", default=None,
                         help="Logical source name to key history by "
                              "(default: the CSV filename)")
    parser.add_argument("--apply-fixes", action="store_true",
                         help="After showing the report, interactively ask approval "
                              "for each auto-fixable action and apply approved ones "
                              "to a NEW output file (the input file is never modified).")
    parser.add_argument("--output", dest="output", default="cleaned_output.csv",
                         help="Path to write the cleaned CSV to, if --apply-fixes is used "
                              "(default: cleaned_output.csv)")
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
        "baseline_profile": None,
        "quality_report": None,
        "drift_report": None,
        "root_cause_report": None,
        "recommendation_report": None,
        "log": [],
    }

    final_state = app.invoke(initial_state)

    print_quality_section(final_state["quality_report"])
    print_drift_section(final_state["drift_report"])
    print_root_cause_section(final_state["root_cause_report"])
    print_recommendation_section(final_state["recommendation_report"])

    if final_state["quality_report"].generated_summary:
        print(f"\nSummary & Recommendation:\n{final_state['quality_report'].generated_summary}")

    print("\n--- Agent Trace ---")
    for line in final_state["log"]:
        print(line)
    print("=" * 60)

    if args.apply_fixes:
        run_apply_fixes_flow(df, final_state["recommendation_report"], args.output)


if __name__ == "__main__":
    main()
