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


EIA_API_BASE = "https://api.eia.gov/v2"
DEFAULT_EIA_API_KEY_PATH = Path("D:/QuantMarket/config/eia_api_key.txt")
SOURCE = "EIA"


@dataclass(frozen=True)
class EiaSeries:
    series_id: str
    route: str
    eia_series_id: str
    display_name: str
    category: str
    unit: str
    frequency: str
    market_relevance: str
    score_direction: str
    transform_hint: str


EIA_ENERGY_SERIES: tuple[EiaSeries, ...] = (
    EiaSeries("EIA_WTI_SPOT", "petroleum/pri/spt", "RWTC", "WTI 현물유가", "energy_price", "usd_per_barrel", "daily", "유가와 인플레이션 비용 압력", "higher_can_be_risk_off", "level_change_zscore"),
    EiaSeries("EIA_BRENT_SPOT", "petroleum/pri/spt", "RBRTE", "Brent 현물유가", "energy_price", "usd_per_barrel", "daily", "글로벌 원유 가격 압력", "higher_can_be_risk_off", "level_change_zscore"),
    EiaSeries("EIA_US_CRUDE_STOCKS", "petroleum/stoc/wstk", "WCESTUS1", "미국 상업 원유재고", "energy_inventory", "thousand_barrels", "weekly", "원유 수급과 유가 변동 요인", "higher_inventory_can_be_risk_on", "wow_zscore"),
    EiaSeries("EIA_CUSHING_CRUDE_STOCKS", "petroleum/stoc/wstk", "W_EPC0_SAX_YCUOK_MBBL", "쿠싱 원유재고", "energy_inventory", "thousand_barrels", "weekly", "WTI 인도지 재고 압력", "higher_inventory_can_be_risk_on", "wow_zscore"),
    EiaSeries("EIA_GASOLINE_STOCKS", "petroleum/stoc/wstk", "WGTSTUS1", "미국 휘발유재고", "energy_inventory", "thousand_barrels", "weekly", "미국 석유제품 수급", "higher_inventory_can_be_risk_on", "wow_zscore"),
    EiaSeries("EIA_DISTILLATE_STOCKS", "petroleum/stoc/wstk", "WDISTUS1", "미국 중간유분재고", "energy_inventory", "thousand_barrels", "weekly", "경유/난방유 수급과 경기 민감 수요", "higher_inventory_can_be_risk_on", "wow_zscore"),
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_eia_api_key(path: Path | None = None) -> str:
    env_key = os.getenv("EIA_API_KEY")
    if env_key:
        return env_key.strip()
    key_path = path or DEFAULT_EIA_API_KEY_PATH
    if not key_path.exists():
        raise FileNotFoundError(f"EIA API key not found. Create {key_path} or set EIA_API_KEY.")
    api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError(f"EIA API key file is empty: {key_path}")
    return api_key


def eia_key_available(path: Path | None = None) -> bool:
    if os.getenv("EIA_API_KEY"):
        return True
    return (path or DEFAULT_EIA_API_KEY_PATH).exists()


def _parse_float(value: object) -> float | None:
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _asof_date(period: str) -> str | None:
    text = str(period)
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    if len(text) == 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) == 6:
        return f"{text[:4]}-{text[4:6]}-01"
    if len(text) == 4:
        return f"{text}-01-01"
    return None


def fetch_eia_series(*, api_key: str, series: EiaSeries) -> dict:
    query = urlencode(
        {
            "api_key": api_key,
            "frequency": series.frequency,
            "data[0]": "value",
            "facets[series][]": series.eia_series_id,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": 0,
            "length": 5000,
        }
    )
    request = Request(f"{EIA_API_BASE}/{series.route}/data/?{query}", headers={"User-Agent": "QuantMarket/1.0"})
    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(str(payload["error"]))
    data = (payload.get("response") or {}).get("data") or []
    if not data:
        raise RuntimeError(f"EIA series not found: {series.eia_series_id}")
    return {"data": data}


def upsert_eia_registry(con, *, timestamp: str) -> None:
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
        for series in EIA_ENERGY_SERIES
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


def upsert_eia_observations(con, *, series: EiaSeries, payload: dict, timestamp: str) -> int:
    rows: list[dict] = []
    for record in payload.get("data") or []:
        asof_date = _asof_date(str(record.get("period") or ""))
        if not asof_date:
            continue
        raw_value = record.get("value")
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


def collect_eia_series(
    *,
    db_path: Path,
    api_key_path: Path | None = None,
    sleep_seconds: float = 0.2,
) -> dict:
    init_global_context_db(db_path)
    timestamp = now_utc_iso()
    run_id = f"eia_{timestamp.replace(':', '').replace('-', '')}"
    api_key = read_eia_api_key(api_key_path)
    with connect_global_context(db_path) as con:
        con.execute(
            """
            INSERT INTO global_collection_run_log (
                run_id, source, started_at, status, requested_series_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, SOURCE, timestamp, "running", len(EIA_ENERGY_SERIES)),
        )
        con.commit()
        try:
            upsert_eia_registry(con, timestamp=timestamp)
            total_rows = 0
            errors: list[str] = []
            for series in EIA_ENERGY_SERIES:
                try:
                    payload = fetch_eia_series(api_key=api_key, series=series)
                    total_rows += upsert_eia_observations(con, series=series, payload=payload, timestamp=timestamp)
                    con.commit()
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
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
                "series_count": len(EIA_ENERGY_SERIES),
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
