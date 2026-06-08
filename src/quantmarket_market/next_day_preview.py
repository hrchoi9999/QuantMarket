from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .analytics import _clamp, format_kst, normalize_asof_kst, now_kst
from .config import NEXT_DAY_PREVIEW_SNAPSHOT_ROOT
from .db import upsert_many, upsert_payload
from .intraday_market import _fetch_yahoo_chart, _latest_quote_from_chart
from .kiwoom_rest import collect_korea_night_futures_proxy
from .payloads import NOTICE_BLOCK, _compliance_meta, build_api_response, write_payload_file

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
REQUEST_HEADERS = {"User-Agent": "QuantMarket/1.0"}

OVERNIGHT_ASSET_SPECS = [
    {
        "asset_code": "KOREA_PROXY_EWY",
        "asset_name": "미국 상장 한국 ETF",
        "asset_group": "korea_proxy",
        "symbol": "EWY",
        "weight": 0.40,
    },
    {
        "asset_code": "SP500_FUT",
        "asset_name": "S&P500 선물",
        "asset_group": "us_futures",
        "symbol": "ES=F",
        "weight": 0.30,
    },
    {
        "asset_code": "NASDAQ100_FUT",
        "asset_name": "나스닥100 선물",
        "asset_group": "us_futures",
        "symbol": "NQ=F",
        "weight": 0.30,
    },
    {
        "asset_code": "USDKRW",
        "asset_name": "USD/KRW",
        "asset_group": "fx",
        "symbol": "KRW=X",
        "weight": 1.00,
    },
    {
        "asset_code": "WTI",
        "asset_name": "WTI 원유",
        "asset_group": "commodity",
        "symbol": "CL=F",
        "weight": 1.00,
    },
    {
        "asset_code": "US10Y",
        "asset_name": "미국 10년 금리",
        "asset_group": "rates",
        "symbol": "^TNX",
        "weight": 1.00,
    },
]

OVERNIGHT_NEWS_QUERIES = {
    "KR": [
        "나스닥 선물 S&P500 선물 달러 유가 미국 금리 한국 증시 전망",
        "미국 증시 선물 유가 미국국채 금리 환율 한국 증시",
        "중동 전쟁 유가 달러 미국 선물 한국 증시 전망",
    ],
    "US": [
        "S&P500 futures Nasdaq futures oil treasury yields overnight risk",
    ],
}

RISK_KEYWORDS = [
    "전쟁",
    "중동",
    "이란",
    "이스라엘",
    "공습",
    "미사일",
    "유가",
    "금리",
    "달러",
    "war",
    "oil",
    "yield",
    "risk",
]


def _collect_kiwoom_korea_night_futures_asset(*, market: str, asof: str, created_at: str) -> dict:
    asset_base = {
        "market": market,
        "asof": asof,
        "session_date": asof[:10],
        "asset_code": "KOSPI200_NIGHT_FUT",
        "asset_name": "국내 야간선물(Kiwoom REST)",
        "asset_group": "korea_futures",
        "created_at": created_at,
    }
    try:
        quote = collect_korea_night_futures_proxy()
        if quote.get("price") is None:
            raise RuntimeError("missing_kiwoom_futures_price")
        return {
            **asset_base,
            "price": quote.get("price"),
            "change_value": quote.get("change_value"),
            "change_pct": quote.get("change_pct"),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "prev_close": quote.get("prev_close"),
            "source": quote.get("source") or "kiwoom_rest",
            "is_fallback": 0,
        }
    except Exception as exc:
        return {
            **asset_base,
            "price": None,
            "change_value": None,
            "change_pct": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "source": f"kiwoom_rest_fallback_error:{type(exc).__name__}",
            "is_fallback": 1,
        }


def _is_preview_window(dt: datetime) -> bool:
    current = dt.timetz().replace(tzinfo=None)
    return current >= time(18, 0) or current <= time(8, 30)



def _next_business_day(value: date) -> date:
    current = value + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current



def _resolve_reference_session(dt: datetime) -> str:
    current = dt.timetz().replace(tzinfo=None)
    current_date = dt.date()
    if current <= time(8, 30):
        if current_date.weekday() >= 5:
            return _next_business_day(current_date).isoformat()
        return current_date.isoformat()
    if current >= time(18, 0):
        return _next_business_day(current_date).isoformat()
    return _next_business_day(current_date).isoformat()



def _safe_round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)



