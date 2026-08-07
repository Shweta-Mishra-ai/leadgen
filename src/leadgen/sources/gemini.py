from __future__ import annotations

import json
import logging

import requests

from leadgen.sources.base import LeadSource

logger = logging.getLogger("leadgen.sources.gemini")

DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

PROMPT_TEMPLATE = """Search the web for recent posts (last 7 days) where
someone is hiring or clearly needs help related to: {topic}
Return ONLY a JSON array: [{{"title": "...", "url": "...", "snippet": "...",
"created": "ISO date or empty"}}]. If nothing qualifies, return []"""


class GeminiSource(LeadSource):
    name = "gemini"

    def __init__(self, api_key: str | None, model: str = DEFAULT_MODEL, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _fetch_topic(self, topic: str) -> list[dict]:
        url = GEMINI_URL_TEMPLATE.format(model=self.model)
        resp = requests.post(
            url,
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": PROMPT_TEMPLATE.format(topic=topic)}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=self.timeout_seconds,
        )
        if resp.status_code >= 500:
            # transient — let the retry wrapper handle it
            raise ConnectionError(f"gemini 5xx: {resp.status_code}")
        resp.raise_for_status()  # 4xx (bad key etc.) raises and is NOT retried

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.warning("gemini unexpected response shape for topic=%r: %s", topic, e)
            return []

        text = text.strip()
        for fence in ("```json", "```"):
            text = text.removeprefix(fence)
            text = text.removesuffix("```")
        text = text.strip()

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("gemini returned non-JSON for topic=%r: %.200s", topic, text)
            return []

        return [
            {
                "source": "gemini",
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "created": item.get("created", ""),
            }
            for item in items
            if item.get("url")
        ]
