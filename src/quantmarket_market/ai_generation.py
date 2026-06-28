from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .ai_briefs import build_ai_brief_prompt, load_ai_briefs, load_previous_ai_brief, upsert_ai_brief
from .config import REPORT_DIR
from .payloads import write_payload_file

OPENAI_MODEL = os.getenv("QUANTMARKET_OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_ENDPOINT = os.getenv("QUANTMARKET_OPENAI_ENDPOINT", "https://api.openai.com/v1/chat/completions").strip()


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
    return cleaned_lines[:8]


def _call_openai(prompt: str) -> list[str]:
    if not OPENAI_API_KEY:
        raise AIGenerationError("OPENAI_API_KEY is not configured.")
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 공개 시장 브리핑용 퀀트 시장분석 작성자입니다. "
                    "투자 자문, 매수/매도 권유, 비중 조절, 타이밍 제안을 하지 마세요."
                ),
            },
            {
                "role": "user",
                "content": (
                    prompt
                    + " 정확히 8줄만 평문으로 답하세요. 1~4줄은 긍정:, 5~8줄은 리스크:로 시작하세요. "
                    "각 줄은 줄바꿈으로 구분하고, 숫자 bullet, JSON, 마크다운, 제목은 쓰지 마세요."
                ),
            },
        ],
        "temperature": 1.0,
        "max_tokens": 720,
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
    choices = payload.get("choices") or []
    if not choices:
        raise AIGenerationError(f"OpenAI returned no choices: {payload}")
    text = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise AIGenerationError(f"OpenAI returned no message content: {payload}")
    lines = _normalize_lines(text)
    if not lines:
        raise AIGenerationError(f"OpenAI returned no usable text lines: {text}")
    return lines[:8]


def refresh_ai_briefs(*, market: str, asof: str, summary: dict, detail: dict, generated_at: str, market_context: dict | None = None, intraday_context: dict | None = None) -> dict:
    report = {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "market_context": market_context or {},
        "intraday_context": intraday_context or {},
        "providers": {
            "openai": {
                "enabled": bool(OPENAI_API_KEY),
                "model": OPENAI_MODEL,
                "status": "not_attempted",
            },
        },
    }

    provider_specs = [
        ("openai", OPENAI_API_KEY, _call_openai, f"openai:{OPENAI_MODEL}"),
    ]

    for provider, api_key, call_fn, source in provider_specs:
        previous_record = load_previous_ai_brief(market=market, asof=asof, provider=provider)
        if previous_record is None and provider == "openai":
            previous_record = load_previous_ai_brief(market=market, asof=asof, provider="gemini")
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
            if previous_lines:
                fallback_source = (previous_record or {}).get("source") or source
                upsert_ai_brief(
                    market=market,
                    asof=asof,
                    provider=provider,
                    summary_lines=previous_lines,
                    generated_at=generated_at,
                    source=f"fallback_previous:{fallback_source}",
                )
                report["providers"][provider].update({
                    "status": "fallback_previous",
                    "error": str(exc),
                    "line_count": len(previous_lines),
                    "summary_lines": previous_lines,
                })
            else:
                report["providers"][provider].update({
                    "status": "error",
                    "error": str(exc),
                })

    write_payload_file(REPORT_DIR / "market_ai_generation_status_latest.json", report)
    return load_ai_briefs(market=market, asof=asof)
