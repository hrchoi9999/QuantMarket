from __future__ import annotations

import json
import math
from typing import Any

from .payloads import NOTICE_BLOCK, _compliance_meta

INDEX_PANEL_SPECS = [
    {"index_code": "1001", "index_name": "KOSPI"},
    {"index_code": "2001", "index_name": "KOSDAQ"},
    {"index_code": "1028", "index_name": "KOSPI200"},
]

DART_PLANNED_FIELDS = [
    "filing_count_total",
    "filing_count_by_type",
    "risk_event_count",
    "highlights",
    "recent_filings",
]


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _safe_ret(current: float | None, previous: float | None) -> float | None:
    if current in (None, 0) or previous in (None, 0):
        return None
    return float(current) / float(previous) - 1.0


def _window_return(closes: list[float], offset: int) -> float | None:
    if len(closes) <= offset:
        return None
    return _safe_ret(closes[0], closes[offset])


def _realized_vol(closes: list[float], periods: int = 20) -> float | None:
    if len(closes) < periods + 1:
        return None
    window = closes[: periods + 1]
    returns: list[float] = []
    for idx in range(len(window) - 1):
        current = window[idx]
        previous = window[idx + 1]
        if current in (None, 0) or previous in (None, 0):
            continue
        returns.append(math.log(float(current) / float(previous)))
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252.0)


def _drawdown(closes: list[float], periods: int = 20) -> float | None:
    if not closes:
        return None
    window = closes[:periods] if len(closes) >= periods else closes
    if not window:
        return None
    peak = max(window)
    if peak in (None, 0):
        return None
    return float(closes[0]) / float(peak) - 1.0


def _source_tier(source: str | None, *, fallback_flag: int | bool | None = None) -> str:
    text = (source or "").lower()
    if fallback_flag:
        return "fallback"
    if text.startswith("fdr:") or text.startswith("krx:") or "official" in text:
        return "official"
    if text.startswith("carry_forward:"):
        return "official_delayed"
    if text.startswith("naver:") or text.startswith("yahoo:"):
        return "proxy"
    if text.startswith("fallback"):
        return "fallback"
    return "proxy" if text else "fallback"


def _breadth_regime_label(*, above_20dma_ratio: float | None, adv_dec_ratio: float | None) -> str:
    breadth = float(above_20dma_ratio or 0.0)
    adv_dec = float(adv_dec_ratio or 1.0)
    if breadth >= 0.6 and adv_dec >= 1.1:
        return "확산 강세"
    if breadth >= 0.5 and adv_dec >= 1.0:
        return "완만한 강세"
    if breadth <= 0.35 and adv_dec < 0.9:
        return "확산 약세"
    if breadth <= 0.45 and adv_dec < 1.0:
        return "완만한 약세"
    return "혼조"


def _direction_label(change_pct: float | None) -> str:
    if change_pct is None:
        return "unavailable"
    if change_pct > 0:
        return "up"
    if change_pct < 0:
        return "down"
    return "flat"


