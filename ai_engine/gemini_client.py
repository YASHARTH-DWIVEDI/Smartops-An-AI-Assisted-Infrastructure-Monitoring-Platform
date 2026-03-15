"""
ai_engine/gemini_client.py
───────────────────────────
Thin wrapper around the Google Generative AI SDK (Gemini).
Falls back gracefully if the SDK is not installed or the key is missing.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from config.settings import get_settings

settings = get_settings()

_SYSTEM_PROMPT = """You are SmartOps, an expert Linux infrastructure analyst.
You will receive recent metric snapshots from a monitored server and must:
1. Identify any anomalies or concerning trends.
2. Explain the most likely root causes in plain language.
3. Provide concrete, actionable remediation steps.
4. Be concise — infrastructure engineers are busy.

Respond ONLY as valid JSON with this exact structure:
{
  "analysis": "<paragraph summarising findings>",
  "suggestions": ["step 1", "step 2", ...]
}
"""


def analyze(server_name: str, metrics: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    try:
        import google.generativeai as genai  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "google-generativeai package not installed. "
            "Run: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=_SYSTEM_PROMPT,
    )

    user_message = (
        f"Server: {server_name}\n"
        f"Recent metrics (newest first):\n"
        f"{json.dumps(metrics[:10], indent=2)}"
    )

    response = model.generate_content(user_message)
    raw = response.text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)
    return {
        "provider": "gemini",
        "analysis": parsed.get("analysis", "No analysis returned."),
        "suggestions": parsed.get("suggestions", []),
    }
