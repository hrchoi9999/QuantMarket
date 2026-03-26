from __future__ import annotations

from typing import Any


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def build_admin_market_timeline_payload(con, *, market: str, asof: str) -> dict:
    points = _rows_to_dicts(
        con.execute(
            """
            SELECT s.asof, s.state_label, s.state_score, s.prev_state_label, s.state_change_direction,
                   c.trend_score, c.breadth_score, c.risk_score, c.defensive_flow_score, c.total_score
            FROM market_state_history s
            JOIN market_component_scores c
              ON s.market = c.market AND s.asof = c.asof
            WHERE s.market = ? AND s.asof <= ?
            ORDER BY s.asof DESC
            LIMIT 72
            """,
            (market, asof),
        ).fetchall()
    )
    points.reverse()
    latest = points[-1] if points else None
    return {
        "market": market,
        "asof": asof,
        "title": "시장 브리핑 타임라인",
        "description": "최근 시장상태와 핵심 점수 흐름을 시간 순서대로 볼 수 있는 admin 전용 데이터입니다.",
        "current_state": latest,
        "points": points,
    }


def build_admin_asset_strength_payload(con, *, market: str, asof: str) -> dict:
    current_assets = _rows_to_dicts(
        con.execute(
            """
            SELECT asset_group, ret_20d, strength_score, strength_rank, strength_label, created_at
            FROM market_asset_relative_strength_hourly
            WHERE market = ? AND asof = ?
            ORDER BY strength_rank ASC, asset_group ASC
            """,
            (market, asof),
        ).fetchall()
    )
    rank_history = _rows_to_dicts(
        con.execute(
            """
            SELECT asof, asset_group, strength_rank, strength_score, strength_label
            FROM market_asset_relative_strength_hourly
            WHERE market = ? AND asof <= ?
            ORDER BY asof DESC, strength_rank ASC
            LIMIT 120
            """,
            (market, asof),
        ).fetchall()
    )
    return {
        "market": market,
        "asof": asof,
        "title": "자산군 상대강도 브리핑",
        "description": "주식, 달러, 채권, 금 등 주요 자산군의 상대강도를 비교하는 admin 전용 데이터입니다.",
        "current_assets": current_assets,
        "rank_history": rank_history,
    }


def build_admin_state_transition_payload(con, *, market: str, asof: str) -> dict:
    current = con.execute(
        """
        SELECT current_state, prev_state, duration_hours, transition_count_5d, transition_count_20d, stability_score, created_at
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
            LIMIT 30
            """,
            (market, asof),
        ).fetchall()
    )
    return {
        "market": market,
        "asof": asof,
        "title": "상태 전이 브리핑",
        "description": "현재 상태의 지속 시간과 최근 상태 전이 빈도를 보여 주는 admin 전용 데이터입니다.",
        "current": dict(current) if current else None,
        "recent_changes": recent_changes,
    }


def build_admin_model_background_payload(
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
    top_assets = (asset_strength.get("current_assets") or [])[:3]
    bottom_assets = sorted(
        asset_strength.get("current_assets") or [],
        key=lambda item: item.get("strength_rank") or 999,
        reverse=True,
    )[:2]
    return {
        "market": market,
        "asof": asof,
        "title": "모델 해석 백그라운드",
        "description": "이번 시장 브리핑을 모델 기준안과 연결해 읽기 위한 admin 전용 요약 데이터입니다.",
        "state_label": summary.get("state_label"),
        "state_score": summary.get("state_score"),
        "summary_line": summary.get("summary_line"),
        "reference_note": summary.get("reference_note"),
        "briefing_tone": today_bridge.get("market_tone"),
        "model_background_points": [
            summary.get("summary_line"),
            detail.get("observation_note"),
            (state_transition.get("current") or {}).get("current_state"),
        ],
        "favorable_signals": detail.get("positive_points") or [],
        "caution_signals": detail.get("warning_points") or [],
        "top_assets": top_assets,
        "bottom_assets": bottom_assets,
        "state_transition": state_transition.get("current"),
        "latest_timeline_point": (timeline.get("points") or [])[-1] if timeline.get("points") else None,
    }


def build_admin_manifest(*, market: str, asof: str, admin_snapshot_dir: str, admin_handoff_dir: str) -> dict:
    return {
        "market": market,
        "asof": asof,
        "visibility": "admin_only_pre_publish",
        "title": "QuantMarket admin market payload manifest",
        "files": {
            "timeline": "admin_market_timeline.json",
            "asset_strength": "admin_market_asset_strength.json",
            "state_transition": "admin_market_state_transition.json",
            "model_background": "admin_market_model_background.json",
            "manifest": "admin_market_manifest.json",
        },
        "snapshot_dir": admin_snapshot_dir,
        "handoff_dir": admin_handoff_dir,
        "note": "이 파일셋은 admin 검토용이며, 사용자 최종 승인 전까지 공개 웹서비스에 연결하지 않습니다.",
    }
