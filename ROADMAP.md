# Roadmap

**Phase 1 — Static Data Quality Report (done, this repo)**
Planner → Profiling Agent → Quality Analysis Agent → Report Agent, run on
a single CSV. Deterministic checks + one constrained LLM call for the
narrative summary.

**Phase 2 — Historical Memory + Drift Detection (done, this repo)**
Each `DataProfile` snapshot is persisted to DuckDB, keyed by source name
+ date. A `DriftAgent` compares today's profile to the most recent prior
snapshot and flags volume drops/spikes, schema changes, missing-rate
shifts, and distribution shifts — e.g. "missing-value rate on `phone`
jumped from 2% to 12% since last week." All comparison logic is a pure,
unit-tested function (`compare_profiles`); no LLM involved in detecting
drift, only in narrating it.

**Phase 3 — Root-Cause Investigation Agent**
The hardest and most interesting phase. Given a flagged anomaly (e.g. a
revenue drop), this agent gets tool access to run its own read-only
SQL/pandas queries — sliced by region, segment, time — to narrow down
a cause, the way you'd manually dig into a dashboard. Needs sandboxing:
read-only credentials, query timeouts, row limits. Validate against
anomalies you inject yourself so you know the "correct" answer.

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
