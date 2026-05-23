from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


KST = timezone(timedelta(hours=9))

SCHEMA_VERSION = "macro_event_calendar_daily.v1"
FEATURE_VERSION = "qm_macro_event_calendar_flags_v1_20260514"
MONTHLY_RELEASE_LAG_DAYS = 21

MONTHLY_EVENT_MAP = {
    "CPIAUCSL": ("inflation_release_flag", "CPI"),
    "CPILFESL": ("inflation_release_flag", "Core CPI"),
    "PPIACO": ("producer_price_release_flag", "PPI"),
    "UNRATE": ("employment_release_flag", "Unemployment"),
    "PAYEMS": ("employment_release_flag", "Payrolls"),
    "CES0500000003": ("wage_release_flag", "Average Hourly Earnings"),
    "FEDFUNDS": ("policy_rate_release_flag", "Fed Funds"),
}

DAILY_SHOCK_SPECS = {
    "VIXCLS": ("vix_shock_event_flag", "VIX", "pct", 0.10),
    "DGS10": ("rate_shock_event_flag", "US10Y", "diff", 0.10),
    "DEXKOUS": ("fx_shock_event_flag", "USDKRW", "pct", 0.01),
    "DCOILWTICO": ("commodity_shock_event_flag", "WTI", "pct", 0.03),
    "BAMLH0A0HYM2": ("credit_shock_event_flag", "HY spread", "diff", 0.10),
}


@dataclass(frozen=True)
class MacroEventCalendarResult:
    output_csv: Path
    report_json: Path
    report_md: Path
    generated_at: str
    row_count: int


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _read_sql(path: Path, sql: str, params: tuple = ()) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    with sqlite3.connect(path) as con:
        return pd.read_sql_query(sql, con, params=params)


def _date_spine(market_context_db: Path) -> pd.DataFrame:
    dates = _read_sql(
        market_context_db,
        """
        SELECT DISTINCT asof_date
        FROM market_context_daily
        WHERE asof_date IS NOT NULL
        ORDER BY asof_date
        """,
    )
    if dates.empty:
        raise RuntimeError("market_context_daily date spine is required.")
    dates["asof_date"] = pd.to_datetime(dates["asof_date"]).dt.strftime("%Y-%m-%d")
    return dates


def _first_spine_date_on_or_after(spine: list[pd.Timestamp], target: pd.Timestamp) -> str | None:
    for item in spine:
        if item >= target:
            return item.strftime("%Y-%m-%d")
    return None


def _monthly_events(global_context_db: Path, spine_dates: pd.Series) -> pd.DataFrame:
    series_ids = tuple(MONTHLY_EVENT_MAP)
    placeholders = ",".join("?" for _ in series_ids)
    obs = _read_sql(
        global_context_db,
        f"""
        SELECT series_id, asof_date, value
        FROM global_observation
        WHERE source='FRED'
          AND series_id IN ({placeholders})
          AND value IS NOT NULL
        ORDER BY series_id, asof_date
        """,
        series_ids,
    )
    if obs.empty:
        return pd.DataFrame(columns=["asof_date", "event_flag", "event_type"])

    spine = [pd.Timestamp(x) for x in spine_dates]
    rows: list[dict] = []
    for row in obs.to_dict("records"):
        source_date = pd.Timestamp(row["asof_date"])
        target = source_date + pd.Timedelta(days=MONTHLY_RELEASE_LAG_DAYS)
        asof_date = _first_spine_date_on_or_after(spine, target)
        if not asof_date:
            continue
        flag, event_type = MONTHLY_EVENT_MAP[row["series_id"]]
        rows.append(
            {
                "asof_date": asof_date,
                "event_flag": flag,
                "event_type": event_type,
                "source_series_id": row["series_id"],
                "source_observation_date": source_date.strftime("%Y-%m-%d"),
                "pit_lag_rule": f"monthly source observation + {MONTHLY_RELEASE_LAG_DAYS} calendar days, then next market date",
            }
        )
    return pd.DataFrame(rows)


