from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .db import upsert_many

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
REQUEST_HEADERS = {"User-Agent": "QuantMarket/1.0"}

CATEGORY_RULES = [
    ("risk", "리스크 공시", ("관리종목", "상장폐지", "영업정지", "횡령", "배임", "회생절차", "파산", "감사의견", "소송", "부도", "거래정지", "실질심사", "상장적격성", "이의신청")),
    ("funding", "자금조달", ("유상증자", "무상증자", "전환사채", "신주인수권부사채", "교환사채", "사채", "증권신고서", "유무상증자")),
    ("shareholder", "지분/자사주", ("자기주식", "주식등의대량보유", "임원ㆍ주요주주", "최대주주", "주요주주", "소유상황보고")),
    ("earnings", "실적/정기보고", ("잠정실적", "매출액또는손익구조", "사업보고서", "반기보고서", "분기보고서", "감사보고서")),
    ("governance", "지배구조/의사결정", ("합병", "분할", "주주총회", "영업양수", "영업양도", "타법인주식", "해산")),
]


def _today_kst(asof: str) -> date:
    return datetime.fromisoformat(asof.replace("Z", "+00:00")).date()


def _get_dart_api_key() -> str | None:
    for env_name in ("DART_API_KEY", "OPENDART_API_KEY"):
        value = (os.getenv(env_name) or "").strip()
        if value:
            return value
    return None


def _request_json(params: dict[str, Any]) -> dict[str, Any]:
    url = f"{DART_LIST_URL}?{urlencode(params)}"
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def _fetch_disclosures(*, api_key: str, corp_cls: str, bgn_de: str, end_de: str, page_count: int = 100) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    page_no = 1
    total_page = 1
    while page_no <= total_page:
        payload = _request_json(
            {
                "crtfc_key": api_key,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "last_reprt_at": "Y",
                "corp_cls": corp_cls,
                "sort": "date",
                "sort_mth": "desc",
                "page_no": page_no,
                "page_count": page_count,
            }
        )
        status = str(payload.get("status") or "")
        if status == "013":
            return results
        if status != "000":
            raise RuntimeError(f"dart_api_status:{status}:{payload.get('message')}")
        total_page = int(payload.get("total_page") or 1)
        results.extend(payload.get("list") or [])
        page_no += 1
    return results


def _classify_report(report_nm: str) -> tuple[str, str, int, str]:
    text = (report_nm or "").strip()
    if "거래정지해제" in text or "매매거래정지해제" in text:
        return "general", "일반 공시", 0, "normal"
    for key, label, keywords in CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            if key == "risk":
                return key, label, 1, "high"
            if key == "funding":
                return key, label, 0, "medium"
            if key == "shareholder":
                return key, label, 0, "medium"
            return key, label, 0, "normal"
    return "general", "일반 공시", 0, "normal"


def _normalize_disclosure(row: dict[str, Any], *, market: str, asof: str, reference_date: str, created_at: str) -> dict[str, Any]:
    category_key, category_label, risk_flag, severity_label = _classify_report(row.get("report_nm") or "")
    rcept_no = str(row.get("rcept_no") or "").strip()
    return {
        "market": market,
        "asof": asof,
        "reference_date": reference_date,
        "rcept_no": rcept_no,
        "corp_cls": row.get("corp_cls"),
        "corp_code": row.get("corp_code"),
        "corp_name": row.get("corp_name"),
        "stock_code": row.get("stock_code"),
        "report_nm": row.get("report_nm") or "",
        "flr_nm": row.get("flr_nm"),
        "rcept_dt": row.get("rcept_dt") or reference_date,
        "rm": row.get("rm"),
        "category_key": category_key,
        "category_label": category_label,
        "risk_flag": int(risk_flag),
        "severity_label": severity_label,
        "source": "opendart:list.json",
        "viewer_url": DART_VIEWER_URL.format(rcept_no=rcept_no),
        "created_at": created_at,
    }


