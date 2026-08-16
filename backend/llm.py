"""Gemini narrative wrapper.

Turns the three agents' structured forecasts into a short, plain-English
executive summary. Implemented as a thin wrapper around the raw
generateContent REST endpoint (rather than the SDK) so it has no extra
package dependency and isn't pinned to a specific SDK's model-name
conventions.

Fails soft everywhere: no API key, a timeout, or a bad response simply
means no summary is produced — it never blocks or fails the analysis.
"""

import httpx
import config


class GeminiNarrator:
    def __init__(self, api_key: str = None, model: str = None, timeout: float = 12.0):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model or config.GEMINI_MODEL
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def summarize(self, agent_results: dict):
        """Return a short executive summary string, or None if unavailable."""
        if not self.enabled:
            return None
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            response = httpx.post(
                url,
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": self._build_prompt(agent_results)}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 400},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            candidates = response.json().get("candidates") or []
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            return text or None
        except Exception:
            return None

    @staticmethod
    def _build_prompt(agent_results: dict) -> str:
        conservative = agent_results.get("conservative", {})
        moderate = agent_results.get("moderate", {})
        aggressive = agent_results.get("aggressive", {})
        return (
            "You are a sales analytics assistant. Below are three revenue forecasts for the same "
            "company - pessimistic, expected, and optimistic 30-day scenarios - produced by statistical "
            "forecasting models. Write a concise executive summary (max 120 words, plain prose, no markdown "
            "headers or bullet symbols) covering: (1) the overall outlook, (2) what drives the spread "
            "between the scenarios, and (3) one concrete, actionable recommendation.\n\n"
            f"Pessimistic (conservative): ${conservative.get('forecasted_total_revenue')} over "
            f"{conservative.get('forecast_days')} days. {conservative.get('insight', '')}\n"
            f"Expected (moderate): ${moderate.get('forecasted_total_revenue')} over "
            f"{moderate.get('forecast_days')} days. {moderate.get('insight', '')}\n"
            f"Optimistic (aggressive): ${aggressive.get('forecasted_total_revenue')} over "
            f"{aggressive.get('forecast_days')} days. {aggressive.get('insight', '')}\n"
        )
