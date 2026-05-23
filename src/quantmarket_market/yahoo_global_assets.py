from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from .global_context_db import connect_global_context, init_global_context_db

SOURCE = "YAHOO"
KST = timezone(timedelta(hours=9))
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
YAHOO_DAILY_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?period1={period1}&period2={period2}&interval=1d&events=history&includeAdjustedClose=true"
)
YAHOO_INTRADAY_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=5m&range=1d"


@dataclass(frozen=True)
class YahooAssetSpec:
    asset_code: str
    symbol: str
    display_name: str
    asset_group: str
    region: str
    currency: str
    market_relevance: str
    score_direction: str


DEFAULT_YAHOO_ASSETS: tuple[YahooAssetSpec, ...] = (
    YahooAssetSpec("SPY", "SPY", "SPDR S&P 500 ETF", "us_equity_broad", "US", "USD", "US large-cap risk appetite", "higher return is risk-on"),
    YahooAssetSpec("QQQ", "QQQ", "Invesco QQQ Trust", "us_equity_growth", "US", "USD", "US growth/technology risk appetite", "higher return is risk-on"),
    YahooAssetSpec("IWM", "IWM", "iShares Russell 2000 ETF", "us_equity_smallcap", "US", "USD", "US small-cap risk appetite", "higher return is risk-on"),
    YahooAssetSpec("DIA", "DIA", "SPDR Dow Jones Industrial Average ETF", "us_equity_broad", "US", "USD", "US blue-chip equity", "higher return is risk-on"),
    YahooAssetSpec("ACWI", "ACWI", "iShares MSCI ACWI ETF", "global_equity", "GLOBAL", "USD", "Global equity risk appetite", "higher return is risk-on"),
    YahooAssetSpec("ACWX", "ACWX", "iShares MSCI ACWI ex U.S. ETF", "global_equity_ex_us", "GLOBAL", "USD", "Global ex-US equity risk appetite", "higher return is risk-on"),
    YahooAssetSpec("EFA", "EFA", "iShares MSCI EAFE ETF", "developed_ex_us_equity", "GLOBAL", "USD", "Developed ex-US equity risk appetite", "higher return is risk-on"),
    YahooAssetSpec("EEM", "EEM", "iShares MSCI Emerging Markets ETF", "em_equity", "EM", "USD", "Emerging market risk appetite", "higher return is risk-on"),
    YahooAssetSpec("FXI", "FXI", "iShares China Large-Cap ETF", "china_equity", "CN", "USD", "China large-cap equity risk appetite", "higher return is risk-on for Asia"),
    YahooAssetSpec("EWJ", "EWJ", "iShares MSCI Japan ETF", "japan_equity", "JP", "USD", "Japan equity risk appetite", "higher return is risk-on for Asia"),
    YahooAssetSpec("EWT", "EWT", "iShares MSCI Taiwan ETF", "taiwan_equity", "TW", "USD", "Taiwan/semiconductor Asia proxy", "higher return is risk-on for Asia tech"),
    YahooAssetSpec("INDA", "INDA", "iShares MSCI India ETF", "india_equity", "IN", "USD", "India equity risk appetite", "higher return is risk-on for Asia"),
    YahooAssetSpec("EWY", "EWY", "iShares MSCI South Korea ETF", "korea_proxy", "KR", "USD", "US-listed Korea proxy", "higher return is risk-on for Korea"),
    YahooAssetSpec("SOXX", "SOXX", "iShares Semiconductor ETF", "semiconductor", "US", "USD", "Global semiconductor risk appetite", "higher return is risk-on for Korea tech exporters"),
    YahooAssetSpec("XLK", "XLK", "Technology Select Sector SPDR", "us_sector_cyclical", "US", "USD", "US technology sector", "higher return is risk-on"),
    YahooAssetSpec("XLY", "XLY", "Consumer Discretionary Select Sector SPDR", "us_sector_cyclical", "US", "USD", "US discretionary sector", "higher return is risk-on"),
    YahooAssetSpec("XLI", "XLI", "Industrial Select Sector SPDR", "us_sector_cyclical", "US", "USD", "US industrial sector", "higher return is risk-on"),
    YahooAssetSpec("XLF", "XLF", "Financial Select Sector SPDR", "us_sector_cyclical", "US", "USD", "US financial sector", "higher return is risk-on"),
    YahooAssetSpec("XLE", "XLE", "Energy Select Sector SPDR", "us_sector_cyclical", "US", "USD", "US energy sector", "higher return is mixed/risk-on when growth-led"),
    YahooAssetSpec("XLV", "XLV", "Health Care Select Sector SPDR", "us_sector_defensive", "US", "USD", "US healthcare defensive sector", "higher relative return can be defensive"),
    YahooAssetSpec("XLP", "XLP", "Consumer Staples Select Sector SPDR", "us_sector_defensive", "US", "USD", "US staples defensive sector", "higher relative return can be defensive"),
    YahooAssetSpec("XLU", "XLU", "Utilities Select Sector SPDR", "us_sector_defensive", "US", "USD", "US utilities defensive sector", "higher relative return can be defensive"),
    YahooAssetSpec("XLC", "XLC", "Communication Services Select Sector SPDR", "us_sector_growth", "US", "USD", "US communication sector", "higher return is risk-on"),
    YahooAssetSpec("XLB", "XLB", "Materials Select Sector SPDR", "us_sector_cyclical", "US", "USD", "US materials sector", "higher return is risk-on"),
    YahooAssetSpec("XLRE", "XLRE", "Real Estate Select Sector SPDR", "us_sector_rate_sensitive", "US", "USD", "US real estate/rate sensitive sector", "higher return is risk-on when rates stable"),
    YahooAssetSpec("KRE", "KRE", "SPDR S&P Regional Banking ETF", "us_financial_stress", "US", "USD", "US regional bank stress/risk appetite proxy", "higher return is risk-on"),
    YahooAssetSpec("XHB", "XHB", "SPDR S&P Homebuilders ETF", "us_rate_sensitive_cyclical", "US", "USD", "US homebuilder rate-sensitive cyclical proxy", "higher return is risk-on when rates stable"),
    YahooAssetSpec("IYT", "IYT", "iShares U.S. Transportation ETF", "us_transport_cyclical", "US", "USD", "US transportation cyclical demand proxy", "higher return is risk-on"),
    YahooAssetSpec("USMV", "USMV", "iShares MSCI USA Min Vol Factor ETF", "us_low_vol", "US", "USD", "US low-volatility defensive equity proxy", "higher relative return can be defensive"),
    YahooAssetSpec("TLT", "TLT", "iShares 20+ Year Treasury Bond ETF", "safe_haven_rates", "US", "USD", "Long-duration US Treasury proxy", "higher return can be risk-off/rate relief"),
    YahooAssetSpec("IEF", "IEF", "iShares 7-10 Year Treasury Bond ETF", "safe_haven_rates", "US", "USD", "Intermediate US Treasury proxy", "higher return can be risk-off/rate relief"),
    YahooAssetSpec("SHY", "SHY", "iShares 1-3 Year Treasury Bond ETF", "safe_haven_rates", "US", "USD", "Short US Treasury proxy", "higher return can be risk-off/rate relief"),
    YahooAssetSpec("HYG", "HYG", "iShares iBoxx High Yield Corporate Bond ETF", "credit_risk", "US", "USD", "High-yield credit appetite", "higher return is risk-on"),
    YahooAssetSpec("LQD", "LQD", "iShares iBoxx Investment Grade Corporate Bond ETF", "credit_quality", "US", "USD", "Investment-grade credit proxy", "higher return is mixed"),
    YahooAssetSpec("GLD", "GLD", "SPDR Gold Shares", "safe_haven_commodity", "GLOBAL", "USD", "Gold safe-haven proxy", "higher return can be risk-off/inflation hedge"),
    YahooAssetSpec("USO", "USO", "United States Oil Fund", "commodity_energy", "GLOBAL", "USD", "Oil price proxy", "higher return can add inflation/input-cost risk"),
    YahooAssetSpec("UUP", "UUP", "Invesco DB US Dollar Index Bullish Fund", "dollar", "US", "USD", "US dollar strength proxy", "higher return is often external pressure for KR"),
    YahooAssetSpec("VIX", "^VIX", "CBOE Volatility Index", "volatility", "US", "USD", "US equity volatility index", "higher level/return is risk-off"),
    YahooAssetSpec("DXY", "DX-Y.NYB", "US Dollar Index", "dollar_index", "US", "USD", "Direct US dollar index proxy", "higher return is often external pressure for KR"),
    YahooAssetSpec("BTCUSD", "BTC-USD", "Bitcoin USD", "crypto_risk", "GLOBAL", "USD", "Crypto risk appetite proxy", "higher return is speculative risk-on"),
)


