from __future__ import annotations

import json
from pathlib import Path

from .analytics import component_summary, pick_top_signals
from .types import ComponentScores, MarketFeatures, StateHistory

API_VERSION = "v1"
API_ENDPOINTS = {
    "summary": "/api/v1/market-analysis/summary?market=KR",
    "detail": "/api/v1/market-analysis/detail?market=KR",
    "today_bridge": "/api/v1/market-analysis/today-bridge?market=KR",
    "manifest": "/api/v1/market-analysis/manifest?market=KR",
    "home": "/api/v1/market-analysis/home?market=KR",
    "page": "/api/v1/market-analysis/page?market=KR",
    "timeline": "/api/v1/market-analysis/timeline?market=KR",
    "asset_strength": "/api/v1/market-analysis/asset-strength?market=KR",
    "state_transition": "/api/v1/market-analysis/state-transition?market=KR",
    "model_background": "/api/v1/market-analysis/model-background?market=KR",
}
PAGE_SLOTS = {
    "main_home.hero_market_status": "summary",
    "main_home.top_signals": "summary.top_signals",
    "today_recommendation.market_bridge": "today_bridge",
    "market_analysis.header_state": "detail.state",
    "market_analysis.ai_brief_blocks": "detail.ai_briefs",
    "market_analysis.component_cards": "detail.components",
    "market_analysis.signal_lists": "detail.positive_points/detail.warning_points",
}
QUANTSERVICE_SLOT_FILES = {
    "main_home.hero_market_status": "quantservice_market_home.json#hero",
    "main_home.top_signals": "quantservice_market_home.json#top_signals",
    "today_recommendation.market_bridge": "quantservice_market_today.json#market_bridge",
    "market_analysis.header_state": "quantservice_market_page.json#header_state",
    "market_analysis.ai_brief_blocks": "quantservice_market_page.json#ai_briefs",
    "market_analysis.component_cards": "quantservice_market_page.json#component_cards",
    "market_analysis.signal_lists": "quantservice_market_page.json#signal_lists",
}

COMPONENT_LABELS = {
    "trend": "시장 추세 점검",
    "breadth": "시장 확산 점검",
    "risk": "시장 변동성 점검",
    "defensive_flow": "방어자산 선호 점검",
}

COMPONENT_DESCRIPTIONS = {
    "trend": "시장 추세 점검은 코스피·코스닥의 최근 흐름이 퀀트투자 모델 해석에 우호적인지 보여 주는 지표입니다.",
    "breadth": "시장 확산 점검은 일부 대형주만 오르는지, 많은 종목이 함께 움직이는지를 통해 모델 해석의 내부 체력을 보여 줍니다.",
    "risk": "시장 변동성 점검은 최근 변동성과 낙폭을 반영해 모델 해석 시 경계 수준을 보여 주는 지표입니다.",
    "defensive_flow": "방어자산 선호 점검은 달러·채권·금 같은 안전자산 선호가 모델 포트폴리오 해석 배경에 어떤 영향을 주는지 보여 줍니다.",
}

STATE_FIELD_DESCRIPTIONS = {
    "state_score": "상태점수는 여러 시장 신호를 합쳐 현재 장세가 퀀트투자 모델 해석에 어떤 배경을 만드는지 보여 주는 합성 점수입니다.",
    "breadth": "breadth는 지수 몇 개가 아니라 시장 안쪽 종목들이 얼마나 넓게 따라오는지를 뜻하며, 모델 해석의 내부 확산 근거로 쓰입니다.",
}

