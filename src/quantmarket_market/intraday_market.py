from __future__ import annotations

import json
import math
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup

from .analytics import _clamp, format_kst, normalize_asof_kst, now_kst
from .db import upsert_many, upsert_payload
from .payloads import write_payload_file

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=5m&range=1d"
NAVER_MARKET_SUM_URL = "https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
NAVER_FUTURES_URL = "https://finance.naver.com/sise/sise_index.naver?code=FUT"
NAVER_FUTURES_POLLING_URL = "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:FUT"
NAVER_PROGRAM_TREND_URL = "https://finance.naver.com/sise/programDealTrendTime.naver?bizdate={bizdate}&sosok="
NAVER_INVESTOR_TREND_URL = "https://finance.naver.com/sise/investorDealTrendTime.naver?bizdate={bizdate}&sosok="
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
KST = timezone(timedelta(hours=9))

INDEX_SPECS = {
    "1001": {"name": "KOSPI", "yahoo_symbol": "^KS11"},
    "2001": {"name": "KOSDAQ", "yahoo_symbol": "^KQ11"},
    "1028": {"name": "KOSPI200", "yahoo_symbol": "^KS200"},
}
FX_SPECS = {
    "USDKRW": {"name": "USD/KRW", "yahoo_symbol": "KRW=X"},
}


@dataclass(frozen=True)
class IntradayRunArtifacts:
    summary: dict
    detail: dict
    manifest: dict


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def _load_latest_daily_reference(con: sqlite3.Connection, *, market: str) -> tuple[dict[str, dict], str | None]:
    latest_date_row = con.execute(
        "SELECT MAX(date) FROM market_index_daily WHERE market = ?",
        (market,),
    ).fetchone()
    latest_date = latest_date_row[0] if latest_date_row and latest_date_row[0] else None
    references: dict[str, dict] = {}
    if not latest_date:
        return references, latest_date
    rows = con.execute(
        """
        SELECT index_code, index_name, open, high, low, close, volume, source
        FROM market_index_daily
        WHERE market = ? AND date = ?
        """,
        (market, latest_date),
    ).fetchall()
    for row in rows:
        references[row[0]] = {
            "index_code": row[0],
            "index_name": row[1],
            "open": float(row[2]) if row[2] is not None else None,
            "high": float(row[3]) if row[3] is not None else None,
            "low": float(row[4]) if row[4] is not None else None,
            "close": float(row[5]) if row[5] is not None else None,
            "volume": float(row[6]) if row[6] is not None else None,
            "source": row[7],
        }
    return references, latest_date


def _load_latest_fx_reference(con: sqlite3.Connection, *, market: str) -> tuple[dict[str, dict], str | None]:
    latest_date_row = con.execute(
        "SELECT MAX(date) FROM market_fx_daily WHERE market = ?",
        (market,),
    ).fetchone()
    latest_date = latest_date_row[0] if latest_date_row and latest_date_row[0] else None
    references: dict[str, dict] = {}
    if not latest_date:
        return references, latest_date
    rows = con.execute(
        """
        SELECT series_code, series_name, close, source
        FROM market_fx_daily
        WHERE market = ? AND date = ?
        """,
        (market, latest_date),
    ).fetchall()
    for row in rows:
        references[row[0]] = {
            "series_code": row[0],
            "series_name": row[1],
            "close": float(row[2]) if row[2] is not None else None,
            "source": row[3],
        }
    return references, latest_date


def _fetch_yahoo_chart(symbol: str) -> dict:
    url = YAHOO_CHART_URL.format(symbol=quote(symbol, safe=""))
    response = requests.get(url, timeout=20, headers=REQUEST_HEADERS)
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError(f"Yahoo chart returned no result for {symbol}")
    return result[0]


def _last_non_null(values: list | None, default=None):
    if not values:
        return default
    for value in reversed(values):
        if value is not None:
            return value
    return default


def _latest_quote_from_chart(chart: dict) -> dict:
    meta = chart.get("meta") or {}
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    latest_ts = timestamps[-1] if timestamps else meta.get("regularMarketTime")
    latest_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc).astimezone(KST) if latest_ts else None
    close_value = meta.get("regularMarketPrice")
    if close_value is None:
        close_value = _last_non_null(quote.get("close"))
    open_value = meta.get("regularMarketOpen")
    if open_value is None:
        open_value = _last_non_null(quote.get("open"))
    high_value = meta.get("regularMarketDayHigh")
    if high_value is None:
        high_value = _last_non_null(quote.get("high"))
    low_value = meta.get("regularMarketDayLow")
    if low_value is None:
        low_value = _last_non_null(quote.get("low"))
    volume_value = meta.get("regularMarketVolume")
    if volume_value is None:
        volume_value = _last_non_null(quote.get("volume"), default=0.0)
    prev_close = meta.get("chartPreviousClose") if meta.get("chartPreviousClose") is not None else meta.get("previousClose")
    return {
        "price": float(close_value) if close_value is not None else None,
        "prev_close": float(prev_close) if prev_close is not None else None,
        "open": float(open_value) if open_value is not None else None,
        "high": float(high_value) if high_value is not None else None,
        "low": float(low_value) if low_value is not None else None,
        "volume": float(volume_value or 0.0),
        "latest_at": latest_dt.isoformat(timespec="seconds") if latest_dt else None,
    }


