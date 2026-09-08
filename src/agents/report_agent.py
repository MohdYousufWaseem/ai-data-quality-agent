"""
Report Agent.

This is the ONE place in the pipeline that calls an LLM. Its only job is
to turn the already-computed QualityReport + DriftReport into a short,
human-readable recommendation -- it does NOT get to invent issues or
numbers.

The Groq client is created lazily (on first use, not at import time).
This matters for the Streamlit UI: if GROQ_API_KEY is missing, we want
to show a friendly in-app message and still display the rest of the
report, rather than crashing the whole app before it even loads.
"""

import os
import json
from groq import Groq
from src.state import GraphState

MODEL = "openai/gpt-oss-120b"

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
