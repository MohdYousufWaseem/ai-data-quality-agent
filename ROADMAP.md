# Roadmap

**Phase 1 — Static Data Quality Report (done)**
Planner → Profiling Agent → Quality Analysis Agent → Report Agent, run on
a single CSV. Deterministic checks + one constrained LLM call for the
narrative summary.

**Phase 2 — Historical Memory + Drift Detection (done)**
Each `DataProfile` snapshot is persisted to DuckDB, keyed by source name
+ date. A `DriftAgent` compares today's profile to the most recent prior
snapshot and flags volume drops/spikes, schema changes, missing-rate
shifts, and distribution shifts. All comparison logic is a pure,
unit-tested function (`compare_profiles`); no LLM involved in detecting
drift, only in narrating it.

**UI (done)**
A Streamlit front end (`streamlit_app.py`) calling the same LangGraph
pipeline as the CLI — no duplicated agent logic. Handles a missing
GROQ_API_KEY gracefully: the structured report still renders, only the
narrative summary is skipped.

**Phase 3 — Root-Cause Investigation Agent (done)**
Given a `volume_drop` or `volume_spike` finding from the Drift Agent, the
`RootCauseAgent` investigates which segment explains it. Deliberately
does **not** use an LLM-driven SQL/pandas query sandbox — instead it
reuses the `value_counts` already captured per low-cardinality categorical
column in each snapshot (added alongside this phase) and computes, for
every category, how much of the total row-count change it accounts for.
If one category explains a majority of the change, it's reported as the
"primary suspect" with an exact contribution percentage; otherwise the
conclusion honestly says the change looks broad-based. Fully deterministic
and unit-tested (`tools/root_cause.py`, `tests/test_root_cause.py`) — the
LLM's only role is narrating the already-computed conclusion in the
executive summary, prioritized above generic drift/quality issues when a
root cause was found.

Known limitation: numeric ID-like columns (e.g. `customer_id`) aren't
excluded from the *quantile drift* check the way high-cardinality columns
are excluded from `value_counts` — a follow-up could add an "ID-like
column" heuristic (e.g. column name ends in `_id`, or `unique_count`
nearly equals `row_count`) to skip quantile checks on surrogate keys.

**Phase 4 — Recommendations + Human-Approved Actions**
A `RecommendationAgent` turns findings into structured, prioritized
suggestions. An `ActionAgent` can execute approved fixes (dedup,
standardize formats, impute values) — always through a staging table,
never direct writes to source data, and only after explicit human
approval. A `ValidationAgent` re-profiles afterward to confirm the fix
worked.

**Phase 5 — Productionize**
Scheduling (cron/Airflow) for recurring checks, Slack/email alerting
when the score drops below a threshold, auth + multi-tenant data source
connections, and cost/latency tuning (cache deterministic results,
reserve LLM calls for reasoning steps only).