def _now_iso() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _unix_date(date_text: str) -> int:
    dt = datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _fetch_yahoo_daily(symbol: str, *, start: str, end: str) -> dict:
    period1 = _unix_date(start)
    period2 = _unix_date(end) + 86400
    url = YAHOO_DAILY_CHART_URL.format(symbol=quote(symbol, safe=""), period1=period1, period2=period2)
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    error = (payload.get("chart") or {}).get("error")
    if error:
        raise RuntimeError(json.dumps(error, ensure_ascii=False))
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError(f"Yahoo chart returned no result for {symbol}")
    return result[0]


def _fetch_yahoo_intraday(symbol: str) -> dict:
    url = YAHOO_INTRADAY_CHART_URL.format(symbol=quote(symbol, safe=""))
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    error = (payload.get("chart") or {}).get("error")
    if error:
        raise RuntimeError(json.dumps(error, ensure_ascii=False))
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError(f"Yahoo intraday chart returned no result for {symbol}")
    return result[0]


def _last_non_null(values: list | None, default=None):
    if not values:
        return default
    for value in reversed(values):
        if value is not None:
            return value
    return default


def _latest_intraday_row(spec: YahooAssetSpec, chart: dict, *, asof: str, collected_at: str) -> dict:
    meta = chart.get("meta") or {}
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    latest_ts = timestamps[-1] if timestamps else meta.get("regularMarketTime")
    latest_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc).astimezone(KST) if latest_ts else None
    price = meta.get("regularMarketPrice")
    if price is None:
        price = _last_non_null(quote.get("close"))
    prev_close = meta.get("chartPreviousClose") if meta.get("chartPreviousClose") is not None else meta.get("previousClose")
    open_value = meta.get("regularMarketOpen")
    if open_value is None:
        open_value = _last_non_null(quote.get("open"))
    high_value = meta.get("regularMarketDayHigh")
    if high_value is None:
        high_value = _last_non_null(quote.get("high"))
    low_value = meta.get("regularMarketDayLow")
    if low_value is None:
        low_value = _last_non_null(quote.get("low"))
    volume = meta.get("regularMarketVolume")
    if volume is None:
        volume = _last_non_null(quote.get("volume"), default=0.0)
    if price is None:
        raise RuntimeError(f"No intraday price for {spec.symbol}")
    price = float(price)
    prev_close = float(prev_close) if prev_close not in (None, 0) else None
    return {
        "source": SOURCE,
        "asset_code": spec.asset_code,
        "symbol": spec.symbol,
        "asof": asof,
        "session_date": latest_dt.date().isoformat() if latest_dt else asof[:10],
        "price": price,
        "change_value": price - prev_close if prev_close else None,
        "change_pct": price / prev_close - 1.0 if prev_close else None,
        "open": float(open_value) if open_value is not None else None,
        "high": float(high_value) if high_value is not None else None,
        "low": float(low_value) if low_value is not None else None,
        "prev_close": prev_close,
        "volume": float(volume or 0.0),
        "quote_time": latest_dt.isoformat(timespec="seconds") if latest_dt else None,
        "collected_at": collected_at,
    }


