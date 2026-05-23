from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .global_context_db import connect_global_context, init_global_context_db


SCHEMA_VERSION = "global_context_daily_v1"
FEATURE_VERSION = "fred_treasury_bls_global_context_v3_20260519"
MONTHLY_RELEASE_LAG_DAYS = 21
TREASURY_RATE_SERIES = ("DGS3MO", "DGS2", "DGS10", "DGS30")
BLS_MONTHLY_SERIES = ("CPIAUCSL", "CPILFESL", "PPIACO", "UNRATE", "PAYEMS", "CES0500000003")

DAILY_SERIES = (
    "DGS3MO",
    "DGS2",
    "DGS10",
    "DGS30",
    "DFII10",
    "T10YIE",
    "VIXCLS",
    "BAMLH0A0HYM2",
    "BAMLC0A0CM",
    "DTWEXBGS",
    "DEXKOUS",
    "DCOILWTICO",
    "GVZCLS",
)

MONTHLY_SERIES = (
    "FEDFUNDS",
    "CPIAUCSL",
    "CPILFESL",
    "PPIACO",
    "UNRATE",
    "PAYEMS",
    "CES0500000003",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def clamp(value: float | None, lower: float = -3.0, upper: float = 3.0) -> float | None:
    if value is None or math.isnan(value):
        return None
    return max(lower, min(upper, value))


def mean(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def pct_change(current: float | None, prev: float | None) -> float | None:
    if current is None or prev in (None, 0):
        return None
    return current / prev - 1.0


def diff(current: float | None, prev: float | None) -> float | None:
    if current is None or prev is None:
        return None
    return current - prev


def zscore(values: list[float | None], current_index: int, window: int = 252) -> float | None:
    start = max(0, current_index - window + 1)
    sample = [v for v in values[start : current_index + 1] if v is not None]
    if len(sample) < 30:
        return None
    mu = sum(sample) / len(sample)
    variance = sum((v - mu) ** 2 for v in sample) / len(sample)
    sigma = math.sqrt(variance)
    current = values[current_index]
    if current is None or sigma == 0:
        return None
    return clamp((current - mu) / sigma)


def rolling_change_zscore(values: list[float | None], current_index: int, lag: int, window: int = 252) -> float | None:
    changes: list[float | None] = []
    for idx in range(len(values)):
        if idx < lag:
            changes.append(None)
        else:
            changes.append(diff(values[idx], values[idx - lag]))
    return zscore(changes, current_index, window=window)


def _monthly_available_cutoff(asof_date: str) -> str:
    """Use monthly macro values only after a conservative public-release lag."""
    return (datetime.fromisoformat(asof_date) - timedelta(days=MONTHLY_RELEASE_LAG_DAYS)).date().isoformat()


def trailing_monthly_value(monthly: dict[str, dict[str, float | None]], series_id: str, asof_date: str) -> float | None:
    series = monthly.get(series_id) or {}
    cutoff = _monthly_available_cutoff(asof_date)
    candidates = [date for date in series if date <= cutoff]
    if not candidates:
        return None
    return series[max(candidates)]


def trailing_monthly_yoy(monthly: dict[str, dict[str, float | None]], series_id: str, asof_date: str) -> float | None:
    series = monthly.get(series_id) or {}
    cutoff = _monthly_available_cutoff(asof_date)
    candidates = sorted(date for date in series if date <= cutoff)
    if not candidates:
        return None
    latest = candidates[-1]
    latest_index = candidates.index(latest)
    if latest_index < 12:
        return None
    return pct_change(series.get(latest), series.get(candidates[latest_index - 12]))


def trailing_monthly_3m_change(monthly: dict[str, dict[str, float | None]], series_id: str, asof_date: str) -> float | None:
    series = monthly.get(series_id) or {}
    cutoff = _monthly_available_cutoff(asof_date)
    candidates = sorted(date for date in series if date <= cutoff)
    if not candidates:
        return None
    latest = candidates[-1]
    latest_index = candidates.index(latest)
    if latest_index < 3:
        return None
    return diff(series.get(latest), series.get(candidates[latest_index - 3]))


def load_series(con, series_ids: tuple[str, ...]) -> dict[str, dict[str, float | None]]:
    placeholders = ",".join("?" for _ in series_ids)
    rows = con.execute(
        f"""
        SELECT series_id, asof_date, value
        FROM global_observation
        WHERE source = 'FRED'
          AND series_id IN ({placeholders})
        ORDER BY asof_date
        """,
        series_ids,
    ).fetchall()
    data: dict[str, dict[str, float | None]] = {series_id: {} for series_id in series_ids}
    for row in rows:
        data[row["series_id"]][row["asof_date"]] = row["value"]
    treasury_ids = tuple(series_id for series_id in series_ids if series_id in TREASURY_RATE_SERIES)
    if treasury_ids:
        treasury_placeholders = ",".join("?" for _ in treasury_ids)
        treasury_rows = con.execute(
            f"""
            SELECT series_id, asof_date, value
            FROM global_observation
            WHERE source = 'TREASURY'
              AND series_id IN ({treasury_placeholders})
              AND value IS NOT NULL
            ORDER BY asof_date
            """,
            treasury_ids,
        ).fetchall()
        for row in treasury_rows:
            data[row["series_id"]][row["asof_date"]] = row["value"]
    bls_ids = tuple(series_id for series_id in series_ids if series_id in BLS_MONTHLY_SERIES)
    if bls_ids:
        bls_placeholders = ",".join("?" for _ in bls_ids)
        bls_rows = con.execute(
            f"""
            SELECT series_id, asof_date, value
            FROM global_observation
            WHERE source = 'BLS'
              AND series_id IN ({bls_placeholders})
              AND value IS NOT NULL
            ORDER BY asof_date
            """,
            bls_ids,
        ).fetchall()
        for row in bls_rows:
            data[row["series_id"]][row["asof_date"]] = row["value"]
    return data


def forward_fill_daily(daily: dict[str, dict[str, float | None]]) -> tuple[list[str], dict[str, list[float | None]]]:
    all_dates = sorted({date for series in daily.values() for date in series})
    filled: dict[str, list[float | None]] = {}
    for series_id, values in daily.items():
        last_value: float | None = None
        filled_values: list[float | None] = []
        for asof_date in all_dates:
            if asof_date in values and values[asof_date] is not None:
                last_value = values[asof_date]
            filled_values.append(last_value)
        filled[series_id] = filled_values
    return all_dates, filled


def build_global_context_rows(con, *, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    daily_raw = load_series(con, DAILY_SERIES)
    monthly_raw = load_series(con, MONTHLY_SERIES)
    dates, daily = forward_fill_daily(daily_raw)
    rows: list[dict] = []
    generated_at = now_iso()

    for idx, asof_date in enumerate(dates):
        if start_date and asof_date < start_date:
            continue
        if end_date and asof_date > end_date:
            continue

        dgs10 = daily["DGS10"][idx]
        dgs2 = daily["DGS2"][idx]
        dgs3mo = daily["DGS3MO"][idx]
        dfii10 = daily["DFII10"][idx]
        t10yie = daily["T10YIE"][idx]
        vix = daily["VIXCLS"][idx]
        hy = daily["BAMLH0A0HYM2"][idx]
        ig = daily["BAMLC0A0CM"][idx]
        dxy = daily["DTWEXBGS"][idx]
        usdkrw = daily["DEXKOUS"][idx]
        wti = daily["DCOILWTICO"][idx]
        gvz = daily["GVZCLS"][idx]

        rate_pressure = mean(
            [
                zscore(daily["DGS10"], idx),
                zscore(daily["DGS2"], idx),
                zscore(daily["DFII10"], idx),
                rolling_change_zscore(daily["DGS10"], idx, lag=20),
            ]
        )
        usd_pressure = mean(
            [
                zscore(daily["DTWEXBGS"], idx),
                zscore(daily["DEXKOUS"], idx),
                rolling_change_zscore(daily["DTWEXBGS"], idx, lag=20),
            ]
        )
        credit_stress = mean(
            [
                zscore(daily["BAMLH0A0HYM2"], idx),
                zscore(daily["BAMLC0A0CM"], idx),
                rolling_change_zscore(daily["BAMLH0A0HYM2"], idx, lag=20),
            ]
        )
        risk_aversion = mean(
            [
                zscore(daily["VIXCLS"], idx),
                rolling_change_zscore(daily["VIXCLS"], idx, lag=20),
                zscore(daily["GVZCLS"], idx),
            ]
        )
        inflation_pressure = mean(
            [
                zscore(daily["T10YIE"], idx),
                trailing_monthly_yoy(monthly_raw, "CPIAUCSL", asof_date),
                trailing_monthly_yoy(monthly_raw, "CPILFESL", asof_date),
                trailing_monthly_yoy(monthly_raw, "PPIACO", asof_date),
            ]
        )
        commodity_pressure = mean(
            [
                zscore(daily["DCOILWTICO"], idx),
                rolling_change_zscore(daily["DCOILWTICO"], idx, lag=20),
            ]
        )
        external_pressure = mean(
            [
                rate_pressure,
                usd_pressure,
                credit_stress,
                risk_aversion,
                inflation_pressure,
                commodity_pressure,
            ]
        )
        global_risk_on = -external_pressure if external_pressure is not None else None

        rows.append(
            {
                "asof_date": asof_date,
                "rate_pressure_score": clamp(rate_pressure),
                "usd_pressure_score": clamp(usd_pressure),
                "credit_stress_score": clamp(credit_stress),
                "risk_aversion_score": clamp(risk_aversion),
                "inflation_pressure_score": clamp(inflation_pressure),
                "commodity_pressure_score": clamp(commodity_pressure),
                "global_risk_on_score": clamp(global_risk_on),
                "external_macro_pressure_score": clamp(external_pressure),
                "yield_curve_10y_2y": diff(dgs10, dgs2),
                "yield_curve_10y_3m": diff(dgs10, dgs3mo),
                "us_10y_rate": dgs10,
                "us_2y_rate": dgs2,
                "us_real_10y_rate": dfii10,
                "breakeven_10y": t10yie,
                "vix_level": vix,
                "hy_spread": hy,
                "ig_spread": ig,
                "dxy_level": dxy,
                "usdkrw_level": usdkrw,
                "wti_level": wti,
                "cpi_yoy": trailing_monthly_yoy(monthly_raw, "CPIAUCSL", asof_date),
                "core_cpi_yoy": trailing_monthly_yoy(monthly_raw, "CPILFESL", asof_date),
                "ppi_yoy": trailing_monthly_yoy(monthly_raw, "PPIACO", asof_date),
                "unrate": trailing_monthly_value(monthly_raw, "UNRATE", asof_date),
                "payrolls_3m_change": trailing_monthly_3m_change(monthly_raw, "PAYEMS", asof_date),
                "monthly_macro_release_lag_days": MONTHLY_RELEASE_LAG_DAYS,
                "feature_version": FEATURE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
            }
        )
    return rows


def upsert_global_context_rows(con, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join(f":{column}" for column in columns)
    updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "asof_date")
    con.executemany(
        f"""
        INSERT INTO global_context_daily ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (asof_date) DO UPDATE SET
            {updates}
        """,
        rows,
    )
    con.commit()


def write_current_outputs(*, rows: list[dict], output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "global_context_daily_current.csv"
    manifest_path = output_dir / "global_context_manifest.json"
    schema_path = output_dir / "global_context_schema.json"

    if rows:
        columns = list(rows[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    manifest = {
        "source_name": "QuantMarket global context",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": now_iso(),
        "row_count": len(rows),
        "start_date": rows[0]["asof_date"] if rows else None,
        "end_date": rows[-1]["asof_date"] if rows else None,
        "files": {
            "global_context_daily_current": csv_path.name,
            "manifest": manifest_path.name,
            "schema": schema_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    schema = {
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "primary_key": ["asof_date"],
        "timezone": "source_dates_are_us_market_or_release_dates; generated_at is local offset ISO8601",
        "score_direction": {
            "rate_pressure_score": "higher means higher rate burden/risk-off pressure",
            "usd_pressure_score": "higher means stronger USD/KRW or dollar pressure",
            "credit_stress_score": "higher means wider credit spread/risk-off pressure",
            "risk_aversion_score": "higher means higher volatility/risk-off pressure",
            "inflation_pressure_score": "higher means stronger inflation pressure",
            "commodity_pressure_score": "higher means commodity cost/volatility pressure",
            "global_risk_on_score": "higher means more favorable global risk appetite",
            "external_macro_pressure_score": "higher means less favorable external macro condition",
        },
        "null_policy": "insufficient lookback or unavailable source observations remain null",
        "pit_policy": (
            "Daily FRED/Treasury source dates are shifted by downstream AI mart to the next KST business date. "
            "U.S. nominal Treasury rates use Treasury direct observations first and FRED fallback when Treasury is unavailable. "
            "BLS monthly inflation/employment observations use BLS first and FRED fallback when BLS is unavailable. "
            f"Monthly macro observations are used only after {MONTHLY_RELEASE_LAG_DAYS} calendar days from the observation date."
        ),
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_and_store_global_context(
    *,
    db_path: Path,
    output_dir: Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    init_global_context_db(db_path)
    with connect_global_context(db_path) as con:
        rows = build_global_context_rows(con, start_date=start_date, end_date=end_date)
        upsert_global_context_rows(con, rows)
    manifest = write_current_outputs(rows=rows, output_dir=output_dir)
    manifest["db_path"] = str(db_path)
    return manifest
