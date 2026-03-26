from __future__ import annotations

from typing import Any


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def build_public_market_timeline_payload(con, *, market: str, asof: str) -> dict:
    points = _rows_to_dicts(
        con.execute(
            """
            SELECT s.asof, s.state_label, s.state_score,
                   c.trend_score, c.breadth_score, c.risk_score, c.defensive_flow_score, c.total_score
            FROM market_state_history s
            JOIN market_component_scores c
              ON s.market = c.market AND s.asof = c.asof
            WHERE s.market = ? AND s.asof <= ?
            ORDER BY s.asof DESC
            LIMIT 24
            """,
            (market, asof),
        ).fetchall()
    )
    points.reverse()
    latest = points[-1] if points else None
    previous = points[-2] if len(points) >= 2 else None
    direction = "unchanged"
    if latest and previous:
        if (latest.get("total_score") or 0.0) > (previous.get("total_score") or 0.0):
            direction = "stronger"
        elif (latest.get("total_score") or 0.0) < (previous.get("total_score") or 0.0):
            direction = "weaker"
    return {
        "market": market,
        "asof": asof,
        "title": "상태 타임라인",
        "description": "최근 시장상태와 핵심 점수 흐름을 시간순으로 정리한 공개 브리핑 데이터입니다.",
        "current_state": latest,
        "trend_direction": direction,
        "points": points,
    }


def build_public_market_asset_strength_payload(con, *, market: str, asof: str) -> dict:
    current_assets = _rows_to_dicts(
        con.execute(
            """
            SELECT asset_group, ret_20d, strength_score, strength_rank, strength_label
            FROM market_asset_relative_strength_hourly
            WHERE market = ? AND asof = ?
            ORDER BY strength_rank ASC, asset_group ASC
            """,
            (market, asof),
        ).fetchall()
    )
    top_assets = current_assets[:2]
    bottom_assets = sorted(current_assets, key=lambda item: item.get("strength_rank") or 999, reverse=True)[:2]
    return {
        "market": market,
        "asof": asof,
        "title": "자산군 상대강도",
        "description": "주요 자산군의 최근 상대 흐름을 비교해 현재 어떤 자산이 상대적으로 강한지 보여 줍니다.",
        "assets": current_assets,
        "top_assets": top_assets,
        "bottom_assets": bottom_assets,
    }


def build_public_market_state_transition_payload(con, *, market: str, asof: str) -> dict:
    current = con.execute(
        """
        SELECT current_state, prev_state, duration_hours, transition_count_5d, transition_count_20d, stability_score
        FROM market_state_transition_stats
        WHERE market = ? AND asof = ?
        """,
        (market, asof),
    ).fetchone()
    recent_changes = _rows_to_dicts(
        con.execute(
            """
            SELECT asof, state_label, prev_state_label, state_change_direction, state_score
            FROM market_state_history
            WHERE market = ? AND asof <= ?
            ORDER BY asof DESC
            LIMIT 10
            """,
            (market, asof),
        ).fetchall()
    )
    current_dict = dict(current) if current else None
    return {
        "market": market,
        "asof": asof,
        "title": "상태 전이 요약",
        "description": "현재 상태가 얼마나 이어지고 있는지와 최근 상태 변화 빈도를 요약한 공개 브리핑 데이터입니다.",
        "current": current_dict,
        "recent_changes": recent_changes,
    }


def build_public_market_model_background_payload(
    *,
    market: str,
    asof: str,
    summary: dict,
    detail: dict,
    today_bridge: dict,
    timeline: dict,
    asset_strength: dict,
    state_transition: dict,
) -> dict:
    top_assets = asset_strength.get("top_assets") or []
    bottom_assets = asset_strength.get("bottom_assets") or []
    current_transition = state_transition.get("current") or {}
    timeline_point = timeline.get("current_state") or {}
    return {
        "market": market,
        "asof": asof,
        "title": "모델 해석 백그라운드",
        "description": "현재 시장브리핑을 모델 기준안과 연결해서 읽기 위한 공개 배경 데이터입니다.",
        "state_label": summary.get("state_label"),
        "state_score": summary.get("state_score"),
        "briefing_tone": today_bridge.get("market_tone"),
        "summary_line": summary.get("summary_line"),
        "reference_note": summary.get("reference_note"),
        "model_background_points": [
            summary.get("summary_line"),
            detail.get("observation_note"),
            f"현재 상태 지속 시간은 {round((current_transition.get('duration_hours') or 0.0), 1)}시간입니다." if current_transition else None,
        ],
        "favorable_signals": (detail.get("positive_points") or [])[:3],
        "caution_signals": (detail.get("warning_points") or [])[:3],
        "top_assets": top_assets,
        "bottom_assets": bottom_assets,
        "state_transition": current_transition,
        "latest_timeline_point": timeline_point,
    }