def _build_summary_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    type_counts: dict[str, int] = {}
    highlights: list[dict[str, Any]] = []
    recent_filings: list[dict[str, Any]] = []
    for row in rows:
        label = row["category_label"]
        type_counts[label] = type_counts.get(label, 0) + 1
        filing = {
            "corp_name": row.get("corp_name"),
            "stock_code": row.get("stock_code"),
            "report_nm": row.get("report_nm"),
            "category_label": row.get("category_label"),
            "severity_label": row.get("severity_label"),
            "viewer_url": row.get("viewer_url"),
            "rcept_no": row.get("rcept_no"),
            "rcept_dt": row.get("rcept_dt"),
            "corp_cls": row.get("corp_cls"),
        }
        recent_filings.append(filing)
        if row.get("risk_flag") or row.get("severity_label") in {"high", "medium"}:
            highlights.append(filing)
    filing_count_by_type = [
        {"category_label": label, "count": count}
        for label, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    highlights = sorted(
        highlights,
        key=lambda item: (0 if item.get("severity_label") == "high" else 1, item.get("corp_name") or ""),
    )[:10]
    return filing_count_by_type, highlights, recent_filings[:20]


def _disabled_summary(*, market: str, asof: str, created_at: str, reason: str, source: str) -> dict[str, Any]:
    return {
        "market": market,
        "asof": asof,
        "reference_date": None,
        "enabled": 0,
        "status_label": "준비 중",
        "availability_reason": reason,
        "filing_count_total": 0,
        "kospi_count": 0,
        "kosdaq_count": 0,
        "risk_event_count": 0,
        "filing_count_by_type_json": "[]",
        "highlights_json": "[]",
        "recent_filings_json": "[]",
        "source": source,
        "created_at": created_at,
    }


def _latest_stored_summary(con, *, market: str, asof: str) -> dict[str, Any] | None:
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
    return dict(row) if row else None


def collect_market_dart_summary(con, *, market: str, asof: str, created_at: str) -> dict[str, Any]:
    if market != "KR":
        return _disabled_summary(
            market=market,
            asof=asof,
            created_at=created_at,
            reason="DART 공시는 현재 KR 시장만 지원합니다.",
            source="opendart:unsupported_market",
        )

    api_key = _get_dart_api_key()
    if not api_key:
        cached = _latest_stored_summary(con, market=market, asof=asof)
        return cached or _disabled_summary(
            market=market,
            asof=asof,
            created_at=created_at,
            reason="DART_API_KEY가 설정되지 않았습니다.",
            source="opendart:missing_key",
        )

    end_date = _today_kst(asof)
    begin_date = end_date - timedelta(days=2)
    bgn_de = begin_date.strftime("%Y%m%d")
    end_de = end_date.strftime("%Y%m%d")
    try:
        raw_rows: list[dict[str, Any]] = []
        for corp_cls in ("Y", "K"):
            raw_rows.extend(
                _fetch_disclosures(
                    api_key=api_key,
                    corp_cls=corp_cls,
                    bgn_de=bgn_de,
                    end_de=end_de,
                )
            )
    except Exception as exc:
        cached = _latest_stored_summary(con, market=market, asof=asof)
        return cached or _disabled_summary(
            market=market,
            asof=asof,
            created_at=created_at,
            reason=f"OpenDART 호출 실패: {type(exc).__name__}",
            source=f"opendart:error:{type(exc).__name__}",
        )

    if not raw_rows:
        summary_row = _disabled_summary(
            market=market,
            asof=asof,
            created_at=created_at,
            reason="최근 3일 범위에서 조회된 공시가 없습니다.",
            source="opendart:no_rows",
        )
        upsert_many(
            con,
            table="market_dart_summary_state",
            columns=list(summary_row.keys()),
            rows=[summary_row],
            conflict_columns=["market", "asof"],
        )
        return summary_row

    reference_date = max(str(row.get("rcept_dt") or "") for row in raw_rows)
    filtered = [
        _normalize_disclosure(
            row,
            market=market,
            asof=asof,
            reference_date=reference_date,
            created_at=created_at,
        )
        for row in raw_rows
        if str(row.get("rcept_dt") or "") == reference_date
    ]
    filing_count_by_type, highlights, recent_filings = _build_summary_rows(filtered)
    summary_row = {
        "market": market,
        "asof": asof,
        "reference_date": reference_date,
        "enabled": 1,
        "status_label": "정상",
        "availability_reason": None,
        "filing_count_total": len(filtered),
        "kospi_count": sum(1 for row in filtered if row.get("corp_cls") == "Y"),
        "kosdaq_count": sum(1 for row in filtered if row.get("corp_cls") == "K"),
        "risk_event_count": sum(int(row.get("risk_flag") or 0) for row in filtered),
        "filing_count_by_type_json": json.dumps(filing_count_by_type, ensure_ascii=False),
        "highlights_json": json.dumps(highlights, ensure_ascii=False),
        "recent_filings_json": json.dumps(recent_filings, ensure_ascii=False),
        "source": "opendart:list.json",
        "created_at": created_at,
    }
    upsert_many(
        con,
        table="market_dart_disclosure_event",
        columns=[
            "market",
            "asof",
            "reference_date",
            "rcept_no",
            "corp_cls",
            "corp_code",
            "corp_name",
            "stock_code",
            "report_nm",
            "flr_nm",
            "rcept_dt",
            "rm",
            "category_key",
            "category_label",
            "risk_flag",
            "severity_label",
            "source",
            "viewer_url",
            "created_at",
        ],
        rows=filtered,
        conflict_columns=["market", "asof", "rcept_no"],
    )
    upsert_many(
        con,
        table="market_dart_summary_state",
        columns=list(summary_row.keys()),
        rows=[summary_row],
        conflict_columns=["market", "asof"],
    )
    return summary_row
