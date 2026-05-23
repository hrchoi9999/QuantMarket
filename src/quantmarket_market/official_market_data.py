from __future__ import annotations

import csv
from datetime import datetime, timedelta

import FinanceDataReader as fdr
import pandas as pd

from .bok_ecos_collector import bok_key_available, collect_bok_ecos_market_data
from .config import MANUAL_RATE_SEED_PATH
from .db import upsert_many

INDEX_SPECS = {
    "1001": {"name": "KOSPI", "fdr_symbol": "^KS11"},
    "2001": {"name": "KOSDAQ", "fdr_symbol": "^KQ11"},
    "1028": {"name": "KOSPI200", "fdr_symbol": "^KS200"},
}
RATE_NAME_MAP = {
    "BASE": "Base Rate",
    "CD91": "CD 91D",
    "KTB3Y": "KTB 3Y",
    "KTB5Y": "KTB 5Y",
}


def _date_range_start(con, *, table: str, key_column: str, key_value: str, market: str, asof_date: str, default_days: int = 120) -> str:
    row = con.execute(
        f"SELECT MAX(date) FROM {table} WHERE market = ? AND {key_column} = ?",
        (market, key_value),
    ).fetchone()
    if row and row[0]:
        last = datetime.strptime(row[0], "%Y-%m-%d").date()
        return (last - timedelta(days=5)).isoformat()
    return (datetime.strptime(asof_date, "%Y-%m-%d").date() - timedelta(days=default_days)).isoformat()


def _normalize_index_df(df: pd.DataFrame, *, market: str, index_code: str, index_name: str, source: str, updated_at: str) -> list[dict]:
    rename_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "Adj Close": "adj_close"}
    df = df.rename(columns=rename_map).copy()
    rows: list[dict] = []
    for dt, row in df.iterrows():
        close = row.get("close")
        if pd.isna(close):
            continue
        rows.append({
            "market": market,
            "index_code": index_code,
            "index_name": index_name,
            "date": pd.Timestamp(dt).strftime("%Y-%m-%d"),
            "open": None if pd.isna(row.get("open")) else float(row.get("open")),
            "high": None if pd.isna(row.get("high")) else float(row.get("high")),
            "low": None if pd.isna(row.get("low")) else float(row.get("low")),
            "close": float(close),
            "volume": None if pd.isna(row.get("volume")) else float(row.get("volume")),
            "value": None,
            "source": source,
            "updated_at": updated_at,
        })
    return rows


def _normalize_fx_df(df: pd.DataFrame, *, market: str, source: str, updated_at: str) -> list[dict]:
    df = df.rename(columns={"Close": "close", "Adj Close": "adj_close"}).copy()
    rows: list[dict] = []
    for dt, row in df.iterrows():
        close = row.get("close")
        if pd.isna(close):
            continue
        rows.append({
            "market": market,
            "series_code": "USDKRW",
            "series_name": "USD/KRW",
            "date": pd.Timestamp(dt).strftime("%Y-%m-%d"),
            "close": float(close),
            "source": source,
            "updated_at": updated_at,
        })
    return rows


