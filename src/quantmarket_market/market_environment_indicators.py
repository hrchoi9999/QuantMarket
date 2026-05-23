from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .config import DB_DIR
from .payloads import NOTICE_BLOCK, _compliance_meta


GLOBAL_MARKET_DB_PATH = DB_DIR / "global_market_context.db"
CHART_LOOKBACK_DAYS = 365 * 3
DEFAULT_CHART_HEIGHT_PX = 160


DOMESTIC_INDEX_SPECS = [
    {"series_id": "KOSPI", "index_code": "1001", "display_name_kr": "코스피", "category_label_kr": "국내 지수"},
    {"series_id": "KOSDAQ", "index_code": "2001", "display_name_kr": "코스닥", "category_label_kr": "국내 지수"},
    {"series_id": "KOSPI200", "index_code": "1028", "display_name_kr": "코스피200", "category_label_kr": "국내 지수"},
]

DOMESTIC_FX_SPECS = [
    {"series_id": "USDKRW", "series_code": "USDKRW", "display_name_kr": "원/달러 환율", "category_label_kr": "국내 환율"},
]

DOMESTIC_RATE_SPECS = [
    {"series_id": "KTB3Y", "rate_code": "KTB3Y", "display_name_kr": "국고채 3년 금리", "category_label_kr": "국내 금리"},
    {"series_id": "KTB5Y", "rate_code": "KTB5Y", "display_name_kr": "국고채 5년 금리", "category_label_kr": "국내 금리"},
    {"series_id": "CD91", "rate_code": "CD91", "display_name_kr": "CD 91일 금리", "category_label_kr": "국내 금리"},
    {"series_id": "BASE", "rate_code": "BASE", "display_name_kr": "한국 기준금리", "category_label_kr": "국내 금리"},
]

FRED_SERIES_IDS = [
    "DGS10",
    "DGS2",
    "DGS30",
    "DGS3MO",
    "DFII10",
    "T10YIE",
    "VIXCLS",
    "DCOILWTICO",
    "DEXKOUS",
    "DEXJPUS",
    "DTWEXBGS",
    "CPIAUCSL",
    "CPILFESL",
    "PPIACO",
    "UNRATE",
    "PAYEMS",
    "FEDFUNDS",
    "BAMLH0A0HYM2",
    "BAMLC0A0CM",
]

BEA_SERIES_IDS = [
    "BEA_GDP",
    "BEA_REAL_GDP",
    "BEA_PCE",
    "BEA_REAL_PCE",
    "BEA_PERSONAL_INCOME",
    "BEA_PCE_PRICE_INDEX",
]

EIA_SERIES_IDS = [
    "EIA_WTI_SPOT",
    "EIA_BRENT_SPOT",
    "EIA_US_CRUDE_STOCKS",
    "EIA_CUSHING_CRUDE_STOCKS",
    "EIA_GASOLINE_STOCKS",
    "EIA_DISTILLATE_STOCKS",
]

BEA_DISPLAY_META = {
    "BEA_GDP": {"display_name": "미국 GDP", "category": "growth", "unit": "billions_usd", "frequency": "quarterly"},
    "BEA_REAL_GDP": {"display_name": "미국 실질 GDP", "category": "growth", "unit": "chained_2017_usd", "frequency": "quarterly"},
    "BEA_PCE": {"display_name": "미국 개인소비지출", "category": "consumption", "unit": "billions_usd", "frequency": "quarterly"},
    "BEA_REAL_PCE": {"display_name": "미국 실질 개인소비지출", "category": "consumption", "unit": "chained_2017_usd", "frequency": "quarterly"},
    "BEA_PERSONAL_INCOME": {"display_name": "미국 개인소득", "category": "income", "unit": "millions_usd_annual_rate", "frequency": "monthly"},
    "BEA_PCE_PRICE_INDEX": {"display_name": "미국 PCE 물가지수", "category": "inflation", "unit": "index", "frequency": "monthly"},
}