def _daily_shock_events(global_context_db: Path, spine_dates: pd.Series) -> pd.DataFrame:
    series_ids = tuple(DAILY_SHOCK_SPECS)
    placeholders = ",".join("?" for _ in series_ids)
    obs = _read_sql(
        global_context_db,
        f"""
        SELECT series_id, asof_date, value
        FROM global_observation
        WHERE source='FRED'
          AND series_id IN ({placeholders})
          AND value IS NOT NULL
        ORDER BY series_id, asof_date
        """,
        series_ids,
    )
    if obs.empty:
        return pd.DataFrame(columns=["asof_date", "event_flag", "event_type"])

    spine = [pd.Timestamp(x) for x in spine_dates]
    rows: list[dict] = []
    for series_id, group in obs.groupby("series_id"):
        flag, event_type, mode, threshold = DAILY_SHOCK_SPECS[series_id]
        group = group.sort_values("asof_date").copy()
        group["prev_value"] = group["value"].shift(1)
        if mode == "pct":
            group["shock_value"] = group["value"] / group["prev_value"] - 1.0
            shock = group["shock_value"].abs() >= threshold
        else:
            group["shock_value"] = group["value"] - group["prev_value"]
            shock = group["shock_value"].abs() >= threshold
        for row in group[shock.fillna(False)].to_dict("records"):
            source_date = pd.Timestamp(row["asof_date"])
            asof_date = _first_spine_date_on_or_after(spine, source_date + pd.Timedelta(days=1))
            if not asof_date:
                continue
            rows.append(
                {
                    "asof_date": asof_date,
                    "event_flag": flag,
                    "event_type": event_type,
                    "source_series_id": series_id,
                    "source_observation_date": source_date.strftime("%Y-%m-%d"),
                    "shock_value": round(float(row["shock_value"]), 8),
                    "pit_lag_rule": "daily source date + 1 calendar day, then next market date",
                }
            )
    return pd.DataFrame(rows)


def _add_window_features(out: pd.DataFrame, scheduled_dates: set[str]) -> pd.DataFrame:
    dates = list(out["asof_date"])
    scheduled_idx = [idx for idx, date in enumerate(dates) if date in scheduled_dates]
    pre = set()
    post = set()
    risk = set(scheduled_dates)
    for idx in scheduled_idx:
        if idx - 1 >= 0:
            pre.add(dates[idx - 1])
            risk.add(dates[idx - 1])
        if idx + 1 < len(dates):
            post.add(dates[idx + 1])
            risk.add(dates[idx + 1])
    out["pre_macro_event_1d_flag"] = out["asof_date"].isin(pre).astype(int)
    out["post_macro_event_1d_flag"] = out["asof_date"].isin(post).astype(int)
    out["macro_event_risk_window_flag"] = out["asof_date"].isin(risk).astype(int)

    scheduled_positions = np.array(scheduled_idx, dtype=int)
    days_since = []
    days_to_next = []
    for idx in range(len(dates)):
        if len(scheduled_positions) == 0:
            days_since.append(np.nan)
            days_to_next.append(np.nan)
            continue
        prev_positions = scheduled_positions[scheduled_positions <= idx]
        next_positions = scheduled_positions[scheduled_positions >= idx]
        days_since.append(float(idx - prev_positions[-1]) if len(prev_positions) else np.nan)
        days_to_next.append(float(next_positions[0] - idx) if len(next_positions) else np.nan)
    out["days_since_scheduled_macro_event"] = days_since
    out["days_to_next_scheduled_macro_event"] = days_to_next
    return out