BRIEFING_COPY = {
    "service_definition": "다양한 시장 데이터 기반의 상황별 퀀트투자 모델 정보 서비스",
    "page_title": "시장 브리핑",
    "page_subtitle": "퀀트투자 모델 해석에 필요한 시장 상태를 같은 기준으로 정리합니다.",
    "summary_title": "시장 브리핑 요약",
    "signal_positive_label": "모델에 우호적인 신호",
    "signal_warning_label": "모델 해석상 주의할 신호",
    "observation_title": "이번 주 모델 해석 포인트",
    "observation_description": "현재 시장 상태를 기준으로 퀀트투자 모델을 읽을 때 참고할 핵심 포인트입니다.",
    "bridge_tone_label": "브리핑 톤",
    "usage_card_title": "이 시장 브리핑은 어디에 쓰이나요?",
    "usage_card_body": [
        "이 브리핑은 멀티애셋 데이터 기반 퀀트투자 모델을 해석하기 위한 공개 기준 데이터입니다.",
        "이번 주 모델 기준안과 변경내역은 이 시장 상태를 참고해 함께 읽을 수 있습니다.",
    ],
    "usage_card_links": [
        {"label": "이번 주 모델 기준안 보기", "target_menu": "이번 주 모델 기준안"},
        {"label": "변경내역 보기", "target_menu": "변경내역"},
    ],
    "data_source_note": "이 데이터는 주간 브리핑용 퀀트투자 모델 해석을 위한 공개 브리핑 데이터입니다.",
    "portfolio_context_note": "시장 상태 자체를 설명하는 동시에 모델 포트폴리오 변화의 배경 정보를 제공합니다.",
}

NOTICE_BLOCK = {
    "title": "주의사항",
    "body": [
        "본 정보는 공개된 기준에 따라 산출된 시장 브리핑용 참고 정보입니다.",
        "특정 이용자의 투자목적, 재산상황, 투자경험 또는 위험선호를 반영한 개별 자문이 아닙니다.",
        "투자판단은 이용자 본인의 책임이며, 자산가격 변동에 따라 원금손실이 발생할 수 있습니다.",
    ],
    "performance_link_note": "시장상태 정보는 모델 해석을 돕기 위한 참고자료이며, 특정 자산의 매수·매도 또는 비중 확대·축소를 직접 권유하지 않습니다.",
}

def _compliance_meta(asof: str | None) -> dict:
    return {
        "public_same_for_all_users": True,
        "non_personalized": True,
        "advisory_action_signal": False,
        "actual_investment_result": False,
        "backtest_result": False,
        "disclaimer_required": True,
        "consumer_channel": "public_market_brief",
        "generated_by": "QuantMarket",
        "intended_use": "market_briefing_reference",
        "model_version": "market_analysis_p1",
        "calculation_version": "market_analysis_p1_20260324",
        "asof": asof,
        "refresh_cycle": "hourly",
        "rebalance_frequency": "not_applicable",
    }


