from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .db import upsert_many
from .kiwoom_rest import get_access_token, _post_json

KST = timezone(timedelta(hours=9))
KIWOOM_HOST = "https://api.kiwoom.com"
INVESTOR_ENDPOINT = "/api/dostk/stkinfo"
INVESTOR_API_ID = "ka10059"
DEFAULT_UNIVERSE_FILE = Path(r"D:\Quant\data\universe\universe_mix_top400_latest.csv")

INVESTOR_FIELD_MAP = {
    "개인": "ind_invsr",
    "외국인": "frgnr_invsr",
    "기관합계": "orgn",
    "금융투자": "fnnc_invt",
    "보험": "insrnc",
    "투신": "invtrt",
    "기타금융": "etc_fnnc",
    "은행": "bank",
    "연기금": "penfnd_etc",
    "사모": "samo_fund",
    "국가": "natn",
    "기타법인": "etc_corp",
    "기타외국인": "natfor",
}


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _normalize_date(value: str) -> str:
    text = str(value).strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"invalid date: {value}")
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"


def _api_date(value: str) -> str:
    return _normalize_date(value).replace("-", "")


def _norm_ticker(value: Any) -> str | None:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits.zfill(6) if digits else None


def _safe_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if text in {"", "-", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _load_universe(path: Path, limit: int | None) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    ticker_col = "ticker" if "ticker" in df.columns else "code" if "code" in df.columns else None
    if ticker_col is None:
        raise ValueError(f"ticker column not found: {path}")
    name_col = "name" if "name" in df.columns else "display_name" if "display_name" in df.columns else None
    market_col = "market" if "market" in df.columns else None
    out = pd.DataFrame(
        {
            "ticker": df[ticker_col].map(_norm_ticker),
            "name": df[name_col] if name_col else None,
            "market_scope": df[market_col] if market_col else None,
        }
    )
    out = out.dropna(subset=["ticker"]).drop_duplicates("ticker").reset_index(drop=True)
    if limit:
        out = out.head(limit)
    return out


def _request_investor_page(token: str, ticker: str, end: str, amt_qty_tp: str, retries: int = 3) -> tuple[list[dict[str, Any]], str, str]:
    payload = None
    headers = None
    for attempt in range(retries + 1):
        payload, headers = _post_json(
            f"{KIWOOM_HOST}{INVESTOR_ENDPOINT}",
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": f"Bearer {token}",
                "api-id": INVESTOR_API_ID,
                "cont-yn": "N",
                "next-key": "",
            },
            body={
                "dt": _api_date(end),
                "stk_cd": ticker,
                "amt_qty_tp": amt_qty_tp,
                "trde_tp": "0",
                "unit_tp": "1",
            },
            timeout=60,
        )
        if int(payload.get("return_code", -1)) == 0:
            break
        if "429" not in str(payload) or attempt >= retries:
            raise RuntimeError(f"Kiwoom {INVESTOR_API_ID} failed: {payload.get('return_msg')}")
        time.sleep(min(10.0, 1.5 * (attempt + 1)))
    rows = payload.get("stk_invsr_orgn") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else [], str(headers.get("cont-yn") or "N"), str(headers.get("next-key") or "")


