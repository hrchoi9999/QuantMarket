from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


KST = timezone(timedelta(hours=9))

SCHEMA_VERSION = "macro_surprise_daily.v1"
FEATURE_VERSION = "qm_macro_surprise_proxy_v1_20260514"
MONTHLY_RELEASE_LAG_DAYS = 21
ROLLING_EXPECTATION_WINDOW = 24
MIN_EXPECTATION_PERIODS = 12

SERIES_SPECS = {
    "CPIAUCSL": {
        "event_group": "inflation",
        "event_type": "CPI",
        "metric": "yoy",
        "risk_off_sign": 1.0,
    },
    "CPILFESL": {
        "event_group": "inflation",
        "event_type": "Core CPI",
        "metric": "yoy",
        "risk_off_sign": 1.0,
    },
    "PPIACO": {
        "event_group": "inflation",
        "event_type": "PPI",
        "metric": "yoy",
        "risk_off_sign": 1.0,
    },
    "CES0500000003": {
        "event_group": "wage",
        "event_type": "Average Hourly Earnings",
        "metric": "yoy",
        "risk_off_sign": 1.0,
    },
    "PAYEMS": {
        "event_group": "employment",
        "event_type": "Payrolls",
        "metric": "mom_diff",
        "risk_off_sign": -1.0,
    },
    "UNRATE": {
        "event_group": "employment",
        "event_type": "Unemployment",
        "metric": "mom_diff",
        "risk_off_sign": 1.0,
    },
    "FEDFUNDS": {
        "event_group": "policy",
        "event_type": "Fed Funds",
        "metric": "mom_diff",
        "risk_off_sign": 1.0,
    },
}


@dataclass(frozen=True)
class MacroSurpriseResult:
    event_csv: Path
    context_csv: Path
    report_json: Path
    report_md: Path
    generated_at: str
    event_row_count: int
    context_row_count: int


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


def _load_observations(global_context_db: Path) -> pd.DataFrame:
    series_ids = tuple(SERIES_SPECS)
    placeholders = ",".join("?" for _ in series_ids)
    return _read_sql(
        global_context_db,
        f"""
        SELECT series_id, asof_date AS source_observation_date, value
        FROM global_observation
        WHERE source='FRED'
          AND series_id IN ({placeholders})
          AND value IS NOT NULL
        ORDER BY series_id, asof_date
        """,
        series_ids,
    )


def _metric_values(group: pd.DataFrame, metric: str) -> pd.Series:
    value = pd.to_numeric(group["value"], errors="coerce")
    if metric == "yoy":
        return value / value.shift(12) - 1.0
    if metric == "mom_pct":
        return value / value.shift(1) - 1.0
    if metric == "mom_diff":
        return value - value.shift(1)
    raise ValueError(f"Unknown macro surprise metric: {metric}")


def _direction_label(value: float | None, *, positive_label: str = "upside", negative_label: str = "downside") -> str | None:
    if value is None or pd.isna(value):
        return None
    if value > 0:
        return positive_label
    if value < 0:
        return negative_label
    return "inline"


def _risk_bias_label(risk_off_zscore: float | None) -> str | None:
    if risk_off_zscore is None or pd.isna(risk_off_zscore):
        return None
    if risk_off_zscore >= 1.0:
        return "risk_off_surprise"
    if risk_off_zscore <= -1.0:
        return "risk_on_surprise"
    return "mixed_or_inline"


