from __future__ import annotations

import json
import sqlite3
from datetime import datetime


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _market_side_from_score(score: float | None) -> str:
    value = float(score or 0.0)
    if value >= 0.3:
        return "bullish"
    if value <= -0.3:
        return "bearish"
    return "neutral"


def load_latest_intraday_context(con: sqlite3.Connection, *, market: str, asof: str) -> dict | None:
    state_row = con.execute(
        """
        SELECT *
        FROM market_intraday_state
        WHERE market = ? AND session_date = ? AND asof <= ?
        ORDER BY asof DESC
        LIMIT 1
        """,
        (market, asof[:10], asof),
    ).fetchone()
    if not state_row:
        return None
    state = dict(state_row)
    intraday_asof = state["asof"]
    futures_rows = [
        dict(row)
        for row in con.execute(
            """
            SELECT *
            FROM market_intraday_futures_snapshot
            WHERE market = ? AND asof = ?
            ORDER BY contract_code ASC
            """,
            (market, intraday_asof),
        ).fetchall()
    ]
    flow_rows = []
    for row in con.execute(
        """
        SELECT *
        FROM market_intraday_flow_signal
        WHERE market = ? AND asof = ?
        ORDER BY signal_code ASC
        """,
        (market, intraday_asof),
    ).fetchall():
        item = dict(row)
        try:
            item["detail"] = json.loads(item.get("detail_json") or "{}")
        except Exception:
            item["detail"] = {}
        flow_rows.append(item)
    breadth_rows = [
        dict(row)
        for row in con.execute(
            """
            SELECT *
            FROM market_intraday_breadth
            WHERE market = ? AND asof = ?
            ORDER BY universe_code ASC
            """,
            (market, intraday_asof),
        ).fetchall()
    ]
    return {
        "state": state,
        "futures": futures_rows,
        "flow_signals": flow_rows,
        "breadth": breadth_rows,
    }


def build_state_intraday_bridge(*, summary: dict, detail: dict, intraday_context: dict | None) -> dict:
    medium_label = summary.get("state_label")
    medium_score = float(summary.get("state_score") or 0.0)
    medium_side = _market_side_from_score(medium_score)
    bridge = {
        "enabled": False,
        "medium_term_label": "정식 시장상태(전일 종가 기준)",
        "medium_term_state_label": medium_label,
        "medium_term_state_score": medium_score,
        "intraday_label": "오늘 장중 흐름(참고용)",
        "alignment": "unavailable",
        "display_label": medium_label,
        "bridge_text": "정식 시장상태는 전일 종가 기준으로 산출됩니다.",
        "basis_lines": [
            "정식 시장상태는 최근 추세와 breadth를 반영한 기준값입니다.",
        ],
        "intraday": None,
    }
    if not intraday_context or not intraday_context.get("state"):
        return bridge

    intraday_state = intraday_context["state"]
    intraday_score = float(intraday_state.get("total_score") or 0.0)
    intraday_side = _market_side_from_score(intraday_score)
    alignment = "aligned" if medium_side == intraday_side else "divergent"
    if medium_side == "neutral" or intraday_side == "neutral":
        alignment = "mixed"

    if medium_side == "bullish" and intraday_side == "bearish":
        display_label = "상승 유지, 단기 조정 동반"
        bridge_text = "정식 시장상태는 상승이지만, 오늘 장중에는 단기 조정 흐름이 나타납니다."
    elif medium_side == "bearish" and intraday_side == "bullish":
        display_label = "하락 상태, 단기 반등 동반"
        bridge_text = "정식 시장상태는 약세지만, 오늘 장중에는 단기 반등 흐름이 관찰됩니다."
    elif alignment == "aligned" and medium_side == "bullish":
        display_label = "상승 흐름 유지"
        bridge_text = "정식 시장상태와 오늘 장중 흐름이 모두 상승 쪽으로 같은 방향을 가리킵니다."
    elif alignment == "aligned" and medium_side == "bearish":
        display_label = "하락 흐름 유지"
        bridge_text = "정식 시장상태와 오늘 장중 흐름이 모두 약세 쪽으로 같은 방향을 가리킵니다."
    else:
        display_label = f"{medium_label}, 오늘 흐름 혼조"
        bridge_text = "정식 시장상태와 오늘 장중 흐름의 방향이 완전히 같지는 않아 함께 해석할 필요가 있습니다."

    basis_lines = [
        f"정식 시장상태 근거: {summary.get('summary_line')}",
        f"장중 흐름 근거: {intraday_state.get('summary_line')}",
    ]

    futures = intraday_context.get("futures") or []
    flow_signals = intraday_context.get("flow_signals") or []
    futures_row = futures[0] if futures else None
    foreigner = next((row for row in flow_signals if row.get("signal_code") == "FOREIGNER_NET"), None)
    program = next((row for row in flow_signals if row.get("signal_code") == "PROGRAM_TOTAL_NET"), None)

    intraday = {
        "asof": intraday_state.get("asof"),
        "session_status": intraday_state.get("session_status"),
        "direction_label": intraday_state.get("direction_label"),
        "total_score": intraday_score,
        "summary_line": intraday_state.get("summary_line"),
        "futures": {
            "contract_name": futures_row.get("contract_name"),
            "change_pct": futures_row.get("change_pct"),
            "price": futures_row.get("price"),
        } if futures_row else None,
        "flow": {
            "foreigner_net": foreigner.get("metric_value") if foreigner else None,
            "program_total_net": program.get("metric_value") if program else None,
        },
    }

    bridge.update(
        {
            "enabled": True,
            "alignment": alignment,
            "display_label": display_label,
            "bridge_text": bridge_text,
            "basis_lines": basis_lines,
            "intraday": intraday,
        }
    )
    return bridge
