"""
ai_engine/diagnostics.py
─────────────────────────
AI diagnostic dispatcher.

Priority chain:
  1. Use the configured AI_PROVIDER (gemini / openai / rule_based)
  2. If provider call fails, fall back to rule_based
  3. Never raise — always return a dict

Usage
-----
    from ai_engine.diagnostics import DiagnosticsEngine
    result = DiagnosticsEngine().analyze(server_name, metrics_list)
    # result = {"provider": "...", "analysis": "...", "suggestions": [...]}
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ai_engine import rule_engine
from config.settings import get_settings

settings = get_settings()


class DiagnosticsEngine:
    """Routes diagnostic requests to the best available AI provider."""

    def analyze(
        self,
        server_name: str,
        metrics: list[dict[str, Any]],
    ) -> dict[str, Any]:
        provider = settings.ai_provider.lower()

        if provider == "gemini":
            return self._try_gemini(server_name, metrics)
        elif provider == "openai":
            return self._try_openai(server_name, metrics)
        else:
            logger.debug("Using rule-based diagnostics (AI_PROVIDER=rule_based)")
            return rule_engine.analyze(server_name, metrics)

    # ── Provider calls with fallback ─────────────────────────────────────

    def _try_gemini(
        self, server_name: str, metrics: list[dict[str, Any]]
    ) -> dict[str, Any]:
        try:
            from ai_engine.gemini_client import analyze
            result = analyze(server_name, metrics)
            logger.info("Gemini diagnostic completed for {}", server_name)
            return result
        except Exception as exc:
            logger.warning(
                "Gemini analysis failed ({}), falling back to rule engine.", exc
            )
            return rule_engine.analyze(server_name, metrics)

    def _try_openai(
        self, server_name: str, metrics: list[dict[str, Any]]
    ) -> dict[str, Any]:
        try:
            from ai_engine.openai_client import analyze
            result = analyze(server_name, metrics)
            logger.info("OpenAI diagnostic completed for {}", server_name)
            return result
        except Exception as exc:
            logger.warning(
                "OpenAI analysis failed ({}), falling back to rule engine.", exc
            )
            return rule_engine.analyze(server_name, metrics)
