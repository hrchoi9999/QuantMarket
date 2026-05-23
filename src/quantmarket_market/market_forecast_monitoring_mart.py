from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KST = timezone(timedelta(hours=9))
SCHEMA_VERSION = "market_forecast_monitoring_daily.v1"
FEATURE_VERSION = "qm_market_forecast_monitoring_v1_20260513"
ROLLING_WINDOWS = [20, 60, 120]


@dataclass(frozen=True)
class MonitoringMartResult:
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


def _read_validation(market_context_db: Path) -> pd.DataFrame:
    with _connect(market_context_db) as con:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_forecast_validation_daily'"
        ).fetchone()
        if not exists:
            raise RuntimeError("market_forecast_validation_daily table is required.")
        return pd.read_sql_query(
            """
            SELECT *
            FROM market_forecast_validation_daily
            WHERE target_available_flag = 1
            ORDER BY asof_date, market_scope, forecast_horizon
            """,
            con,
        )


def _rolling_corr(score: pd.Series, target: pd.Series, window: int) -> pd.Series:
    return score.rolling(window, min_periods=max(10, window // 2)).corr(target)


def _build_group_monitoring(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("asof_date").copy()
    numeric_columns = [
        "baseline_forecast_error",
        "ai_forecast_error",
        "market_forecast_score",
        "predicted_forward_return",
        "target_forward_return",
        "baseline_direction_hit_flag",
        "ai_direction_hit_flag",
    ]
    for column in numeric_columns:
        g[column] = pd.to_numeric(g[column], errors="coerce")
    g["baseline_abs_error"] = g["baseline_forecast_error"].abs()
    g["ai_abs_error"] = g["ai_forecast_error"].abs()
    for window in ROLLING_WINDOWS:
        g[f"baseline_corr_{window}d"] = _rolling_corr(g["market_forecast_score"], g["target_forward_return"], window)
        g[f"ai_corr_{window}d"] = _rolling_corr(g["predicted_forward_return"], g["target_forward_return"], window)
        g[f"baseline_hit_rate_{window}d"] = g["baseline_direction_hit_flag"].rolling(window, min_periods=max(10, window // 2)).mean()
        g[f"ai_hit_rate_{window}d"] = g["ai_direction_hit_flag"].rolling(window, min_periods=max(10, window // 2)).mean()
        g[f"baseline_mae_{window}d"] = g["baseline_abs_error"].rolling(window, min_periods=max(10, window // 2)).mean()
        g[f"ai_mae_{window}d"] = g["ai_abs_error"].rolling(window, min_periods=max(10, window // 2)).mean()
        g[f"ai_minus_baseline_corr_{window}d"] = g[f"ai_corr_{window}d"] - g[f"baseline_corr_{window}d"]
        g[f"ai_minus_baseline_hit_rate_{window}d"] = g[f"ai_hit_rate_{window}d"] - g[f"baseline_hit_rate_{window}d"]
        g[f"ai_minus_baseline_mae_{window}d"] = g[f"ai_mae_{window}d"] - g[f"baseline_mae_{window}d"]
    return g


def _quality_label(row: pd.Series) -> str:
    corr = row.get("ai_corr_60d")
    hit = row.get("ai_hit_rate_60d")
    if pd.isna(corr) or pd.isna(hit):
        return "insufficient_history"
    if corr >= 0.2 and hit >= 0.56:
        return "strong"
    if corr >= 0.1 and hit >= 0.53:
        return "usable"
    if corr <= -0.05 or hit < 0.48:
        return "weak"
    return "watch"


def build_market_forecast_monitoring_mart(
    *,
    market_context_db: Path,
    output_dir: Path,
    report_dir: Path,
) -> MonitoringMartResult:
    generated_at = _now_kst()
    validation = _read_validation(market_context_db)
    frames = [
        _build_group_monitoring(g)
        for _, g in validation.groupby(["market_scope", "forecast_horizon"], sort=False)
    ]
    out = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    out["monitoring_quality_label"] = out.apply(_quality_label, axis=1)
    out["schema_version_monitoring"] = SCHEMA_VERSION
    out["feature_version_monitoring"] = FEATURE_VERSION
    out["generated_at_monitoring"] = generated_at

    keep_columns = [
        "asof_date",
        "market_scope",
        "forecast_horizon",
        "target_forward_return",
        "market_forecast_score",
        "predicted_forward_return",
        "baseline_direction_hit_flag",
        "ai_direction_hit_flag",
        "baseline_forecast_error",
        "ai_forecast_error",
        "baseline_abs_error",
        "ai_abs_error",
    ]
    for window in ROLLING_WINDOWS:
        keep_columns.extend(
            [
                f"baseline_corr_{window}d",
                f"ai_corr_{window}d",
                f"baseline_hit_rate_{window}d",
                f"ai_hit_rate_{window}d",
                f"baseline_mae_{window}d",
                f"ai_mae_{window}d",
                f"ai_minus_baseline_corr_{window}d",
                f"ai_minus_baseline_hit_rate_{window}d",
                f"ai_minus_baseline_mae_{window}d",
            ]
        )
    keep_columns.extend(["monitoring_quality_label", "schema_version_monitoring", "feature_version_monitoring", "generated_at_monitoring"])
    out = out[keep_columns].sort_values(["asof_date", "market_scope", "forecast_horizon"]).reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "market_forecast_monitoring_daily_current.csv"
    report_json = report_dir / "market_forecast_monitoring_latest.json"
    report_md = report_dir / "market_forecast_monitoring_latest.md"
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS market_forecast_monitoring_daily")
        out.to_sql("market_forecast_monitoring_daily", con, if_exists="replace", index=False)
        con.commit()

    latest = (
        out.sort_values("asof_date")
        .groupby(["market_scope", "forecast_horizon"], as_index=False)
        .tail(1)
        .sort_values(["market_scope", "forecast_horizon"])
    )
    quality_distribution = out["monitoring_quality_label"].value_counts(dropna=False).rename_axis("label").reset_index(name="rows").to_dict("records")
    report = {
        "source_name": "QuantMarket market forecast monitoring mart",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "row_count": int(len(out)),
        "date_range": {
            "start": str(out["asof_date"].min()) if not out.empty else None,
            "end": str(out["asof_date"].max()) if not out.empty else None,
        },
        "primary_key": ["asof_date", "market_scope", "forecast_horizon"],
        "rolling_windows": ROLLING_WINDOWS,
        "quality_distribution": quality_distribution,
        "latest_by_scope_horizon": latest.to_dict("records"),
        "output_paths": {
            "db": str(market_context_db),
            "table": "market_forecast_monitoring_daily",
            "csv": str(output_csv),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Market Forecast Monitoring Mart",
        "",
        f"- generated_at: {generated_at}",
        f"- schema_version: {SCHEMA_VERSION}",
        f"- feature_version: {FEATURE_VERSION}",
        f"- rows: {len(out)}",
        f"- csv: `{output_csv}`",
        "",
        "## Quality Distribution",
        "",
    ]
    for row in quality_distribution:
        lines.append(f"- {row['label']}: {row['rows']}")
    lines.extend(["", "## Latest By Scope/Horizon", ""])
    lines.append("| scope | horizon | ai corr 60d | ai hit 60d | ai mae 60d | quality |")
    lines.append("|---|---|---:|---:|---:|---|")
    for row in latest.to_dict("records"):
        lines.append(
            f"| {row['market_scope']} | {row['forecast_horizon']} | "
            f"{row.get('ai_corr_60d')} | {row.get('ai_hit_rate_60d')} | {row.get('ai_mae_60d')} | "
            f"{row.get('monitoring_quality_label')} |"
        )
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["market_forecast_monitoring_daily"] = output_csv.name
    manifest.setdefault("tables", {})["market_forecast_monitoring_daily"] = {
        "file": output_csv.name,
        "row_count": int(len(out)),
        "start_date": report["date_range"]["start"],
        "end_date": report["date_range"]["end"],
        "duplicate_key_count": int(out.duplicated(["asof_date", "market_scope", "forecast_horizon"]).sum()) if not out.empty else 0,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return MonitoringMartResult(
        output_csv=output_csv,
        report_json=report_json,
        report_md=report_md,
        generated_at=generated_at,
        row_count=int(len(out)),
    )
