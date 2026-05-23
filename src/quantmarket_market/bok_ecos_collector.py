from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from .db import upsert_many


ECOS_API_BASE = "https://ecos.bok.or.kr/api"
DEFAULT_BOK_API_KEY_PATH = Path("D:/QuantMarket/config/bok_ecos_api_key.txt")
SOURCE = "bok_ecos"


@dataclass(frozen=True)
class EcosSeries:
    output_table: str
    output_code: str
    output_name: str
    stat_code: str
    cycle: str
    item_code: str
    unit: str


RATE_SERIES: tuple[EcosSeries, ...] = (
    EcosSeries("market_rates_daily", "CD91", "CD 91D", "817Y002", "D", "010502000", "percent"),
    EcosSeries("market_rates_daily", "KTB3Y", "KTB 3Y", "817Y002", "D", "010200000", "percent"),
    EcosSeries("market_rates_daily", "KTB5Y", "KTB 5Y", "817Y002", "D", "010200001", "percent"),
    EcosSeries("market_rates_daily", "BASE", "Base Rate", "722Y001", "M", "0101000", "percent"),
)

FX_SERIES = EcosSeries("market_fx_daily", "USDKRW", "USD/KRW", "731Y001", "D", "0000001", "KRW per USD")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_bok_api_key(path: Path | None = None) -> str:
    env_key = os.getenv("BOK_ECOS_API_KEY") or os.getenv("ECOS_API_KEY")
    if env_key:
        return env_key.strip()
    key_path = path or DEFAULT_BOK_API_KEY_PATH
    if not key_path.exists():
        raise FileNotFoundError(
            f"BOK ECOS API key not found. Create {key_path} or set BOK_ECOS_API_KEY."
        )
    api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError(f"BOK ECOS API key file is empty: {key_path}")
    return api_key


def _daily_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def _monthly_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-01"


def _ecos_date(series: EcosSeries, value: str) -> str:
    return _daily_date(value) if series.cycle == "D" else _monthly_date(value)


def _compact_date(value: str, *, cycle: str) -> str:
    return value.replace("-", "")[:8] if cycle == "D" else value.replace("-", "")[:6]


def _parse_float(value: str | None) -> float | None:
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fetch_ecos_series(
    *,
    api_key: str,
    series: EcosSeries,
    start: str,
    end: str,
    start_no: int = 1,
    end_no: int = 10000,
) -> list[dict]:
    start_value = _compact_date(start, cycle=series.cycle)
    end_value = _compact_date(end, cycle=series.cycle)
    url = (
        f"{ECOS_API_BASE}/StatisticSearch/{quote(api_key)}/json/kr/"
        f"{start_no}/{end_no}/{series.stat_code}/{series.cycle}/{start_value}/{end_value}/{series.item_code}"
    )
    request = Request(url, headers={"User-Agent": "QuantMarket/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "RESULT" in payload:
        result = payload["RESULT"]
        code = result.get("CODE")
        if code and code != "INFO-000":
            raise RuntimeError(f"ECOS error {code}: {result.get('MESSAGE')}")
    search = payload.get("StatisticSearch") or {}
    return list(search.get("row") or [])


def collect_bok_ecos_market_data(
    con,
    *,
    market: str,
    start_date: str,
    end_date: str,
    updated_at: str,
    api_key_path: Path | None = None,
    sleep_seconds: float = 0.1,
) -> dict:
    api_key = read_bok_api_key(api_key_path)
    stats = {
        "source": SOURCE,
        "start_date": start_date,
        "end_date": end_date,
        "fx_rows": 0,
        "rate_rows": 0,
        "errors": [],
    }

    fx_rows: list[dict] = []
    for row in fetch_ecos_series(api_key=api_key, series=FX_SERIES, start=start_date, end=end_date):
        value = _parse_float(row.get("DATA_VALUE"))
        if value is None:
            continue
        fx_rows.append(
            {
                "market": market,
                "series_code": FX_SERIES.output_code,
                "series_name": FX_SERIES.output_name,
                "date": _ecos_date(FX_SERIES, row["TIME"]),
                "close": value,
                "source": f"{SOURCE}:{FX_SERIES.stat_code}:{FX_SERIES.item_code}",
                "updated_at": updated_at,
            }
        )
    if fx_rows:
        upsert_many(
            con,
            table="market_fx_daily",
            columns=["market", "series_code", "series_name", "date", "close", "source", "updated_at"],
            rows=fx_rows,
            conflict_columns=["market", "series_code", "date"],
        )
        stats["fx_rows"] = len(fx_rows)

    rate_rows: list[dict] = []
    for series in RATE_SERIES:
        try:
            for row in fetch_ecos_series(api_key=api_key, series=series, start=start_date, end=end_date):
                value = _parse_float(row.get("DATA_VALUE"))
                if value is None:
                    continue
                rate_rows.append(
                    {
                        "market": market,
                        "rate_code": series.output_code,
                        "rate_name": series.output_name,
                        "date": _ecos_date(series, row["TIME"]),
                        "value": value,
                        "source": f"{SOURCE}:{series.stat_code}:{series.item_code}",
                        "updated_at": updated_at,
                    }
                )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        except Exception as exc:
            stats["errors"].append(f"{series.output_code}: {exc}")
    if rate_rows:
        upsert_many(
            con,
            table="market_rates_daily",
            columns=["market", "rate_code", "rate_name", "date", "value", "source", "updated_at"],
            rows=rate_rows,
            conflict_columns=["market", "rate_code", "date"],
        )
        stats["rate_rows"] = len(rate_rows)
    return stats


def bok_key_available(path: Path | None = None) -> bool:
    if os.getenv("BOK_ECOS_API_KEY") or os.getenv("ECOS_API_KEY"):
        return True
    return (path or DEFAULT_BOK_API_KEY_PATH).exists()