def build_market_index_panel_payload(con, *, market: str, asof: str, generated_at: str) -> dict:
    panel_rows: list[dict[str, Any]] = []
    asof_date = asof[:10]
    for spec in INDEX_PANEL_SPECS:
        history = _rows_to_dicts(
            con.execute(
                """
                SELECT date, open, high, low, close, volume, value, source
                FROM market_index_daily
                WHERE market = ? AND index_code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 70
                """,
                (market, spec["index_code"], asof_date),
            ).fetchall()
        )
        if not history:
            continue
        latest = history[0]
        closes = [float(row["close"]) for row in history if row.get("close") is not None]
        panel_rows.append(
            {
                "index_code": spec["index_code"],
                "index_name": spec["index_name"],
                "date": latest.get("date"),
                "close": latest.get("close"),
                "ret_1d": _window_return(closes, 1),
                "ret_5d": _window_return(closes, 5),
                "ret_20d": _window_return(closes, 20),
                "ret_60d": _window_return(closes, 60),
                "realized_vol_20d": _realized_vol(closes, 20),
                "drawdown_20d": _drawdown(closes, 20),
                "source": latest.get("source"),
                "source_tier": _source_tier(latest.get("source")),
            }
        )

    strongest_20d = max(
        (row for row in panel_rows if row.get("ret_20d") is not None),
        key=lambda item: item.get("ret_20d") or -999.0,
        default=None,
    )
    weakest_20d = min(
        (row for row in panel_rows if row.get("ret_20d") is not None),
        key=lambda item: item.get("ret_20d") or 999.0,
        default=None,
    )
    return {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "title": "KRX 지수 패널",
        "description": "국내 대표 지수의 최근 흐름과 변동성 상태를 한 번에 보는 공개형 시장 데이터 패널입니다.",
        "indices": panel_rows,
        "summary": {
            "count": len(panel_rows),
            "strongest_20d_index": strongest_20d.get("index_name") if strongest_20d else None,
            "weakest_20d_index": weakest_20d.get("index_name") if weakest_20d else None,
            "all_official": all(row.get("source_tier") == "official" for row in panel_rows) if panel_rows else False,
        },
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_market_breadth_detail_payload(con, *, market: str, asof: str, generated_at: str) -> dict:
    feature_row = con.execute(
        """
        SELECT *
        FROM market_features_hourly
        WHERE market = ? AND asof <= ?
        ORDER BY asof DESC
        LIMIT 1
        """,
        (market, asof),
    ).fetchone()
    features = dict(feature_row) if feature_row else {}

    intraday_asof_row = con.execute(
        """
        SELECT MAX(asof)
        FROM market_intraday_breadth
        WHERE market = ? AND asof <= ?
        """,
        (market, asof),
    ).fetchone()
    intraday_asof = intraday_asof_row[0] if intraday_asof_row and intraday_asof_row[0] else None
    intraday_rows = []
    if intraday_asof:
        intraday_rows = _rows_to_dicts(
            con.execute(
                """
                SELECT universe_code, advancers, decliners, flat_count, adv_dec_ratio, positive_ratio, source, is_fallback
                FROM market_intraday_breadth
                WHERE market = ? AND asof = ?
                ORDER BY universe_code ASC
                """,
                (market, intraday_asof),
            ).fetchall()
        )
    for row in intraday_rows:
        row["source_tier"] = _source_tier(row.get("source"), fallback_flag=row.get("is_fallback"))

    close_breadth = {
        "asof": features.get("asof"),
        "above_20dma_ratio": features.get("above_20dma_ratio"),
        "above_60dma_ratio": features.get("above_60dma_ratio"),
        "adv_dec_ratio": features.get("adv_dec_ratio"),
        "new_high_count": features.get("new_high_count"),
        "new_low_count": features.get("new_low_count"),
        "breadth_universe_count": features.get("breadth_universe_count"),
        "breadth_proxy_flag": bool(features.get("breadth_proxy_flag")),
        "breadth_regime_label": _breadth_regime_label(
            above_20dma_ratio=features.get("above_20dma_ratio"),
            adv_dec_ratio=features.get("adv_dec_ratio"),
        ),
    }
    return {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "title": "시장 내부 확산 상세",
        "description": "종가 기준 breadth와 최신 장중 breadth를 함께 비교해 시장 내부 체력을 읽는 공개형 데이터 패널입니다.",
        "close_breadth": close_breadth,
        "intraday_breadth": {
            "asof": intraday_asof,
            "available": bool(intraday_rows),
            "rows": intraday_rows,
        },
        "summary": {
            "close_regime_label": close_breadth["breadth_regime_label"],
            "intraday_positive_universe_count": sum(
                1 for row in intraday_rows if (row.get("positive_ratio") or 0.0) >= 0.5
            ),
            "uses_proxy": bool(features.get("breadth_proxy_flag")) or any(
                row.get("source_tier") in {"proxy", "fallback"} for row in intraday_rows
            ),
        },
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_market_us_macro_panel_payload(con, *, market: str, asof: str, generated_at: str) -> dict:
    snapshot_asof_row = con.execute(
        """
        SELECT MAX(asof)
        FROM market_overnight_asset_snapshot
        WHERE market = ? AND asof <= ?
        """,
        (market, asof),
    ).fetchone()
    snapshot_asof = snapshot_asof_row[0] if snapshot_asof_row and snapshot_asof_row[0] else None
    asset_rows = []
    if snapshot_asof:
        asset_rows = _rows_to_dicts(
            con.execute(
                """
                SELECT asset_code, asset_name, asset_group, price, change_value, change_pct, source, is_fallback
                FROM market_overnight_asset_snapshot
                WHERE market = ? AND asof = ?
                ORDER BY asset_group ASC, asset_code ASC
                """,
                (market, snapshot_asof),
            ).fetchall()
        )
    for row in asset_rows:
        if row.get("asset_code") == "KOREA_PROXY_EWY":
            row["asset_name"] = "미국 상장 한국 ETF"
        row["source_tier"] = _source_tier(row.get("source"), fallback_flag=row.get("is_fallback"))
        row["direction_label"] = _direction_label(row.get("change_pct"))

    preview_row = con.execute(
        """
        SELECT preview_label, preview_score, headline_line, summary_line
        FROM market_next_day_preview_state
        WHERE market = ? AND asof <= ?
        ORDER BY asof DESC
        LIMIT 1
        """,
        (market, asof),
    ).fetchone()
    preview = dict(preview_row) if preview_row else {}

    top_movers = sorted(
        (row for row in asset_rows if row.get("change_pct") is not None),
        key=lambda item: abs(item.get("change_pct") or 0.0),
        reverse=True,
    )[:3]
    return {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "title": "미국/글로벌 매크로 패널",
        "description": "미국 선물, 금리, 환율, 원유와 미국 상장 한국 ETF를 함께 보여 주는 공개형 글로벌 참고 패널입니다.",
        "snapshot_asof": snapshot_asof,
        "assets": asset_rows,
        "summary": {
            "preview_label": preview.get("preview_label"),
            "preview_score": preview.get("preview_score"),
            "headline_line": preview.get("headline_line"),
            "summary_line": preview.get("summary_line"),
            "top_movers": top_movers,
            "all_proxy": all(row.get("source_tier") == "proxy" for row in asset_rows) if asset_rows else False,
        },
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_market_dart_summary_payload(con, *, market: str, asof: str, generated_at: str) -> dict:
    row = con.execute(
        """
        SELECT *
        FROM market_dart_summary_state
        WHERE market = ? AND asof <= ?
        ORDER BY asof DESC
        LIMIT 1
        """,
        (market, asof),
    ).fetchone()
    if not row:
        return {
            "market": market,
            "asof": asof,
            "generated_at": generated_at,
            "title": "DART 공시 요약",
            "description": "DART 기반 시장 공시 흐름 패널은 아직 생성되지 않았습니다.",
            "enabled": False,
            "status_label": "준비 중",
            "availability_reason": "OpenDART 요약 데이터가 아직 DB에 없습니다.",
            "planned_fields": DART_PLANNED_FIELDS,
            "compliance_meta": _compliance_meta(asof),
            "notice_block": NOTICE_BLOCK,
        }

    state = dict(row)
    filing_count_by_type = json.loads(state.get("filing_count_by_type_json") or "[]")
    highlights = json.loads(state.get("highlights_json") or "[]")
    recent_filings = json.loads(state.get("recent_filings_json") or "[]")
    return {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "title": "DART 공시 요약",
        "description": "상장사 공시 흐름을 OpenDART 기준으로 요약한 공개형 시장 데이터 패널입니다.",
        "enabled": bool(state.get("enabled")),
        "status_label": state.get("status_label"),
        "availability_reason": state.get("availability_reason"),
        "reference_date": state.get("reference_date"),
        "filing_count_total": state.get("filing_count_total", 0),
        "market_breakdown": {
            "kospi_count": state.get("kospi_count", 0),
            "kosdaq_count": state.get("kosdaq_count", 0),
        },
        "risk_event_count": state.get("risk_event_count", 0),
        "filing_count_by_type": filing_count_by_type,
        "highlights": highlights,
        "recent_filings": recent_filings,
        "source": {
            "provider": "OpenDART",
            "endpoint": "list.json",
            "source_tier": "official",
        },
        "planned_next_fields": DART_PLANNED_FIELDS,
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }
