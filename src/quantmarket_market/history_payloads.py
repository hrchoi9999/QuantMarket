from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from typing import Any

from .analytics import format_kst
from .payloads import NOTICE_BLOCK, _compliance_meta

DEFAULT_LOOKBACK_DAYS = 90
NEXT_DAY_PREVIEW_LOOKBACK_DAYS = 30
TIMEZONE_NAME = "Asia/Seoul"


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _cutoff_asof(asof: str, lookback_days: int) -> str:
    current = datetime.fromisoformat(asof.replace("Z", "+00:00"))
    cutoff = current - timedelta(days=lookback_days)
    return format_kst(cutoff)


def _history_meta(
    *,
    source_name: str,
    schema_version: str,
    asof: str,
    generated_at: str,
    market: str,
    interval: str,
    lookback_days: int,
) -> dict:
    return {
        "source_name": source_name,
        "schema_version": schema_version,
        "as_of_date": asof,
        "generated_at": generated_at,
        "market": market,
        "timezone": TIMEZONE_NAME,
        "interval": interval,
        "lookback_days": lookback_days,
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }


def _is_preview_window(asof: str) -> bool:
    dt = datetime.fromisoformat(asof.replace("Z", "+00:00"))
    current = dt.timetz().replace(tzinfo=None)
    return current >= time(18, 0) or current <= time(8, 30)


