from __future__ import annotations

import json
import logging

from leadgen.sources.base import LeadSource

logger = logging.getLogger("leadgen.sources.grok")

PROMPT_TEMPLATE = """Search X (Twitter) and Reddit for recent posts where
someone is looking to hire, or expresses a clear need, related to: {topic}
Only include results from the last 7 days, with real hiring/need intent.
Return ONLY a JSON array: [{{"platform": "x" or "reddit", "title": "...",
"url": "...", "snippet": "...", "created": "ISO date or empty"}}]
If nothing qualifies, return []"""


class GrokSource(LeadSource):
    name = "grok"

    def __init__(self, api_key: str | None, model: str = "grok-2-latest", **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.model = model or "grok-2-latest"
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url="https://api.x.ai/v1")
        return self._client

    def _fetch_topic(self, topic: str) -> list[dict]:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(topic=topic)}],
            timeout=self.timeout_seconds,
        )
        text = resp.choices[0].message.content or ""
        text = text.strip()
        for fence in ("```json", "```"):
            text = text.removeprefix(fence)
            text = text.removesuffix("```")
        text = text.strip()
        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("grok returned non-JSON for topic=%r: %.200s", topic, text)
            return []
        if not isinstance(items, list):
            return []
        return [
            {
                "source": f"grok_{item.get('platform', 'unknown')}",
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "created": item.get("created", ""),
            }
            for item in items
            if isinstance(item, dict) and item.get("url")
        ]