def build_macro_event_calendar_daily(
    *,
    market_context_db: Path,
    global_context_db: Path,
    output_dir: Path,
    report_dir: Path,
) -> MacroEventCalendarResult:
    generated_at = _now_kst()
    spine = _date_spine(market_context_db)
    out = spine.copy()
    flag_columns = sorted(set(MONTHLY_EVENT_MAP.values()) | set(DAILY_SHOCK_SPECS.values()))
    flag_columns = [item[0] for item in flag_columns]
    for col in flag_columns:
        out[col] = 0

    monthly = _monthly_events(global_context_db, out["asof_date"])
    daily = _daily_shock_events(global_context_db, out["asof_date"])
    events = pd.concat([monthly, daily], ignore_index=True)
    scheduled_dates = set(monthly["asof_date"].dropna().astype(str)) if not monthly.empty else set()

    if not events.empty:
        for event_flag, group in events.groupby("event_flag"):
            counts = group.groupby("asof_date").size().rename(event_flag).reset_index()
            out = out.drop(columns=[event_flag]).merge(counts, on="asof_date", how="left")
            out[event_flag] = out[event_flag].fillna(0).astype(int)

    scheduled_flags = [
        "employment_release_flag",
        "inflation_release_flag",
        "policy_rate_release_flag",
        "producer_price_release_flag",
        "wage_release_flag",
    ]
    shock_flags = [
        "commodity_shock_event_flag",
        "credit_shock_event_flag",
        "fx_shock_event_flag",
        "rate_shock_event_flag",
        "vix_shock_event_flag",
    ]
    out["scheduled_macro_event_count"] = out[[c for c in scheduled_flags if c in out.columns]].sum(axis=1).astype(int)
    out["macro_shock_event_count"] = out[[c for c in shock_flags if c in out.columns]].sum(axis=1).astype(int)
    out["macro_event_count"] = out["scheduled_macro_event_count"] + out["macro_shock_event_count"]
    out["major_macro_event_flag"] = (out["macro_event_count"] > 0).astype(int)
    out = _add_window_features(out, scheduled_dates)
    out["macro_event_density_5d"] = out["macro_event_count"].rolling(5, min_periods=1).sum()
    out["macro_event_pressure_score"] = (
        0.15 * out["scheduled_macro_event_count"]
        + 0.35 * out["macro_shock_event_count"]
        + 0.10 * out["macro_event_risk_window_flag"]
    ).clip(0.0, 1.0)
    out["macro_event_source_count"] = 0
    if not events.empty:
        out = out.merge(
            events.groupby("asof_date")["source_series_id"].nunique().rename("macro_event_source_count").reset_index(),
            on="asof_date",
            how="left",
            suffixes=("", "_new"),
        )
        if "macro_event_source_count_new" in out.columns:
            out["macro_event_source_count"] = out["macro_event_source_count_new"].fillna(0).astype(int)
            out = out.drop(columns=["macro_event_source_count_new"])
    out["macro_event_pit_lag_rule"] = "monthly events use conservative source month +21d; daily shocks use source date +1d; both align to next market date"
    out["feature_version"] = FEATURE_VERSION
    out["schema_version"] = SCHEMA_VERSION
    out["generated_at"] = generated_at

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "macro_event_calendar_daily_current.csv"
    output_csv_full = output_dir / "macro_event_calendar_daily.csv"
    report_json = report_dir / "macro_event_calendar_daily_latest.json"
    report_md = report_dir / "macro_event_calendar_daily_latest.md"
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    out.to_csv(output_csv_full, index=False, encoding="utf-8-sig")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS macro_event_calendar_daily")
        out.to_sql("macro_event_calendar_daily", con, if_exists="replace", index=False)
        con.commit()

    duplicate_key_count = int(out.duplicated(["asof_date"], keep=False).sum())
    date_range = {
        "start": str(out["asof_date"].min()) if not out.empty else None,
        "end": str(out["asof_date"].max()) if not out.empty else None,
    }
    event_summary = {
        "scheduled_event_days": int((out["scheduled_macro_event_count"] > 0).sum()),
        "shock_event_days": int((out["macro_shock_event_count"] > 0).sum()),
        "risk_window_days": int(out["macro_event_risk_window_flag"].sum()),
        "major_macro_event_days": int(out["major_macro_event_flag"].sum()),
    }
    report = {
        "source_name": "QuantMarket macro event calendar daily",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "primary_key": ["asof_date"],
        "date_range": date_range,
        "row_count": int(len(out)),
        "duplicate_key_count": duplicate_key_count,
        "event_summary": event_summary,
        "source_paths": {
            "market_context_db": str(market_context_db),
            "global_context_db_readonly": str(global_context_db),
        },
        "output_paths": {
            "db": str(market_context_db),
            "table": "macro_event_calendar_daily",
            "csv": str(output_csv),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
        "pit_policy": out["macro_event_pit_lag_rule"].iloc[0] if not out.empty else None,
        "notes": [
            "V1 starts with event flags only; no actual macro surprise value is used.",
            "Future days-to-next is calendar metadata, not macro outcome data.",
            "Monthly FRED events use the same conservative 21-day lag rule as global_context_daily.",
        ],
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# QuantMarket Macro Event Calendar Daily",
        "",
        f"- generated_at: {generated_at}",
        f"- schema_version: {SCHEMA_VERSION}",
        f"- feature_version: {FEATURE_VERSION}",
        f"- rows: {len(out)}",
        f"- date_range: {date_range['start']} ~ {date_range['end']}",
        f"- csv: `{output_csv}`",
        "",
        "## Event Summary",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in event_summary.items())
    lines.extend(["", "## PIT Policy", "", f"- {report['pit_policy']}", ""])
    report_md.write_text("\n".join(lines), encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["macro_event_calendar_daily"] = output_csv.name
    manifest.setdefault("tables", {})["macro_event_calendar_daily"] = {
        "file": output_csv.name,
        "row_count": int(len(out)),
        "start_date": date_range["start"],
        "end_date": date_range["end"],
        "duplicate_key_count": duplicate_key_count,
        "event_summary": event_summary,
    }
    manifest.setdefault("warnings", []).append(
        "macro_event_calendar_daily v1 is event-flag only; it does not include realized macro surprise values."
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    schema_path = output_dir / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {"tables": {}}
    schema.setdefault("tables", {})["macro_event_calendar_daily"] = {
        "primary_key": ["asof_date"],
        "join_keys": ["asof_date"],
        "point_in_time_policy": report["pit_policy"],
        "columns": [
            {"column_name": col, "data_type": str(out[col].dtype), "nullable": bool(out[col].isna().any())}
            for col in out.columns
        ],
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    return MacroEventCalendarResult(
        output_csv=output_csv,
        report_json=report_json,
        report_md=report_md,
        generated_at=generated_at,
        row_count=int(len(out)),
    )
