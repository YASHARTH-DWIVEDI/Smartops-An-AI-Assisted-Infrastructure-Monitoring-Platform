"""

Google Gemini AI Client for SmartOps diagnostics.

Sends metric context to Gemini and parses the structured response.
Falls back gracefully if the API is unavailable.
"""

import json
import os
import textwrap
from typing import Optional

from shared.logging_config import get_logger

logger = get_logger("ai_engine.gemini")

DIAGNOSIS_PROMPT_TEMPLATE = """
You are an expert Linux systems administrator and SRE (Site Reliability Engineer).
Analyze the following server metrics and provide a structured diagnostic report.

Server: {server_name}
Metrics snapshot:
  - CPU Usage:    {cpu_percent:.1f}%
  - Memory Usage: {memory_percent:.1f}%
  - Disk Usage:   {disk_percent:.1f}%
  - Load Avg (1m/5m/15m): {load_avg_1m:.2f} / {load_avg_5m:.2f} / {load_avg_15m:.2f}
  - Uptime:       {uptime_hours:.1f} hours
  - Processes:    {process_count}
  - Net Sent:     {net_kb_sent:.1f} KB
  - Net Recv:     {net_kb_recv:.1f} KB

Alert thresholds: CPU>90%, Memory>90%, Disk>85%

Respond ONLY with a valid JSON object with this exact structure:
{{
  "severity": "healthy|warning|critical",
  "summary": "2-3 sentence overview of the server health situation",
  "causes": ["cause 1", "cause 2", "cause 3"],
  "recommendations": ["step 1", "step 2", "step 3", "step 4"]
}}

Be specific and actionable. Include actual Linux commands in recommendations where appropriate.
"""



class GeminiClient:
    """
    Google Gemini client for AI-powered metric diagnosis.

    Requires GEMINI_API_KEY environment variable.
    Raises GeminiUnavailableError if the API cannot be reached.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model = None

        if not self.api_key:
            raise GeminiUnavailableError("GEMINI_API_KEY not set.")

        self._init_client()

    def _init_client(self):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel("gemini-pro")
            logger.info("Gemini client initialised.")
        except ImportError:
            raise GeminiUnavailableError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )
        except Exception as e:
            raise GeminiUnavailableError(f"Gemini init failed: {e}")

    async def diagnose(self, metrics: dict, server_name: str) -> dict:
        """
        Send metrics to Gemini and return parsed diagnosis.

        Returns:
            dict with keys: severity, summary, causes, recommendations
        """
        prompt = DIAGNOSIS_PROMPT_TEMPLATE.format(
            server_name=server_name,
            cpu_percent=metrics.get("cpu_percent", 0),
            memory_percent=metrics.get("memory_percent", 0),
            disk_percent=metrics.get("disk_percent", 0),
            load_avg_1m=metrics.get("load_avg_1m", 0),
            load_avg_5m=metrics.get("load_avg_5m", 0),
            load_avg_15m=metrics.get("load_avg_15m", 0),
            uptime_hours=(metrics.get("uptime_seconds", 0) or 0) / 3600,
            process_count=metrics.get("process_count", 0) or 0,
            net_kb_sent=(metrics.get("net_bytes_sent", 0) or 0) / 1024,
            net_kb_recv=(metrics.get("net_bytes_recv", 0) or 0) / 1024,
        )

        try:
            logger.debug(f"Sending diagnosis request to Gemini for {server_name}")
            response = self._model.generate_content(prompt)
            raw_text = response.text.strip()

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            parsed = json.loads(raw_text)

            # Validate expected keys
            for key in ("severity", "summary", "causes", "recommendations"):
                if key not in parsed:
                    raise ValueError(f"Missing key in Gemini response: {key}")

            logger.info(f" Gemini diagnosis complete for {server_name}: severity={parsed['severity']}")

            return {
                "server_name": server_name,
                "provider": "gemini",
                "severity": parsed.get("severity", "unknown"),
                "summary": parsed.get("summary", ""),
                "causes": parsed.get("causes", []),
                "recommendations": parsed.get("recommendations", []),
                "raw_response": raw_text,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            raise GeminiUnavailableError(f"Invalid JSON from Gemini: {e}")
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise GeminiUnavailableError(f"Gemini API error: {e}")


class GeminiUnavailableError(Exception):
    """Raised when Gemini is not available — triggers fallback to rules engine."""