METRIC_DEFINITIONS = {
    "kospi_20d_ret": {
        "label": "코스피 20거래일 수익률",
        "semantic_type": "period_return_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "최근 20거래일 동안 코스피 종가가 얼마나 변했는지 나타내는 기간 수익률입니다.",
        "display_label_recommended": "코스피 1개월 수익률",
        "display_percent_value": True,
        "default_visible": False,
        "visibility_note": "현재 데이터 소스 정합성 확인 전까지는 사용자 화면 기본 노출보다 내부 검증용으로 쓰는 것을 권장합니다.",
    },
    "kospi_60d_ret": {
        "label": "코스피 60거래일 수익률",
        "semantic_type": "period_return_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "최근 60거래일 동안 코스피 종가가 얼마나 변했는지 나타내는 기간 수익률입니다.",
        "display_label_recommended": "코스피 3개월 수익률",
        "display_percent_value": True,
        "default_visible": False,
        "visibility_note": "현재 데이터 소스 정합성 확인 전까지는 사용자 화면 기본 노출보다 내부 검증용으로 쓰는 것을 권장합니다.",
    },
    "kosdaq_20d_ret": {
        "label": "코스닥 20거래일 수익률",
        "semantic_type": "period_return_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "최근 20거래일 동안 코스닥 종가가 얼마나 변했는지 나타내는 기간 수익률입니다.",
        "display_label_recommended": "코스닥 1개월 수익률",
        "display_percent_value": True,
        "default_visible": False,
        "visibility_note": "현재 데이터 소스 정합성 확인 전까지는 사용자 화면 기본 노출보다 내부 검증용으로 쓰는 것을 권장합니다.",
    },
    "above_20dma_ratio": {
        "label": "20일선 위 종목 비율",
        "semantic_type": "breadth_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "전체 대상 종목 중 현재가가 20일 이동평균선 위에 있는 종목 비율입니다.",
        "display_label_recommended": "20일선 위 종목 비율",
        "display_percent_value": True,
        "default_visible": True,
    },
    "above_60dma_ratio": {
        "label": "60일선 위 종목 비율",
        "semantic_type": "breadth_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "전체 대상 종목 중 현재가가 60일 이동평균선 위에 있는 종목 비율입니다.",
        "display_label_recommended": "60일선 위 종목 비율",
        "display_percent_value": True,
        "default_visible": True,
    },
    "adv_dec_ratio": {
        "label": "상승/하락 종목 비율",
        "semantic_type": "breadth_ratio",
        "unit": "ratio",
        "display_unit": "ratio",
        "description": "오른 종목 수와 내린 종목 수의 비율로, 시장 내부 확산력을 보여 줍니다.",
        "display_label_recommended": "상승/하락 종목 비율",
        "display_percent_value": False,
        "default_visible": True,
    },
    "realized_vol_20d": {
        "label": "20거래일 실현변동성",
        "semantic_type": "volatility_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "최근 20거래일 가격 흔들림의 크기를 요약한 값입니다.",
        "display_label_recommended": "최근 20일 변동성",
        "display_percent_value": True,
        "default_visible": True,
    },
    "drawdown_20d": {
        "label": "20거래일 낙폭",
        "semantic_type": "drawdown_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "최근 20거래일 안에서 고점 대비 현재 낙폭이 얼마나 되는지 보여 줍니다.",
        "display_label_recommended": "최근 20일 낙폭",
        "display_percent_value": True,
        "default_visible": True,
    },
    "usdkrw_20d_ret": {
        "label": "원달러 20거래일 변화율",
        "semantic_type": "period_return_ratio",
        "unit": "ratio",
        "display_unit": "percent",
        "description": "최근 20거래일 동안 원달러 환율이 얼마나 변했는지 나타냅니다.",
        "display_label_recommended": "원달러 1개월 변화율",
        "display_percent_value": True,
        "default_visible": True,
    },
    "rate_cd91_20d_chg": {
        "label": "CD91 20거래일 변화폭",
        "semantic_type": "rate_change",
        "unit": "percentage_point",
        "display_unit": "bp",
        "description": "최근 20거래일 동안 CD91 금리가 얼마나 움직였는지 보여 줍니다.",
        "display_label_recommended": "CD91 20일 변화폭",
        "display_percent_value": False,
        "default_visible": True,
    },
    "rate_ktb3y_20d_chg": {
        "label": "국고채3년 20거래일 변화폭",
        "semantic_type": "rate_change",
        "unit": "percentage_point",
        "display_unit": "bp",
        "description": "최근 20거래일 동안 국고채 3년 금리가 얼마나 움직였는지 보여 줍니다.",
        "display_label_recommended": "국고채3년 20일 변화폭",
        "display_percent_value": False,
        "default_visible": True,
    },
}


def _build_display_metrics(metrics: dict) -> dict:
    display: dict[str, dict] = {}
    for key, value in metrics.items():
        definition = METRIC_DEFINITIONS.get(key)
        if definition is None or not isinstance(value, (int, float)):
            continue
        item = {
            "label": definition.get("display_label_recommended") or definition.get("label") or key,
            "raw_value": value,
            "semantic_type": definition.get("semantic_type"),
            "description": definition.get("description"),
            "default_visible": definition.get("default_visible", True),
        }
        if definition.get("display_unit") == "percent":
            item["display_unit"] = "percent"
            item["display_value"] = round(float(value) * 100.0, 2)
        elif definition.get("display_unit") == "bp":
            item["display_unit"] = "bp"
            item["display_value"] = round(float(value) * 100.0, 1)
        else:
            item["display_unit"] = definition.get("display_unit") or definition.get("unit")
            item["display_value"] = round(float(value), 4)
        if definition.get("visibility_note"):
            item["visibility_note"] = definition["visibility_note"]
        display[key] = item
    return display


