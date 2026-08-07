from __future__ import annotations

import re

TECH_PATTERNS = {
    "Python": r"\b(python|django|fastapi|flask|celery)\b",
    "Node/TS": r"\b(node|nodejs|typescript|express|nest|nextjs|react)\b",
    "AI/LLM": r"\b(openai|langchain|llm|gpt-4|claude|rag|vector|pinecone|chroma)\b",
    "Automation/Webhooks": r"\b(n8n|zapier|make|puppeteer|playwright|selenium|scraping)\b",
    "Cloud/DevOps": r"\b(aws|gcp|azure|docker|kubernetes|terraform|serverless)\b",
    "Database": r"\b(postgres|postgresql|mongodb|redis|mysql|supabase)\b",
}


def detect_lead_tech_stack(title: str, snippet: str) -> list[str]:
    """Detects technical stack keywords from lead title and snippet."""
    text = f"{title} {snippet}".lower()
    detected = []
    for tech, pattern in TECH_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            detected.append(tech)
    return detected or ["General Tech"]