def build_market_timeline_history_payload(
    con,
    *,
    market: str,
    asof: str,
    generated_at: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict:
    cutoff = _cutoff_asof(asof, lookback_days)
    series = _rows_to_dicts(
        con.execute(
            """
            SELECT s.asof,
                   c.total_score,
                   c.trend_score,
                   c.breadth_score,
                   c.risk_score,
                   c.defensive_flow_score,
                   s.state_label
            FROM market_state_history s
            JOIN market_component_scores c
              ON s.market = c.market AND s.asof = c.asof
            WHERE s.market = ?
              AND s.asof >= ?
              AND s.asof <= ?
            ORDER BY s.asof ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    return {
        **_history_meta(
            source_name="QuantMarket",
            schema_version="market_timeline_history.v1",
            asof=asof,
            generated_at=generated_at,
            market=market,
            interval="1h",
            lookback_days=lookback_days,
        ),
        "series": series,
    }


def build_market_asset_strength_history_payload(
    con,
    *,
    market: str,
    asof: str,
    generated_at: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict:
    cutoff = _cutoff_asof(asof, lookback_days)
    series = _rows_to_dicts(
        con.execute(
            """
            SELECT asof,
                   asset_group,
                   strength_score,
                   ret_20d,
                   strength_rank,
                   strength_label
            FROM market_asset_relative_strength_hourly
            WHERE market = ?
              AND asof >= ?
              AND asof <= ?
            ORDER BY asof ASC, strength_rank ASC, asset_group ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    return {
        **_history_meta(
            source_name="QuantMarket",
            schema_version="market_asset_strength_history.v1",
            asof=asof,
            generated_at=generated_at,
            market=market,
            interval="1h",
            lookback_days=lookback_days,
        ),
        "series": series,
    }


def build_market_state_transition_history_payload(
    con,
    *,
    market: str,
    asof: str,
    generated_at: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict:
    cutoff = _cutoff_asof(asof, lookback_days)
    series = _rows_to_dicts(
        con.execute(
            """
            SELECT s.asof,
                   t.current_state,
                   t.prev_state,
                   s.state_change_direction,
                   t.transition_count_5d,
                   t.transition_count_20d,
                   t.stability_score,
                   s.state_score
            FROM market_state_transition_stats t
            JOIN market_state_history s
              ON t.market = s.market AND t.asof = s.asof
            WHERE t.market = ?
              AND t.asof >= ?
              AND t.asof <= ?
            ORDER BY t.asof ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    return {
        **_history_meta(
            source_name="QuantMarket",
            schema_version="market_state_transition_history.v1",
            asof=asof,
            generated_at=generated_at,
            market=market,
            interval="1h",
            lookback_days=lookback_days,
        ),
        "series": series,
    }


def _direction_label(change_pct: float | None) -> str:
    if change_pct is None:
        return "unavailable"
    if change_pct > 0:
        return "up"
    if change_pct < 0:
        return "down"
    return "flat"


def _status_label(asset: dict) -> str:
    if asset.get("is_fallback"):
        return "fallback"
    if asset.get("change_pct") is None:
        return "missing"
    return "live"


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


def build_next_day_preview_history_payload(
    con,
    *,
    market: str,
    asof: str,
    generated_at: str,
    lookback_days: int = NEXT_DAY_PREVIEW_LOOKBACK_DAYS,
) -> dict:
    cutoff = _cutoff_asof(asof, lookback_days)
    rows = _rows_to_dicts(
        con.execute(
            """
            SELECT asof,
                   reference_session,
                   preview_label,
                   overnight_assets_json
            FROM market_next_day_preview_state
            WHERE market = ?
              AND asof >= ?
              AND asof <= ?
            ORDER BY asof ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    series: list[dict[str, Any]] = []
    for row in rows:
        assets = json.loads(row.get("overnight_assets_json") or "[]")
        overnight_assets = [
            {
                "asset_code": asset.get("asset_code"),
                "change_pct": asset.get("change_pct"),
                "direction_label": _direction_label(asset.get("change_pct")),
                "status_label": _status_label(asset),
            }
            for asset in assets
        ]
        active_now = _is_preview_window(row.get("asof"))
        series.append(
            {
                "asof": row.get("asof"),
                "reference_session": row.get("reference_session"),
                "active_now": active_now,
                "preview_label": row.get("preview_label"),
                "overnight_assets": overnight_assets,
            }
        )
    return {
        **_history_meta(
            source_name="QuantMarket",
            schema_version="market_next_day_preview_history.v1",
            asof=asof,
            generated_at=generated_at,
            market=market,
            interval="1h",
            lookback_days=lookback_days,
        ),
        "series": series,
    }


def build_market_breadth_detail_history_payload(
    con,
    *,
    market: str,
    asof: str,
    generated_at: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    intraday_lookback_days: int = 10,
) -> dict:
    cutoff = _cutoff_asof(asof, lookback_days)
    intraday_cutoff = _cutoff_asof(asof, intraday_lookback_days)

    close_rows = _rows_to_dicts(
        con.execute(
            """
            SELECT asof,
                   above_20dma_ratio,
                   above_60dma_ratio,
                   adv_dec_ratio,
                   new_high_count,
                   new_low_count,
                   breadth_universe_count,
                   breadth_proxy_flag
            FROM market_features_hourly
            WHERE market = ?
              AND asof >= ?
              AND asof <= ?
            ORDER BY asof ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    close_series: list[dict[str, Any]] = []
    for row in close_rows:
        close_series.append(
            {
                **row,
                "breadth_regime_label": _breadth_regime_label(
                    above_20dma_ratio=row.get("above_20dma_ratio"),
                    adv_dec_ratio=row.get("adv_dec_ratio"),
                ),
            }
        )

    intraday_rows = _rows_to_dicts(
        con.execute(
            """
            SELECT asof,
                   session_date,
                   universe_code,
                   advancers,
                   decliners,
                   flat_count,
                   adv_dec_ratio,
                   positive_ratio,
                   source,
                   is_fallback
            FROM market_intraday_breadth
            WHERE market = ?
              AND asof >= ?
              AND asof <= ?
            ORDER BY asof ASC, universe_code ASC
            """,
            (market, intraday_cutoff, asof),
        ).fetchall()
    )
    intraday_series: list[dict[str, Any]] = []
    for row in intraday_rows:
        intraday_series.append(
            {
                **row,
                "source_tier": _source_tier(
                    row.get("source"),
                    fallback_flag=row.get("is_fallback"),
                ),
                "status_label": "fallback" if row.get("is_fallback") else "live",
            }
        )

    latest_close_asof = close_series[-1]["asof"] if close_series else None
    latest_intraday_asof = intraday_series[-1]["asof"] if intraday_series else None
    return {
        **_history_meta(
            source_name="QuantMarket",
            schema_version="market_breadth_detail_history.v1",
            asof=asof,
            generated_at=generated_at,
            market=market,
            interval="1h",
            lookback_days=lookback_days,
        ),
        "series": close_series,
        "close_series": close_series,
        "intraday_series": intraday_series,
        "close_interval": "1h",
        "intraday_interval": "15m",
        "intraday_lookback_days": intraday_lookback_days,
        "summary": {
            "latest_close_asof": latest_close_asof,
            "latest_intraday_asof": latest_intraday_asof,
            "close_points": len(close_series),
            "intraday_points": len(intraday_series),
        },
    }


def build_market_us_macro_panel_history_payload(
    con,
    *,
    market: str,
    asof: str,
    generated_at: str,
    lookback_days: int = NEXT_DAY_PREVIEW_LOOKBACK_DAYS,
) -> dict:
    cutoff = _cutoff_asof(asof, lookback_days)
    asset_rows = _rows_to_dicts(
        con.execute(
            """
            SELECT asof,
                   session_date,
                   asset_code,
                   asset_name,
                   asset_group,
                   price,
                   change_value,
                   change_pct,
                   source,
                   is_fallback
            FROM market_overnight_asset_snapshot
            WHERE market = ?
              AND asof >= ?
              AND asof <= ?
            ORDER BY asof ASC, asset_group ASC, asset_code ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    asset_series: list[dict[str, Any]] = []
    for row in asset_rows:
        asset = dict(row)
        if asset.get("asset_code") == "KOREA_PROXY_EWY":
            asset["asset_name"] = "미국 상장 한국 ETF"
        asset["source_tier"] = _source_tier(
            asset.get("source"),
            fallback_flag=asset.get("is_fallback"),
        )
        asset["direction_label"] = _direction_label(asset.get("change_pct"))
        asset["status_label"] = _status_label(asset)
        asset_series.append(asset)

    preview_rows = _rows_to_dicts(
        con.execute(
            """
            SELECT asof,
                   reference_session,
                   preview_label,
                   preview_score,
                   overnight_futures_bias,
                   global_risk_bias,
                   overnight_fx_bias,
                   headline_line,
                   summary_line
            FROM market_next_day_preview_state
            WHERE market = ?
              AND asof >= ?
              AND asof <= ?
            ORDER BY asof ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    preview_series = [dict(row) for row in preview_rows]
    latest_asset_asof = asset_series[-1]["asof"] if asset_series else None
    latest_preview_asof = preview_series[-1]["asof"] if preview_series else None
    return {
        **_history_meta(
            source_name="QuantMarket",
            schema_version="market_us_macro_panel_history.v1",
            asof=asof,
            generated_at=generated_at,
            market=market,
            interval="1h",
            lookback_days=lookback_days,
        ),
        "series": asset_series,
        "asset_series": asset_series,
        "preview_series": preview_series,
        "summary": {
            "latest_asset_asof": latest_asset_asof,
            "latest_preview_asof": latest_preview_asof,
            "asset_points": len(asset_series),
            "preview_points": len(preview_series),
        },
    }


def build_market_dart_summary_history_payload(
    con,
    *,
    market: str,
    asof: str,
    generated_at: str,
    lookback_days: int = NEXT_DAY_PREVIEW_LOOKBACK_DAYS,
) -> dict:
    cutoff = _cutoff_asof(asof, lookback_days)
    rows = _rows_to_dicts(
        con.execute(
            """
            WITH latest_per_reference_date AS (
                SELECT market, reference_date, MAX(asof) AS latest_asof
                FROM market_dart_summary_state
                WHERE market = ?
                  AND asof >= ?
                  AND asof <= ?
                  AND enabled = 1
                  AND reference_date IS NOT NULL
                GROUP BY market, reference_date
            )
            SELECT s.asof,
                   s.reference_date,
                   s.filing_count_total,
                   s.kospi_count,
                   s.kosdaq_count,
                   s.risk_event_count,
                   s.filing_count_by_type_json
            FROM market_dart_summary_state s
            JOIN latest_per_reference_date x
              ON s.market = x.market
             AND s.reference_date = x.reference_date
             AND s.asof = x.latest_asof
            ORDER BY s.reference_date ASC
            """,
            (market, cutoff, asof),
        ).fetchall()
    )
    series: list[dict[str, Any]] = []
    for row in rows:
        type_counts = json.loads(row.get("filing_count_by_type_json") or "[]")
        type_map = {item.get("category_label"): item.get("count") for item in type_counts}
        series.append(
            {
                "asof": row.get("asof"),
                "reference_date": row.get("reference_date"),
                "filing_count_total": row.get("filing_count_total"),
                "kospi_count": row.get("kospi_count"),
                "kosdaq_count": row.get("kosdaq_count"),
                "risk_event_count": row.get("risk_event_count"),
                "funding_count": type_map.get("자금조달", 0),
                "shareholder_count": type_map.get("지분/자사주", 0),
                "earnings_count": type_map.get("실적/정기보고", 0),
                "governance_count": type_map.get("지배구조/의사결정", 0),
                "general_count": type_map.get("일반 공시", 0),
                "type_counts": type_counts,
            }
        )
    return {
        **_history_meta(
            source_name="QuantMarket",
            schema_version="market_dart_summary_history.v1",
            asof=asof,
            generated_at=generated_at,
            market=market,
            interval="1d",
            lookback_days=lookback_days,
        ),
        "series": series,
    }