def _fetch_rss_titles(query: str, limit: int = 4) -> tuple[list[str], str]:
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=20) as response:
        xml_bytes = response.read()
    root = ElementTree.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        return [], url
    titles: list[str] = []
    for item in channel.findall("item"):
        title_text = (item.findtext("title") or "").strip()
        if not title_text:
            continue
        title_text = title_text.replace(" - Google 뉴스", "").strip()
        if title_text not in titles:
            titles.append(title_text)
        if len(titles) >= limit:
            break
    return titles, url



def _collect_news_context(*, market: str, asof: str, created_at: str) -> dict:
    headlines: list[str] = []
    source_urls: list[str] = []
    for query in OVERNIGHT_NEWS_QUERIES.get(market, OVERNIGHT_NEWS_QUERIES["KR"]):
        try:
            titles, url = _fetch_rss_titles(query)
        except Exception:
            continue
        source_urls.append(url)
        for title in titles:
            if title not in headlines:
                headlines.append(title)
    risk_headlines = [
        title for title in headlines
        if any(keyword.lower() in title.lower() for keyword in RISK_KEYWORDS)
    ]
    return {
        "market": market,
        "asof": asof,
        "session_date": asof[:10],
        "headline_count": len(headlines),
        "risk_headline_count": len(risk_headlines),
        "caution_bias": bool(risk_headlines),
        "headlines": headlines[:8],
        "risk_headlines": risk_headlines[:5],
        "source_urls": source_urls,
        "created_at": created_at,
    }



def _collect_overnight_assets(*, market: str, asof: str, created_at: str) -> list[dict]:
    rows: list[dict] = [
        _collect_kiwoom_korea_night_futures_asset(market=market, asof=asof, created_at=created_at)
    ]
    for spec in OVERNIGHT_ASSET_SPECS:
        try:
            chart = _fetch_yahoo_chart(spec["symbol"])
            latest = _latest_quote_from_chart(chart)
            price = latest.get("price")
            prev_close = latest.get("prev_close")
            if price is None:
                raise RuntimeError("missing_price")
            change_value = price - prev_close if prev_close not in (None, 0) else None
            change_pct = (price / prev_close - 1.0) if prev_close not in (None, 0) else None
            rows.append(
                {
                    "market": market,
                    "asof": asof,
                    "session_date": asof[:10],
                    "asset_code": spec["asset_code"],
                    "asset_name": spec["asset_name"],
                    "asset_group": spec["asset_group"],
                    "price": float(price),
                    "change_value": float(change_value) if change_value is not None else None,
                    "change_pct": float(change_pct) if change_pct is not None else None,
                    "open": latest.get("open"),
                    "high": latest.get("high"),
                    "low": latest.get("low"),
                    "prev_close": float(prev_close) if prev_close is not None else None,
                    "source": f"yahoo:{spec['symbol']}",
                    "is_fallback": 0,
                    "created_at": created_at,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "market": market,
                    "asof": asof,
                    "session_date": asof[:10],
                    "asset_code": spec["asset_code"],
                    "asset_name": spec["asset_name"],
                    "asset_group": spec["asset_group"],
                    "price": None,
                    "change_value": None,
                    "change_pct": None,
                    "open": None,
                    "high": None,
                    "low": None,
                    "prev_close": None,
                    "source": f"fallback_error:{type(exc).__name__}:{spec['symbol']}",
                    "is_fallback": 1,
                    "created_at": created_at,
                }
            )
    return rows



def _asset_map(asset_rows: list[dict]) -> dict[str, dict]:
    return {row["asset_code"]: row for row in asset_rows}



def _weighted_average(values: list[tuple[float | None, float]]) -> float:
    active = [(value, weight) for value, weight in values if value is not None]
    if not active:
        return 0.0
    total_weight = sum(weight for _, weight in active) or 1.0
    return sum(value * weight for value, weight in active) / total_weight



def _sign(value: float | None) -> int:
    if value is None:
        return 0
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0



def _compute_biases(asset_rows: list[dict], news_context: dict) -> dict:
    assets = _asset_map(asset_rows)
    kr_fut = assets.get("KOSPI200_NIGHT_FUT", {}).get("change_pct")
    ewy = assets.get("KOREA_PROXY_EWY", {}).get("change_pct")
    es = assets.get("SP500_FUT", {}).get("change_pct")
    nq = assets.get("NASDAQ100_FUT", {}).get("change_pct")
    usdkrw = assets.get("USDKRW", {}).get("change_pct")
    wti = assets.get("WTI", {}).get("change_pct")
    us10y = assets.get("US10Y", {}).get("change_pct")
    overnight_futures_bias = _clamp(_weighted_average([
        (kr_fut * 10.0 if kr_fut is not None else None, 0.40),
        (ewy * 10.0 if ewy is not None else None, 0.20),
        (es * 10.0 if es is not None else None, 0.20),
        (nq * 10.0 if nq is not None else None, 0.20),
    ]))
    oil_penalty = max((wti or 0.0) * 5.0, 0.0)
    yield_penalty = max((us10y or 0.0) * 4.0, 0.0)
    news_penalty = min(float(news_context.get("risk_headline_count", 0)) * 0.25, 1.0)
    global_risk_bias = _clamp(
        _weighted_average([
            (es * 8.0 if es is not None else None, 0.45),
            (nq * 8.0 if nq is not None else None, 0.45),
            ((-1.0 * (wti or 0.0) * 3.0), 0.10),
        ])
        - oil_penalty
        - yield_penalty
        - news_penalty
    )
    overnight_fx_bias = _clamp((-1.0 * (usdkrw or 0.0)) * 12.0)
    next_day_preview_score = _clamp(
        overnight_futures_bias * 0.45
        + global_risk_bias * 0.35
        + overnight_fx_bias * 0.20
    )
    if kr_fut is None and ewy is None:
        korea_signal_alignment = "unavailable"
    elif kr_fut is None or ewy is None:
        korea_signal_alignment = "single_source"
    elif _sign(kr_fut) == _sign(ewy):
        korea_signal_alignment = "aligned"
    else:
        korea_signal_alignment = "mixed"
    return {
        "overnight_futures_bias": round(float(overnight_futures_bias), 4),
        "korea_signal_alignment": korea_signal_alignment,
        "global_risk_bias": round(float(global_risk_bias), 4),
        "overnight_fx_bias": round(float(overnight_fx_bias), 4),
        "next_day_preview_score": round(float(next_day_preview_score), 4),
    }



def _preview_label(score: float) -> str:
    if score >= 1.2:
        return "장초반 우호 가능성"
    if score >= 0.4:
        return "장초반 우호 흐름"
    if score <= -1.2:
        return "장초반 부담 가능성"
    if score <= -0.4:
        return "장초반 경계 흐름"
    return "혼조 출발 가능성"



def _asset_brief_line(asset: dict | None, positive: str, negative: str, neutral: str) -> tuple[str | None, bool | None]:
    if not asset:
        return None, None
    change_pct = asset.get("change_pct")
    if change_pct is None:
        return None, None
    if change_pct >= 0.003:
        return positive.format(change=round(change_pct * 100.0, 2)), True
    if change_pct <= -0.003:
        return negative.format(change=round(change_pct * 100.0, 2)), False
    return neutral.format(change=round(change_pct * 100.0, 2)), None