def _summary_line(scores: ComponentScores, features: MarketFeatures) -> str:
    if scores.total_score >= 1.0:
        return "공식 지표와 내부 breadth 기준으로 퀀트투자 모델 해석에 우호적인 상승 흐름이 우세합니다."
    if scores.total_score >= 0.3:
        return "지수 흐름은 우호적이지만 퀀트투자 모델 해석을 위해 내부 확산이 더 확인되는지 함께 볼 필요가 있습니다."
    if scores.total_score > -0.3:
        return "추세와 방어심리가 엇갈려 모델 해석상 뚜렷한 우세 방향은 아직 제한적입니다."
    if scores.total_score > -1.0:
        return "지수 방어력은 남아 있지만 모델 해석상 내부 확산은 약한 편으로 읽힙니다."
    return "하락 압력과 방어심리가 커져 퀀트투자 모델 해석에서도 경계가 우선되는 구간입니다."


def _reference_note(scores: ComponentScores) -> str:
    if scores.total_score >= 1.0:
        return "상승 흐름이 관찰되지만 퀀트투자 모델 해석을 위해 내부 확산과 변동성 지표를 함께 볼 필요가 있습니다."
    if scores.total_score >= 0.3:
        return "지수 흐름은 비교적 우호적이지만 모델 해석을 위해 내부 종목 확산과 위험 지표를 함께 살펴볼 구간입니다."
    if scores.total_score > -0.3:
        return "방향성 우위가 뚜렷하지 않아 모델 해석상 추세와 방어 신호를 함께 관찰할 필요가 있습니다."
    if scores.total_score > -1.0:
        return "지수 방어력보다 내부 약화 신호가 더 두드러지는지 모델 해석 기준으로 점검이 필요한 구간입니다."
    return "하락 압력과 방어 심리가 함께 강해지는 구간으로, 퀀트투자 모델 해석에서도 위험 신호 점검이 중요합니다."


def _component_status_badge(key: str, score: float) -> dict:
    if score >= 1.0:
        label = "좋음"
        tone = "good"
    elif score > -0.5:
        label = "보통"
        tone = "neutral"
    else:
        label = "나쁨"
        tone = "bad"

    reasons = {
        "trend": {
            "good": "상승 방향 신호가 우세합니다.",
            "neutral": "방향성 우위가 뚜렷하지 않습니다.",
            "bad": "하락 방향 신호가 우세합니다.",
        },
        "breadth": {
            "good": "상승 흐름이 종목 전반으로 비교적 퍼집니다.",
            "neutral": "내부 확산 신호가 혼재합니다.",
            "bad": "내부 종목 확산이 약한 편입니다.",
        },
        "risk": {
            "good": "변동성 부담이 상대적으로 낮습니다.",
            "neutral": "변동성 경계가 함께 존재합니다.",
            "bad": "변동성 부담이 큰 편입니다.",
        },
        "defensive_flow": {
            "good": "방어자산 쏠림이 강하지 않습니다.",
            "neutral": "방어 심리는 중립권입니다.",
            "bad": "방어자산 선호가 강해진 상태입니다.",
        },
    }
    reason = reasons.get(key, {}).get(tone, "시장 상태를 종합한 참고 판정입니다.")
    return {
        "label": label,
        "tone": tone,
        "reason": reason,
    }


