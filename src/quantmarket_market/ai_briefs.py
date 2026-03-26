from __future__ import annotations

import json
from datetime import datetime

from .config import REFERENCE_DIR

AI_BRIEFS_PATH = REFERENCE_DIR / "market_ai_briefs_manual.json"
PROVIDERS = {
    "chatgpt": "ChatGPT",
    "gemini": "제미나이",
}
PROVIDER_THEME_LABELS = {
    "chatgpt": "모델 해석 참고",
    "gemini": "시장 분위기 참고",
}
CHATGPT_VIEWPOINTS = [
    ("macro_liquidity", "매크로 관점: 유동성/금리/환율"),
    ("macro_global", "매크로 관점: 대외 이벤트/위험자산 환경"),
    ("micro_breadth", "마이크로 관점: 종목 확산/시장 내부 체력"),
    ("micro_tape", "마이크로 관점: 단기 흐름/변동성 구조"),
]
GEMINI_FOCUS_ROTATION = [
    ("index_fx", "지수와 환율의 현재 흐름"),
    ("breadth_vol", "종목 확산과 변동성 체감"),
    ("futures_flow", "선물과 수급의 방향성"),
    ("news_risk", "뉴스와 대외 리스크 맥락"),
]


def ensure_ai_briefs_file() -> None:
    AI_BRIEFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not AI_BRIEFS_PATH.exists():
        AI_BRIEFS_PATH.write_text(json.dumps({"records": []}, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_store() -> dict:
    ensure_ai_briefs_file()
    return json.loads(AI_BRIEFS_PATH.read_text(encoding="utf-8-sig"))


def _write_store(store: dict) -> None:
    AI_BRIEFS_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_asof(value: str | None) -> datetime:
    if not value:
        return datetime.min
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min


def _matching_records(*, market: str, provider: str | None = None) -> list[dict]:
    store = _load_store()
    records = store.get("records") or []
    filtered = [record for record in records if record.get("market") == market]
    if provider:
        filtered = [record for record in filtered if record.get("provider") == provider]
    return filtered


def _provider_viewpoint(provider: str, asof: str) -> dict | None:
    dt = _parse_asof(asof)
    if provider == "chatgpt":
        key, label = CHATGPT_VIEWPOINTS[dt.hour % len(CHATGPT_VIEWPOINTS)]
        return {"key": key, "label": label}
    if provider == "gemini":
        key, label = GEMINI_FOCUS_ROTATION[dt.hour % len(GEMINI_FOCUS_ROTATION)]
        return {"key": key, "label": label}
    return None


def load_ai_briefs(*, market: str, asof: str) -> dict:
    records = _matching_records(market=market)
    by_provider = {
        record.get("provider"): record
        for record in records
        if record.get("asof") == asof
    }
    providers = []
    for provider, label in PROVIDERS.items():
        record = by_provider.get(provider) or {}
        providers.append(
            {
                "provider": provider,
                "label": label,
                "theme_label": PROVIDER_THEME_LABELS.get(provider),
                "viewpoint": _provider_viewpoint(provider, asof),
                "enabled": bool(record.get("summary_lines")),
                "generated_at": record.get("generated_at"),
                "source": record.get("source") or "manual_pending",
                "summary_lines": record.get("summary_lines") or [],
            }
        )
    return {
        "enabled": any(item["enabled"] for item in providers),
        "market": market,
        "asof": asof,
        "layout": "two_small_blocks",
        "title": "퀀트투자 모델 브리핑 참고",
        "compliance_meta": {
            "public_same_for_all_users": True,
            "non_personalized": True,
            "advisory_action_signal": False,
            "intended_use": "market_briefing_reference",
        },
        "providers": providers,
    }


def load_previous_ai_brief(*, market: str, asof: str, provider: str) -> dict | None:
    records = _matching_records(market=market, provider=provider)
    current_dt = _parse_asof(asof)
    previous = [record for record in records if _parse_asof(record.get("asof")) < current_dt]
    if not previous:
        return None
    previous.sort(key=lambda item: _parse_asof(item.get("asof")), reverse=True)
    return previous[0]


def upsert_ai_brief(*, market: str, asof: str, provider: str, summary_lines: list[str], generated_at: str, source: str = "manual") -> dict:
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported AI provider: {provider}")
    cleaned_lines = [line.strip() for line in summary_lines if line and line.strip()]
    if len(cleaned_lines) > 4:
        raise ValueError("AI brief must contain at most 4 lines.")
    store = _load_store()
    records = store.get("records") or []
    updated = False
    for record in records:
        if record.get("market") == market and record.get("asof") == asof and record.get("provider") == provider:
            record.update(
                {
                    "market": market,
                    "asof": asof,
                    "provider": provider,
                    "generated_at": generated_at,
                    "source": source,
                    "summary_lines": cleaned_lines,
                }
            )
            updated = True
            break
    if not updated:
        records.append(
            {
                "market": market,
                "asof": asof,
                "provider": provider,
                "generated_at": generated_at,
                "source": source,
                "summary_lines": cleaned_lines,
            }
        )
    store["records"] = records
    _write_store(store)
    return load_ai_briefs(market=market, asof=asof)


def _gemini_direction_guidance(state_label: str | None, state_score: float | None) -> str:
    score = float(state_score or 0.0)
    if state_label in {"강상승", "상승"} or score >= 1.0:
        return "시장 주 방향은 분명한 상승 쪽으로 설명하세요. '소폭', '완만', '미미한' 같은 과도한 축소 표현은 피하세요. 다만 내부 확산과 변동성의 제약은 별도로 짚으세요."
    if state_label in {"강하락", "하락"} or score <= -1.0:
        return "시장 주 방향은 분명한 약세 쪽으로 설명하세요. 하락 압력을 약하게 표현하지 말고, 경계감이 우세한 분위기를 먼저 전하세요."
    return "시장 주 방향이 뚜렷하지 않다면 혼조 또는 중립적 분위기를 객관적으로 설명하세요."


def build_ai_brief_prompt(*, provider: str, market: str, asof: str, summary: dict, detail: dict, previous_lines: list[str] | None = None, market_context: dict | None = None, intraday_context: dict | None = None) -> str:
    top_signals = summary.get("top_signals") or []
    positive_points = detail.get("positive_points") or []
    warning_points = detail.get("warning_points") or []
    reference_note = summary.get("reference_note") or detail.get("observation_note")
    state = detail.get("state") or {}
    components = detail.get("components") or {}
    previous_text = " / ".join(previous_lines or []) or "없음"
    market_context = market_context or {}
    intraday_context = intraday_context or {}
    context_headlines = market_context.get("headlines") or []
    risk_headlines = market_context.get("risk_headlines") or []
    caution_bias = bool(market_context.get("caution_bias"))
    viewpoint = _provider_viewpoint(provider, asof)
    state_bridge = detail.get("state_intraday_bridge") or summary.get("state_intraday_bridge") or {}
    intraday = state_bridge.get("intraday") or {}
    intraday_direction = intraday.get("direction_label")
    intraday_summary = intraday.get("summary_line")
    intraday_flow = intraday.get("flow") or {}
    intraday_futures = intraday.get("futures") or {}
    bridge_text = state_bridge.get("bridge_text") or "없음"
    alignment = state_bridge.get("alignment") or "unavailable"

    common = (
        f"당신은 주간 브리핑용 퀀트투자 모델 해석에 연결되는 {market} 시장 브리핑 작성자입니다. "
        f"{asof} 기준 시장을 정확히 4문장으로 요약하세요. "
        "이 문장은 불특정 다수에게 동일하게 제공되는 설명형 시장 브리핑입니다. "
        "개인 맞춤 조언, 매수/매도 권유, 비중 확대/축소 제안, 타이밍 제시는 금지합니다. "
        "숫자 나열식 설명을 피하고, 시장 상태와 관찰 포인트를 설명형으로 정리하세요. "
        "직전 1시간 브리핑과 같은 표현, 같은 논점, 같은 문장 구조를 반복하지 마세요. "
        "이번 시간에 새로 관찰된 장중 신호가 있으면 반드시 그 변화를 반영하세요. "
        "매 문장은 완결형 평서문으로 끝내고, 공백 포함 약 30자 안팎의 밀도로 작성하세요. "
        f"정식 시장상태={state.get('label')}({state.get('score')}), 정식-장중 브리지={bridge_text}, alignment={alignment}, "
        f"장중 방향={intraday_direction}, 장중 요약={intraday_summary}, 선물={intraday_futures}, 수급={intraday_flow}, "
        f"상단 신호={top_signals[:3]}, 긍정 신호={positive_points[:3]}, 주의 신호={warning_points[:3]}, 참고 문장={reference_note}, "
        f"구성 점수={{trend:{components.get('trend', {}).get('score')}, breadth:{components.get('breadth', {}).get('score')}, risk:{components.get('risk', {}).get('score')}, defensive:{components.get('defensive_flow', {}).get('score')}}}, "
        f"직전 1시간 브리핑={previous_text}, 최근 시장 뉴스={context_headlines[:5]}, 위험 뉴스={risk_headlines[:3]}, caution_bias={caution_bias}. "
    )

    chatgpt_instruction = (
        f"ChatGPT 블록은 '모델 해석 참고' 관점으로 작성하세요. 이번 시간의 해석 관점은 '{(viewpoint or {}).get('label')}'. "
        "한 시간마다 관점을 바꾸기 위해, 이번 브리핑은 지정된 관점 하나에 집중해 해석하세요. "
        "시장 구조, 추세의 질, 위험 신호, 관찰 포인트를 설명형으로 정리하세요. "
        "정식 시장상태와 오늘 장중 흐름이 엇갈리면 그 차이를 1문장 이상으로 분명히 설명하세요. "
        "다른 시간대와 같은 각도 반복을 피하고, 이번 관점에서 새롭게 읽히는 포인트를 앞에 배치하세요. "
        "포지션, 비중, 매수, 매도, 대응 전략 같은 표현은 쓰지 마세요. "
        "macro_liquidity이면 금리/달러/유동성 축, macro_global이면 대외 이벤트와 위험자산 환경, micro_breadth이면 종목 확산과 내부 체력, micro_tape이면 단기 흐름과 변동성 구조를 중심으로 쓰세요. "
        "장중 선물과 수급이 약하면 그 이유를 함께 넣고, 장중과 정식 상태가 다르면 '중기 상태는 유지되지만 오늘은 조정' 같은 식으로 구분해서 쓰세요."
    )

    gemini_instruction = (
        f"제미나이 블록은 '시장 분위기 참고' 관점으로 작성하세요. 이번 시간의 중점 포인트는 '{(viewpoint or {}).get('label')}'. "
        "첫 문장에서 현재 장세의 주 방향을 객관적으로 분명하게 말하고, 정식 시장상태와 오늘 장중 흐름이 다르면 그 차이를 바로 설명하세요. "
        f"{_gemini_direction_guidance(state.get('label'), state.get('score'))} "
        "각 문장은 반드시 근거를 포함해 쓰세요. 예를 들어 지수 방향, 종목 확산력, 변동성, 달러/유가, 선물, 외국인/프로그램 수급, 최근 뉴스 중 하나 이상을 문장 안에 직접 넣으세요. "
        "장세의 공기와 분위기를 전하되, 추상적인 느낌만 말하지 말고 무엇 때문에 그런 분위기로 읽히는지 함께 설명하세요. "
        "'긴장감'이라는 단어는 쓰지 마세요. '변동성이 커진다', '상승세가 종목 전반으로 퍼지지 않는다', '외국인 순매도가 커서 조심스러운 분위기다'처럼 근거가 보이는 표현으로 바꾸세요. "
        "행동 지침이나 자문처럼 읽히는 문장은 쓰지 마세요. "
        "이번 시간의 focus에 맞춰 문장 1개 이상을 달라지게 쓰고, 장중 신호가 이전 시간과 다르면 그 변화를 우선 반영하세요."
    )

    provider_instruction = chatgpt_instruction if provider == "chatgpt" else gemini_instruction
    return common + provider_instruction
