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
        items = []

        # 1. Parse text JSON output
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            for fence in ("```json", "```"):
                text = text.removeprefix(fence)
                text = text.removesuffix("```")
            text = text.strip()
            parsed = json.loads(text)
            if isinstance(parsed, list):
                items.extend(parsed)
        except Exception:  # noqa: BLE001
            pass

        # 2. Extract groundingMetadata URLs from Google Search Grounding
        try:
            candidate = data["candidates"][0]
            metadata = candidate.get("groundingMetadata", {})
            chunks = metadata.get("groundingChunks", [])
            for chunk in chunks:
                web = chunk.get("web", {})
                if web.get("uri"):
                    items.append({
                        "title": web.get("title", f"Lead for {topic}"),
                        "url": web.get("uri"),
                        "snippet": f"Google Search lead for {topic}",
                        "created": "",
                    })
        except Exception:  # noqa: BLE001
            pass

        results = []
        for item in items:
            if isinstance(item, dict) and item.get("url"):
                results.append({
                    "source": "gemini",
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                    "created": item.get("created", ""),
                })
        return results