def _rows_from_chart(spec: YahooAssetSpec, chart: dict, collected_at: str) -> list[dict]:
    timestamps = chart.get("timestamp") or []
    indicators = chart.get("indicators") or {}
    quote = (indicators.get("quote") or [{}])[0]
    adjclose = ((indicators.get("adjclose") or [{}])[0]).get("adjclose") or []
    rows: list[dict] = []
    for idx, ts in enumerate(timestamps):
        asof_date = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        close_value = (quote.get("close") or [None] * len(timestamps))[idx]
        if close_value is None:
            continue
        rows.append(
            {
                "source": SOURCE,
                "asset_code": spec.asset_code,
                "symbol": spec.symbol,
                "asof_date": asof_date,
                "open": (quote.get("open") or [None] * len(timestamps))[idx],
                "high": (quote.get("high") or [None] * len(timestamps))[idx],
                "low": (quote.get("low") or [None] * len(timestamps))[idx],
                "close": close_value,
                "adj_close": adjclose[idx] if idx < len(adjclose) else close_value,
                "volume": (quote.get("volume") or [None] * len(timestamps))[idx],
                "collected_at": collected_at,
            }
        )
    return rows


def collect_yahoo_global_assets(
    *,
    db_path: Path,
    start: str,
    end: str,
    sleep_seconds: float = 0.2,
) -> dict:
    init_global_context_db(db_path)
    collected_at = _now_iso()
    inserted_rows = 0
    failed: list[dict] = []
    with connect_global_context(db_path) as con:
        con.executemany(
            """
            INSERT INTO global_asset_registry (
                source, asset_code, symbol, display_name, asset_group, region, currency,
                market_relevance, score_direction, is_active, created_at, updated_at
            )
            VALUES (
                :source, :asset_code, :symbol, :display_name, :asset_group, :region, :currency,
                :market_relevance, :score_direction, 1, :created_at, :updated_at
            )
            ON CONFLICT(source, asset_code) DO UPDATE SET
                symbol=excluded.symbol,
                display_name=excluded.display_name,
                asset_group=excluded.asset_group,
                region=excluded.region,
                currency=excluded.currency,
                market_relevance=excluded.market_relevance,
                score_direction=excluded.score_direction,
                is_active=1,
                updated_at=excluded.updated_at
            """,
            [
                {
                    "source": SOURCE,
                    "asset_code": spec.asset_code,
                    "symbol": spec.symbol,
                    "display_name": spec.display_name,
                    "asset_group": spec.asset_group,
                    "region": spec.region,
                    "currency": spec.currency,
                    "market_relevance": spec.market_relevance,
                    "score_direction": spec.score_direction,
                    "created_at": collected_at,
                    "updated_at": collected_at,
                }
                for spec in DEFAULT_YAHOO_ASSETS
            ],
        )
        for spec in DEFAULT_YAHOO_ASSETS:
            try:
                chart = _fetch_yahoo_daily(spec.symbol, start=start, end=end)
                rows = _rows_from_chart(spec, chart, collected_at)
                con.executemany(
                    """
                    INSERT INTO global_asset_daily (
                        source, asset_code, symbol, asof_date, open, high, low, close,
                        adj_close, volume, collected_at
                    )
                    VALUES (
                        :source, :asset_code, :symbol, :asof_date, :open, :high, :low, :close,
                        :adj_close, :volume, :collected_at
                    )
                    ON CONFLICT(source, asset_code, asof_date) DO UPDATE SET
                        symbol=excluded.symbol,
                        open=excluded.open,
                        high=excluded.high,
                        low=excluded.low,
                        close=excluded.close,
                        adj_close=excluded.adj_close,
                        volume=excluded.volume,
                        collected_at=excluded.collected_at
                    """,
                    rows,
                )
                inserted_rows += len(rows)
                con.commit()
            except Exception as exc:
                failed.append({"asset_code": spec.asset_code, "symbol": spec.symbol, "error": f"{type(exc).__name__}: {exc}"})
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    return {
        "source": SOURCE,
        "db_path": str(db_path),
        "start": start,
        "end": end,
        "asset_count": len(DEFAULT_YAHOO_ASSETS),
        "inserted_or_updated_rows": inserted_rows,
        "failed": failed,
        "collected_at": collected_at,
    }