def _supporting_and_risk_points(asset_rows: list[dict], news_context: dict, preview_label: str) -> tuple[list[str], list[str]]:
    assets = _asset_map(asset_rows)
    supporting: list[str] = []
    risks: list[str] = []
    kr_fut = assets.get("KOSPI200_NIGHT_FUT", {}).get("change_pct")
    ewy = assets.get("KOREA_PROXY_EWY", {}).get("change_pct")
    if kr_fut is not None and ewy is not None and _sign(kr_fut) != 0 and _sign(kr_fut) != _sign(ewy):
        risks.append(
            "국내 야간선물과 EWY 프록시 방향이 엇갈려, 내일 장초반은 방향성보다 변동성 확인이 우선입니다."
        )

    def add_point(asset_code: str, *, up_line: str, down_line: str, flat_line: str, up_supports: bool, down_supports: bool) -> None:
        asset = assets.get(asset_code)
        if not asset:
            return
        change_pct = asset.get("change_pct")
        if change_pct is None:
            return
        change = round(change_pct * 100.0, 2)
        if change_pct >= 0.003:
            line = up_line.format(change=change)
            (supporting if up_supports else risks).append(line)
            return
        if change_pct <= -0.003:
            line = down_line.format(change=change)
            (supporting if down_supports else risks).append(line)
            return
        line = flat_line.format(change=change)
        if preview_label.startswith("장초반 경계") or preview_label.startswith("장초반 부담"):
            risks.append(line)
        else:
            supporting.append(line)

    add_point(
        "SP500_FUT",
        up_line="S&P500 선물이 {change}% 올라 글로벌 위험자산 흐름이 비교적 우호적입니다.",
        down_line="S&P500 선물이 {change}% 내려 글로벌 위험자산 흐름이 부담으로 읽힙니다.",
        flat_line="S&P500 선물 흐름은 {change}% 수준으로 방향성이 크지 않습니다.",
        up_supports=True,
        down_supports=False,
    )
    add_point(
        "NASDAQ100_FUT",
        up_line="나스닥100 선물이 {change}% 올라 기술주 선호 흐름이 이어집니다.",
        down_line="나스닥100 선물이 {change}% 내려 성장주 심리가 다소 위축된 모습입니다.",
        flat_line="나스닥100 선물은 {change}% 수준으로 혼조 흐름입니다.",
        up_supports=True,
        down_supports=False,
    )
    add_point(
        "KOSPI200_NIGHT_FUT",
        up_line="Kiwoom 국내 야간선물이 {change}% 올라 내일 장초반 국내지수 출발 여건이 비교적 우호적입니다.",
        down_line="Kiwoom 국내 야간선물이 {change}% 내려 내일 장초반 국내지수 부담 신호가 먼저 확인됩니다.",
        flat_line="Kiwoom 국내 야간선물은 {change}% 수준으로 뚜렷한 방향성은 아직 제한적입니다.",
        up_supports=True,
        down_supports=False,
    )
    add_point(
        "KOREA_PROXY_EWY",
        up_line="미국 상장 한국 ETF가 {change}% 올라 해외 시장에서도 한국 자산 선호가 비교적 우호적입니다.",
        down_line="미국 상장 한국 ETF가 {change}% 내려 해외 시장에서 보는 한국 자산 심리는 다소 부담스럽습니다.",
        flat_line="미국 상장 한국 ETF는 {change}% 수준으로 방향성이 제한적입니다.",
        up_supports=True,
        down_supports=False,
    )
    add_point(
        "USDKRW",
        up_line="달러가 {change}% 올라 원화 약세 부담이 이어지고 있습니다.",
        down_line="달러가 {change}% 내려 환율 부담은 다소 완화된 모습입니다.",
        flat_line="달러 흐름은 {change}% 수준으로 환율 부담이 크지 않습니다.",
        up_supports=False,
        down_supports=True,
    )
    add_point(
        "WTI",
        up_line="WTI가 {change}% 올라 에너지 가격 변수 부담이 커졌습니다.",
        down_line="WTI가 {change}% 내려 유가 부담은 다소 완화된 모습입니다.",
        flat_line="WTI는 {change}% 수준으로 유가 방향이 제한적입니다.",
        up_supports=False,
        down_supports=True,
    )
    add_point(
        "US10Y",
        up_line="미국 10년 금리가 {change}% 올라 금리 부담을 덜어보긴 어렵습니다.",
        down_line="미국 10년 금리가 {change}% 내려 금리 부담은 다소 완화됐습니다.",
        flat_line="미국 10년 금리는 {change}% 수준으로 큰 방향성은 없습니다.",
        up_supports=False,
        down_supports=True,
    )

    for headline in news_context.get("risk_headlines") or []:
        risks.append(f"주요 뉴스에서는 '{headline}' 이슈가 함께 거론되고 있습니다.")
    supporting = supporting[:3]
    risks = risks[:3]
    if not supporting:
        supporting = ["야간 자산 움직임은 대체로 혼조권에 머물러 한쪽 방향을 강하게 시사하진 않습니다."]
    if not risks:
        risks = ["추가적인 야간 부담 신호는 제한적이지만 장초반 변동성 가능성은 열어둘 필요가 있습니다."]
    return supporting, risks