def _request_investor_rows(token: str, ticker: str, end: str, amt_qty_tp: str, start: str | None, sleep: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_end = _api_date(end)
    start_norm = _normalize_date(start) if start else None
    seen: set[str] = set()
    while current_end and current_end not in seen:
        seen.add(current_end)
        page, cont_yn, next_key = _request_investor_page(token, ticker, current_end, amt_qty_tp)
        rows.extend(page)
        if start_norm and page:
            page_dates = [_normalize_date(str(row.get("dt"))) for row in page if row.get("dt")]
            if page_dates and min(page_dates) <= start_norm:
                break
        if cont_yn.upper() != "Y" or not next_key:
            break
        current_end = next_key
        if sleep > 0:
            time.sleep(sleep)
    return rows


def _rows_to_records(
    *,
    ticker: str,
    name: str | None,
    market_scope: str | None,
    amount_rows: list[dict[str, Any]],
    quantity_rows: list[dict[str, Any]],
    start: str | None,
    end: str,
    collected_at: str,
) -> list[dict[str, Any]]:
    amount_by_date = {str(row.get("dt")): row for row in amount_rows if row.get("dt")}
    quantity_by_date = {str(row.get("dt")): row for row in quantity_rows if row.get("dt")}
    start_norm = _normalize_date(start) if start else None
    end_norm = _normalize_date(end)
    records: list[dict[str, Any]] = []
    for dt in sorted(set(amount_by_date) | set(quantity_by_date)):
        try:
            trade_date = _normalize_date(dt)
        except ValueError:
            continue
        if start_norm and trade_date < start_norm:
            continue
        if trade_date > end_norm:
            continue
        amount_row = amount_by_date.get(dt, {})
        qty_row = quantity_by_date.get(dt, {})
        for investor, field in INVESTOR_FIELD_MAP.items():
            net_value_million = _safe_number(amount_row.get(field))
            records.append(
                {
                    "date": trade_date,
                    "ticker": ticker,
                    "name": name,
                    "market_scope": market_scope,
                    "investor": investor,
                    "net_volume": _safe_number(qty_row.get(field)),
                    "net_value": None if net_value_million is None else net_value_million * 1_000_000.0,
                    "source": f"kiwoom_rest_{INVESTOR_API_ID}",
                    "collected_at": collected_at,
                }
            )
    return records


def collect_kiwoom_investor_flows(
    con: sqlite3.Connection,
    *,
    universe_file: Path = DEFAULT_UNIVERSE_FILE,
    end: str,
    start: str | None,
    limit: int | None = None,
    sleep: float = 0.05,
) -> dict[str, Any]:
    collected_at = _now_kst()
    universe = _load_universe(universe_file, limit)
    token, expires_dt = get_access_token()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for item in universe.to_dict(orient="records"):
        ticker = item["ticker"]
        try:
            amount_rows = _request_investor_rows(token, ticker, end, "1", start, sleep)
            if sleep > 0:
                time.sleep(sleep)
            quantity_rows = _request_investor_rows(token, ticker, end, "2", start, sleep)
            rows.extend(
                _rows_to_records(
                    ticker=ticker,
                    name=item.get("name"),
                    market_scope=item.get("market_scope"),
                    amount_rows=amount_rows,
                    quantity_rows=quantity_rows,
                    start=start,
                    end=end,
                    collected_at=collected_at,
                )
            )
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)[:300]})
        if sleep > 0:
            time.sleep(sleep)

    if rows:
        upsert_many(
            con,
            table="kiwoom_stock_investor_flow_daily",
            columns=["date", "ticker", "name", "market_scope", "investor", "net_volume", "net_value", "source", "collected_at"],
            rows=rows,
            conflict_columns=["date", "ticker", "investor"],
        )
        if limit is None:
            _upsert_market_aggregate(con, rows, collected_at=collected_at)

    result = {
        "status": "ok" if not errors else "partial",
        "source": f"kiwoom_rest_{INVESTOR_API_ID}",
        "universe_file": str(universe_file),
        "universe_count": int(len(universe)),
        "rows": int(len(rows)),
        "saved": int(len(rows)),
        "market_aggregate_saved": bool(rows and limit is None),
        "start": None if start is None else _normalize_date(start),
        "end": _normalize_date(end),
        "token_expires_dt": expires_dt,
        "errors": errors[:20],
        "error_count": len(errors),
    }
    _write_status(con, result, collected_at=collected_at)
    return result


def _upsert_market_aggregate(con: sqlite3.Connection, rows: list[dict[str, Any]], *, collected_at: str) -> None:
    df = pd.DataFrame(rows)
    if df.empty:
        return
    df = df[df["investor"].isin(["외국인", "기관합계", "개인"])]
    df = df[df["market_scope"].isin(["KOSPI", "KOSDAQ"])]
    if df.empty:
        return
    scoped = [df.copy()]
    all_df = df.copy()
    all_df["market_scope"] = "ALL"
    scoped.append(all_df)
    out = pd.concat(scoped, ignore_index=True)
    agg = out.groupby(["date", "market_scope", "investor"], as_index=False)["net_value"].sum()
    records = [
        {
            "market": "KR",
            "date": row["date"],
            "market_scope": row["market_scope"],
            "investor": row["investor"],
            "net_buy_value": None if pd.isna(row["net_value"]) else float(row["net_value"]),
            "source": f"kiwoom_rest_{INVESTOR_API_ID}:top_universe_aggregate",
            "source_status": "proxy_top_universe",
            "updated_at": collected_at,
        }
        for row in agg.to_dict(orient="records")
    ]
    upsert_many(
        con,
        table="market_investor_flow_daily",
        columns=["market", "date", "market_scope", "investor", "net_buy_value", "source", "source_status", "updated_at"],
        rows=records,
        conflict_columns=["market", "date", "market_scope", "investor"],
    )


def _write_status(con: sqlite3.Connection, result: dict[str, Any], *, collected_at: str) -> None:
    upsert_many(
        con,
        table="market_source_collection_status",
        columns=["source_name", "market", "asof_date", "status", "row_count", "message", "detail_json", "updated_at"],
        rows=[
            {
                "source_name": "kiwoom_investor_flows",
                "market": "KR",
                "asof_date": result["end"],
                "status": result["status"],
                "row_count": int(result["saved"]),
                "message": None if result["status"] == "ok" else f"errors={result['error_count']}",
                "detail_json": json.dumps(result, ensure_ascii=False),
                "updated_at": collected_at,
            }
        ],
        conflict_columns=["source_name", "market", "asof_date"],
    )
