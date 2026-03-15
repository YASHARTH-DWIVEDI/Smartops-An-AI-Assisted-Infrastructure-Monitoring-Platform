"""
Diagnostics Engine — dispatches to Gemini AI or rule-based fallback.

Priority:
  1. Try Gemini if GEMINI_API_KEY is set
  2. Fall back to rule-based engine on any error
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ai_engine.rules import RuleBasedEngine
from ai_engine.gemini_client import GeminiClient, GeminiUnavailableError
from shared.logging_config import get_logger

logger = get_logger("ai_engine.diagnostics")


class DiagnosticsEngine:
    """
    Unified entry point for AI-powered metric diagnosis.

    Tries Gemini first, falls back to rule-based engine.
    """

    def __init__(self):
        self._rules = RuleBasedEngine()
        self._gemini: GeminiClient | None = None
        self._gemini_available = False
        self._try_init_gemini()

    def _try_init_gemini(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logger.info("GEMINI_API_KEY not set — using rule-based engine.")
            return
        try:
            self._gemini = GeminiClient(api_key=api_key)
            self._gemini_available = True
            logger.info("Gemini AI engine ready.")
        except GeminiUnavailableError as e:
            logger.warning(f"Gemini not available: {e}. Falling back to rules.")

    async def diagnose(self, metrics: dict, server_name: str) -> dict:
        """
        Analyze metrics and return a diagnosis dict.

        Returns dict compatible with DiagnoseResponse schema.
        """
        # Try Gemini first
        if self._gemini_available and self._gemini:
            try:
                result = await self._gemini.diagnose(metrics, server_name)
                logger.info(f"Diagnosis for {server_name} via Gemini: {result['severity']}")
                return result
            except GeminiUnavailableError as e:
                logger.warning(f"Gemini failed ({e}), falling back to rules.")

        # Rule-based fallback
        result = self._rules.diagnose(metrics, server_name)
        logger.info(f"Diagnosis for {server_name} via rules: {result['severity']}")
        return result