def _headline_and_summary(preview_label: str, biases: dict, market_flow_label: str) -> tuple[str, str]:
    score = biases["next_day_preview_score"]
    if preview_label == "장초반 우호 가능성":
        headline = "야간 선물과 글로벌 위험자산 흐름은 내일 장초반에 비교적 우호적인 배경으로 읽힙니다."
    elif preview_label == "장초반 우호 흐름":
        headline = "야간 선물과 글로벌 자산 흐름은 내일 장초반에 다소 우호적인 신호를 보입니다."
    elif preview_label == "장초반 부담 가능성":
        headline = "야간 선물과 글로벌 위험자산 흐름은 내일 장초반 부담 요인으로 작용할 가능성이 있습니다."
    elif preview_label == "장초반 경계 흐름":
        headline = "야간 흐름은 내일 장초반에 다소 경계적인 출발 가능성을 시사합니다."
    else:
        headline = "야간 자산 흐름은 혼조권에 머물러 내일 장초반 방향성은 아직 제한적입니다."
    if abs(score) >= 1.0:
        summary = f"다만 현재 퀀트모델 시장 흐름({market_flow_label}) 자체를 바꾸는 수준으로 해석하진 않고, 장초반 참고 레이어로만 봅니다."
    else:
        summary = f"현재 퀀트모델 시장 흐름({market_flow_label})과는 별도로, 장초반 수급과 환율을 함께 확인할 필요가 있습니다."
    return headline, summary



def _title_candidates(preview_label: str, reference_session: str) -> list[str]:
    return [
        f"{reference_session} 익일 신호 테스트",
        f"익일 신호 테스트: {preview_label}",
        f"야간/장외 스트레스 점검: {preview_label}",
    ]



def _caption_lines(preview_label: str, headline_line: str, supporting_points: list[str], risk_points: list[str], summary_line: str) -> list[str]:
    lines = [preview_label, headline_line]
    lines.extend(supporting_points[:1])
    lines.extend(risk_points[:1])
    lines.append(summary_line)
    return lines[:5]



def _content_hash_payload(preview_label: str, headline_line: str, score: float, supporting_points: list[str], risk_points: list[str], assets: list[dict]) -> str:
    compact_assets = [
        {
            "asset_code": item.get("asset_code"),
            "change_pct": _safe_round(item.get("change_pct"), 4),
        }
        for item in assets
    ]
    base = {
        "preview_label": preview_label,
        "headline_line": headline_line,
        "preview_score": _safe_round(score, 2),
        "supporting_0": (supporting_points or [None])[0],
        "risk_0": (risk_points or [None])[0],
        "assets": compact_assets,
    }
    return hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()



def _load_previous_state(con, *, market: str, asof: str):
    return con.execute(
        """
        SELECT *
        FROM market_next_day_preview_state
        WHERE market = ? AND asof < ?
        ORDER BY asof DESC
        LIMIT 1
        """,
        (market, asof),
    ).fetchone()



def _material_change(previous_row, *, preview_label: str, headline_line: str, score: float, futures_bias: float, supporting_points: list[str], risk_points: list[str]) -> bool:
    if previous_row is None:
        return True
    previous_support = json.loads(previous_row["supporting_points_json"] or "[]")
    previous_risk = json.loads(previous_row["risk_points_json"] or "[]")
    previous_futures_bias = float(previous_row["overnight_futures_bias"])
    if previous_row["preview_label"] != preview_label:
        return True
    if previous_row["headline_line"] != headline_line:
        return True
    if abs(float(previous_row["preview_score"]) - float(score)) >= 0.35:
        return True
    if _sign(previous_futures_bias) != _sign(futures_bias):
        return True
    if (previous_support or [None])[0] != (supporting_points or [None])[0]:
        return True
    if (previous_risk or [None])[0] != (risk_points or [None])[0]:
        return True
    return False



