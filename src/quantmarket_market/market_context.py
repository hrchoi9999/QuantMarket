from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .config import REPORT_DIR
from .payloads import write_payload_file

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
RISK_KEYWORDS = [
    "이란",
    "이스라엘",
    "중동",
    "전쟁",
    "공습",
    "미사일",
    "유가",
    "oil",
    "iran",
    "israel",
    "conflict",
    "war",
    "risk-off",
]

MARKET_QUERIES = {
    "KR": [
        "한국 증시 OR 코스피 OR 코스닥 시장 분위기",
        "이란 OR 이스라엘 OR 중동 유가 증시",
        "코스피 변동성 외국인 수급",
    ],
    "US": [
        "US stock market sentiment volatility",
        "Iran Israel oil stocks",
        "S&P 500 breadth volatility",
    ],
}


@dataclass
class MarketContext:
    market: str
    fetched_at: str
    headlines: list[str]
    risk_headlines: list[str]
    caution_bias: bool
    source_urls: list[str]

    def as_dict(self) -> dict:
        return {
            "market": self.market,
            "fetched_at": self.fetched_at,
            "headlines": self.headlines,
            "risk_headlines": self.risk_headlines,
            "caution_bias": self.caution_bias,
            "source_urls": self.source_urls,
        }


def _fetch_rss_titles(query: str, limit: int = 4) -> tuple[list[str], str]:
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))
    request = Request(url, headers={"User-Agent": "QuantMarket/1.0"})
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
        titles.append(title_text)
        if len(titles) >= limit:
            break
    return titles, url


def fetch_market_context(*, market: str, fetched_at: str) -> dict:
    queries = MARKET_QUERIES.get(market, MARKET_QUERIES["KR"])
    headlines: list[str] = []
    source_urls: list[str] = []
    for query in queries:
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
    context = MarketContext(
        market=market,
        fetched_at=fetched_at,
        headlines=headlines[:8],
        risk_headlines=risk_headlines[:5],
        caution_bias=bool(risk_headlines),
        source_urls=source_urls,
    )
    write_payload_file(REPORT_DIR / "market_context_latest.json", context.as_dict())
    return context.as_dict()
