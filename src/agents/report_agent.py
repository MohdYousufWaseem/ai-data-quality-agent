"""
Report Agent.

This is the ONE place in Phase 1 that calls an LLM. Its only job is to
turn the structured QualityReport into a short, human-readable
recommendation — it does NOT get to invent issues or numbers. We pass
it the already-computed structured data and constrain it to summarizing
and recommending, which keeps it from hallucinating findings.

Uses Groq's free API (OpenAI-compatible client) running an open-weight
model. Swap the model name below for any other Groq-hosted model if
you like: https://console.groq.com/docs/models
"""

import os
import json
from groq import Groq
from src.state import GraphState

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a data quality analyst writing a short executive \
summary of a data quality report. You will be given a JSON object with the \
computed score, quality issues, and any drift findings (changes compared to \
a previous snapshot). Do NOT invent numbers or issues that are not in the \
JSON. Write:
1. A one-sentence overall verdict.
2. A "Recommended Action" line: the single most important next step. If \
there are drift findings, especially critical ones (like a volume drop or \
a missing-value spike), prioritize explaining that over static quality \
issues -- a sudden change is usually more urgent than a static issue.

Keep it under 70 words total. No preamble, no markdown headers."""


def report_agent(state: GraphState) -> GraphState:
    report = state["quality_report"]
    drift_report = state.get("drift_report")

    payload = {
        "quality_report": report.model_dump(),
        "drift_report": drift_report.model_dump() if drift_report else None,
    }

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Report JSON:\n{json.dumps(payload, indent=2)}"},
        ],
    )

    summary_text = response.choices[0].message.content

    report.generated_summary = summary_text.strip()
    state["quality_report"] = report
    state["log"].append(f"[ReportAgent] Generated narrative summary via Groq ({MODEL}).")
    return state