def build_summary_payload(*, features: MarketFeatures, scores: ComponentScores, state: StateHistory) -> dict:
    positives, warnings = pick_top_signals(features, scores)
    top_signals = (warnings + positives)[:2]
    prev_text = state.prev_state_label or "초기 산출"
    return {
        "market": features.market,
        "asof": features.asof,
        "state_label": scores.state_label,
        "state_score": scores.total_score,
        "summary_line": _summary_line(scores, features),
        "change_vs_prev": f"{prev_text} -> {scores.state_label}",
        "top_signals": top_signals,
        "reference_note": _reference_note(scores),
        "state_intraday_bridge": None,
        "service_definition": BRIEFING_COPY["service_definition"],
        "summary_title": BRIEFING_COPY["summary_title"],
        "compliance_meta": _compliance_meta(features.asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_detail_payload(*, features: MarketFeatures, scores: ComponentScores, state: StateHistory, quant_context: dict | None = None, ai_note: dict | None = None) -> dict:
    quant_context = quant_context or {}
    positives, warnings = pick_top_signals(features, scores)
    metrics = {
            "kospi_1d_ret": features.kospi_1d_ret,
            "kospi_20d_ret": features.kospi_20d_ret,
            "kospi_60d_ret": features.kospi_60d_ret,
            "kosdaq_20d_ret": features.kosdaq_20d_ret,
            "kosdaq_60d_ret": features.kosdaq_60d_ret,
            "above_20dma_ratio": features.above_20dma_ratio,
            "above_60dma_ratio": features.above_60dma_ratio,
            "adv_dec_ratio": features.adv_dec_ratio,
            "new_high_count": features.new_high_count,
            "new_low_count": features.new_low_count,
            "breadth_universe_count": features.breadth_universe_count,
            "realized_vol_20d": features.realized_vol_20d,
            "drawdown_5d": features.drawdown_5d,
            "drawdown_20d": features.drawdown_20d,
            "usdkrw_20d_ret": features.usdkrw_20d_ret,
            "bond_20d_ret": features.bond_20d_ret,
            "gold_20d_ret": features.gold_20d_ret,
            "inverse_20d_ret": features.inverse_20d_ret,
            "rate_cd91_20d_chg": features.rate_cd91_20d_chg,
            "rate_ktb3y_20d_chg": features.rate_ktb3y_20d_chg,
            "regime_3m_score": features.regime_3m_score,
            "proxy_flags": {
                "breadth": bool(features.breadth_proxy_flag),
                "defensive_flow": bool(features.defensive_proxy_flag),
            },
        }
    return {
        "market": features.market,
        "asof": features.asof,
        "state": {
            "label": scores.state_label,
            "score": scores.total_score,
            "prev_label": state.prev_state_label,
            "change_direction": state.state_change_direction,
            "description": STATE_FIELD_DESCRIPTIONS["state_score"],
            "tooltip": STATE_FIELD_DESCRIPTIONS["state_score"],
        },
        "descriptions": {
            "state_score": STATE_FIELD_DESCRIPTIONS["state_score"],
            "breadth": STATE_FIELD_DESCRIPTIONS["breadth"],
            "components": COMPONENT_DESCRIPTIONS,
        },
        "page_meta": {
            "service_definition": BRIEFING_COPY["service_definition"],
            "page_title": BRIEFING_COPY["page_title"],
            "page_subtitle": BRIEFING_COPY["page_subtitle"],
        },
        "state_intraday_bridge": None,
        "components": {
            "trend": {
                "score": scores.trend_score,
                "label": COMPONENT_LABELS["trend"],
                "summary": component_summary("trend", scores.trend_score, features),
                "description": COMPONENT_DESCRIPTIONS["trend"],
                "status_badge": _component_status_badge("trend", scores.trend_score),
            },
            "breadth": {
                "score": scores.breadth_score,
                "label": COMPONENT_LABELS["breadth"],
                "summary": component_summary("breadth", scores.breadth_score, features),
                "description": COMPONENT_DESCRIPTIONS["breadth"],
                "status_badge": _component_status_badge("breadth", scores.breadth_score),
            },
            "risk": {
                "score": scores.risk_score,
                "label": COMPONENT_LABELS["risk"],
                "summary": component_summary("risk", scores.risk_score, features),
                "description": COMPONENT_DESCRIPTIONS["risk"],
                "status_badge": _component_status_badge("risk", scores.risk_score),
            },
            "defensive_flow": {
                "score": scores.defensive_flow_score,
                "label": COMPONENT_LABELS["defensive_flow"],
                "summary": component_summary("defensive_flow", scores.defensive_flow_score, features),
                "description": COMPONENT_DESCRIPTIONS["defensive_flow"],
                "status_badge": _component_status_badge("defensive_flow", scores.defensive_flow_score),
            },
        },
        "metrics": metrics,
        "metric_definitions": METRIC_DEFINITIONS,
        "display_metrics": _build_display_metrics(metrics),
        "data_sources": {
            "official_market": "QuantMarket market_analysis.db",
            "quant_readonly": {
                "price_db": str(quant_context.get("price_db")) if quant_context.get("price_db") else None,
                "regime_db": str(quant_context.get("regime_db")) if quant_context.get("regime_db") else None,
                "representative_assets": quant_context.get("representative_assets"),
            },
        },
        "positive_points": positives,
        "warning_points": warnings,
        "signal_labels": {
            "positive": BRIEFING_COPY["signal_positive_label"],
            "warning": BRIEFING_COPY["signal_warning_label"],
        },
        "observation_title": BRIEFING_COPY["observation_title"],
        "observation_description": BRIEFING_COPY["observation_description"],
        "observation_note": _reference_note(scores),
        "model_reference_points": {
            "title": BRIEFING_COPY["observation_title"],
            "description": BRIEFING_COPY["observation_description"],
            "body": _reference_note(scores),
        },
        "usage_guide_card": {
            "title": BRIEFING_COPY["usage_card_title"],
            "body": BRIEFING_COPY["usage_card_body"],
            "links": BRIEFING_COPY["usage_card_links"],
        },
        "ai_note": ai_note or {"enabled": False, "summary": None},
        "compliance_meta": _compliance_meta(features.asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_today_bridge_payload(*, features: MarketFeatures, scores: ComponentScores) -> dict:
    if scores.total_score >= 1.0:
        tone = "위험선호 환경"
    elif scores.total_score >= -0.3:
        tone = "중립 해석 환경"
    else:
        tone = "방어 우위 환경"
    return {
        "market": features.market,
        "asof": features.asof,
        "state_label": scores.state_label,
        "state_score": scores.total_score,
        "market_tone": tone,
        "tone_label": BRIEFING_COPY["bridge_tone_label"],
        "reference_text": _reference_note(scores),
        "state_intraday_bridge": None,
        "service_definition": BRIEFING_COPY["service_definition"],
        "compliance_meta": _compliance_meta(features.asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_quantservice_home_payload(*, summary: dict, detail: dict, today_bridge: dict) -> dict:
    return {
        "market": summary.get("market"),
        "asof": summary.get("asof"),
        "hero": {
            "title": BRIEFING_COPY["page_title"],
            "service_definition": BRIEFING_COPY["service_definition"],
            "subtitle": BRIEFING_COPY["page_subtitle"],
            "state_label": summary.get("state_label"),
            "state_score": summary.get("state_score"),
            "summary_line": summary.get("summary_line"),
            "change_vs_prev": summary.get("change_vs_prev"),
            "reference_note": summary.get("reference_note"),
            "state_intraday_bridge": summary.get("state_intraday_bridge"),
        },
        "top_signals": summary.get("top_signals", []),
        "today_bridge": {
            "tone_label": today_bridge.get("tone_label"),
            "market_tone": today_bridge.get("market_tone"),
            "reference_text": today_bridge.get("reference_text"),
            "state_label": today_bridge.get("state_label"),
            "state_intraday_bridge": today_bridge.get("state_intraday_bridge"),
        },
        "compliance_meta": _compliance_meta(summary.get("asof")),
        "notice_block": NOTICE_BLOCK,
        "component_preview": [
            {
                "key": key,
                "label": value.get("label"),
                "score": value.get("score"),
                "summary": value.get("summary"),
                "description": value.get("description") or COMPONENT_DESCRIPTIONS.get(key),
                "status_badge": value.get("status_badge"),
            }
            for key, value in (detail.get("components") or {}).items()
        ],
        "service_definition": BRIEFING_COPY["service_definition"],
        "consumer_slots": {
            "main_home.hero_market_status": "hero",
            "main_home.top_signals": "top_signals",
        },
    }


def build_quantservice_today_payload(*, summary: dict, today_bridge: dict) -> dict:
    return {
        "market": summary.get("market"),
        "asof": summary.get("asof"),
        "market_bridge": today_bridge,
        "service_definition": BRIEFING_COPY["service_definition"],
        "compliance_meta": _compliance_meta(summary.get("asof")),
        "notice_block": NOTICE_BLOCK,
        "headline": {
            "state_label": summary.get("state_label"),
            "summary_line": summary.get("summary_line"),
            "state_intraday_bridge": today_bridge.get("state_intraday_bridge"),
        },
        "consumer_slots": {
            "today_recommendation.market_bridge": "market_bridge",
        },
    }


def build_quantservice_page_payload(*, detail: dict, summary: dict, ai_briefs: dict | None = None) -> dict:
    component_cards = [
        {
            "key": key,
            "label": value.get("label"),
            "score": value.get("score"),
            "summary": value.get("summary"),
            "description": value.get("description") or COMPONENT_DESCRIPTIONS.get(key),
            "status_badge": value.get("status_badge"),
        }
        for key, value in (detail.get("components") or {}).items()
    ]
    return {
        "market": detail.get("market"),
        "asof": detail.get("asof"),
        "page_meta": detail.get("page_meta") or {
            "service_definition": BRIEFING_COPY["service_definition"],
            "page_title": BRIEFING_COPY["page_title"],
            "page_subtitle": BRIEFING_COPY["page_subtitle"],
        },
        "header_state": detail.get("state"),
        "state_intraday_bridge": detail.get("state_intraday_bridge"),
        "ai_briefs": ai_briefs or {
            "enabled": False,
            "market": detail.get("market"),
            "asof": detail.get("asof"),
            "title": "퀀트투자 모델 브리핑 참고",
            "layout": "two_small_blocks",
            "providers": [],
        },
        "component_cards": component_cards,
        "signal_lists": {
            "positive_label": detail.get("signal_labels", {}).get("positive") or BRIEFING_COPY["signal_positive_label"],
            "warning_label": detail.get("signal_labels", {}).get("warning") or BRIEFING_COPY["signal_warning_label"],
            "positive_points": detail.get("positive_points", []),
            "warning_points": detail.get("warning_points", []),
            "observation_title": detail.get("observation_title") or BRIEFING_COPY["observation_title"],
            "observation_description": detail.get("observation_description") or BRIEFING_COPY["observation_description"],
            "observation_note": detail.get("observation_note"),
        },
        "metrics": detail.get("metrics", {}),
        "metric_definitions": detail.get("metric_definitions", {}),
        "display_metrics": detail.get("display_metrics", {}),
        "descriptions": detail.get("descriptions", {}),
        "data_sources": detail.get("data_sources", {}),
        "summary_line": summary.get("summary_line"),
        "service_definition": BRIEFING_COPY["service_definition"],
        "usage_guide_card": detail.get("usage_guide_card") or {
            "title": BRIEFING_COPY["usage_card_title"],
            "body": BRIEFING_COPY["usage_card_body"],
            "links": BRIEFING_COPY["usage_card_links"],
        },
        "data_source_note": BRIEFING_COPY["data_source_note"],
        "portfolio_context_note": BRIEFING_COPY["portfolio_context_note"],
        "compliance_meta": _compliance_meta(detail.get("asof")),
        "notice_block": NOTICE_BLOCK,
        "consumer_slots": {
            "market_analysis.header_state": "header_state",
            "market_analysis.ai_brief_blocks": "ai_briefs",
            "market_analysis.component_cards": "component_cards",
            "market_analysis.signal_lists": "signal_lists",
        },
    }


def build_api_response(*, endpoint: str, market: str, asof: str, payload: dict) -> dict:
    return {
        "api_version": API_VERSION,
        "endpoint": endpoint,
        "market": market,
        "asof": asof,
        "generated_by": "QuantMarket",
        "compliance_meta": _compliance_meta(asof),
        "data": payload,
    }


def build_manifest(*, features: MarketFeatures, db_path: Path) -> dict:
    return {
        "market": features.market,
        "asof": features.asof,
        "db_path": str(db_path),
        "artifacts": [
            "market_analysis_summary.json",
            "market_analysis_detail.json",
            "market_analysis_today_bridge.json",
            "market_analysis_manifest.json",
            "market_briefing_timeline.json",
            "market_briefing_asset_strength.json",
            "market_briefing_state_transition.json",
            "market_briefing_model_background.json",
            "api_v1_market_analysis_summary.json",
            "api_v1_market_analysis_detail.json",
            "api_v1_market_analysis_today_bridge.json",
            "quantservice_market_home.json",
            "quantservice_market_today.json",
            "quantservice_market_page.json",
            "quantservice_market_timeline.json",
            "quantservice_market_asset_strength.json",
            "quantservice_market_state_transition.json",
            "quantservice_market_model_background.json",
            "quantservice_market_manifest.json",
            "api_v1_market_analysis_home.json",
            "api_v1_market_analysis_page.json",
            "api_v1_market_analysis_timeline.json",
            "api_v1_market_analysis_asset_strength.json",
            "api_v1_market_analysis_state_transition.json",
            "api_v1_market_analysis_model_background.json",
        ],
        "api_endpoints": API_ENDPOINTS,
        "page_slots": PAGE_SLOTS,
        "producer": "QuantMarket",
        "consumer": "QuantService",
        "version": "p1",
        "compliance_meta": _compliance_meta(features.asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_quantservice_manifest(*, features: MarketFeatures, db_path: Path, source_snapshot_dir: Path, handoff_dir: Path) -> dict:
    return {
        "market": features.market,
        "asof": features.asof,
        "generated_by": "QuantMarket",
        "consumer": "QuantService",
        "handoff_version": "2026-03-24-p2",
        "compliance_meta": _compliance_meta(features.asof),
        "notice_block": NOTICE_BLOCK,
        "freshness": {
            "target_update_interval_minutes": 60,
            "consumer_warning_after_minutes": 90,
            "consumer_stale_after_minutes": 180,
        },
        "source_db_path": str(db_path),
        "source_snapshot_dir": str(source_snapshot_dir),
        "handoff_dir": str(handoff_dir),
        "files": {
            "home": "quantservice_market_home.json",
            "today": "quantservice_market_today.json",
            "page": "quantservice_market_page.json",
            "manifest": "quantservice_market_manifest.json",
            "api_home": "api_v1_market_analysis_home.json",
            "api_page": "api_v1_market_analysis_page.json",
            "api_summary": "api_v1_market_analysis_summary.json",
            "api_detail": "api_v1_market_analysis_detail.json",
            "api_today_bridge": "api_v1_market_analysis_today_bridge.json",
        },
        "optional_files": {
            "timeline": "quantservice_market_timeline.json",
            "asset_strength": "quantservice_market_asset_strength.json",
            "state_transition": "quantservice_market_state_transition.json",
            "model_background": "quantservice_market_model_background.json",
            "api_timeline": "api_v1_market_analysis_timeline.json",
            "api_asset_strength": "api_v1_market_analysis_asset_strength.json",
            "api_state_transition": "api_v1_market_analysis_state_transition.json",
            "api_model_background": "api_v1_market_analysis_model_background.json",
        },
        "slot_files": QUANTSERVICE_SLOT_FILES,
        "api_endpoints": API_ENDPOINTS,
        "upload_policy": {
            "manifest_written_last": True,
            "utf8_json": True,
            "atomic_current_replace_target": True,
        },
        "data_lineage": {
            "producer": "QuantMarket",
            "consumer": "QuantService",
            "public_rollout_phase": "market_briefing_enhancement_phase1",
        },
        "notes": [
            "QuantService can read these handoff artifacts from local sync or a remote current URL with the same filenames.",
            "QuantService remains the UI layer; QuantMarket remains the producer of market-analysis data.",
            "QuantMarket publishes current payload files first and updates quantservice_market_manifest.json last.",
            "optional_files are phase1 public enhancement payloads and should gracefully fallback when absent.",
        ],
        "branding_copy": {
            "service_definition": BRIEFING_COPY["service_definition"],
            "page_title": BRIEFING_COPY["page_title"],
            "page_subtitle": BRIEFING_COPY["page_subtitle"],
            "signal_positive_label": BRIEFING_COPY["signal_positive_label"],
            "signal_warning_label": BRIEFING_COPY["signal_warning_label"],
            "observation_title": BRIEFING_COPY["observation_title"],
            "bridge_tone_label": BRIEFING_COPY["bridge_tone_label"],
        },
    }


def write_payload_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
