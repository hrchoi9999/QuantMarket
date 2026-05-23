from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .global_context_db import connect_global_context, init_global_context_db


TREASURY_XML_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
SOURCE = "TREASURY"

ATOM_NS = "{http://www.w3.org/2005/Atom}"
META_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
DATA_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices}"


@dataclass(frozen=True)
class TreasurySeries:
    series_id: str
    display_name: str
    field_name: str
    market_relevance: str


TREASURY_YIELD_SERIES: tuple[TreasurySeries, ...] = (
    TreasurySeries("DGS3MO", "미국 국채 3개월 금리", "BC_3MONTH", "미국 단기 금리와 정책금리 기대"),
    TreasurySeries("DGS2", "미국 국채 2년 금리", "BC_2YEAR", "정책금리 기대와 성장주 할인율"),
    TreasurySeries("DGS10", "미국 국채 10년 금리", "BC_10YEAR", "글로벌 할인율과 위험자산 부담"),
    TreasurySeries("DGS30", "미국 국채 30년 금리", "BC_30YEAR", "미국 장기 금리 환경"),
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _parse_float(value: str | None) -> float | None:
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _month_keys(start_date: str, end_date: str) -> list[str]:
    start = datetime.fromisoformat(start_date).date().replace(day=1)
    end = datetime.fromisoformat(end_date).date().replace(day=1)
    months: list[str] = []
    cursor = start
    while cursor <= end:
        months.append(cursor.strftime("%Y%m"))
        year = cursor.year + (1 if cursor.month == 12 else 0)
        month = 1 if cursor.month == 12 else cursor.month + 1
        cursor = cursor.replace(year=year, month=month)
    return months


def fetch_treasury_month(month_key: str) -> list[dict]:
    query = urlencode(
        {
            "data": "daily_treasury_yield_curve",
            "field_tdr_date_value_month": month_key,
        }
    )
    request = Request(f"{TREASURY_XML_URL}?{query}", headers={"User-Agent": "QuantMarket/1.0"})
    with urlopen(request, timeout=30) as response:
        xml_text = response.read().decode("utf-8")

    root = ET.fromstring(xml_text)
    records: list[dict] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        props = entry.find(f".//{META_NS}properties")
        if props is None:
            continue
        date_node = props.find(f"{DATA_NS}NEW_DATE")
        if date_node is None or not date_node.text:
            continue
        asof_date = date_node.text[:10]
        row = {"asof_date": asof_date}
        for series in TREASURY_YIELD_SERIES:
            node = props.find(f"{DATA_NS}{series.field_name}")
            row[series.series_id] = node.text if node is not None else None
        records.append(row)
    return records


def upsert_treasury_registry(con, *, timestamp: str) -> None:
    rows = [
        {
            "source": SOURCE,
            "series_id": series.series_id,
            "display_name": series.display_name,
            "category": "rates",
            "unit": "percent",
            "frequency": "daily",
            "market_relevance": series.market_relevance,
            "score_direction": "higher_is_risk_off",
            "transform_hint": "level_change_zscore",
            "is_active": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for series in TREASURY_YIELD_SERIES
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


def upsert_treasury_observations(con, *, records: list[dict], start_date: str, end_date: str, timestamp: str) -> int:
    rows: list[dict] = []
    for record in records:
        asof_date = record["asof_date"]
        if asof_date < start_date or asof_date > end_date:
            continue
        for series in TREASURY_YIELD_SERIES:
            raw_value = record.get(series.series_id)
            rows.append(
                {
                    "source": SOURCE,
                    "series_id": series.series_id,
                    "asof_date": asof_date,
                    "value": _parse_float(raw_value),
                    "raw_value": raw_value,
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


def collect_treasury_yield_curve(
    *,
    db_path: Path,
    start_date: str,
    end_date: str,
    sleep_seconds: float = 0.2,
) -> dict:
    init_global_context_db(db_path)
    timestamp = now_utc_iso()
    run_id = f"treasury_{timestamp.replace(':', '').replace('-', '')}"
    month_keys = _month_keys(start_date, end_date)

    with connect_global_context(db_path) as con:
        con.execute(
            """
            INSERT INTO global_collection_run_log (
                run_id, source, started_at, status, start_date, end_date,
                requested_series_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, SOURCE, timestamp, "running", start_date, end_date, len(TREASURY_YIELD_SERIES)),
        )
        con.commit()
        try:
            upsert_treasury_registry(con, timestamp=timestamp)
            total_rows = 0
            errors: list[str] = []
            for month_key in month_keys:
                try:
                    records = fetch_treasury_month(month_key)
                    total_rows += upsert_treasury_observations(
                        con,
                        records=records,
                        start_date=start_date,
                        end_date=end_date,
                        timestamp=timestamp,
                    )
                    con.commit()
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
                except Exception as exc:
                    errors.append(f"{month_key}: {exc}")

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
                "start_date": start_date,
                "end_date": end_date,
                "series_count": len(TREASURY_YIELD_SERIES),
                "month_count": len(month_keys),
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
