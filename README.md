# AI Data Quality & Analytics Agent

An autonomous, multi-agent system that profiles tabular data, detects
quality issues and drift over time, **investigates why a volume anomaly
happened**, scores the dataset, and writes a human-readable report — built
with [LangGraph](https://github.com/langchain-ai/langgraph),
[DuckDB](https://duckdb.org), [Groq](https://console.groq.com) (free-tier
LLM API), and a [Streamlit](https://streamlit.io) UI.

This covers **Phases 1–4** of a larger project, plus a UI. The remaining
roadmap (scheduling/alerting, productionizing) is in
[`ROADMAP.md`](./ROADMAP.md).

## The headline feature: root-cause investigation

Given two snapshots of the same data source over time, the agent doesn't
just say "row count dropped 25%" — it identifies **which segment** caused
it, deterministically, no LLM guessing involved:

```
$ python -m src.main data/sample_transactions_week2.csv --as-of 2026-07-31 --source-name transactions_export.csv

============================================================
DRIFT REPORT
============================================================
Comparing 2026-07-24  ->  2026-07-31

  ❌ Row count dropped 25.0% (40 -> 30).
  ⚠️ Category 'North' in 'region' disappeared (was 25.0% of rows).

============================================================
ROOT CAUSE INVESTIGATION
============================================================
Anomaly type: volume_drop
Total row-count change: -10

🎯 PRIMARY SUSPECT: 'North' in column 'region'
   10 rows -> 0 rows (100% of the total change)

Conclusion: 100% of the row-count change is attributable to 'North' in
column 'region': it went from 10 rows to 0 rows. Its disappearance from
the dataset largely explains the overall drop.
```

Try it yourself with the seeded transactions dataset (see **Run it** below).

## Human-approved fixes

Detecting issues is only half the job — Phase 4 adds proposing and (with
approval) applying fixes, without ever touching your original file:

```bash
python -m src.main data/sample_customers.csv --apply-fixes
```
```
RECOMMENDED FIXES
============================================================
  [AUTO-FIXABLE] (action_0) Remove 2 duplicate row(s), keeping the first occurrence of each.
  [MANUAL REVIEW] (action_1) 2 rows have an email that doesn't match a valid email pattern.
  [AUTO-FIXABLE] (action_2) Fill 3 missing value(s) in 'phone' (median/most common value).
  [AUTO-FIXABLE] (action_3) Fill 1 missing value(s) in 'age' (median/most common value).
  [MANUAL REVIEW] (action_4) Column 'age' has 2 outlier(s) outside the expected range.

APPROVE FIXES
============================================================
Apply fix: Remove 2 duplicate row(s)...   Apply? [y/N]: y
Apply fix: Fill 3 missing value(s) in 'phone'...   Apply? [y/N]: y
Apply fix: Fill 1 missing value(s) in 'age'...   Apply? [y/N]: y

VALIDATION RESULT
============================================================
Rows: 20 -> 18
Score: 51/100 -> 86/100
Remaining issues: 5 -> 2

Cleaned data written to: cleaned_output.csv
(The original input file was not modified.)
```

Only duplicates and missing values get an automated fix proposed —
invalid formats and outliers are always left for manual review, since
correcting them requires judgment a script shouldn't assume. In the UI,
the same flow is a checklist with an "Apply Selected Fixes" button and a
download link for the cleaned CSV.

## Try it: the UI

```bash
streamlit run streamlit_app.py
```

Upload a CSV, pick a source name and date, and click **Run Analysis**. Run
the same source name twice with two different dates (or two different
files representing "the same feed over time") to see the Drift Agent catch
real changes, and the Root Cause Agent explain them. Then review the
Recommended Fixes section and approve what you want applied.

The UI is a thin presentation layer only — it calls the exact same
LangGraph pipeline as the CLI (`src/graph.py`), plus the same
`tools/actions.py` / `tools/validation.py` for the human-approval step.
No agent logic lives in `streamlit_app.py`; if the pipeline changes, both
the CLI and the UI pick it up automatically.

## What it does

Given a CSV, the agent pipeline (`Planner → Profiling → Drift → Root Cause
→ Quality Analysis → Recommendation → Report`):
1. Profiles every column: nulls, types, cardinality, numeric quantiles
   (p10/p25/p50/p75/p90), and category frequencies for low-cardinality
   columns
2. Detects duplicate records, invalid emails, missing values, and
   statistical outliers
3. Compares today's profile against the most recent historical snapshot
   and flags volume drops/spikes, schema changes, missing-rate shifts,
   numeric mean/quantile shifts, and categorical distribution shifts
   (new/disappeared/shifted categories)
4. **If a volume anomaly was flagged**, investigates every tracked
   categorical column to find which category's row count explains most
   of the change, and reports a primary suspect when one exists
5. Computes a 0–100 data quality score
6. Proposes fixes for the safe, unambiguous issues (duplicates, missing
   values) and marks everything else (invalid formats, outliers) for
   manual review only — proposing never executes anything
7. Uses a free LLM (Groq API) to write a short executive summary —
   constrained to the already-computed facts, so it can't invent numbers
   or causes; when a root cause was found, it's prioritized above
   everything else in the summary

**Separately**, once you review the proposals: approve some or all of the
auto-fixable actions (in the UI or via `--apply-fixes` in the CLI), and
the Action Agent applies them to a *copy* of the data — the original file
is never touched — then the Validation Agent re-checks the result and
shows you a real before/after comparison.

## Why this project is architecturally interesting

Most "AI data quality" demos are a single prompt: "here's a CSV, tell me
what's wrong with it." That's fragile — the LLM has to both *compute*
statistics and *reason* about them in one shot, which means numbers (and
causes) get hallucinated. This project separates concerns on purpose:

| Layer | Implementation | Why |
|---|---|---|
| Profiling & quality checks | Plain Python (pandas, regex, IQR) | Deterministic, fast, cheap, and unit-testable |
| Drift comparison | Plain Python, pure function (`compare_profiles`) | No LLM needed to diff two known JSON structures |
| Root cause investigation | Plain Python, pure function (`investigate_volume_anomaly`) | Attributing a row-count change to a segment is arithmetic on stored `value_counts`, not reasoning — a sandboxed SQL-generating LLM agent would be riskier and slower for the same answer |
| Recommending fixes | Plain Python, maps issue type → proposal | Only safe, unambiguous fixes (dedup, impute) are proposed; the rest is flagged for a human, not guessed at |
| Applying fixes | Plain Python, operates on a DataFrame copy | Proposing is automatic; *executing* requires an explicit human click/approval, and never mutates the original file |
| Validating fixes | Plain Python, re-runs the same checks | "Did the score actually improve" is a fact to compute, not something an LLM needs to assert |
| Historical snapshots | DuckDB, one embedded file | Gives the system memory without a database server |
| Scoring | Plain Python, transparent weighting | Explainable — no black box |
| Report writing | LLM (Groq), fed only the computed JSON, fails gracefully | Reasoning/summarization is the one thing worth spending a model call on; it narrates the root cause, it doesn't discover it |
| Orchestration | LangGraph state machine | Makes the automatic pipeline explicit; applying fixes is deliberately kept *outside* this graph since it needs a human in the loop |
| Presentation | Streamlit, calling the same graph + action tools as the CLI | Zero duplicated logic between CLI and UI |

The agents communicate through strict Pydantic schemas (`src/schemas.py`),
not free text.

## Project structure

```
ai-data-quality-agent/
├── streamlit_app.py                    # UI, calls the same graph as the CLI
├── data/
│   ├── sample_customers.csv            # quality-issue demo dataset
│   ├── sample_customers_week2.csv      # drift demo (schema/volume/missing-rate)
│   ├── sample_transactions.csv         # root-cause demo, week 1
│   ├── sample_transactions_week2.csv   # root-cause demo, week 2 (North vanishes)
│   └── history.duckdb                  # created automatically on first run
├── src/
│   ├── schemas.py                      # shared data contracts between agents
│   ├── state.py                        # LangGraph shared state
│   ├── graph.py                        # wires agents into a state graph
│   ├── main.py                         # CLI entry point
│   ├── agents/
│   │   ├── planner_agent.py
│   │   ├── profiling_agent.py
│   │   ├── drift_agent.py              # compares vs. history, saves new snapshot
│   │   ├── root_cause_agent.py         # explains volume anomalies
│   │   ├── quality_agent.py
│   │   ├── recommendation_agent.py     # proposes fixes (never executes)
│   │   └── report_agent.py             # the only agent that calls an LLM
│   └── tools/
│       ├── profiling.py                # deterministic profiling + quantiles/value_counts
│       ├── quality_checks.py           # duplicate/email/missing/outlier checks
│       ├── drift_checks.py             # pure profile-vs-profile comparison
│       ├── root_cause.py               # pure volume-anomaly attribution
│       ├── recommendations.py          # issue -> proposed fix mapping
│       ├── actions.py                  # applies approved fixes (human-triggered)
│       ├── validation.py               # before/after comparison after fixes
│       ├── snapshot_store.py           # DuckDB persistence for history
│       └── scoring.py                  # 0-100 scoring logic
└── tests/
    ├── test_quality_checks.py
    ├── test_profiling.py
    ├── test_drift_checks.py
    ├── test_root_cause.py
    ├── test_recommendations.py
    ├── test_actions.py
    └── test_validation.py
```

## Setup

```bash
git clone <your-repo-url>
cd ai-data-quality-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY (free: console.groq.com/keys)
```

## Run it

**UI:**
```bash
streamlit run streamlit_app.py
```

**CLI — root-cause demo** (the flagship scenario: a region's rows vanish):
```bash
python -m src.main data/sample_transactions.csv --as-of 2026-07-24 --source-name transactions_export.csv
python -m src.main data/sample_transactions_week2.csv --as-of 2026-07-31 --source-name transactions_export.csv
```

**CLI — general quality + drift demo:**
```bash
python -m src.main data/sample_customers.csv --as-of 2026-08-05 --source-name customers_export.csv
python -m src.main data/sample_customers_week2.csv --as-of 2026-08-12 --source-name customers_export.csv
```

## Run the tests

```bash
pytest tests/ -v
```

All sample datasets were seeded with **known** issues, drift, and root
causes (a region whose transactions completely stop, a 50% row-count drop,
a schema change, missing-rate spikes) so the tests verify the logic
actually catches and explains what it's supposed to.

## Roadmap

See [`ROADMAP.md`](./ROADMAP.md) for what's left: human-approved automated
fixes, and productionizing (scheduling, alerting, auth).

## Tech stack

Python · pandas · Pydantic · LangGraph · DuckDB · Groq API · Streamlit · pytest
