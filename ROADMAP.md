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

**Phase 4 — Recommendations + Human-Approved Actions (done)**
A `RecommendationAgent` (a normal, automatic graph node) turns each
`QualityIssue` into a structured `FixAction` proposal — but only proposes,
never executes. Only `duplicate_records` (drop duplicates, keep first) and
`missing_values` (median for numeric columns, mode for text columns) get
`auto_fixable=True`; invalid formats and statistical outliers are marked
`manual_review_only` since correcting them requires business judgment a
script shouldn't assume.

Applying a fix is a *separate*, human-triggered step outside the automatic
graph (`tools/actions.py` + `tools/validation.py`), invoked from the UI
(checkboxes + "Apply Selected Fixes" button) or the CLI (`--apply-fixes`,
which interactively asks approval for each action). Every fix operates on
a copy of the DataFrame — the original uploaded file or CSV is never
mutated; the cleaned result is written to a new file, and the UI offers it
as a download. A `ValidationReport` re-runs the same deterministic checks
before/after to show whether the score actually improved, rather than
just asserting it.

**Phase 5 — Productionize**
Scheduling (cron/Airflow) for recurring checks, Slack/email alerting
when the score drops below a threshold, auth + multi-tenant data source
connections, and cost/latency tuning (cache deterministic results,
reserve LLM calls for reasoning steps only).