def build_next_day_preview_outputs(
    con,
    *,
    market: str,
    asof: str | None,
    summary: dict,
    detail: dict,
    snapshot_dir,
    handoff_dir,
) -> dict:
    current_dt = now_kst()
    asof = normalize_asof_kst(asof, now=current_dt)
    created_at = format_kst(current_dt)
    asof_dt = datetime.fromisoformat(asof.replace("Z", "+00:00"))
    reference_session = _resolve_reference_session(asof_dt)
    active_now = _is_preview_window(asof_dt)
    asset_rows = _collect_overnight_assets(market=market, asof=asof, created_at=created_at)
    news_context = _collect_news_context(market=market, asof=asof, created_at=created_at)
    biases = _compute_biases(asset_rows, news_context)
    preview_label = _preview_label(biases["next_day_preview_score"])
    supporting_points, risk_points = _supporting_and_risk_points(asset_rows, news_context, preview_label)
    market_flow_label = summary.get("state_label") or (detail.get("state") or {}).get("label") or "중립"
    market_flow_score = summary.get("state_score") or (detail.get("state") or {}).get("score") or 0.0
    market_flow_reference_note = summary.get("reference_note") or detail.get("observation_note") or ""
    headline_line, summary_line = _headline_and_summary(preview_label, biases, market_flow_label)
    overnight_assets_public = [
        {
            "asset_code": row["asset_code"],
            "asset_name": row["asset_name"],
            "asset_group": row["asset_group"],
            "change_pct": row["change_pct"],
            "price": row["price"],
            "source": row["source"],
            "is_fallback": bool(row["is_fallback"]),
        }
        for row in asset_rows
    ]
    content_hash = _content_hash_payload(
        preview_label,
        headline_line,
        biases["next_day_preview_score"],
        supporting_points,
        risk_points,
        overnight_assets_public,
    )
    previous_row = _load_previous_state(con, market=market, asof=asof)
    material_change_flag = _material_change(
        previous_row,
        preview_label=preview_label,
        headline_line=headline_line,
        score=biases["next_day_preview_score"],
        futures_bias=biases["overnight_futures_bias"],
        supporting_points=supporting_points,
        risk_points=risk_points,
    )

    upsert_many(
        con,
        table="market_overnight_asset_snapshot",
        columns=[
            "market", "asof", "session_date", "asset_code", "asset_name", "asset_group", "price", "change_value", "change_pct",
            "open", "high", "low", "prev_close", "source", "is_fallback", "created_at",
        ],
        rows=asset_rows,
        conflict_columns=["market", "asof", "asset_code"],
    )
    upsert_many(
        con,
        table="market_overnight_news_context",
        columns=["market", "asof", "session_date", "headline_count", "risk_headline_count", "caution_bias", "context_json", "created_at"],
        rows=[
            {
                "market": market,
                "asof": asof,
                "session_date": asof[:10],
                "headline_count": news_context["headline_count"],
                "risk_headline_count": news_context["risk_headline_count"],
                "caution_bias": 1 if news_context["caution_bias"] else 0,
                "context_json": json.dumps(news_context, ensure_ascii=False),
                "created_at": created_at,
            }
        ],
        conflict_columns=["market", "asof"],
    )
    upsert_many(
        con,
        table="market_next_day_preview_state",
        columns=[
            "market", "asof", "reference_session", "preview_label", "preview_score", "overnight_futures_bias", "global_risk_bias",
            "overnight_fx_bias", "headline_line", "summary_line", "supporting_points_json", "risk_points_json", "overnight_assets_json",
            "content_hash", "material_change_flag", "source", "created_at",
        ],
        rows=[
            {
                "market": market,
                "asof": asof,
                "reference_session": reference_session,
                "preview_label": preview_label,
                "preview_score": biases["next_day_preview_score"],
                "overnight_futures_bias": biases["overnight_futures_bias"],
                "global_risk_bias": biases["global_risk_bias"],
                "overnight_fx_bias": biases["overnight_fx_bias"],
                "headline_line": headline_line,
                "summary_line": summary_line,
                "supporting_points_json": json.dumps(supporting_points, ensure_ascii=False),
                "risk_points_json": json.dumps(risk_points, ensure_ascii=False),
                "overnight_assets_json": json.dumps(overnight_assets_public, ensure_ascii=False),
                "content_hash": content_hash,
                "material_change_flag": 1 if material_change_flag else 0,
                "source": "kiwoom_rest_optional+yahoo_chart+google_news_rss",
                "created_at": created_at,
            }
        ],
        conflict_columns=["market", "asof"],
    )

    notice_block = {
        "title": "주의사항",
        "short_notice": "익일 신호 테스트용 참고 정보입니다.",
        "body": NOTICE_BLOCK["body"],
        "preview_only": "야간/장외 자산 흐름을 참고해 만든 검증 전 실험값이며, 정식 시장 현황판 점수나 개별 투자자문이 아닙니다.",
    }
    preview_payload = {
        "market": market,
        "asof": asof,
        "reference_session": reference_session,
        "content_mode": "next_day_preview",
        "source_type": "public_next_day_preview",
        "experiment_label": "익일 신호 테스트",
        "experiment_status": "validation_required",
        "official_score_impact": False,
        "active_now": active_now,
        "active_window": {
            "start": "18:00",
            "end": "08:30",
            "timezone": "Asia/Seoul",
        },
        "title": "익일 신호 테스트",
        "preview_label": preview_label,
        "preview_score": biases["next_day_preview_score"],
        "headline_line": headline_line,
        "summary_line": summary_line,
        "supporting_points": supporting_points,
        "risk_points": risk_points,
        "overnight_assets": overnight_assets_public,
        "biases": biases,
        "market_flow_label": market_flow_label,
        "market_flow_score": market_flow_score,
        "market_flow_reference_note": market_flow_reference_note,
        "title_candidates": _title_candidates(preview_label, reference_session),
        "hook_line": headline_line,
        "caption_lines": _caption_lines(preview_label, headline_line, supporting_points, risk_points, summary_line),
        "narration_lines": _caption_lines(preview_label, headline_line, supporting_points, risk_points, summary_line),
        "tags": ["시장브리핑", "익일신호테스트", "야간장외스트레스", "퀀트모델", "한국증시", "멀티애셋"],
        "content_hash": content_hash,
        "material_change_flag": material_change_flag,
        "freshness": {
            "target_update_interval_minutes": 60,
            "consumer_warning_after_minutes": 90,
            "consumer_stale_after_minutes": 240,
        },
        "lineage": {
            "producer": "QuantMarket",
            "upstream_sources": ["kiwoom_rest_optional", "yahoo_chart", "google_news_rss"],
            "related_layers": ["quant_model_market_flow", "intraday_flow"],
        },
        "visibility": "public_next_day_preview",
        "notice_block": notice_block,
        "compliance_meta": _compliance_meta(asof),
    }
    quantservice_payload = {
        **preview_payload,
        "display_title": "익일 신호 테스트",
        "display_subtitle": "야간/장외 자산 흐름과 주요 뉴스를 바탕으로 다음 거래일 참고 신호를 별도 실험값으로 정리합니다.",
    }
    api_payload = build_api_response(
        endpoint=f"/api/v1/market-analysis/next-day-preview?market={market}",
        market=market,
        asof=asof,
        payload=preview_payload,
    )
    manifest = {
        "market": market,
        "asof": asof,
        "generated_at": created_at,
        "reference_session": reference_session,
        "content_modes": ["next_day_preview"],
        "visibility": "public_next_day_preview",
        "freshness": preview_payload["freshness"],
        "lineage": preview_payload["lineage"],
        "files": {
            "snapshot": "market_next_day_preview.json",
            "handoff": "quantservice_market_next_day_preview.json",
            "api": "api_v1_market_analysis_next_day_preview.json",
            "manifest": "market_next_day_preview_manifest.json",
        },
        "change_detection_rule": {
            "preview_label_change": True,
            "headline_line_change": True,
            "preview_score_delta_gte": 0.35,
            "futures_direction_change": True,
            "top_point_change": True,
        },
        "content_hash": content_hash,
        "material_change_flag": material_change_flag,
        "notice_block": notice_block,
        "compliance_meta": _compliance_meta(asof),
    }

    upsert_payload(con, market=market, asof=asof, payload_type="next_day_preview", payload=preview_payload, created_at=created_at)
    upsert_payload(con, market=market, asof=asof, payload_type="quantservice_next_day_preview", payload=quantservice_payload, created_at=created_at)
    upsert_payload(con, market=market, asof=asof, payload_type="api_next_day_preview", payload=api_payload, created_at=created_at)
    upsert_payload(con, market=market, asof=asof, payload_type="next_day_preview_manifest", payload=manifest, created_at=created_at)

    write_payload_file(snapshot_dir / "market_next_day_preview.json", preview_payload)
    write_payload_file(snapshot_dir / "market_next_day_preview_manifest.json", manifest)
    write_payload_file(handoff_dir / "quantservice_market_next_day_preview.json", quantservice_payload)
    write_payload_file(handoff_dir / "api_v1_market_analysis_next_day_preview.json", api_payload)
    write_payload_file(handoff_dir / "market_next_day_preview_manifest.json", manifest)

    snapshot_day_dir = NEXT_DAY_PREVIEW_SNAPSHOT_ROOT / asof[:10]
    stamp = asof.replace(":", "").replace("-", "")
    write_payload_file(snapshot_day_dir / f"market_next_day_preview_{stamp}.json", preview_payload)
    write_payload_file(snapshot_day_dir / f"market_next_day_preview_manifest_{stamp}.json", manifest)

    return {
        "preview": preview_payload,
        "quantservice": quantservice_payload,
        "api": api_payload,
        "manifest": manifest,
    }
