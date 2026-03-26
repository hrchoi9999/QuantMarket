from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .ai_briefs import build_ai_brief_prompt, load_ai_briefs, load_previous_ai_brief, upsert_ai_brief
from .config import REPORT_DIR
from .payloads import write_payload_file

OPENAI_MODEL = os.getenv("QUANTMARKET_OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"

GEMINI_MODEL = os.getenv("QUANTMARKET_GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


class AIGenerationError(RuntimeError):
    pass


def _normalize_lines(text: str) -> list[str]:
    cleaned_lines: list[str] = []
    for raw in text.replace("```", "").splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("here is") or lowered.startswith("json"):
            continue
        cleaned_lines.append(line)
    if len(cleaned_lines) == 1:
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned_lines[0]) if part.strip()]
        if len(parts) > 1:
            cleaned_lines = parts
    return cleaned_lines[:4]


def _call_openai(prompt: str) -> list[str]:
    if not OPENAI_API_KEY:
        raise AIGenerationError("OPENAI_API_KEY is not configured.")
    body = {
        "model": OPENAI_MODEL,
        "input": prompt + " 정확히 4문장만 평문으로 답하세요. 각 문장은 줄바꿈으로 구분하고, 숫자 bullet, JSON, 마크다운, 제목은 쓰지 마세요.",
        "max_output_tokens": 320,
        "temperature": 0.9,
    }
    request = Request(
        OPENAI_ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AIGenerationError(f"OpenAI HTTP {exc.code}: {detail}") from exc
    text = payload.get("output_text") or ""
    if not text:
        output = payload.get("output") or []
        text_parts: list[str] = []
        for item in output:
            for content in item.get("content", []) or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    text_parts.append(content["text"])
        text = "\n".join(text_parts)
    lines = _normalize_lines(text)
    if not lines:
        raise AIGenerationError(f"OpenAI returned no usable text lines: {payload}")
    return lines[:4]


def _call_gemini(prompt: str) -> list[str]:
    if not GEMINI_API_KEY:
        raise AIGenerationError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured.")
    body = {
        "contents": [{
            "parts": [{
                "text": prompt + " 정확히 4문장만 평문으로 답하세요. 각 문장은 줄바꿈으로 구분하고, 숫자 bullet, JSON, 마크다운, 제목은 쓰지 마세요."
            }]
        }],
        "generationConfig": {
            "temperature": 1.0,
            "maxOutputTokens": 320,
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        },
    }
    request = Request(
        f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AIGenerationError(f"Gemini HTTP {exc.code}: {detail}") from exc
    candidates = payload.get("candidates") or []
    if not candidates:
        raise AIGenerationError(f"Gemini returned no candidates: {payload}")
    text_parts: list[str] = []
    for part in candidates[0].get("content", {}).get("parts", []):
        if part.get("text"):
            text_parts.append(part["text"])
    if not text_parts:
        raise AIGenerationError(f"Gemini returned no text parts: {payload}")
    lines = _normalize_lines("\n".join(text_parts))
    if not lines:
        raise AIGenerationError(f"Gemini returned no usable text lines: {text_parts}")
    return lines[:4]


def refresh_ai_briefs(*, market: str, asof: str, summary: dict, detail: dict, generated_at: str, market_context: dict | None = None, intraday_context: dict | None = None) -> dict:
    report = {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "market_context": market_context or {},
        "intraday_context": intraday_context or {},
        "providers": {
            "chatgpt": {
                "enabled": bool(OPENAI_API_KEY),
                "model": OPENAI_MODEL,
                "status": "not_attempted",
            },
            "gemini": {
                "enabled": bool(GEMINI_API_KEY),
                "model": GEMINI_MODEL,
                "status": "not_attempted",
            },
        },
    }

    provider_specs = [
        ("chatgpt", OPENAI_API_KEY, _call_openai, f"openai:{OPENAI_MODEL}"),
        ("gemini", GEMINI_API_KEY, _call_gemini, f"gemini:{GEMINI_MODEL}"),
    ]

    for provider, api_key, call_fn, source in provider_specs:
        previous_record = load_previous_ai_brief(market=market, asof=asof, provider=provider)
        previous_lines = (previous_record or {}).get("summary_lines") or []
        report["providers"][provider]["previous_asof"] = (previous_record or {}).get("asof")
        report["providers"][provider]["previous_summary_lines"] = previous_lines
        if not api_key:
            report["providers"][provider]["status"] = "missing_api_key"
            continue
        prompt = build_ai_brief_prompt(
            provider=provider,
            market=market,
            asof=asof,
            summary=summary,
            detail=detail,
            previous_lines=previous_lines,
            market_context=market_context,
            intraday_context=intraday_context,
        )
        try:
            lines = call_fn(prompt)
            upsert_ai_brief(
                market=market,
                asof=asof,
                provider=provider,
                summary_lines=lines,
                generated_at=generated_at,
                source=source,
            )
            report["providers"][provider].update({
                "status": "ok",
                "line_count": len(lines),
                "summary_lines": lines,
            })
        except AIGenerationError as exc:
            report["providers"][provider].update({
                "status": "error",
                "error": str(exc),
            })

    write_payload_file(REPORT_DIR / "market_ai_generation_status_latest.json", report)
    return load_ai_briefs(market=market, asof=asof)