def _collect_intraday_index_rows_yahoo(*, market: str, asof: str, updated_at: str, daily_reference: dict[str, dict]) -> tuple[list[dict], bool, str]:
    rows: list[dict] = []
    try:
        for index_code, spec in INDEX_SPECS.items():
            chart = _fetch_yahoo_chart(spec["yahoo_symbol"])
            latest = _latest_quote_from_chart(chart)
            prev_close = latest.get("prev_close") or daily_reference.get(index_code, {}).get("close")
            if latest.get("price") is None:
                raise RuntimeError(f"No live price for {spec['yahoo_symbol']}")
            price = float(latest["price"])
            change_value = float(price - prev_close) if prev_close not in (None, 0) else None
            change_pct = float(price / prev_close - 1.0) if prev_close not in (None, 0) else None
            rows.append(
                {
                    "market": market,
                    "asof": asof,
                    "session_date": asof[:10],
                    "index_code": index_code,
                    "index_name": spec["name"],
                    "price": price,
                    "change_value": change_value,
                    "change_pct": change_pct,
                    "open": latest.get("open"),
                    "high": latest.get("high"),
                    "low": latest.get("low"),
                    "prev_close": prev_close,
                    "volume": latest.get("volume"),
                    "source": f"yahoo:{spec['yahoo_symbol']}",
                    "is_fallback": 0,
                    "created_at": updated_at,
                }
            )
        return rows, False, "yahoo_chart"
    except Exception as exc:
        return [], True, f"yahoo_chart_error:{type(exc).__name__}"


def _collect_intraday_fx_rows_yahoo(*, market: str, asof: str, updated_at: str, fx_reference: dict[str, dict]) -> tuple[list[dict], bool, str]:
    rows: list[dict] = []
    try:
        for series_code, spec in FX_SPECS.items():
            chart = _fetch_yahoo_chart(spec["yahoo_symbol"])
            latest = _latest_quote_from_chart(chart)
            prev_close = latest.get("prev_close") or fx_reference.get(series_code, {}).get("close")
            if latest.get("price") is None:
                raise RuntimeError(f"No live FX price for {spec['yahoo_symbol']}")
            price = float(latest["price"])
            change_value = float(price - prev_close) if prev_close not in (None, 0) else None
            change_pct = float(price / prev_close - 1.0) if prev_close not in (None, 0) else None
            rows.append(
                {
                    "market": market,
                    "asof": asof,
                    "session_date": asof[:10],
                    "series_code": series_code,
                    "series_name": spec["name"],
                    "price": price,
                    "change_value": change_value,
                    "change_pct": change_pct,
                    "open": latest.get("open"),
                    "high": latest.get("high"),
                    "low": latest.get("low"),
                    "prev_close": prev_close,
                    "source": f"yahoo:{spec['yahoo_symbol']}",
                    "is_fallback": 0,
                    "created_at": updated_at,
                }
            )
        return rows, False, "yahoo_chart"
    except Exception as exc:
        return [], True, f"yahoo_chart_error:{type(exc).__name__}"


def _collect_intraday_breadth_krx(*, market: str, asof: str, updated_at: str) -> tuple[list[dict], bool, str]:
    result_rows: list[dict] = []
    for code, name in (("1001", "KOSPI"), ("2001", "KOSDAQ")):
        try:
            df = fdr.SnapDataReader(f"KRX/INDEX/STOCK/{code}")
        except Exception as exc:
            return [], True, f"krx_breadth_error:{type(exc).__name__}"
        if df is None or df.empty:
            return [], True, "krx_breadth_empty"
        change_pct_col = _find_column(df, ["등락률", "ChagesRatio", "수익률", "변동률"])
        if not change_pct_col:
            return [], True, "krx_breadth_missing_change_pct"
        series = pd.to_numeric(df[change_pct_col], errors="coerce").dropna()
        if series.empty:
            return [], True, "krx_breadth_no_numeric"
        if series.abs().median() > 3:
            series = series / 100.0
        advancers = int((series > 0).sum())
        decliners = int((series < 0).sum())
        flat_count = int((series == 0).sum())
        total = advancers + decliners + flat_count
        result_rows.append(
            {
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "universe_code": name,
                "advancers": advancers,
                "decliners": decliners,
                "flat_count": flat_count,
                "adv_dec_ratio": float((advancers + 1) / (decliners + 1)),
                "positive_ratio": float(advancers / total) if total else 0.0,
                "source": f"fdr:KRX/INDEX/STOCK/{code}",
                "is_fallback": 0,
                "created_at": updated_at,
            }
        )
    return result_rows, False, "fdr:KRX/INDEX/STOCK"


