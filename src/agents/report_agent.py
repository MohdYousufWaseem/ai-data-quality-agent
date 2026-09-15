"""
Report Agent.

This is the ONE place in the pipeline that calls an LLM. Its only job is
to turn the already-computed QualityReport + DriftReport + RootCauseReport
into a short, human-readable recommendation -- it does NOT get to invent
issues, numbers, or root causes. The actual "why did this happen" fact
was already determined deterministically by RootCauseAgent; this agent
only narrates it.

The Groq client is created lazily (on first use, not at import time).
This matters for the Streamlit UI: if GROQ_API_KEY is missing, we want
to show a friendly in-app message and still display the rest of the
report, rather than crashing the whole app before it even loads.
"""

import os
import json
from groq import Groq
from src.state import GraphState

MODEL = "openai/gpt-oss-20b"

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at "
                "https://console.groq.com/keys and add it to your .env file."
            )
        _client = Groq(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are a data quality analyst writing a short executive \
summary. You will be given a JSON object with the computed score, quality \
issues, drift findings (changes vs. a previous snapshot), a root-cause \
investigation (an already-computed explanation for any volume anomaly), \
and a recommendation report (proposed fixes -- not yet applied, awaiting \
human approval). Do NOT invent numbers, issues, or causes that are not in \
the JSON -- your only job is to phrase the given facts clearly, not to \
reason further about causes yourself.

Priority order for what to lead with:
1. If root_cause_report.triggered is true AND it has a primary_suspect, \
lead with that root cause -- it's the most specific and actionable fact \
available (e.g. "the row-count drop is explained by X region"). State it \
as the "Recommended Action": go investigate/fix that specific segment.
2. Otherwise, if there are critical drift findings, lead with those.
3. Otherwise, summarize the static quality issues. If recommendation_report \
has auto-fixable actions, you may mention that an automated fix is \
available and awaiting approval, but do not claim it has been applied.

Write:
1. A one-sentence overall verdict.
2. A "Recommended Action" line: the single most important next step.

Keep it under 70 words total. No preamble, no markdown headers."""


def report_agent(state: GraphState) -> GraphState:
    report = state["quality_report"]
    drift_report = state.get("drift_report")
    root_cause_report = state.get("root_cause_report")
    recommendation_report = state.get("recommendation_report")

    payload = {
        "quality_report": report.model_dump(),
        "drift_report": drift_report.model_dump() if drift_report else None,
        "root_cause_report": root_cause_report.model_dump() if root_cause_report else None,
        "recommendation_report": recommendation_report.model_dump() if recommendation_report else None,
    }

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=1024,
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Report JSON:\n{json.dumps(payload, indent=2)}"},
            ],
        )
        summary_text = (response.choices[0].message.content or "").strip()

        if not summary_text:
            raise RuntimeError(
                "Model returned empty content (likely spent its full token "
                "budget on internal reasoning). Try raising max_tokens further."
            )

        report.generated_summary = summary_text
        state["log"].append(f"[ReportAgent] Generated narrative summary via Groq ({MODEL}).")

    except Exception as e:
        report.generated_summary = (
            f"(Summary unavailable: {e}. The structured report above is still "
            f"fully computed -- this only affects the narrative write-up.)"
        )
        state["log"].append(f"[ReportAgent] Skipped LLM summary due to error: {e}")

    state["quality_report"] = report
    return state
