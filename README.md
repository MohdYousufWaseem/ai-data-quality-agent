# AI Data Quality & Analytics Agent

An autonomous, multi-agent system that profiles tabular data, detects quality
issues and drift over time, scores the dataset, and writes a human-readable
report — built with [LangGraph](https://github.com/langchain-ai/langgraph),
[DuckDB](https://duckdb.org), and [Groq](https://console.groq.com) (free-tier
LLM API, running Llama 3.3 70B).

This covers **Phases 1–2** of a larger project. The remaining roadmap
(root-cause investigation, human-approved automated fixes) is in
[`ROADMAP.md`](./ROADMAP.md).

## What it does right now

Given a CSV, the agent pipeline:
1. Profiles every column (nulls, types, cardinality, distributions)
2. Detects duplicate records, invalid emails, missing values, and statistical outliers
3. **Compares today's profile against the most recent historical snapshot** and
   flags volume drops/spikes, schema changes, missing-rate shifts, and
   distribution shifts
4. Computes a 0–100 data quality score
5. Uses a free LLM (Groq API, Llama 3.3 70B) to write a short executive
   summary and recommendation — constrained to the already-computed facts,
   so it can't invent numbers, and prioritized toward drift findings when
   present since a sudden change is usually more urgent than a static issue

```
$ python -m src.main data/sample_customers_week2.csv --as-of 2026-08-12 --source-name customers_export.csv

============================================================
DATA QUALITY REPORT
============================================================
Source: customers_export.csv
Rows analyzed: 10
Overall Score: 46/100
...

============================================================
DRIFT REPORT
============================================================
Comparing 2026-08-05  ->  2026-08-12

  ❌ Row count dropped 50.0% (20 -> 10).
  ❌ Column 'region' was present before but is missing now.
  ⚠️ New column 'loyalty_tier' appeared that wasn't present before.
  ❌ Missing-value rate on 'phone' jumped from 15.0% to 60.0%.
  ⚠️ Column 'age' changed type from float64 to int64.

Summary & Recommendation:
[LLM-generated verdict, prioritizing the drift findings]
============================================================
```

## Why this project is architecturally interesting

Most "AI data quality" demos are a single prompt: "here's a CSV, tell me
what's wrong with it." That's fragile — the LLM has to both *compute*
statistics and *reason* about them in one shot, which means numbers get
hallucinated. It's also stateless — it can't tell you "this changed since
last week" because it has no memory of last week.

This project separates concerns on purpose, and gives the system memory:

| Layer | Implementation | Why |
|---|---|---|
| Profiling & quality checks | Plain Python (pandas, regex, IQR) | Deterministic, fast, cheap, and unit-testable |
| Drift comparison | Plain Python, pure function (`compare_profiles`) | Same reason — comparing two known JSON structures needs no LLM |
| Historical snapshots | DuckDB, one embedded file | Gives the system memory without standing up a database server |
| Scoring | Plain Python, transparent weighting | Explainable — no black box |
| Report writing | LLM (Groq/Llama 3.3), fed only the computed JSON | Reasoning/summarization is the one thing worth spending a model call on |
| Orchestration | LangGraph state machine | Makes the pipeline explicit and lets later phases branch conditionally |

The agents communicate through strict Pydantic schemas
(`src/schemas.py`), not free text — see `Planner → Profiling → Drift →
Quality Analysis → Report` in `src/graph.py`.

## Project structure

```
ai-data-quality-agent/
├── data/
│   ├── sample_customers.csv       # "week 1" snapshot, seeded with known issues
│   ├── sample_customers_week2.csv # "week 2" snapshot, seeded with known drift
│   └── history.duckdb             # created automatically on first run
├── src/
│   ├── schemas.py                  # shared data contracts between agents
│   ├── state.py                    # LangGraph shared state
│   ├── graph.py                    # wires agents into a state graph
│   ├── main.py                     # CLI entry point
│   ├── agents/
│   │   ├── planner_agent.py
│   │   ├── profiling_agent.py
│   │   ├── drift_agent.py          # compares vs. history, saves new snapshot
│   │   ├── quality_agent.py
│   │   └── report_agent.py         # the only agent that calls an LLM
│   └── tools/
│       ├── profiling.py            # deterministic profiling
│       ├── quality_checks.py       # duplicate/email/missing/outlier checks
│       ├── drift_checks.py         # pure profile-vs-profile comparison
│       ├── snapshot_store.py       # DuckDB persistence for history
│       └── scoring.py              # 0-100 scoring logic
└── tests/
    ├── test_quality_checks.py      # "known-answer" tests against seeded issues
    └── test_drift_checks.py        # "known-answer" tests against seeded drift
```

## Setup

```bash
git clone <your-repo-url>
cd ai-data-quality-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env .env   # then add your GROQ_API_KEY (free: console.groq.com/keys)
```

## Run it

**First run** — no history yet, so the Drift Agent just saves a baseline:
```bash
python -m src.main data/sample_customers.csv --as-of 2026-08-05 --source-name customers_export.csv
```

**Second run** — same logical source, a week later, with real changes seeded in:
```bash
python -m src.main data/sample_customers_week2.csv --as-of 2026-08-12 --source-name customers_export.csv
```

`--source-name` is what lets two different files be treated as the same
recurring data feed over time (a daily/weekly export would naturally have
a new filename each time). `--as-of` lets you simulate dates for a demo
instead of waiting for real days to pass — omit it to default to today.

Re-running the plain `python -m src.main data/sample_customers.csv` from
Phase 1 still works exactly as before; it'll just also get a drift check
against whatever history exists for that filename.

## Run the tests

```bash
pytest tests/ -v
```

`sample_customers.csv` and `sample_customers_week2.csv` were seeded with
**known** differences — a 50% row-count drop, a `region`→`loyalty_tier`
schema change, and a phone missing-rate jump from 15% to 60% — so the
tests verify the drift logic actually catches what it's supposed to,
rather than just "runs without crashing."

## Roadmap

See [`ROADMAP.md`](./ROADMAP.md) for Phases 3–5: a natural-language
root-cause investigation agent (e.g. "why did revenue drop 18%?"), and
a human-approved auto-remediation layer.

## Tech stack

Python · pandas · Pydantic · LangGraph · DuckDB · Groq API (Llama 3.3) · pytest