def collect_yahoo_global_assets_intraday(
    *,
    db_path: Path,
    asof: str | None = None,
    sleep_seconds: float = 0.05,
) -> dict:
    init_global_context_db(db_path)
    collected_at = _now_iso()
    asof_value = asof or collected_at
    inserted_rows = 0
    failed: list[dict] = []
    with connect_global_context(db_path) as con:
        con.executemany(
            """
            INSERT INTO global_asset_registry (
                source, asset_code, symbol, display_name, asset_group, region, currency,
                market_relevance, score_direction, is_active, created_at, updated_at
            )
            VALUES (
                :source, :asset_code, :symbol, :display_name, :asset_group, :region, :currency,
                :market_relevance, :score_direction, 1, :created_at, :updated_at
            )
            ON CONFLICT(source, asset_code) DO UPDATE SET
                symbol=excluded.symbol,
                display_name=excluded.display_name,
                asset_group=excluded.asset_group,
                region=excluded.region,
                currency=excluded.currency,
                market_relevance=excluded.market_relevance,
                score_direction=excluded.score_direction,
                is_active=1,
                updated_at=excluded.updated_at
            """,
            [
                {
                    "source": SOURCE,
                    "asset_code": spec.asset_code,
                    "symbol": spec.symbol,
                    "display_name": spec.display_name,
                    "asset_group": spec.asset_group,
                    "region": spec.region,
                    "currency": spec.currency,
                    "market_relevance": spec.market_relevance,
                    "score_direction": spec.score_direction,
                    "created_at": collected_at,
                    "updated_at": collected_at,
                }
                for spec in DEFAULT_YAHOO_ASSETS
            ],
        )
        for spec in DEFAULT_YAHOO_ASSETS:
            try:
                chart = _fetch_yahoo_intraday(spec.symbol)
                row = _latest_intraday_row(spec, chart, asof=asof_value, collected_at=collected_at)
                con.execute(
                    """
                    INSERT INTO global_asset_intraday_snapshot (
                        source, asset_code, symbol, asof, session_date, price, change_value,
                        change_pct, open, high, low, prev_close, volume, quote_time, collected_at
                    )
                    VALUES (
                        :source, :asset_code, :symbol, :asof, :session_date, :price, :change_value,
                        :change_pct, :open, :high, :low, :prev_close, :volume, :quote_time, :collected_at
                    )
                    ON CONFLICT(source, asset_code, asof) DO UPDATE SET
                        symbol=excluded.symbol,
                        session_date=excluded.session_date,
                        price=excluded.price,
                        change_value=excluded.change_value,
                        change_pct=excluded.change_pct,
                        open=excluded.open,
                        high=excluded.high,
                        low=excluded.low,
                        prev_close=excluded.prev_close,
                        volume=excluded.volume,
                        quote_time=excluded.quote_time,
                        collected_at=excluded.collected_at
                    """,
                    row,
                )
                inserted_rows += 1
                con.commit()
            except Exception as exc:
                failed.append({"asset_code": spec.asset_code, "symbol": spec.symbol, "error": f"{type(exc).__name__}: {exc}"})
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    return {
        "source": SOURCE,
        "mode": "intraday",
        "db_path": str(db_path),
        "asof": asof_value,
        "asset_count": len(DEFAULT_YAHOO_ASSETS),
        "inserted_or_updated_rows": inserted_rows,
        "failed": failed,
        "collected_at": collected_at,
    }
