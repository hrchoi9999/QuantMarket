from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .config import ROOT_DIR
from .db import upsert_many

KST = timezone(timedelta(hours=9))
KRX_COOKIE_HEADER_PATH = ROOT_DIR / "config" / "krx_cookie_header.txt"
KRX_JSON_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
KRX_REFERER = "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201"

MARKET_ID = {
    "KOSPI": "STK",
    "KOSDAQ": "KSQ",
    "ALL": "ALL",
}

INVESTOR_COLUMNS = {
    "TRDVAL1": "기관합계",
    "TRDVAL2": "기타법인",
    "TRDVAL3": "개인",
    "TRDVAL4": "외국인합계",
    "TRDVAL_TOT": "전체",
}


class KrxLoginRequiredError(RuntimeError):
    pass


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _compact_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None
    return float(text)


def _date_yyyy_mm_dd(value: str) -> str:
    return datetime.strptime(value.strip(), "%Y/%m/%d").date().isoformat()


def _load_cookie_header(cookie_header_path: Path | None = None) -> str | None:
    path = cookie_header_path or KRX_COOKIE_HEADER_PATH
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def _post_krx_json(bld: str, params: dict[str, Any], *, cookie_header: str | None) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": KRX_REFERER,
        "Origin": "https://data.krx.co.kr",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header

    payload = {
        "bld": bld,
        "locale": "ko_KR",
        "csvxls_isNo": "false",
        **params,
    }
    response = requests.post(KRX_JSON_URL, data=payload, headers=headers, timeout=30)
    text = response.text.strip()
    if response.status_code == 400 and text.upper() == "LOGOUT":
        raise KrxLoginRequiredError("KRX responded LOGOUT. Add a valid browser Cookie header to config/krx_cookie_header.txt.")
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        if "로그인" in text or "LOGOUT" in text.upper():
            raise KrxLoginRequiredError("KRX login session is required.") from exc
        raise
    if isinstance(data, dict) and str(data.get("errorCode", "")).upper() in {"LOGOUT", "401"}:
        raise KrxLoginRequiredError("KRX login session is required.")
    return data


def _fetch_market_flow_rows(
    *,
    start_yyyymmdd: str,
    end_yyyymmdd: str,
    market_scope: str,
    cookie_header: str | None,
) -> list[dict[str, Any]]:
    data = _post_krx_json(
        "dbms/MDC/STAT/standard/MDCSTAT02202",
        {
            "strtDd": start_yyyymmdd,
            "endDd": end_yyyymmdd,
            "mktId": MARKET_ID[market_scope],
            "etf": "",
            "etn": "",
            "elw": "",
            "inqTpCd": "2",
            "trdVolVal": "2",
            "askBid": "3",
            "share": "1",
            "money": "1",
        },
        cookie_header=cookie_header,
    )
    return list(data.get("output") or [])


def collect_krx_official_market_data(
    con,
    *,
    market: str,
    start_date: str,
    end_date: str,
    updated_at: str | None = None,
    cookie_header_path: Path | None = None,
) -> dict[str, Any]:
    """Collect KRX official market-level investor flow.

    KRX Data Marketplace currently requires a logged-in browser session for this
    endpoint. The cookie header is read from config/krx_cookie_header.txt, which
    is git-ignored.
    """
    updated_at = updated_at or _now_kst()
    cookie_header = _load_cookie_header(cookie_header_path)
    stats: dict[str, Any] = {
        "source": "krx:data_marketplace:MDCSTAT02202",
        "market": market,
        "start_date": start_date,
        "end_date": end_date,
        "row_count": 0,
        "status": "skipped",
        "message": None,
    }
    if market != "KR":
        stats["message"] = "Only KR market is supported."
        _write_status(con, stats, asof_date=end_date, updated_at=updated_at)
        return stats
    if not cookie_header:
        stats["status"] = "not_configured"
        stats["message"] = f"Missing KRX Cookie header file: {KRX_COOKIE_HEADER_PATH}"
        _write_status(con, stats, asof_date=end_date, updated_at=updated_at)
        return stats

    start_yyyymmdd = start_date.replace("-", "")
    end_yyyymmdd = end_date.replace("-", "")
    rows_out: list[dict[str, Any]] = []
    try:
        for scope in ("KOSPI", "KOSDAQ", "ALL"):
            raw_rows = _fetch_market_flow_rows(
                start_yyyymmdd=start_yyyymmdd,
                end_yyyymmdd=end_yyyymmdd,
                market_scope=scope,
                cookie_header=cookie_header,
            )
            for raw in raw_rows:
                date = _date_yyyy_mm_dd(str(raw.get("TRD_DD")))
                for column, investor in INVESTOR_COLUMNS.items():
                    rows_out.append(
                        {
                            "market": market,
                            "date": date,
                            "market_scope": scope,
                            "investor": investor,
                            "net_buy_value": _compact_number(raw.get(column)),
                            "source": "krx:data_marketplace:MDCSTAT02202",
                            "source_status": "official_login_session",
                            "updated_at": updated_at,
                        }
                    )
    except KrxLoginRequiredError as exc:
        stats["status"] = "login_required"
        stats["message"] = str(exc)
        _write_status(con, stats, asof_date=end_date, updated_at=updated_at)
        return stats

    if rows_out:
        upsert_many(
            con,
            table="market_investor_flow_daily",
            columns=[
                "market",
                "date",
                "market_scope",
                "investor",
                "net_buy_value",
                "source",
                "source_status",
                "updated_at",
            ],
            rows=rows_out,
            conflict_columns=["market", "date", "market_scope", "investor"],
        )
    stats["row_count"] = len(rows_out)
    stats["status"] = "ok" if rows_out else "empty"
    stats["message"] = None if rows_out else "KRX returned no rows."
    _write_status(con, stats, asof_date=end_date, updated_at=updated_at)
    return stats


def _write_status(con, stats: dict[str, Any], *, asof_date: str, updated_at: str) -> None:
    upsert_many(
        con,
        table="market_source_collection_status",
        columns=[
            "source_name",
            "market",
            "asof_date",
            "status",
            "row_count",
            "message",
            "detail_json",
            "updated_at",
        ],
        rows=[
            {
                "source_name": "krx_official_market_data",
                "market": stats["market"],
                "asof_date": asof_date,
                "status": stats["status"],
                "row_count": int(stats.get("row_count") or 0),
                "message": stats.get("message"),
                "detail_json": json.dumps(stats, ensure_ascii=False),
                "updated_at": updated_at,
            }
        ],
        conflict_columns=["source_name", "market", "asof_date"],
    )