EIA_DISPLAY_META = {
    "EIA_WTI_SPOT": {"display_name": "WTI 현물유가", "category": "energy_price", "unit": "usd_per_barrel", "frequency": "daily"},
    "EIA_BRENT_SPOT": {"display_name": "Brent 현물유가", "category": "energy_price", "unit": "usd_per_barrel", "frequency": "daily"},
    "EIA_US_CRUDE_STOCKS": {"display_name": "미국 상업 원유재고", "category": "energy_inventory", "unit": "thousand_barrels", "frequency": "weekly"},
    "EIA_CUSHING_CRUDE_STOCKS": {"display_name": "쿠싱 원유재고", "category": "energy_inventory", "unit": "thousand_barrels", "frequency": "weekly"},
    "EIA_GASOLINE_STOCKS": {"display_name": "미국 휘발유재고", "category": "energy_inventory", "unit": "thousand_barrels", "frequency": "weekly"},
    "EIA_DISTILLATE_STOCKS": {"display_name": "미국 중간유분재고", "category": "energy_inventory", "unit": "thousand_barrels", "frequency": "weekly"},
}

TREASURY_RATE_SERIES_IDS = {"DGS10", "DGS2", "DGS30", "DGS3MO"}
BLS_MONTHLY_SERIES_IDS = {"CPIAUCSL", "CPILFESL", "PPIACO", "UNRATE", "PAYEMS"}

YAHOO_ASSET_CODES = [
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "EWY",
    "EEM",
    "ACWI",
    "TLT",
    "IEF",
    "SHY",
    "GLD",
    "USO",
    "UUP",
    "DXY",
    "VIX",
    "HYG",
    "LQD",
    "SOXX",
    "XLK",
    "XLY",
    "XLI",
    "XLF",
    "XLE",
    "XLV",
    "XLP",
    "XLU",
    "XLC",
    "XLB",
    "XLRE",
]

FRED_CATEGORY_LABELS = {
    "rates": "미국 금리",
    "rates_real": "미국 실질금리",
    "inflation_expectation": "미국 기대인플레이션",
    "risk": "변동성",
    "commodity": "원자재",
    "fx": "환율/달러",
    "inflation": "미국 물가",
    "employment": "미국 고용",
    "policy": "미국 정책금리",
    "credit": "미국 신용스프레드",
    "commodity_risk": "원자재 변동성",
    "growth": "미국 성장",
    "consumption": "미국 소비",
    "income": "미국 소득",
    "energy_price": "에너지 가격",
    "energy_inventory": "에너지 재고",
}

YAHOO_CATEGORY_LABELS = {
    "us_equity_broad": "미국 대표 지수 ETF",
    "us_equity_growth": "미국 성장주 ETF",
    "us_equity_smallcap": "미국 중소형주 ETF",
    "korea_proxy": "한국 관련 해외 ETF",
    "em_equity": "신흥국 ETF",
    "global_equity": "글로벌 주식 ETF",
    "safe_haven_rates": "미국 국채 ETF",
    "safe_haven_commodity": "금 ETF",
    "commodity_energy": "원유 ETF",
    "dollar": "달러 ETF",
    "dollar_index": "달러지수",
    "volatility": "변동성",
    "credit_risk": "하이일드 채권 ETF",
    "credit_quality": "투자등급 채권 ETF",
    "semiconductor": "반도체 ETF",
    "us_sector_cyclical": "미국 경기민감 섹터 ETF",
    "us_sector_growth": "미국 성장 섹터 ETF",
    "us_sector_defensive": "미국 방어 섹터 ETF",
    "us_sector_rate_sensitive": "미국 금리민감 섹터 ETF",
}


def _asof_date(asof: str) -> str:
    return asof[:10]


def _cutoff_date(asof: str) -> str:
    parsed = date.fromisoformat(_asof_date(asof))
    return (parsed - timedelta(days=CHART_LOOKBACK_DAYS)).isoformat()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_tier(source: str | None) -> str:
    text = (source or "").lower()
    if text.startswith("fdr:") or text.startswith("krx:") or text.startswith("bok_ecos:") or text == "fred":
        return "official"
    if text.startswith("manual") or text.startswith("sample"):
        return "fallback"
    if text.startswith("yahoo"):
        return "proxy"
    return "proxy" if text else "fallback"


def _period_label(start_date: str | None, end_date: str | None) -> str:
    if not start_date or not end_date:
        return "데이터 준비 중"
    return f"{start_date} ~ {end_date}"