def _fetch_html(url: str, session: requests.Session | None = None) -> str:
    requester = session.get if session is not None else requests.get
    response = requester(url, timeout=20, headers=REQUEST_HEADERS)
    response.raise_for_status()
    if not response.encoding:
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _naver_market_last_page_from_html(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    pager_link = soup.select_one("td.pgRR a") or soup.select_one("td.pgR a")
    href = pager_link.get("href", "") if pager_link else ""
    match = re.search(r"page=(\d+)", href)
    if match:
        return max(int(match.group(1)), 1)
    return 1


def _parse_naver_market_breadth_page(html: str) -> tuple[int, int, int, int]:
    soup = BeautifulSoup(html, "html.parser")
    advancers = 0
    decliners = 0
    flat_count = 0
    stock_count = 0
    for tr in soup.select("table.type_2 tr"):
        if not tr.select_one("a.tltle"):
            continue
        stock_count += 1
        icon = tr.select_one("td:nth-of-type(4) em")
        rate_span = tr.select_one("td:nth-of-type(5) span")
        classes = icon.get("class", []) if icon else []
        if "bu_pup" in classes:
            advancers += 1
        elif "bu_pdn" in classes:
            decliners += 1
        else:
            rate_text = (rate_span.get_text(" ", strip=True) if rate_span else "").replace("%", "").replace(",", "")
            try:
                rate_value = float(rate_text)
            except Exception:
                rate_value = 0.0
            if rate_value > 0:
                advancers += 1
            elif rate_value < 0:
                decliners += 1
            else:
                flat_count += 1
    return advancers, decliners, flat_count, stock_count


def _collect_intraday_breadth_naver(*, market: str, asof: str, updated_at: str) -> tuple[list[dict], bool, str]:
    result_rows: list[dict] = []
    with requests.Session() as session:
        for sosok, universe_code in ((0, "KOSPI"), (1, "KOSDAQ")):
            try:
                first_html = _fetch_html(NAVER_MARKET_SUM_URL.format(sosok=sosok, page=1), session=session)
                last_page = _naver_market_last_page_from_html(first_html)
                advancers, decliners, flat_count, stock_count = _parse_naver_market_breadth_page(first_html)

                if last_page > 1:
                    with ThreadPoolExecutor(max_workers=6) as executor:
                        futures = {
                            executor.submit(_fetch_html, NAVER_MARKET_SUM_URL.format(sosok=sosok, page=page), session): page
                            for page in range(2, last_page + 1)
                        }
                        for future in as_completed(futures):
                            page_html = future.result()
                            a, d, f, c = _parse_naver_market_breadth_page(page_html)
                            advancers += a
                            decliners += d
                            flat_count += f
                            stock_count += c

                total = advancers + decliners + flat_count
                if stock_count == 0 or total == 0:
                    return [], True, "naver_breadth_empty"
                result_rows.append(
                    {
                        "market": market,
                        "asof": asof,
                        "session_date": asof[:10],
                        "universe_code": universe_code,
                        "advancers": advancers,
                        "decliners": decliners,
                        "flat_count": flat_count,
                        "adv_dec_ratio": float((advancers + 1) / (decliners + 1)),
                        "positive_ratio": float(advancers / total),
                        "source": f"naver:sise_market_sum:{sosok}:{last_page}pages",
                        "is_fallback": 0,
                        "created_at": updated_at,
                    }
                )
            except Exception as exc:
                return [], True, f"naver_breadth_error:{type(exc).__name__}"
    return result_rows, False, "naver:sise_market_sum"


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text == "-":
        return None
    sign = -1.0 if text.startswith(("-", "▼")) else 1.0
    text = text.lstrip("+-▲▼").strip()
    if not text:
        return None
    try:
        return sign * float(text)
    except Exception:
        return None


def _signal_direction_label(value: float | None) -> str:
    if value is None:
        return "중립"
    if value > 0:
        return "순매수 우위"
    if value < 0:
        return "순매도 우위"
    return "중립"


def _signal_strength_label(value: float | None) -> str:
    magnitude = abs(value or 0.0)
    if magnitude >= 10000:
        return "강함"
    if magnitude >= 3000:
        return "보통"
    return "약함"


def _collect_intraday_futures_rows_naver(*, market: str, asof: str, updated_at: str) -> tuple[list[dict], bool, str]:
    try:
        response = requests.get(NAVER_FUTURES_POLLING_URL, timeout=20, headers=REQUEST_HEADERS)
        response.raise_for_status()
        payload = response.json()
        datas = ((((payload.get("result") or {}).get("areas") or [{}])[0]).get("datas") or [])
        if datas:
            data = datas[0]
            price = float(data["nv"]) / 100.0 if data.get("nv") is not None else None
            change_value = float(data["cv"]) / 100.0 if data.get("cv") is not None else None
            change_pct = float(data["cr"]) / 100.0 if data.get("cr") is not None else None
            open_value = float(data["ov"]) / 100.0 if data.get("ov") is not None else None
            high_value = float(data["hv"]) / 100.0 if data.get("hv") is not None else None
            low_value = float(data["lv"]) / 100.0 if data.get("lv") is not None else None
            volume = float(data["aq"]) if data.get("aq") is not None else None
            value_million = float(data["aa"]) / 1_000_000.0 if data.get("aa") is not None else None
            prev_close = price - change_value if price is not None and change_value is not None else None
            row = {
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "contract_code": "FUT",
                "contract_name": "코스피200 선물",
                "price": price,
                "change_value": change_value,
                "change_pct": change_pct,
                "open": open_value,
                "high": high_value,
                "low": low_value,
                "prev_close": prev_close,
                "volume": volume,
                "value_million": value_million,
                "source": "naver:polling:SERVICE_INDEX:FUT",
                "is_fallback": 0,
                "created_at": updated_at,
            }
            return [row], False, "naver:polling:SERVICE_INDEX:FUT"
    except Exception:
        pass
    try:
        html = _fetch_html(NAVER_FUTURES_URL)
        soup = BeautifulSoup(html, "html.parser")
        detail = soup.select_one("div.subtop_sise_detail")
        if detail is None:
            return [], True, "naver_futures_missing_detail"
        text = " ".join(detail.stripped_strings)
        match = re.search(
            r"주요시세\s+(?P<name>.+?)\s+(?P<price>[\d,]+\.\d+)\s+시가\s+(?P<open>[\d,]+\.\d+)\s+전일대비\s*(?P<mark>[▲▼+-]?)\s*(?P<change>[\d,]+\.\d+)\s+고가\s+(?P<high>[\d,]+\.\d+)\s+등락률\s+(?P<pct>[+-]?[\d,]+\.\d+)%\s+저가\s+(?P<low>[\d,]+\.\d+)\s+약정수량\s+(?P<volume>[\d,]+)\s+약정대금\(백만\)\s+(?P<value>[\d,]+)",
            text,
        )
        if not match:
            return [], True, "naver_futures_parse_error"
        price = _parse_number(match.group("price"))
        change_value = _parse_number(f"{match.group('mark')}{match.group('change')}")
        change_pct = _parse_number(match.group("pct"))
        open_value = _parse_number(match.group("open"))
        high_value = _parse_number(match.group("high"))
        low_value = _parse_number(match.group("low"))
        volume = _parse_number(match.group("volume"))
        value_million = _parse_number(match.group("value"))
        if change_pct is not None:
            change_pct = change_pct / 100.0
        prev_close = price - change_value if price is not None and change_value is not None else None
        row = {
            "market": market,
            "asof": asof,
            "session_date": asof[:10],
            "contract_code": "FUT",
            "contract_name": match.group("name").strip(),
            "price": price,
            "change_value": change_value,
            "change_pct": change_pct,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "prev_close": prev_close,
            "volume": volume,
            "value_million": value_million,
            "source": "naver:sise_index:FUT",
            "is_fallback": 0,
            "created_at": updated_at,
        }
        return [row], False, "naver:sise_index:FUT"
    except Exception as exc:
        return [], True, f"naver_futures_error:{type(exc).__name__}"


def _extract_first_data_cells(url: str, min_cells: int) -> tuple[list[str], str | None]:
    try:
        html = _fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.select("table.type_1 tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if len(cells) >= min_cells and re.match(r"\d{2}:\d{2}", cells[0] or ""):
                return cells, None
        return [], "missing_data_row"
    except Exception as exc:
        return [], f"fetch_error:{type(exc).__name__}"


def _collect_intraday_flow_signals_naver(*, market: str, asof: str, updated_at: str) -> tuple[list[dict], bool, str]:
    bizdate = asof[:10].replace("-", "")
    program_cells, program_error = _extract_first_data_cells(NAVER_PROGRAM_TREND_URL.format(bizdate=bizdate), 10)
    investor_cells, investor_error = _extract_first_data_cells(NAVER_INVESTOR_TREND_URL.format(bizdate=bizdate), 11)
    rows: list[dict] = []
    if program_cells:
        arb_net = _parse_number(program_cells[3])
        nonarb_net = _parse_number(program_cells[6])
        total_net = _parse_number(program_cells[9])
        for signal_code, signal_name, metric_value, detail in [
            ("PROGRAM_TOTAL_NET", "프로그램 전체 순매수", total_net, {"time": program_cells[0], "arb_net": arb_net, "nonarb_net": nonarb_net, "total_net": total_net}),
            ("PROGRAM_NONARB_NET", "프로그램 비차익 순매수", nonarb_net, {"time": program_cells[0], "arb_net": arb_net, "nonarb_net": nonarb_net, "total_net": total_net}),
        ]:
            rows.append({
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "signal_code": signal_code,
                "signal_name": signal_name,
                "metric_value": metric_value,
                "metric_unit": "억원",
                "direction_label": _signal_direction_label(metric_value),
                "strength_label": _signal_strength_label(metric_value),
                "source": "naver:programDealTrendTime",
                "is_fallback": 0,
                "detail_json": json.dumps(detail, ensure_ascii=False),
                "created_at": updated_at,
            })
    if investor_cells:
        foreigner_net = _parse_number(investor_cells[2])
        institution_net = _parse_number(investor_cells[3])
        individual_net = _parse_number(investor_cells[1])
        for signal_code, signal_name, metric_value, detail in [
            ("FOREIGNER_NET", "외국인 순매수", foreigner_net, {"time": investor_cells[0], "individual_net": individual_net, "foreigner_net": foreigner_net, "institution_net": institution_net}),
            ("INSTITUTION_NET", "기관계 순매수", institution_net, {"time": investor_cells[0], "individual_net": individual_net, "foreigner_net": foreigner_net, "institution_net": institution_net}),
        ]:
            rows.append({
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "signal_code": signal_code,
                "signal_name": signal_name,
                "metric_value": metric_value,
                "metric_unit": "억원",
                "direction_label": _signal_direction_label(metric_value),
                "strength_label": _signal_strength_label(metric_value),
                "source": "naver:investorDealTrendTime",
                "is_fallback": 0,
                "detail_json": json.dumps(detail, ensure_ascii=False),
                "created_at": updated_at,
            })
    if not rows:
        suffix = ";".join(part for part in [program_error, investor_error] if part) or "no_rows"
        return [], True, f"naver_flow_error:{suffix}"
    return rows, False, "naver:programDealTrendTime+investorDealTrendTime"


def _build_futures_overlay(futures_rows: list[dict], index_rows: list[dict]) -> dict | None:
    if not futures_rows:
        return None
    future = futures_rows[0]
    kospi200 = next((row for row in index_rows if row.get("index_code") == "1028"), None)
    relative_gap = None
    relative_label = "비교 데이터 부족"
    if kospi200 and future.get("change_pct") is not None and kospi200.get("change_pct") is not None:
        relative_gap = float(future["change_pct"] - kospi200["change_pct"])
        if relative_gap >= 0.002:
            relative_label = "현물 대비 선물 우위"
        elif relative_gap <= -0.002:
            relative_label = "현물 대비 선물 약세"
        else:
            relative_label = "현물과 유사"
    return {
        "contract_code": future.get("contract_code"),
        "contract_name": future.get("contract_name"),
        "change_pct": future.get("change_pct"),
        "change_value": future.get("change_value"),
        "price": future.get("price"),
        "relative_gap_pct": relative_gap,
        "relative_label": relative_label,
        "volume": future.get("volume"),
        "value_million": future.get("value_million"),
        "source": future.get("source"),
    }


def _flow_summary_overlay(flow_rows: list[dict]) -> dict | None:
    if not flow_rows:
        return None
    signal_map = {row.get("signal_code"): row for row in flow_rows}
    program = signal_map.get("PROGRAM_TOTAL_NET")
    foreigner = signal_map.get("FOREIGNER_NET")
    institution = signal_map.get("INSTITUTION_NET")
    messages: list[str] = []
    negative_count = sum(1 for row in (program, foreigner, institution) if row and (row.get("metric_value") or 0.0) < 0)
    positive_count = sum(1 for row in (program, foreigner, institution) if row and (row.get("metric_value") or 0.0) > 0)
    if negative_count >= 2:
        messages.append("프로그램과 주요 투자주체 흐름은 순매도 우위입니다.")
    elif positive_count >= 2:
        messages.append("프로그램과 주요 투자주체 흐름은 순매수 우위입니다.")
    if foreigner is not None and (foreigner.get("metric_value") or 0.0) <= -10000:
        messages.append("외국인 순매도가 큰 편이라 장중 부담 요인으로 읽힙니다.")
    elif foreigner is not None and (foreigner.get("metric_value") or 0.0) >= 10000:
        messages.append("외국인 순매수가 커서 장중 지지력으로 해석됩니다.")
    if program is not None and (program.get("metric_value") or 0.0) <= -5000:
        messages.append("프로그램 순매도 규모도 커서 지수 압박 신호가 동반됩니다.")
    elif program is not None and (program.get("metric_value") or 0.0) >= 5000:
        messages.append("프로그램 순매수 규모가 커서 지수 보강 신호가 동반됩니다.")
    return {
        "messages": messages[:2],
        "signal_codes": [row.get("signal_code") for row in flow_rows],
    }


def _fallback_intraday_index_rows(*, market: str, asof: str, updated_at: str, daily_reference: dict[str, dict], reference_date: str | None, reason: str) -> list[dict]:
    rows: list[dict] = []
    for index_code, spec in INDEX_SPECS.items():
        ref = daily_reference.get(index_code)
        if not ref or ref.get("close") is None:
            continue
        close_value = float(ref["close"])
        rows.append(
            {
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "index_code": index_code,
                "index_name": spec["name"],
                "price": close_value,
                "change_value": 0.0,
                "change_pct": 0.0,
                "open": ref.get("open"),
                "high": ref.get("high"),
                "low": ref.get("low"),
                "prev_close": close_value,
                "volume": ref.get("volume"),
                "source": f"fallback_prev_close:{reference_date}:{reason}",
                "is_fallback": 1,
                "created_at": updated_at,
            }
        )
    return rows


def _fallback_intraday_fx_rows(*, market: str, asof: str, updated_at: str, fx_reference: dict[str, dict], reference_date: str | None, reason: str) -> list[dict]:
    rows: list[dict] = []
    for series_code, spec in FX_SPECS.items():
        ref = fx_reference.get(series_code)
        if not ref or ref.get("close") is None:
            continue
        close_value = float(ref["close"])
        rows.append(
            {
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "series_code": series_code,
                "series_name": spec["name"],
                "price": close_value,
                "change_value": 0.0,
                "change_pct": 0.0,
                "open": close_value,
                "high": close_value,
                "low": close_value,
                "prev_close": close_value,
                "source": f"fallback_prev_close:{reference_date}:{reason}",
                "is_fallback": 1,
                "created_at": updated_at,
            }
        )
    return rows


def _fallback_intraday_breadth_rows(*, market: str, asof: str, updated_at: str, reference_date: str | None, reason: str) -> list[dict]:
    rows = []
    for universe_code in ("KOSPI", "KOSDAQ"):
        rows.append(
            {
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "universe_code": universe_code,
                "advancers": 0,
                "decliners": 0,
                "flat_count": 0,
                "adv_dec_ratio": 1.0,
                "positive_ratio": 0.0,
                "source": f"fallback_unavailable:{reference_date}:{reason}",
                "is_fallback": 1,
                "created_at": updated_at,
            }
        )
    return rows


def _direction_label(total_score: float) -> str:
    if total_score >= 1.0:
        return "강세"
    if total_score >= 0.2:
        return "소폭 강세"
    if total_score > -0.2:
        return "혼조"
    if total_score > -1.0:
        return "약세"
    return "강한 약세"


def _intraday_summary(*, session_status: str, direction_label: str, breadth_available: bool, risk_score: float, fx_rows: list[dict], futures_overlay: dict | None, flow_overlay: dict | None) -> str:
    if session_status == "fallback_prev_close":
        return "장중 실시간 수집이 아직 붙지 않아 전일 종가 기준 참고 스냅샷을 보여 줍니다."
    if direction_label in {"강세", "소폭 강세"}:
        base = "코스피와 코스닥이 장중 기준으로 강세 흐름을 보입니다."
    elif direction_label in {"약세", "강한 약세"}:
        base = "코스피와 코스닥이 장중 기준으로 약세 흐름을 보입니다."
    else:
        base = "코스피와 코스닥이 장중 기준으로 혼조 흐름을 보입니다."
    usdkrw = fx_rows[0] if fx_rows else None
    if usdkrw and usdkrw.get("change_pct") is not None:
        if usdkrw["change_pct"] >= 0.002:
            base += " 원달러 강세가 함께 나타나고 있습니다."
        elif usdkrw["change_pct"] <= -0.002:
            base += " 원달러는 비교적 안정된 흐름입니다."
    if futures_overlay:
        if futures_overlay.get("relative_label") == "현물 대비 선물 약세":
            base += " 선물은 코스피200보다 더 약하게 움직입니다."
        elif futures_overlay.get("relative_label") == "현물 대비 선물 우위":
            base += " 선물은 코스피200보다 상대적으로 견조합니다."
    if flow_overlay:
        for message in flow_overlay.get("messages") or []:
            base += f" {message}"
    if not breadth_available:
        base += " 다만 종목 확산 데이터는 아직 붙지 않아 지수 중심 참고만 제공합니다."
    if risk_score <= -0.8:
        base += " 장중 변동성은 경계가 필요한 수준입니다."
    return base


def collect_intraday_market_snapshot(
    con: sqlite3.Connection,
    *,
    market: str = "KR",
    asof: str | None = None,
    snapshot_dir=None,
    handoff_dir=None,
) -> IntradayRunArtifacts:
    current_dt = now_kst()
    asof = normalize_asof_kst(asof, now=current_dt)
    created_at = format_kst(current_dt)

    daily_reference, reference_date = _load_latest_daily_reference(con, market=market)
    fx_reference, fx_reference_date = _load_latest_fx_reference(con, market=market)
    index_rows, index_fallback, index_source = _collect_intraday_index_rows_yahoo(
        market=market,
        asof=asof,
        updated_at=created_at,
        daily_reference=daily_reference,
    )
    fx_rows, fx_fallback, fx_source = _collect_intraday_fx_rows_yahoo(
        market=market,
        asof=asof,
        updated_at=created_at,
        fx_reference=fx_reference,
    )
    breadth_rows, breadth_fallback, breadth_source = _collect_intraday_breadth_krx(
        market=market,
        asof=asof,
        updated_at=created_at,
    )
    if breadth_fallback:
        naver_breadth_rows, naver_breadth_fallback, naver_breadth_source = _collect_intraday_breadth_naver(
            market=market,
            asof=asof,
            updated_at=created_at,
        )
        if not naver_breadth_fallback and naver_breadth_rows:
            breadth_rows = naver_breadth_rows
            breadth_fallback = False
            breadth_source = naver_breadth_source
        else:
            breadth_source = f"{breadth_source};fallback2={naver_breadth_source}"

    futures_rows, futures_fallback, futures_source = _collect_intraday_futures_rows_naver(
        market=market,
        asof=asof,
        updated_at=created_at,
    )
    flow_rows, flow_fallback, flow_source = _collect_intraday_flow_signals_naver(
        market=market,
        asof=asof,
        updated_at=created_at,
    )

    if not index_rows:
        index_rows = _fallback_intraday_index_rows(
            market=market,
            asof=asof,
            updated_at=created_at,
            daily_reference=daily_reference,
            reference_date=reference_date,
            reason=index_source,
        )
        index_fallback = True
    if not fx_rows:
        fx_rows = _fallback_intraday_fx_rows(
            market=market,
            asof=asof,
            updated_at=created_at,
            fx_reference=fx_reference,
            reference_date=fx_reference_date,
            reason=fx_source,
        )
        fx_fallback = True
    if not breadth_rows:
        breadth_rows = _fallback_intraday_breadth_rows(
            market=market,
            asof=asof,
            updated_at=created_at,
            reference_date=reference_date,
            reason=breadth_source,
        )
        breadth_fallback = True

    upsert_many(
        con,
        table="market_intraday_index_snapshot",
        columns=[
            "market", "asof", "session_date", "index_code", "index_name", "price", "change_value", "change_pct",
            "open", "high", "low", "prev_close", "volume", "source", "is_fallback", "created_at",
        ],
        rows=index_rows,
        conflict_columns=["market", "asof", "index_code"],
    )
    upsert_many(
        con,
        table="market_intraday_fx_snapshot",
        columns=[
            "market", "asof", "session_date", "series_code", "series_name", "price", "change_value", "change_pct",
            "open", "high", "low", "prev_close", "source", "is_fallback", "created_at",
        ],
        rows=fx_rows,
        conflict_columns=["market", "asof", "series_code"],
    )
    upsert_many(
        con,
        table="market_intraday_breadth",
        columns=[
            "market", "asof", "session_date", "universe_code", "advancers", "decliners", "flat_count", "adv_dec_ratio",
            "positive_ratio", "source", "is_fallback", "created_at",
        ],
        rows=breadth_rows,
        conflict_columns=["market", "asof", "universe_code"],
    )
    if futures_rows:
        upsert_many(
            con,
            table="market_intraday_futures_snapshot",
            columns=[
                "market", "asof", "session_date", "contract_code", "contract_name", "price", "change_value", "change_pct",
                "open", "high", "low", "prev_close", "volume", "value_million", "source", "is_fallback", "created_at",
            ],
            rows=futures_rows,
            conflict_columns=["market", "asof", "contract_code"],
        )
    if flow_rows:
        upsert_many(
            con,
            table="market_intraday_flow_signal",
            columns=[
                "market", "asof", "session_date", "signal_code", "signal_name", "metric_value", "metric_unit", "direction_label",
                "strength_label", "source", "is_fallback", "detail_json", "created_at",
            ],
            rows=flow_rows,
            conflict_columns=["market", "asof", "signal_code"],
        )

    tracked = [row for row in index_rows if row.get("index_code") in {"1001", "2001", "1028"}]
    avg_change_pct = sum((row.get("change_pct") or 0.0) for row in tracked) / max(len(tracked), 1)
    breadth_available = not breadth_fallback
    breadth_avg = sum((row.get("positive_ratio") or 0.5) for row in breadth_rows) / max(len(breadth_rows), 1)
    range_positions = []
    for row in tracked:
        high = row.get("high")
        low = row.get("low")
        price = row.get("price")
        if None in (high, low, price) or high == low:
            continue
        range_positions.append(float((price - low) / (high - low)))
    avg_range_position = sum(range_positions) / len(range_positions) if range_positions else 0.5
    usdkrw_change_pct = (fx_rows[0].get("change_pct") or 0.0) if fx_rows else 0.0

    direction_score = _clamp(avg_change_pct * 120.0)
    breadth_signal = (breadth_avg - 0.5) * 6.0 + math.log(max(sum((row.get("adv_dec_ratio") or 1.0) for row in breadth_rows) / max(len(breadth_rows), 1), 1e-6)) * 0.8
    breadth_score = _clamp(breadth_signal) if breadth_available else 0.0
    risk_score = _clamp((avg_range_position - 0.5) * 4.0 - abs(avg_change_pct) * 35.0 - (usdkrw_change_pct * 30.0))
    total_score = _clamp(direction_score * 0.55 + breadth_score * 0.20 + risk_score * 0.25)

    if index_fallback:
        session_status = "fallback_prev_close"
        direction_score = 0.0
        breadth_score = 0.0
        risk_score = 0.0
        total_score = 0.0
        direction_label = "전일 기준 참고"
    elif breadth_fallback:
        session_status = "live_indexes_only"
        direction_label = _direction_label(total_score)
    else:
        session_status = "live"
        direction_label = _direction_label(total_score)

    futures_overlay = _build_futures_overlay(futures_rows, tracked)
    flow_overlay = _flow_summary_overlay(flow_rows)
    summary_line = _intraday_summary(
        session_status=session_status,
        direction_label=direction_label,
        breadth_available=breadth_available,
        risk_score=risk_score,
        fx_rows=fx_rows,
        futures_overlay=futures_overlay,
        flow_overlay=flow_overlay,
    )
    state_row = {
        "market": market,
        "asof": asof,
        "session_date": asof[:10],
        "session_status": session_status,
        "direction_label": direction_label,
        "direction_score": round(direction_score, 4),
        "breadth_score": round(breadth_score, 4),
        "risk_score": round(risk_score, 4),
        "total_score": round(total_score, 4),
        "summary_line": summary_line,
        "reference_close_date": reference_date,
        "source": f"index={index_source};fx={fx_source};breadth={breadth_source};futures={futures_source};flow={flow_source}",
        "created_at": created_at,
    }
    upsert_many(
        con,
        table="market_intraday_state",
        columns=list(state_row.keys()),
        rows=[state_row],
        conflict_columns=["market", "asof"],
    )

    summary = {
        "market": market,
        "asof": asof,
        "session_status": session_status,
        "reference_close_date": reference_date,
        "direction_label": direction_label,
        "total_score": round(total_score, 4),
        "summary_line": summary_line,
        "indexes": [
            {
                "index_code": row["index_code"],
                "index_name": row["index_name"],
                "price": row["price"],
                "change_pct": row.get("change_pct"),
                "change_value": row.get("change_value"),
                "is_fallback": bool(row.get("is_fallback")),
            }
            for row in tracked
        ],
        "fx": [
            {
                "series_code": row["series_code"],
                "series_name": row["series_name"],
                "price": row["price"],
                "change_pct": row.get("change_pct"),
                "change_value": row.get("change_value"),
                "is_fallback": bool(row.get("is_fallback")),
            }
            for row in fx_rows
        ],
        "futures": [
            {
                "contract_code": row["contract_code"],
                "contract_name": row["contract_name"],
                "price": row["price"],
                "change_pct": row.get("change_pct"),
                "change_value": row.get("change_value"),
                "volume": row.get("volume"),
                "value_million": row.get("value_million"),
                "is_fallback": bool(row.get("is_fallback")),
            }
            for row in futures_rows
        ],
        "flow_signals": [
            {
                "signal_code": row["signal_code"],
                "signal_name": row["signal_name"],
                "metric_value": row.get("metric_value"),
                "metric_unit": row.get("metric_unit"),
                "direction_label": row.get("direction_label"),
                "strength_label": row.get("strength_label"),
                "is_fallback": bool(row.get("is_fallback")),
            }
            for row in flow_rows
        ],
        "signal_overlay": {
            "futures_overlay": futures_overlay,
            "flow_overlay": flow_overlay,
        },
    }
    detail = {
        "market": market,
        "asof": asof,
        "session_status": session_status,
        "reference_close_date": reference_date,
        "state": state_row,
        "indexes": index_rows,
        "fx": fx_rows,
        "futures": futures_rows,
        "breadth": breadth_rows,
        "flow_signals": [
            {**row, "detail": json.loads(row["detail_json"])}
            for row in flow_rows
        ],
        "signal_overlay": {
            "futures_overlay": futures_overlay,
            "flow_overlay": flow_overlay,
            "futures_source": futures_source,
            "flow_source": flow_source,
            "futures_available": not futures_fallback and bool(futures_rows),
            "flow_available": not flow_fallback and bool(flow_rows),
        },
        "description": "장중 참고용 현재 지표 스냅샷입니다. 정식 시장상태를 대체하지 않고 당일 흐름을 보조 설명하는 용도입니다.",
        "notice": "장중 수치는 실시간 또는 지연 시세 기준이며, 종가 확정 전 참고 정보입니다.",
    }
    manifest = {
        "market": market,
        "asof": asof,
        "visibility": "admin_only_pre_publish",
        "title": "QuantMarket intraday snapshot manifest",
        "files": {
            "summary": "admin_market_intraday_summary.json",
            "detail": "admin_market_intraday_detail.json",
            "manifest": "admin_market_intraday_manifest.json",
        },
        "note": "장중 참고용 현재 지표이며 공개 반영 전까지 admin 검토용으로만 사용합니다.",
    }

    upsert_payload(con, market=market, asof=asof, payload_type="admin_intraday_summary", payload=summary, created_at=created_at)
    upsert_payload(con, market=market, asof=asof, payload_type="admin_intraday_detail", payload=detail, created_at=created_at)
    upsert_payload(con, market=market, asof=asof, payload_type="admin_intraday_manifest", payload=manifest, created_at=created_at)

    if snapshot_dir:
        write_payload_file(snapshot_dir / "admin_market_intraday_summary.json", summary)
        write_payload_file(snapshot_dir / "admin_market_intraday_detail.json", detail)
        write_payload_file(snapshot_dir / "admin_market_intraday_manifest.json", manifest)
    if handoff_dir:
        write_payload_file(handoff_dir / "admin_market_intraday_summary.json", summary)
        write_payload_file(handoff_dir / "admin_market_intraday_detail.json", detail)
        write_payload_file(handoff_dir / "admin_market_intraday_manifest.json", manifest)

    return IntradayRunArtifacts(summary=summary, detail=detail, manifest=manifest)
