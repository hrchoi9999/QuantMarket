from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .global_context_db import connect_global_context, init_global_context_db


FRED_API_BASE = "https://api.stlouisfed.org/fred"
DEFAULT_FRED_API_KEY_PATH = Path("D:/QuantMarket/config/fred_api_key.txt")
SOURCE = "FRED"


@dataclass(frozen=True)
class FredSeries:
    series_id: str
    display_name: str
    category: str
    unit: str
    frequency: str
    market_relevance: str
    score_direction: str
    transform_hint: str


DEFAULT_FRED_SERIES: tuple[FredSeries, ...] = (
    FredSeries("DGS3MO", "미국 국채 3개월 금리", "rates", "percent", "daily", "단기 정책금리 압력", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("DGS2", "미국 국채 2년 금리", "rates", "percent", "daily", "정책금리 기대와 성장주 할인율", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("DGS10", "미국 국채 10년 금리", "rates", "percent", "daily", "글로벌 할인율과 위험자산 부담", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("DGS30", "미국 국채 30년 금리", "rates", "percent", "daily", "장기 금리 환경", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("DFII10", "미국 10년 실질금리", "rates_real", "percent", "daily", "실질 할인율과 성장주 부담", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("T10YIE", "미국 10년 기대인플레이션", "inflation_expectation", "percent", "daily", "인플레이션 기대", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("VIXCLS", "VIX 변동성 지수", "risk", "index", "daily", "글로벌 위험회피 심리", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("BAMLH0A0HYM2", "미국 하이일드 스프레드", "credit", "percent", "daily", "신용위험과 위험자산 선호", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("BAMLC0A0CM", "미국 투자등급 회사채 스프레드", "credit", "percent", "daily", "우량 신용시장 스트레스", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("DTWEXBGS", "미국 달러 광의 명목지수", "fx", "index", "daily", "달러 강세와 비미국 위험자산 부담", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("DEXKOUS", "원달러 환율", "fx", "krw_per_usd", "daily", "한국시장 외국인 수급 부담", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("DEXJPUS", "엔달러 환율", "fx", "jpy_per_usd", "daily", "아시아 환율 환경", "mixed", "level_change_zscore"),
    FredSeries("DCOILWTICO", "WTI 유가", "commodity", "usd_per_barrel", "daily", "물가와 비용 압력", "higher_can_be_risk_off", "level_change_zscore"),
    FredSeries("GVZCLS", "CBOE 금 ETF 변동성 지수", "commodity_risk", "index", "daily", "금 관련 안전자산 변동성", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("FEDFUNDS", "미국 연방기금금리", "policy", "percent", "monthly", "통화정책 레벨", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("CPIAUCSL", "미국 CPI", "inflation", "index", "monthly", "소비자물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
    FredSeries("CPILFESL", "미국 Core CPI", "inflation", "index", "monthly", "근원 물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
    FredSeries("PPIACO", "미국 PPI", "inflation", "index", "monthly", "생산자물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
    FredSeries("UNRATE", "미국 실업률", "employment", "percent", "monthly", "경기 둔화와 고용 여건", "higher_is_risk_off", "level_change_zscore"),
    FredSeries("PAYEMS", "미국 비농업고용", "employment", "thousands", "monthly", "고용 모멘텀", "higher_momentum_is_risk_on", "mom_zscore"),
    FredSeries("CES0500000003", "미국 민간 평균시간당임금", "employment", "usd_per_hour", "monthly", "임금 물가 압력", "higher_momentum_is_risk_off", "yoy_mom_zscore"),
)


def read_fred_api_key(path: Path | None = None) -> str:
    key_path = path or DEFAULT_FRED_API_KEY_PATH
    api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError(f"FRED API key file is empty: {key_path}")
    return api_key


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _request_json(path: str, params: dict[str, str | int]) -> dict:
    query = urlencode({**params, "file_type": "json"})
    url = f"{FRED_API_BASE}/{path}?{query}"
    request = Request(url, headers={"User-Agent": "QuantMarket/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_observations(
    *,
    api_key: str,
    series_id: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    payload = _request_json(
        "series/observations",
        {
            "api_key": api_key,
            "series_id": series_id,
            "observation_start": start_date,
            "observation_end": end_date,
        },
    )
    return list(payload.get("observations") or [])


def parse_float(value: str | None) -> float | None:
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def upsert_series_registry(con, series_list: Iterable[FredSeries], *, timestamp: str) -> None:
    rows = [
        {
            "source": SOURCE,
            "series_id": item.series_id,
            "display_name": item.display_name,
            "category": item.category,
            "unit": item.unit,
            "frequency": item.frequency,
            "market_relevance": item.market_relevance,
            "score_direction": item.score_direction,
            "transform_hint": item.transform_hint,
            "is_active": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for item in series_list
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


def upsert_observations(con, *, series_id: str, observations: Iterable[dict], timestamp: str) -> int:
    rows = []
    for obs in observations:
        rows.append(
            {
                "source": SOURCE,
                "series_id": series_id,
                "asof_date": obs.get("date"),
                "value": parse_float(obs.get("value")),
                "raw_value": obs.get("value"),
                "realtime_start": obs.get("realtime_start") or obs.get("date"),
                "realtime_end": obs.get("realtime_end") or obs.get("date"),
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


def collect_fred_series(
    *,
    db_path: Path,
    api_key_path: Path,
    start_date: str,
    end_date: str,
    series_ids: list[str] | None = None,
    sleep_seconds: float = 0.2,
) -> dict:
    init_global_context_db(db_path)
    timestamp = now_utc_iso()
    run_id = timestamp.replace(":", "").replace("-", "")
    api_key = read_fred_api_key(api_key_path)
    selected = [
        item
        for item in DEFAULT_FRED_SERIES
        if not series_ids or item.series_id in set(series_ids)
    ]
    with connect_global_context(db_path) as con:
        con.execute(
            """
            INSERT INTO global_collection_run_log (
                run_id, source, started_at, status, start_date, end_date,
                requested_series_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, SOURCE, timestamp, "running", start_date, end_date, len(selected)),
        )
        con.commit()
        try:
            upsert_series_registry(con, selected, timestamp=timestamp)
            total_rows = 0
            errors: list[str] = []
            for item in selected:
                try:
                    observations = fetch_observations(
                        api_key=api_key,
                        series_id=item.series_id,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    total_rows += upsert_observations(
                        con,
                        series_id=item.series_id,
                        observations=observations,
                        timestamp=timestamp,
                    )
                    con.commit()
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
                except Exception as exc:
                    errors.append(f"{item.series_id}: {exc}")
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
                "series_count": len(selected),
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
