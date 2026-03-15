"""
ai_engine/openai_client.py
───────────────────────────
Thin wrapper around the OpenAI Python SDK.
Falls back gracefully if the SDK is not installed or the key is missing.
"""

from __future__ import annotations

import json
from typing import Any

from config.settings import get_settings

settings = get_settings()

_SYSTEM_PROMPT = """You are SmartOps, an expert Linux infrastructure analyst.
Analyse the provided server metrics and respond ONLY as valid JSON:
{
  "analysis": "<concise summary of findings>",
  "suggestions": ["actionable step 1", "actionable step 2", ...]
}
"""


def analyze(server_name: str, metrics: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai package not installed. Run: pip install openai"
        ) from exc

    client = OpenAI(api_key=settings.openai_api_key)

    user_message = (
        f"Server: {server_name}\n"
        f"Recent metrics (newest first):\n"
        f"{json.dumps(metrics[:10], indent=2)}"
    )

    completion = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        max_tokens=800,
        temperature=0.3,
    )

    raw = completion.choices[0].message.content or "{}"
    parsed = json.loads(raw)

    return {
        "provider": "openai",
        "analysis": parsed.get("analysis", "No analysis returned."),
        "suggestions": parsed.get("suggestions", []),
    }