def _build_event_rows(global_context_db: Path, spine_dates: pd.Series, generated_at: str) -> pd.DataFrame:
    obs = _load_observations(global_context_db)
    if obs.empty:
        return pd.DataFrame()
    spine = [pd.Timestamp(x) for x in spine_dates]
    frames = []
    for series_id, group in obs.groupby("series_id"):
        spec = SERIES_SPECS[series_id]
        g = group.sort_values("source_observation_date").copy()
        g["source_observation_date"] = pd.to_datetime(g["source_observation_date"]).dt.strftime("%Y-%m-%d")
        g["actual_value"] = pd.to_numeric(g["value"], errors="coerce")
        g["previous_value"] = g["actual_value"].shift(1)
        g["actual_mom_change"] = g["actual_value"] - g["previous_value"]
        g["actual_pct_change"] = g["actual_value"] / g["previous_value"] - 1.0
        g["actual_metric_value"] = _metric_values(g, str(spec["metric"]))
        g["expected_proxy_value"] = (
            g["actual_metric_value"]
            .shift(1)
            .rolling(ROLLING_EXPECTATION_WINDOW, min_periods=MIN_EXPECTATION_PERIODS)
            .mean()
        )
        proxy_std = (
            g["actual_metric_value"]
            .shift(1)
            .rolling(ROLLING_EXPECTATION_WINDOW, min_periods=MIN_EXPECTATION_PERIODS)
            .std(ddof=0)
            .replace(0.0, np.nan)
        )
        g["proxy_surprise_value"] = g["actual_metric_value"] - g["expected_proxy_value"]
        g["proxy_surprise_zscore"] = g["proxy_surprise_value"] / proxy_std
        g["risk_off_surprise_zscore"] = g["proxy_surprise_zscore"] * float(spec["risk_off_sign"])
        g["surprise_direction_label"] = g["proxy_surprise_zscore"].map(_direction_label)
        g["risk_bias_label"] = g["risk_off_surprise_zscore"].map(_risk_bias_label)
        g["asof_date"] = [
            _first_spine_date_on_or_after(
                spine,
                pd.Timestamp(source_date) + pd.Timedelta(days=MONTHLY_RELEASE_LAG_DAYS),
            )
            for source_date in g["source_observation_date"]
        ]
        g["source"] = "FRED"
        g["source_series_id"] = series_id
        g["event_group"] = str(spec["event_group"])
        g["event_type"] = str(spec["event_type"])
        g["metric_type"] = str(spec["metric"])
        g["consensus_value"] = np.nan
        g["consensus_source"] = None
        g["consensus_surprise_value"] = np.nan
        g["has_consensus_flag"] = 0
        g["pit_lag_rule"] = f"monthly source observation + {MONTHLY_RELEASE_LAG_DAYS} calendar days, then next market date"
        g["feature_version"] = FEATURE_VERSION
        g["schema_version"] = SCHEMA_VERSION
        g["generated_at"] = generated_at
        frames.append(g)
    events = pd.concat(frames, ignore_index=True)
    events = events[events["asof_date"].notna()].copy()
    output_cols = [
        "asof_date",
        "source_observation_date",
        "source",
        "source_series_id",
        "event_group",
        "event_type",
        "metric_type",
        "actual_value",
        "previous_value",
        "actual_mom_change",
        "actual_pct_change",
        "actual_metric_value",
        "expected_proxy_value",
        "proxy_surprise_value",
        "proxy_surprise_zscore",
        "risk_off_surprise_zscore",
        "surprise_direction_label",
        "risk_bias_label",
        "consensus_value",
        "consensus_source",
        "consensus_surprise_value",
        "has_consensus_flag",
        "pit_lag_rule",
        "feature_version",
        "schema_version",
        "generated_at",
    ]
    return events[output_cols].sort_values(["asof_date", "source_series_id"]).reset_index(drop=True)


