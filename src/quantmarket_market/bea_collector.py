from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .global_context_db import connect_global_context, init_global_context_db


BEA_API_URL = "https://apps.bea.gov/api/data/"
DEFAULT_BEA_API_KEY_PATH = Path("D:/QuantMarket/config/bea_api_key.txt")
SOURCE = "BEA"


@dataclass(frozen=True)
class BeaSeries:
    series_id: str
    display_name: str
    category: str
    unit: str
    frequency: str
    table_name: str
    line_number: int
    market_relevance: str
    score_direction: str
    transform_hint: str


BEA_NIPA_SERIES: tuple[BeaSeries, ...] = (
    BeaSeries("BEA_GDP", "미국 GDP", "growth", "billions_usd", "quarterly", "T10105", 1, "미국 명목 성장 레벨", "higher_momentum_is_risk_on", "qoq_yoy_growth"),
    BeaSeries("BEA_REAL_GDP", "미국 실질 GDP", "growth", "chained_2017_usd", "quarterly", "T10106", 1, "미국 실질 성장", "higher_momentum_is_risk_on", "qoq_yoy_growth"),
    BeaSeries("BEA_PCE", "미국 개인소비지출", "consumption", "billions_usd", "quarterly", "T10105", 2, "미국 소비 경기", "higher_momentum_is_risk_on", "qoq_yoy_growth"),
    BeaSeries("BEA_REAL_PCE", "미국 실질 개인소비지출", "consumption", "chained_2017_usd", "quarterly", "T10106", 2, "미국 실질 소비 경기", "higher_momentum_is_risk_on", "qoq_yoy_growth"),
    BeaSeries("BEA_PERSONAL_INCOME", "미국 개인소득", "income", "millions_usd_annual_rate", "monthly", "T20600", 1, "미국 가계 소득 여건", "higher_momentum_is_risk_on", "mom_yoy_growth"),
    BeaSeries("BEA_PCE_PRICE_INDEX", "미국 PCE 물가지수", "inflation", "index", "monthly", "T20804", 1, "연준 선호 물가 지표", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_bea_api_key(path: Path | None = None) -> str:
    env_key = os.getenv("BEA_API_KEY")
    if env_key:
        return env_key.strip()
    key_path = path or DEFAULT_BEA_API_KEY_PATH
    if not key_path.exists():
        raise FileNotFoundError(f"BEA API key not found. Create {key_path} or set BEA_API_KEY.")
    api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError(f"BEA API key file is empty: {key_path}")
    return api_key


def bea_key_available(path: Path | None = None) -> bool:
    if os.getenv("BEA_API_KEY"):
        return True
    return (path or DEFAULT_BEA_API_KEY_PATH).exists()


def _parse_float(value: str | None) -> float | None:
    if value in (None, "", "."):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _asof_date(time_period: str) -> str | None:
    if not time_period:
        return None
    if "Q" in time_period:
        year, quarter_text = time_period.split("Q", 1)
        quarter = int(quarter_text)
        month = {1: 1, 2: 4, 3: 7, 4: 10}.get(quarter)
        return f"{int(year):04d}-{month:02d}-01" if month else None
    if "M" in time_period:
        year, month_text = time_period.split("M", 1)
        return f"{int(year):04d}-{int(month_text):02d}-01"
    if len(time_period) == 4 and time_period.isdigit():
        return f"{int(time_period):04d}-01-01"
    return None


def _request_bea(params: dict[str, str | int]) -> dict:
    query = urlencode({**params, "ResultFormat": "JSON"})
    request = Request(f"{BEA_API_URL}?{query}", headers={"User-Agent": "QuantMarket/1.0"})
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bea_nipa_table(
    *,
    api_key: str,
    table_name: str,
    frequency: str,
    year: str = "ALL",
) -> list[dict]:
    payload = _request_bea(
        {
            "UserID": api_key,
            "method": "GetData",
            "DatasetName": "NIPA",
            "TableName": table_name,
            "Frequency": "Q" if frequency == "quarterly" else "M",
            "Year": year,
        }
    )
    beaapi = payload.get("BEAAPI") or {}
    results = beaapi.get("Results") or {}
    if "Error" in results:
        error = results["Error"]
        raise RuntimeError(f"BEA error {error.get('APIErrorCode')}: {error.get('APIErrorDescription')}")
    return list(results.get("Data") or [])


def upsert_bea_registry(con, *, timestamp: str) -> None:
    rows = [
        {
            "source": SOURCE,
            "series_id": series.series_id,
            "display_name": series.display_name,
            "category": series.category,
            "unit": series.unit,
            "frequency": series.frequency,
            "market_relevance": series.market_relevance,
            "score_direction": series.score_direction,
            "transform_hint": series.transform_hint,
            "is_active": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for series in BEA_NIPA_SERIES
    ]
    con.executemany(
        """
        INSERT INTO global_series_registry (
            source, series_id, display_name, category, unit, frequency,
            market_relevance, score_direction, transform_hint, is_active,
            created_at, updated_at
        )
        VALUES (
            :source, :series_id, :display_name, :category, :unit, :frequency,
            :market_relevance, :score_direction, :transform_hint, :is_active,
            :created_at, :updated_at
        )
        ON CONFLICT (source, series_id) DO UPDATE SET
            display_name=excluded.display_name,
            category=excluded.category,
            unit=excluded.unit,
            frequency=excluded.frequency,
            market_relevance=excluded.market_relevance,
            score_direction=excluded.score_direction,
            transform_hint=excluded.transform_hint,
            is_active=excluded.is_active,
            updated_at=excluded.updated_at
        """,
        rows,
    )


def upsert_bea_observations(con, *, series: BeaSeries, records: list[dict], timestamp: str) -> int:
    rows: list[dict] = []
    for record in records:
        if str(record.get("LineNumber")) != str(series.line_number):
            continue
        asof_date = _asof_date(str(record.get("TimePeriod") or ""))
        if not asof_date:
            continue
        raw_value = record.get("DataValue")
        rows.append(
            {
                "source": SOURCE,
                "series_id": series.series_id,
                "asof_date": asof_date,
                "value": _parse_float(raw_value),
                "raw_value": str(raw_value) if raw_value is not None else None,
                "realtime_start": asof_date,
                "realtime_end": asof_date,
                "collected_at": timestamp,
            }
        )
    if not rows:
        return 0
    con.executemany(
        """
        INSERT INTO global_observation (
            source, series_id, asof_date, value, raw_value,
            realtime_start, realtime_end, collected_at
        )
        VALUES (
            :source, :series_id, :asof_date, :value, :raw_value,
            :realtime_start, :realtime_end, :collected_at
        )
        ON CONFLICT (source, series_id, asof_date, realtime_start, realtime_end) DO UPDATE SET
            value=excluded.value,
            raw_value=excluded.raw_value,
            collected_at=excluded.collected_at
        """,
        rows,
    )
    return len(rows)


def collect_bea_series(
    *,
    db_path: Path,
    api_key_path: Path | None = None,
    sleep_seconds: float = 0.2,
) -> dict:
    init_global_context_db(db_path)
    timestamp = now_utc_iso()
    run_id = f"bea_{timestamp.replace(':', '').replace('-', '')}"
    api_key = read_bea_api_key(api_key_path)
    with connect_global_context(db_path) as con:
        con.execute(
            """
            INSERT INTO global_collection_run_log (
                run_id, source, started_at, status, requested_series_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, SOURCE, timestamp, "running", len(BEA_NIPA_SERIES)),
        )
        con.commit()
        try:
            upsert_bea_registry(con, timestamp=timestamp)
            total_rows = 0
            errors: list[str] = []
            cache: dict[tuple[str, str], list[dict]] = {}
            for series in BEA_NIPA_SERIES:
                key = (series.table_name, series.frequency)
                try:
                    if key not in cache:
                        cache[key] = fetch_bea_nipa_table(
                            api_key=api_key,
                            table_name=series.table_name,
                            frequency=series.frequency,
                        )
                        if sleep_seconds > 0:
                            time.sleep(sleep_seconds)
                    total_rows += upsert_bea_observations(
                        con,
                        series=series,
                        records=cache[key],
                        timestamp=timestamp,
                    )
                    con.commit()
                except Exception as exc:
                    errors.append(f"{series.series_id}: {exc}")
            status = "success" if not errors else "partial_success"
            finished_at = now_utc_iso()
            con.execute(
                """
                UPDATE global_collection_run_log
                SET finished_at=?, status=?, inserted_or_updated_rows=?, error_message=?
                WHERE run_id=?
                """,
                (finished_at, status, total_rows, "\n".join(errors) if errors else None, run_id),
            )
            con.commit()
            return {
                "run_id": run_id,
                "source": SOURCE,
                "status": status,
                "series_count": len(BEA_NIPA_SERIES),
                "rows": total_rows,
                "errors": errors,
                "db_path": str(db_path),
            }
        except Exception as exc:
            finished_at = now_utc_iso()
            con.execute(
                """
                UPDATE global_collection_run_log
                SET finished_at=?, status=?, error_message=?
                WHERE run_id=?
                """,
                (finished_at, "failed", str(exc), run_id),
            )
            con.commit()
            raise