def _points(rows: list[sqlite3.Row], *, date_key: str, value_key: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        value = _to_float(row[value_key])
        if value is None:
            continue
        out.append({"date": row[date_key], "value": value})
    return out


def _latest_intraday_index(con: sqlite3.Connection, *, market: str, asof: str) -> dict[str, sqlite3.Row]:
    asof_date = _asof_date(asof)
    latest_asof = con.execute(
        """
        SELECT MAX(asof)
        FROM market_intraday_index_snapshot
        WHERE market = ? AND session_date = ? AND asof <= ?
        """,
        (market, asof_date, asof),
    ).fetchone()[0]
    if not latest_asof:
        return {}
    rows = con.execute(
        """
        SELECT index_code, price, change_value, change_pct, source, is_fallback, asof
        FROM market_intraday_index_snapshot
        WHERE market = ? AND session_date = ? AND asof = ?
        """,
        (market, asof_date, latest_asof),
    ).fetchall()
    return {row["index_code"]: row for row in rows if row["price"] is not None}


def _latest_intraday_fx(con: sqlite3.Connection, *, market: str, asof: str) -> dict[str, sqlite3.Row]:
    asof_date = _asof_date(asof)
    latest_asof = con.execute(
        """
        SELECT MAX(asof)
        FROM market_intraday_fx_snapshot
        WHERE market = ? AND session_date = ? AND asof <= ?
        """,
        (market, asof_date, asof),
    ).fetchone()[0]
    if not latest_asof:
        return {}
    rows = con.execute(
        """
        SELECT series_code, price, change_value, change_pct, source, is_fallback, asof
        FROM market_intraday_fx_snapshot
        WHERE market = ? AND session_date = ? AND asof = ?
        """,
        (market, asof_date, latest_asof),
    ).fetchall()
    return {row["series_code"]: row for row in rows if row["price"] is not None}


def _apply_intraday_point(payload: dict[str, Any], row: sqlite3.Row | None, *, asof_date: str) -> dict[str, Any]:
    if row is None or row["price"] is None:
        return payload
    value = _to_float(row["price"])
    if value is None:
        return payload
    points = list(payload.get("points") or [])
    point = {
        "date": asof_date,
        "value": value,
        "point_type": "current_intraday_quote",
        "quote_asof": row["asof"],
        "source": row["source"],
        "is_fallback": bool(row["is_fallback"]),
        "change_value": _to_float(row["change_value"]),
        "change_pct": _to_float(row["change_pct"]),
        "source_note": "실행시점 장중 현재값을 시장 환경 지표 현재 포인트로 표시합니다.",
    }
    if points and points[-1].get("date") == asof_date:
        points[-1] = point
    else:
        points.append(point)
    payload.update(
        {
            "end_date": asof_date,
            "latest_date": asof_date,
            "latest_value": value,
            "latest_point_type": "current_intraday_quote",
            "latest_change_value": point["change_value"],
            "latest_change_pct": point["change_pct"],
            "quote_asof": row["asof"],
            "source_detail": row["source"],
            "period_label": _period_label(payload.get("start_date"), asof_date),
            "points": points,
        }
    )
    return payload


def _domestic_index_series(con: sqlite3.Connection, *, market: str, asof: str, cutoff: str) -> list[dict[str, Any]]:
    series = []
    intraday = _latest_intraday_index(con, market=market, asof=asof)
    asof_date = _asof_date(asof)
    for spec in DOMESTIC_INDEX_SPECS:
        params = (market, spec["index_code"], _asof_date(asof))
        meta = con.execute(
            """
            SELECT MIN(date) start_date, MAX(date) end_date, COUNT(*) row_count
            FROM market_index_daily
            WHERE market = ? AND index_code = ? AND date <= ? AND source <> 'sample_seed'
            """,
            params,
        ).fetchone()
        latest = con.execute(
            """
            SELECT date, close, source
            FROM market_index_daily
            WHERE market = ? AND index_code = ? AND date <= ? AND source <> 'sample_seed'
            ORDER BY date DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        rows = con.execute(
            """
            SELECT date, close
            FROM market_index_daily
            WHERE market = ? AND index_code = ? AND date <= ? AND date >= ? AND source <> 'sample_seed'
            ORDER BY date ASC
            """,
            (*params, cutoff),
        ).fetchall()
        source = latest["source"] if latest else None
        payload = _series_payload(
            spec=spec,
            source_provider="KRX/FDR",
            source_detail=source or "market_index_daily",
            source_tier=_source_tier(source),
            unit="index",
            frequency="daily",
            meta=meta,
            latest=latest,
            latest_value_key="close",
            points=_points(rows, date_key="date", value_key="close"),
        )
        series.append(_apply_intraday_point(payload, intraday.get(spec["index_code"]), asof_date=asof_date))
    return series


def _domestic_fx_series(con: sqlite3.Connection, *, market: str, asof: str, cutoff: str) -> list[dict[str, Any]]:
    series = []
    intraday = _latest_intraday_fx(con, market=market, asof=asof)
    asof_date = _asof_date(asof)
    for spec in DOMESTIC_FX_SPECS:
        params = (market, spec["series_code"], _asof_date(asof))
        meta = con.execute(
            """
            SELECT MIN(date) start_date, MAX(date) end_date, COUNT(*) row_count
            FROM market_fx_daily
            WHERE market = ? AND series_code = ? AND date <= ? AND source <> 'sample_seed'
            """,
            params,
        ).fetchone()
        latest = con.execute(
            """
            SELECT date, close, source
            FROM market_fx_daily
            WHERE market = ? AND series_code = ? AND date <= ? AND source <> 'sample_seed'
            ORDER BY date DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        rows = con.execute(
            """
            SELECT date, close
            FROM market_fx_daily
            WHERE market = ? AND series_code = ? AND date <= ? AND date >= ? AND source <> 'sample_seed'
            ORDER BY date ASC
            """,
            (*params, cutoff),
        ).fetchall()
        source = latest["source"] if latest else None
        source_provider = "BOK ECOS" if (source or "").startswith("bok_ecos:") else "FinanceDataReader"
        payload = _series_payload(
            spec=spec,
            source_provider=source_provider,
            source_detail=source or "market_fx_daily",
            source_tier=_source_tier(source),
            unit="KRW per USD",
            frequency="daily",
            meta=meta,
            latest=latest,
            latest_value_key="close",
            points=_points(rows, date_key="date", value_key="close"),
        )
        series.append(_apply_intraday_point(payload, intraday.get(spec["series_code"]), asof_date=asof_date))
    return series


def _domestic_rate_series(con: sqlite3.Connection, *, market: str, asof: str, cutoff: str) -> list[dict[str, Any]]:
    series = []
    for spec in DOMESTIC_RATE_SPECS:
        params = (market, spec["rate_code"], _asof_date(asof))
        meta = con.execute(
            """
            SELECT MIN(date) start_date, MAX(date) end_date, COUNT(*) row_count
            FROM market_rates_daily
            WHERE market = ? AND rate_code = ? AND date <= ?
            """,
            params,
        ).fetchone()
        latest = con.execute(
            """
            SELECT date, value, source
            FROM market_rates_daily
            WHERE market = ? AND rate_code = ? AND date <= ?
            ORDER BY date DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        rows = con.execute(
            """
            SELECT date, value
            FROM market_rates_daily
            WHERE market = ? AND rate_code = ? AND date <= ? AND date >= ?
            ORDER BY date ASC
            """,
            (*params, cutoff),
        ).fetchall()
        source = latest["source"] if latest else None
        source_provider = "BOK ECOS" if (source or "").startswith("bok_ecos:") else "QuantMarket seed/manual"
        series.append(
            _series_payload(
                spec=spec,
                source_provider=source_provider,
                source_detail=source or "market_rates_daily",
                source_tier=_source_tier(source),
                unit="percent",
                frequency="daily",
                meta=meta,
                latest=latest,
                latest_value_key="value",
                points=_points(rows, date_key="date", value_key="value"),
            )
        )
    return series


def _fred_series(*, asof: str, cutoff: str, global_db_path: Path) -> list[dict[str, Any]]:
    if not global_db_path.exists():
        return []
    con = sqlite3.connect(global_db_path)
    con.row_factory = sqlite3.Row
    try:
        series = []
        for series_id in FRED_SERIES_IDS + BEA_SERIES_IDS + EIA_SERIES_IDS:
            if series_id in TREASURY_RATE_SERIES_IDS:
                source_candidates = ["TREASURY", "FRED"]
            elif series_id in BLS_MONTHLY_SERIES_IDS:
                source_candidates = ["BLS", "FRED"]
            elif series_id in BEA_SERIES_IDS:
                source_candidates = ["BEA"]
            elif series_id in EIA_SERIES_IDS:
                source_candidates = ["EIA"]
            else:
                source_candidates = ["FRED"]
            source_placeholders = ",".join("?" for _ in source_candidates)
            registry = con.execute(
                f"""
                SELECT display_name, category, unit, frequency
                FROM global_series_registry
                WHERE source IN ({source_placeholders}) AND series_id = ?
                ORDER BY CASE source WHEN 'TREASURY' THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (*source_candidates, series_id),
            ).fetchone()
            combined_all: dict[str, tuple[float | None, str]] = {}
            combined_points: dict[str, tuple[float | None, str]] = {}
            for source in reversed(source_candidates):
                source_rows = con.execute(
                    """
                    SELECT asof_date, value
                    FROM global_observation
                    WHERE source = ? AND series_id = ? AND asof_date <= ? AND value IS NOT NULL
                    ORDER BY asof_date ASC
                    """,
                    (source, series_id, _asof_date(asof)),
                ).fetchall()
                for row in source_rows:
                    combined_all[row["asof_date"]] = (row["value"], source)
                    if row["asof_date"] >= cutoff:
                        combined_points[row["asof_date"]] = (row["value"], source)
            sorted_all_dates = sorted(combined_all)
            sorted_point_dates = sorted(combined_points)
            latest_date = sorted_all_dates[-1] if sorted_all_dates else None
            latest_source = combined_all[latest_date][1] if latest_date else source_candidates[-1]
            meta = {
                "start_date": sorted_all_dates[0] if sorted_all_dates else None,
                "end_date": sorted_all_dates[-1] if sorted_all_dates else None,
                "row_count": len(sorted_all_dates),
            }
            latest = {
                "asof_date": latest_date,
                "value": combined_all[latest_date][0] if latest_date else None,
            }
            point_payload = [
                {"asof_date": item_date, "value": combined_points[item_date][0]}
                for item_date in sorted_point_dates
            ]
            fallback_meta = BEA_DISPLAY_META.get(series_id, {}) or EIA_DISPLAY_META.get(series_id, {})
            category = registry["category"] if registry else fallback_meta.get("category", "macro")
            if series_id in TREASURY_RATE_SERIES_IDS:
                source_provider = "U.S. Treasury/FRED"
            elif series_id in BLS_MONTHLY_SERIES_IDS:
                source_provider = "BLS/FRED"
            elif series_id in BEA_SERIES_IDS:
                source_provider = "BEA"
            elif series_id in EIA_SERIES_IDS:
                source_provider = "EIA"
            else:
                source_provider = "FRED"
            spec = {
                "series_id": series_id,
                "display_name_kr": registry["display_name"] if registry else fallback_meta.get("display_name", series_id),
                "category_label_kr": FRED_CATEGORY_LABELS.get(category, "FRED 지표"),
            }
            series.append(
                _series_payload(
                    spec=spec,
                    source_provider=source_provider,
                    source_detail=f"{latest_source}:{series_id}",
                    source_tier="official",
                    unit=(registry["unit"] if registry else None) or fallback_meta.get("unit") or "value",
                    frequency=(registry["frequency"] if registry else None) or fallback_meta.get("frequency") or "daily",
                    meta=meta,
                    latest=latest,
                    latest_date_key="asof_date",
                    latest_value_key="value",
                    points=_points(point_payload, date_key="asof_date", value_key="value"),
                )
            )
        return series
    finally:
        con.close()


def _yahoo_series(*, asof: str, cutoff: str, global_db_path: Path) -> list[dict[str, Any]]:
    if not global_db_path.exists():
        return []
    con = sqlite3.connect(global_db_path)
    con.row_factory = sqlite3.Row
    try:
        intraday = _latest_yahoo_intraday(con, asof=asof)
        asof_date = _asof_date(asof)
        series = []
        for asset_code in YAHOO_ASSET_CODES:
            params = ("YAHOO", asset_code, _asof_date(asof))
            registry = con.execute(
                """
                SELECT symbol, display_name, asset_group
                FROM global_asset_registry
                WHERE source = ? AND asset_code = ?
                """,
                ("YAHOO", asset_code),
            ).fetchone()
            meta = con.execute(
                """
                SELECT MIN(asof_date) start_date, MAX(asof_date) end_date, COUNT(*) row_count
                FROM global_asset_daily
                WHERE source = ? AND asset_code = ? AND asof_date <= ?
                """,
                params,
            ).fetchone()
            latest = con.execute(
                """
                SELECT asof_date, COALESCE(adj_close, close) value
                FROM global_asset_daily
                WHERE source = ? AND asset_code = ? AND asof_date <= ?
                ORDER BY asof_date DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            rows = con.execute(
                """
                SELECT asof_date, COALESCE(adj_close, close) value
                FROM global_asset_daily
                WHERE source = ? AND asset_code = ? AND asof_date <= ? AND asof_date >= ?
                ORDER BY asof_date ASC
                """,
                (*params, cutoff),
            ).fetchall()
            group = registry["asset_group"] if registry else "global_asset"
            symbol = registry["symbol"] if registry else asset_code
            spec = {
                "series_id": asset_code,
                "display_name_kr": registry["display_name"] if registry else asset_code,
                "category_label_kr": YAHOO_CATEGORY_LABELS.get(group, "Yahoo 글로벌 자산"),
            }
            payload = _series_payload(
                spec=spec,
                source_provider="Yahoo Finance",
                source_detail=f"Yahoo:{symbol}",
                source_tier="proxy",
                unit="price",
                frequency="daily",
                meta=meta,
                latest=latest,
                latest_date_key="asof_date",
                latest_value_key="value",
                points=_points(rows, date_key="asof_date", value_key="value"),
            )
            series.append(_apply_global_intraday_point(payload, intraday.get(asset_code), asof_date=asof_date))
        return series
    finally:
        con.close()


def _latest_yahoo_intraday(con: sqlite3.Connection, *, asof: str) -> dict[str, sqlite3.Row]:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='global_asset_intraday_snapshot'"
    ).fetchone()
    if not exists:
        return {}
    latest_asof = con.execute(
        """
        SELECT MAX(asof)
        FROM global_asset_intraday_snapshot
        WHERE source = 'YAHOO' AND asof <= ?
        """,
        (asof,),
    ).fetchone()[0]
    if not latest_asof:
        return {}
    rows = con.execute(
        """
        SELECT asset_code, price, change_value, change_pct, symbol, quote_time, asof, session_date
        FROM global_asset_intraday_snapshot
        WHERE source = 'YAHOO' AND asof = ?
        """,
        (latest_asof,),
    ).fetchall()
    return {row["asset_code"]: row for row in rows if row["price"] is not None}


def _apply_global_intraday_point(payload: dict[str, Any], row: sqlite3.Row | None, *, asof_date: str) -> dict[str, Any]:
    if row is None or row["price"] is None:
        return payload
    value = _to_float(row["price"])
    if value is None:
        return payload
    points = list(payload.get("points") or [])
    point = {
        "date": asof_date,
        "value": value,
        "point_type": "current_global_intraday_quote",
        "quote_asof": row["asof"],
        "quote_time": row["quote_time"],
        "us_session_date": row["session_date"],
        "source": f"Yahoo:{row['symbol']}",
        "change_value": _to_float(row["change_value"]),
        "change_pct": _to_float(row["change_pct"]),
        "source_note": "실행시점 Yahoo 글로벌 현재값을 시장 환경 지표 현재 포인트로 표시합니다.",
    }
    if points and points[-1].get("date") == asof_date:
        points[-1] = point
    else:
        points.append(point)
    payload.update(
        {
            "end_date": asof_date,
            "latest_date": asof_date,
            "latest_value": value,
            "latest_point_type": "current_global_intraday_quote",
            "latest_change_value": point["change_value"],
            "latest_change_pct": point["change_pct"],
            "quote_asof": row["asof"],
            "quote_time": row["quote_time"],
            "us_session_date": row["session_date"],
            "period_label": _period_label(payload.get("start_date"), asof_date),
            "points": points,
        }
    )
    return payload


def _series_payload(
    *,
    spec: dict[str, Any],
    source_provider: str,
    source_detail: str,
    source_tier: str,
    unit: str,
    frequency: str,
    meta: sqlite3.Row | None,
    latest: sqlite3.Row | None,
    points: list[dict[str, Any]],
    latest_date_key: str = "date",
    latest_value_key: str = "value",
) -> dict[str, Any]:
    start_date = meta["start_date"] if meta else None
    end_date = meta["end_date"] if meta else None
    latest_date = latest[latest_date_key] if latest else None
    latest_value = _to_float(latest[latest_value_key]) if latest else None
    return {
        "series_id": spec["series_id"],
        "display_name_kr": spec["display_name_kr"],
        "category_label_kr": spec["category_label_kr"],
        "source_provider": source_provider,
        "source_detail": source_detail,
        "source_tier": source_tier,
        "unit": unit,
        "frequency": frequency,
        "start_date": start_date,
        "end_date": end_date,
        "row_count": int(meta["row_count"] or 0) if meta else 0,
        "period_label": _period_label(start_date, end_date),
        "latest_date": latest_date,
        "latest_value": latest_value,
        "chart_type": "line",
        "default_chart_height_px": DEFAULT_CHART_HEIGHT_PX,
        "popup_enabled": True,
        "points": points,
    }


def _section_payload(
    *,
    section_id: str,
    title: str,
    description: str,
    order: int,
    series: list[dict[str, Any]],
    coverage_warning: str | None = None,
) -> dict[str, Any]:
    payload = {
        "section_id": section_id,
        "title": title,
        "description": description,
        "display_order": order,
        "chart_type": "line",
        "series_count": len(series),
        "series": series,
    }
    if coverage_warning:
        payload["coverage_warning"] = coverage_warning
    return payload


def build_market_environment_indicators_payload(
    con: sqlite3.Connection,
    *,
    market: str,
    asof: str,
    generated_at: str,
    global_db_path: Path = GLOBAL_MARKET_DB_PATH,
) -> dict[str, Any]:
    cutoff = _cutoff_date(asof)
    domestic_series = (
        _domestic_index_series(con, market=market, asof=asof, cutoff=cutoff)
        + _domestic_fx_series(con, market=market, asof=asof, cutoff=cutoff)
        + _domestic_rate_series(con, market=market, asof=asof, cutoff=cutoff)
    )
    fred_series = _fred_series(asof=asof, cutoff=cutoff, global_db_path=global_db_path)
    yahoo_series = _yahoo_series(asof=asof, cutoff=cutoff, global_db_path=global_db_path)
    return {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "title": "시장 환경 지표",
        "description": "국내 시장 원천 데이터, FRED 매크로/금리 데이터, Yahoo 글로벌 시장 데이터를 선 그래프로 확인하는 공개형 시장 환경 지표입니다.",
        "chart_policy": {
            "default_chart_type": "line",
            "default_chart_height_px": DEFAULT_CHART_HEIGHT_PX,
            "popup_enabled": True,
            "popup_chart_height_px": 420,
            "points_lookback_days": CHART_LOOKBACK_DAYS,
            "points_lookback_label": "최근 3년",
            "full_history_available_in_qm_db": True,
        },
        "sections": [
            _section_payload(
                section_id="domestic_source",
                title="국내 시장 원천 데이터",
                description="국내 대표 지수, 원/달러 환율, 국내 금리 데이터를 먼저 확인합니다.",
                order=1,
                series=domestic_series,
                coverage_warning="국내 금리 장기 이력은 현재 보강 대상이며, 일부 구간은 seed/manual 데이터입니다.",
            ),
            _section_payload(
                section_id="fred_macro",
                title="FRED/BLS/BEA/EIA 매크로·금리 데이터",
                description="미국 금리, 물가, 고용, GDP, 소비, 에너지, 신용스프레드 등 글로벌 매크로 원천 지표입니다.",
                order=2,
                series=fred_series,
            ),
            _section_payload(
                section_id="yahoo_global",
                title="Yahoo 글로벌 시장 데이터",
                description="미국 주식, 채권, 원자재, 달러, 한국 관련 해외 ETF 등 글로벌 시장 프록시입니다.",
                order=3,
                series=yahoo_series,
            ),
        ],
        "source_order": ["domestic_source", "fred_macro", "yahoo_global"],
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }


def build_market_environment_indicators_manifest(
    *,
    market: str,
    asof: str,
    generated_at: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    sections = payload.get("sections") or []
    return {
        "market": market,
        "asof": asof,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "title": "시장 환경 지표 manifest",
        "schema_version": "market_environment_indicators.v1",
        "handoff_version": "2026-05-19-market-environment-indicators",
        "files": {
            "quantservice": "quantservice_market_environment_indicators.json",
            "api": "api_v1_market_environment_indicators.json",
            "manifest": "quantservice_market_environment_indicators_manifest.json",
        },
        "section_order": [section.get("section_id") for section in sections],
        "section_counts": {
            section.get("section_id"): section.get("series_count", 0)
            for section in sections
        },
        "chart_policy": payload.get("chart_policy") or {},
        "compliance_meta": _compliance_meta(asof),
        "notice_block": NOTICE_BLOCK,
    }