def _clip_score(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(max(-1.0, min(1.0, value / 3.0)))


def _latest_group_z(events: pd.DataFrame, group: str) -> pd.DataFrame:
    sample = events[events["event_group"] == group].dropna(subset=["risk_off_surprise_zscore"]).copy()
    if sample.empty:
        return pd.DataFrame(columns=["asof_date", f"{group}_surprise_risk_off_score"])
    sample["signed_score"] = sample["risk_off_surprise_zscore"].map(_clip_score)
    return (
        sample.groupby("asof_date", as_index=False)["signed_score"]
        .mean()
        .rename(columns={"signed_score": f"{group}_surprise_risk_off_score"})
    )


def _build_context(spine: pd.DataFrame, events: pd.DataFrame, generated_at: str) -> pd.DataFrame:
    out = spine.copy()
    if events.empty:
        event_groups: list[str] = []
    else:
        event_groups = sorted(events["event_group"].dropna().unique())
    for group in ["inflation", "employment", "policy", "wage"]:
        out = out.merge(_latest_group_z(events, group), on="asof_date", how="left")

    if events.empty:
        out["macro_surprise_event_count"] = 0
        out["macro_surprise_has_consensus_count"] = 0
        out["macro_surprise_abs_zscore_max"] = np.nan
        out["macro_surprise_risk_off_score"] = np.nan
    else:
        event_count = events.groupby("asof_date").size().rename("macro_surprise_event_count").reset_index()
        consensus_count = events.groupby("asof_date")["has_consensus_flag"].sum().rename("macro_surprise_has_consensus_count").reset_index()
        max_abs = (
            events.groupby("asof_date")["proxy_surprise_zscore"]
            .apply(lambda s: s.abs().max())
            .rename("macro_surprise_abs_zscore_max")
            .reset_index()
        )
        risk_score = (
            events.dropna(subset=["risk_off_surprise_zscore"])
            .assign(signed_score=lambda df: df["risk_off_surprise_zscore"].map(_clip_score))
            .groupby("asof_date")["signed_score"]
            .mean()
            .rename("macro_surprise_risk_off_score")
            .reset_index()
        )
        out = out.merge(event_count, on="asof_date", how="left")
        out = out.merge(consensus_count, on="asof_date", how="left")
        out = out.merge(max_abs, on="asof_date", how="left")
        out = out.merge(risk_score, on="asof_date", how="left")
    out["macro_surprise_event_count"] = out["macro_surprise_event_count"].fillna(0).astype(int)
    out["macro_surprise_has_consensus_count"] = out["macro_surprise_has_consensus_count"].fillna(0).astype(int)
    out["macro_surprise_consensus_available_flag"] = (out["macro_surprise_has_consensus_count"] > 0).astype(int)
    out["macro_surprise_proxy_available_flag"] = (out["macro_surprise_event_count"] > 0).astype(int)
    out["macro_surprise_pressure_score"] = pd.to_numeric(out["macro_surprise_risk_off_score"], errors="coerce").clip(lower=0.0, upper=1.0)
    out["macro_surprise_relief_score"] = (-pd.to_numeric(out["macro_surprise_risk_off_score"], errors="coerce")).clip(lower=0.0, upper=1.0)
    out["macro_surprise_event_density_63d"] = out["macro_surprise_event_count"].rolling(63, min_periods=1).sum()
    out["macro_surprise_pit_lag_rule"] = f"monthly source observation + {MONTHLY_RELEASE_LAG_DAYS} calendar days, then next market date"
    out["macro_surprise_source_policy"] = (
        "FRED actual-only proxy surprise. consensus_value is intentionally null until a licensed/available consensus source is connected."
    )
    out["feature_version"] = FEATURE_VERSION
    out["schema_version"] = SCHEMA_VERSION
    out["generated_at"] = generated_at
    return out.sort_values("asof_date").reset_index(drop=True)


def build_macro_surprise_daily(
    *,
    market_context_db: Path,
    global_context_db: Path,
    output_dir: Path,
    report_dir: Path,
) -> MacroSurpriseResult:
    generated_at = _now_kst()
    spine = _date_spine(market_context_db)
    events = _build_event_rows(global_context_db, spine["asof_date"], generated_at)
    context = _build_context(spine, events, generated_at)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    event_csv = output_dir / "macro_surprise_event_daily_current.csv"
    event_csv_full = output_dir / "macro_surprise_event_daily.csv"
    context_csv = output_dir / "macro_surprise_context_daily_current.csv"
    context_csv_full = output_dir / "macro_surprise_context_daily.csv"
    report_json = report_dir / "macro_surprise_daily_latest.json"
    report_md = report_dir / "macro_surprise_daily_latest.md"
    events.to_csv(event_csv, index=False, encoding="utf-8-sig")
    events.to_csv(event_csv_full, index=False, encoding="utf-8-sig")
    context.to_csv(context_csv, index=False, encoding="utf-8-sig")
    context.to_csv(context_csv_full, index=False, encoding="utf-8-sig")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS macro_surprise_event_daily")
        con.execute("DROP TABLE IF EXISTS macro_surprise_context_daily")
        events.to_sql("macro_surprise_event_daily", con, if_exists="replace", index=False)
        context.to_sql("macro_surprise_context_daily", con, if_exists="replace", index=False)
        con.commit()

    date_range = {
        "start": str(context["asof_date"].min()) if not context.empty else None,
        "end": str(context["asof_date"].max()) if not context.empty else None,
    }
    event_group_counts = (
        events["event_group"].value_counts(dropna=False).rename_axis("event_group").reset_index(name="rows").to_dict("records")
        if not events.empty
        else []
    )
    report = {
        "source_name": "QuantMarket macro surprise daily",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "row_counts": {
            "macro_surprise_event_daily": int(len(events)),
            "macro_surprise_context_daily": int(len(context)),
        },
        "date_range": date_range,
        "event_group_counts": event_group_counts,
        "consensus_available": False,
        "source_paths": {
            "market_context_db": str(market_context_db),
            "global_context_db_readonly": str(global_context_db),
        },
        "output_paths": {
            "event_csv": str(event_csv),
            "context_csv": str(context_csv),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
        "pit_policy": context["macro_surprise_pit_lag_rule"].iloc[0] if not context.empty else None,
        "notes": [
            "V1 is actual-only FRED proxy surprise; consensus_value remains null.",
            "proxy_surprise_zscore compares the released metric to a prior rolling expectation using only earlier observations.",
            "risk_off_surprise_zscore converts each event type into a common risk-off direction.",
        ],
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# QuantMarket Macro Surprise Daily",
        "",
        f"- generated_at: {generated_at}",
        f"- schema_version: {SCHEMA_VERSION}",
        f"- feature_version: {FEATURE_VERSION}",
        f"- event rows: {len(events)}",
        f"- context rows: {len(context)}",
        f"- date_range: {date_range['start']} ~ {date_range['end']}",
        f"- context_csv: `{context_csv}`",
        f"- event_csv: `{event_csv}`",
        "",
        "## Event Group Counts",
        "",
    ]
    lines.extend(f"- {row['event_group']}: {row['rows']}" for row in event_group_counts)
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["macro_surprise_event_daily"] = event_csv.name
    manifest.setdefault("canonical_files", {})["macro_surprise_context_daily"] = context_csv.name
    manifest.setdefault("tables", {})["macro_surprise_event_daily"] = {
        "file": event_csv.name,
        "row_count": int(len(events)),
        "start_date": str(events["asof_date"].min()) if not events.empty else None,
        "end_date": str(events["asof_date"].max()) if not events.empty else None,
        "duplicate_key_count": int(events.duplicated(["asof_date", "source_series_id", "source_observation_date"], keep=False).sum()) if not events.empty else 0,
    }
    manifest.setdefault("tables", {})["macro_surprise_context_daily"] = {
        "file": context_csv.name,
        "row_count": int(len(context)),
        "start_date": date_range["start"],
        "end_date": date_range["end"],
        "duplicate_key_count": int(context.duplicated(["asof_date"], keep=False).sum()) if not context.empty else 0,
    }
    manifest.setdefault("warnings", []).append(
        "macro_surprise_daily v1 is actual-only proxy surprise. consensus fields are reserved but null."
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    schema_path = output_dir / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {"tables": {}}
    for table_name, frame in {
        "macro_surprise_event_daily": events,
        "macro_surprise_context_daily": context,
    }.items():
        schema.setdefault("tables", {})[table_name] = {
            "primary_key": ["asof_date", "source_series_id", "source_observation_date"]
            if table_name == "macro_surprise_event_daily"
            else ["asof_date"],
            "join_keys": ["asof_date"],
            "point_in_time_policy": report["pit_policy"],
            "source_policy": "FRED actual-only proxy surprise; consensus fields reserved for future source integration.",
            "columns": [
                {"column_name": col, "data_type": str(frame[col].dtype), "nullable": bool(frame[col].isna().any())}
                for col in frame.columns
            ],
        }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    return MacroSurpriseResult(
        event_csv=event_csv,
        context_csv=context_csv,
        report_json=report_json,
        report_md=report_md,
        generated_at=generated_at,
        event_row_count=int(len(events)),
        context_row_count=int(len(context)),
    )