def _load_manual_rate_seed(*, market: str, updated_at: str) -> list[dict]:
    if not MANUAL_RATE_SEED_PATH.exists():
        return []
    rows: list[dict] = []
    with MANUAL_RATE_SEED_PATH.open('r', encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            if not row.get('date') or not row.get('rate_code') or not row.get('value'):
                continue
            rows.append({
                'market': market,
                'rate_code': row['rate_code'].strip(),
                'rate_name': (row.get('rate_name') or RATE_NAME_MAP.get(row['rate_code'].strip()) or row['rate_code'].strip()).strip(),
                'date': row['date'].strip(),
                'value': float(row['value']),
                'source': (row.get('source') or 'manual_seed').strip(),
                'updated_at': updated_at,
            })
    return rows


def _carry_forward_latest_rates(con, *, market: str, asof_date: str, updated_at: str) -> list[dict]:
    latest_date_row = con.execute(
        "SELECT MAX(date) FROM market_rates_daily WHERE market = ?",
        (market,),
    ).fetchone()
    latest_date = latest_date_row[0] if latest_date_row and latest_date_row[0] else None
    if not latest_date:
        return []
    out: list[dict] = []
    for row in con.execute(
        "SELECT rate_code, rate_name, value, source FROM market_rates_daily WHERE market = ? AND date = ?",
        (market, latest_date),
    ):
        out.append({
            'market': market,
            'rate_code': row[0],
            'rate_name': row[1],
            'date': asof_date,
            'value': float(row[2]),
            'source': f"carry_forward:{row[3]}",
            'updated_at': updated_at,
        })
    return out


def collect_official_market_data(con, *, market: str, asof_date: str, updated_at: str) -> dict:
    stats = {"index_rows": 0, "fx_rows": 0, "rate_rows": 0, "rate_source": None}
    if market != "KR":
        return stats

    index_rows_all: list[dict] = []
    for code, spec in INDEX_SPECS.items():
        start = _date_range_start(con, table="market_index_daily", key_column="index_code", key_value=code, market=market, asof_date=asof_date)
        df = fdr.DataReader(spec["fdr_symbol"], start, asof_date)
        rows = _normalize_index_df(df, market=market, index_code=code, index_name=spec["name"], source=f"fdr:{spec['fdr_symbol']}", updated_at=updated_at)
        index_rows_all.extend(rows)
    if index_rows_all:
        upsert_many(con, table="market_index_daily", columns=["market", "index_code", "index_name", "date", "open", "high", "low", "close", "volume", "value", "source", "updated_at"], rows=index_rows_all, conflict_columns=["market", "index_code", "date"])
        stats["index_rows"] = len(index_rows_all)

    fx_start = _date_range_start(con, table="market_fx_daily", key_column="series_code", key_value="USDKRW", market=market, asof_date=asof_date)
    fx_df = fdr.DataReader("USD/KRW", fx_start, asof_date)
    fx_rows = _normalize_fx_df(fx_df, market=market, source="fdr:USD/KRW", updated_at=updated_at)
    if fx_rows:
        upsert_many(con, table="market_fx_daily", columns=["market", "series_code", "series_name", "date", "close", "source", "updated_at"], rows=fx_rows, conflict_columns=["market", "series_code", "date"])
        stats["fx_rows"] = len(fx_rows)

    bok_stats = None
    if bok_key_available():
        try:
            bok_start = min(
                fx_start,
                _date_range_start(con, table="market_rates_daily", key_column="rate_code", key_value="CD91", market=market, asof_date=asof_date),
                _date_range_start(con, table="market_rates_daily", key_column="rate_code", key_value="KTB3Y", market=market, asof_date=asof_date),
                _date_range_start(con, table="market_rates_daily", key_column="rate_code", key_value="KTB5Y", market=market, asof_date=asof_date),
            )
            bok_stats = collect_bok_ecos_market_data(
                con,
                market=market,
                start_date=bok_start,
                end_date=asof_date,
                updated_at=updated_at,
            )
            if bok_stats.get("fx_rows", 0) > 0:
                stats["fx_rows"] += int(bok_stats["fx_rows"])
            if bok_stats.get("rate_rows", 0) > 0:
                stats["rate_rows"] = int(bok_stats["rate_rows"])
                stats["rate_source"] = "bok_ecos"
        except Exception as exc:
            stats["bok_ecos_error"] = str(exc)

    rate_rows = []
    rate_source = None
    if stats.get("rate_source") != "bok_ecos":
        rate_rows = _load_manual_rate_seed(market=market, updated_at=updated_at)
        rate_source = 'manual_seed' if rate_rows else None
        if not rate_rows:
            rate_rows = _carry_forward_latest_rates(con, market=market, asof_date=asof_date, updated_at=updated_at)
            rate_source = 'carry_forward' if rate_rows else None
    if rate_rows:
        upsert_many(con, table="market_rates_daily", columns=["market", "rate_code", "rate_name", "date", "value", "source", "updated_at"], rows=rate_rows, conflict_columns=["market", "rate_code", "date"])
        stats["rate_rows"] = len(rate_rows)
        stats["rate_source"] = rate_source

    return stats
