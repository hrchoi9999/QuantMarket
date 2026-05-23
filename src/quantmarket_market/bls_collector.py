from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from .global_context_db import connect_global_context, init_global_context_db


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
SOURCE = "BLS"


@dataclass(frozen=True)
class BlsSeries:
    series_id: str
    bls_series_id: str
    display_name: str
    category: str
    unit: str
    market_relevance: str
    score_direction: str
    transform_hint: str


BLS_MONTHLY_SERIES: tuple[BlsSeries, ...] = (
    BlsSeries("CPIAUCSL", "CUSR0000SA0", "미국 CPI", "inflation", "index", "미국 소비자물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
    BlsSeries("CPILFESL", "CUSR0000SA0L1E", "미국 Core CPI", "inflation", "index", "미국 근원 소비자물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
    BlsSeries("PPIACO", "WPU00000000", "미국 PPI", "inflation", "index", "미국 생산자물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
    BlsSeries("UNRATE", "LNS14000000", "미국 실업률", "employment", "percent", "미국 고용 둔화 압력", "higher_is_risk_off", "level_change_zscore"),
    BlsSeries("PAYEMS", "CES0000000001", "미국 비농업고용", "employment", "thousands", "미국 고용 모멘텀", "higher_momentum_is_risk_on", "mom_zscore"),
    BlsSeries("CES0500000003", "CES0500000003", "미국 민간 평균시간당임금", "employment", "usd_per_hour", "미국 임금 물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
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


def _month_date(year: str, period: str) -> str | None:
    if not period.startswith("M") or period == "M13":
        return None
    month = int(period[1:])
    return f"{int(year):04d}-{month:02d}-01"


def _year_chunks(start_year: int, end_year: int, *, chunk_years: int = 10) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    cursor = start_year
    while cursor <= end_year:
        chunk_end = min(end_year, cursor + chunk_years - 1)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + 1
    return chunks


def fetch_bls_series(
    *,
    series_ids: list[str],
    start_year: int,
    end_year: int,
) -> list[dict]:
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
        "annualaverage": False,
    }
    request = Request(
        BLS_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "QuantMarket/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS error: {data.get('status')} {data.get('message')}")
    return list(((data.get("Results") or {}).get("series")) or [])


def upsert_bls_registry(con, *, timestamp: str) -> None:
    rows = [
        {
            "source": SOURCE,
            "series_id": series.series_id,
            "display_name": series.display_name,
            "category": series.category,
            "unit": series.unit,
            "frequency": "monthly",
            "market_relevance": series.market_relevance,
            "score_direction": series.score_direction,
            "transform_hint": series.transform_hint,
            "is_active": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for series in BLS_MONTHLY_SERIES
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


def upsert_bls_observations(con, *, response_series: list[dict], timestamp: str) -> int:
    logical_by_bls = {series.bls_series_id: series.series_id for series in BLS_MONTHLY_SERIES}
    rows: list[dict] = []
    for item in response_series:
        logical_id = logical_by_bls.get(item.get("seriesID"))
        if not logical_id:
            continue
        for obs in item.get("data") or []:
            asof_date = _month_date(obs.get("year", ""), obs.get("period", ""))
            if not asof_date:
                continue
            rows.append(
                {
                    "source": SOURCE,
                    "series_id": logical_id,
                    "asof_date": asof_date,
                    "value": _parse_float(obs.get("value")),
                    "raw_value": obs.get("value"),
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


def collect_bls_series(
    *,
    db_path: Path,
    start_year: int,
    end_year: int,
    sleep_seconds: float = 0.2,
) -> dict:
    init_global_context_db(db_path)
    timestamp = now_utc_iso()
    run_id = f"bls_{timestamp.replace(':', '').replace('-', '')}"
    series_ids = [series.bls_series_id for series in BLS_MONTHLY_SERIES]
    chunks = _year_chunks(start_year, end_year)
    with connect_global_context(db_path) as con:
        con.execute(
            """
            INSERT INTO global_collection_run_log (
                run_id, source, started_at, status, start_date, end_date,
                requested_series_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, SOURCE, timestamp, "running", str(start_year), str(end_year), len(series_ids)),
        )
        con.commit()
        try:
            upsert_bls_registry(con, timestamp=timestamp)
            total_rows = 0
            errors: list[str] = []
            for chunk_start, chunk_end in chunks:
                try:
                    response_series = fetch_bls_series(
                        series_ids=series_ids,
                        start_year=chunk_start,
                        end_year=chunk_end,
                    )
                    total_rows += upsert_bls_observations(
                        con,
                        response_series=response_series,
                        timestamp=timestamp,
                    )
                    con.commit()
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
                except Exception as exc:
                    errors.append(f"{chunk_start}-{chunk_end}: {exc}")
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
                "start_year": start_year,
                "end_year": end_year,
                "series_count": len(series_ids),
                "chunk_count": len(chunks),
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
