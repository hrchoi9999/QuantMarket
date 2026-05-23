from __future__ import annotations

from .payloads import NOTICE_BLOCK, _compliance_meta


SOURCE_TIERS = {
    "official": {
        "label": "official",
        "description": "공식 또는 공식에 준하는 기준 데이터입니다.",
        "examples": ["KRX 종가 데이터", "DART 공시", "수동 검증 금리 seed"],
    },
    "official_delayed": {
        "label": "official_delayed",
        "description": "공식 계열이지만 장중 또는 반영 시점이 지연될 수 있는 데이터입니다.",
        "examples": ["일부 장마감 후 반영 데이터"],
    },
    "proxy": {
        "label": "proxy",
        "description": "공식 실시간 데이터가 없을 때 방향성과 분위기를 참고하기 위한 대체 데이터입니다.",
        "examples": ["Yahoo chart 기반 장중 프록시", "미국 상장 한국 ETF", "Naver breadth fallback"],
    },
    "fallback": {
        "label": "fallback",
        "description": "실시간/정상 수집 실패 시 깨짐을 막기 위해 직전 값이나 대체 방식으로 유지한 데이터입니다.",
        "examples": ["전일 종가 유지", "missing series 빈값 처리"],
    },
}


def build_market_analysis_tabs_payload(
    *,
    market: str,
    asof: str,
    generated_at: str,
) -> dict:
    return {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "title": "시장 분석",
        "description": "시장 데이터를 차트와 표 중심으로 나누어 보는 공개형 데이터 열람 페이지입니다.",
        "tabs": [
            {
                "tab_id": "market_state",
                "label": "시장 상태",
                "description": "시장 상태점수와 상태 전이 흐름을 봅니다.",
                "current_files": [
                    "quantservice_market_timeline.json",
                    "quantservice_market_state_transition.json",
                ],
                "history_files": [
                    "quantservice_market_timeline_history.json",
                    "quantservice_market_state_transition_history.json",
                ],
            },
            {
                "tab_id": "asset_strength",
                "label": "자산 강도",
                "description": "주요 자산군의 상대강도와 최근 흐름을 비교합니다.",
                "current_files": [
                    "quantservice_market_asset_strength.json",
                ],
                "history_files": [
                    "quantservice_market_asset_strength_history.json",
                ],
            },
            {
                "tab_id": "intraday_overnight",
                "label": "장중/야간 참고",
                "description": "오늘 장중 흐름과 내일 시장 전망 참고 레이어를 함께 봅니다.",
                "current_files": [
                    "quantservice_market_live_context.json",
                    "quantservice_market_next_day_preview.json",
                ],
                "history_files": [
                    "quantservice_market_next_day_preview_history.json",
                ],
            },
            {
                "tab_id": "data_guide",
                "label": "데이터 해설",
                "description": "지표 의미, 데이터 출처, official/proxy/fallback 구분을 설명합니다.",
                "current_files": [
                    "quantservice_market_data_guide.json",
                ],
                "history_files": [],
            },
        ],
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_market_live_context_payload(
    *,
    market: str,
    asof: str,
    summary: dict,
    detail: dict,
    today_bridge: dict,
    next_day_preview: dict,
) -> dict:
    state_intraday_bridge = (
        today_bridge.get("state_intraday_bridge")
        or detail.get("state_intraday_bridge")
        or summary.get("state_intraday_bridge")
        or {}
    )
    intraday = state_intraday_bridge.get("intraday") or {}
    return {
        "market": market,
        "asof": asof,
        "title": "장중/야간 참고",
        "description": "종가 기준 시장 흐름과 별도로, 오늘 장중 흐름과 다음 거래일 장초반 참고 신호를 함께 정리한 공개 데이터입니다.",
        "state_intraday_bridge": state_intraday_bridge,
        "intraday_reference": {
            "enabled": bool(intraday),
            "label": state_intraday_bridge.get("intraday_label") or "오늘 장중 흐름",
            "description": state_intraday_bridge.get("intraday_description") or "장중 참고 레이어",
            "asof": intraday.get("asof"),
            "direction_label": intraday.get("direction_label"),
            "total_score": intraday.get("total_score"),
            "summary_line": intraday.get("summary_line"),
            "futures": intraday.get("futures") or {},
            "flow": intraday.get("flow") or {},
        },
        "next_day_preview": next_day_preview,
        "view_mode": {
            "market_flow": "정식/종가 기준",
            "intraday": "장중 참고",
            "overnight": "다음 거래일 장초반 참고",
        },
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_market_data_guide_payload(
    *,
    market: str,
    asof: str,
    detail: dict,
) -> dict:
    metrics = detail.get("metric_definitions") or {}
    descriptions = detail.get("descriptions") or {}
    display_metrics = detail.get("display_metrics") or {}
    return {
        "market": market,
        "asof": asof,
        "title": "데이터 해설",
        "description": "시장 분석 화면에서 쓰이는 지표 의미와 데이터 출처 계층을 설명합니다.",
        "state_score_guide": {
            "label": "상태점수",
            "description": descriptions.get("state_score"),
        },
        "breadth_guide": {
            "label": "breadth",
            "description": descriptions.get("breadth"),
        },
        "component_descriptions": descriptions.get("components") or {},
        "metric_catalog": [
            {
                "metric_key": key,
                "label": item.get("label"),
                "semantic_type": item.get("semantic_type"),
                "display_unit": item.get("display_unit"),
                "description": item.get("description"),
                "default_visible": item.get("default_visible"),
                "visibility_note": item.get("visibility_note"),
            }
            for key, item in metrics.items()
        ],
        "default_visible_metrics": [
            {
                "metric_key": key,
                "label": item.get("label"),
                "display_unit": item.get("display_unit"),
                "description": item.get("description"),
            }
            for key, item in display_metrics.items()
            if item.get("default_visible", True)
        ],
        "source_tiers": SOURCE_TIERS,
        "data_usage_note": "시장 분석은 공개형 데이터 열람 서비스이며, 지표 해석을 돕는 참고 정보입니다.",
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }
