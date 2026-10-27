import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def check_with_gemini(text: str) -> List[Dict[str, Any]]:
    """
    Optional LLM review using Google Gemini API.
    If GEMINI_API_KEY is not set, or the API call fails or times out,
    returns an empty list gracefully without throwing an exception.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return []

    if not text or not text.strip():
        return []

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
You are Inkloom AI, a brand governance compliance reviewer.
Analyze the following marketing draft for subtle tone issues, unverified claims, or compliance risks.
Only flag issues that are NOT basic banned words (e.g. check for subtle overpromises, vague superlatives, passive aggression, unverified statistics).

Draft to review:
\"\"\"{text}\"\"\"

Return a valid JSON array of objects with the following schema:
[
  {{
    "matched_text": "exact substring from draft",
    "severity": "high" | "medium" | "low",
    "status": "violation" | "needs verification",
    "explanation": "concise explanation of brand risk",
    "rule_source": "Inkloom Tone & Nuance Guidelines (AI Assessor)",
    "suggested_rewrite": "context-aware rewrite preserving marketing intent"
  }}
]
If there are no additional subtle issues, return [].
Return ONLY the raw JSON array, with no Markdown ticks or wrapping text.
"""
        response = model.generate_content(prompt)
        if not response or not response.text:
            return []

        raw_text = response.text.strip()
        # Strip markdown fences if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        parsed = json.loads(raw_text)
        if not isinstance(parsed, list):
            return []

        findings: List[Dict[str, Any]] = []
        for item in parsed:
            matched = str(item.get("matched_text", ""))
            start_pos = text.find(matched) if matched else -1
            end_pos = start_pos + len(matched) if start_pos != -1 else -1

            findings.append({
                "matched_text": matched,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "severity": item.get("severity", "medium").lower(),
                "status": item.get("status", "violation"),
                "explanation": item.get("explanation", "Tone or claim check flagged by AI analysis"),
                "rule_source": item.get("rule_source", "Inkloom Tone & Nuance Guidelines (AI Assessor)"),
                "suggested_rewrite": item.get("suggested_rewrite", matched),
                "engine_source": "gemini_llm"
            })
        return findings

    except Exception as e:
        logger.warning(f"Gemini API check skipped or failed gracefully: {e}")
        return []
