from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .ai_training_context_mart import MARKET_PROXY_TICKERS

KST = timezone(timedelta(hours=9))
HORIZON_DAYS = {"1d": 1, "5d": 5, "20d": 20}


@dataclass(frozen=True)
class ForecastValidationResult:
    report_json: Path
    report_md: Path
    detail_csv: Path
    label_csv: Path
    quintile_csv: Path
    target_csv: Path
    validation_csv: Path
    generated_at: str


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _ro_connect(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _read_forecast(market_context_db: Path) -> pd.DataFrame:
    with _ro_connect(market_context_db) as con:
        return pd.read_sql_query(
            """
            SELECT *
            FROM market_forecast_daily
            ORDER BY asof_date, market_scope, forecast_horizon
            """,
            con,
        )


def _read_calibrated(market_context_db: Path) -> pd.DataFrame:
    with _ro_connect(market_context_db) as con:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_forecast_ai_calibrated_daily'"
        ).fetchone()
        if not exists:
            return pd.DataFrame()
        return pd.read_sql_query(
            """
            SELECT asof_date, market_scope, forecast_horizon,
                   predicted_forward_return, calibrated_forecast_score,
                   calibrated_forecast_label, calibration_confidence_score,
                   calibration_model_version
            FROM market_forecast_ai_calibrated_daily
            ORDER BY asof_date, market_scope, forecast_horizon
            """,
            con,
        )


def _read_proxy_prices(price_db: Path) -> pd.DataFrame:
    tickers = [MARKET_PROXY_TICKERS["KOSPI"], MARKET_PROXY_TICKERS["KOSDAQ"]]
    placeholders = ",".join("?" for _ in tickers)
    with _ro_connect(price_db) as con:
        df = pd.read_sql_query(
            f"""
            SELECT ticker, date, close
            FROM prices_daily
            WHERE ticker IN ({placeholders})
            ORDER BY ticker, date
            """,
            con,
            params=tickers,
        )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["asof_date"] = df["date"].dt.strftime("%Y-%m-%d")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df


def _build_scope_close(price_db: Path) -> pd.DataFrame:
    prices = _read_proxy_prices(price_db)
    if prices.empty:
        return pd.DataFrame(columns=["asof_date", "market_scope", "close"])

    frames = []
    for scope, ticker in MARKET_PROXY_TICKERS.items():
        g = prices[prices["ticker"] == ticker].sort_values("date").copy()
        g["market_scope"] = scope
        frames.append(g[["asof_date", "market_scope", "close"]])

    k = frames[0].set_index("asof_date")["close"].rename("kospi")
    q = frames[1].set_index("asof_date")["close"].rename("kosdaq")
    both = pd.concat([k, q], axis=1).dropna()
    daily_ret = both["kospi"].pct_change().fillna(0.0) * 0.6 + both["kosdaq"].pct_change().fillna(0.0) * 0.4
    all_close = (1.0 + daily_ret).cumprod() * 100.0
    frames.append(
        pd.DataFrame(
            {
                "asof_date": all_close.index,
                "market_scope": "ALL",
                "close": all_close.values,
            }
        )
    )
    return pd.concat(frames, ignore_index=True, sort=False)


def _forward_returns(scope_close: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, g in scope_close.groupby("market_scope"):
        g = g.sort_values("asof_date").reset_index(drop=True)
        close = pd.to_numeric(g["close"], errors="coerce")
        for horizon, days in HORIZON_DAYS.items():
            out = g[["asof_date", "market_scope"]].copy()
            out["forecast_horizon"] = horizon
            out["target_forward_return"] = close.shift(-days) / close - 1.0
            out["target_start_close"] = close
            out["target_end_close"] = close.shift(-days)
            out["target_end_asof_date"] = g["asof_date"].shift(-days)
            out["target_horizon_trading_days"] = days
            future_closes = pd.concat([close.shift(-step) for step in range(1, days + 1)], axis=1)
            out["target_forward_max_drawdown"] = future_closes.min(axis=1) / close - 1.0
            out["target_forward_max_runup"] = future_closes.max(axis=1) / close - 1.0
            rows.append(out)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _build_target_mart(scope_close: pd.DataFrame, generated_at: str) -> pd.DataFrame:
    target = _forward_returns(scope_close)
    if target.empty:
        return target
    benchmark = target[target["market_scope"] == "ALL"][
        ["asof_date", "forecast_horizon", "target_forward_return"]
    ].rename(columns={"target_forward_return": "target_all_forward_return"})
    target = target.merge(benchmark, on=["asof_date", "forecast_horizon"], how="left")
    target["target_excess_return_vs_all"] = target["target_forward_return"] - target["target_all_forward_return"]
    target.loc[target["market_scope"] == "ALL", "target_excess_return_vs_all"] = 0.0
    target["target_excess_return_vs_cash"] = target["target_forward_return"]
    target["target_direction_label"] = target["target_forward_return"].map(
        lambda value: None if pd.isna(value) else ("up" if value > 0 else "down_or_flat")
    )
    target["target_upside_flag"] = (target["target_forward_return"] > 0).astype("Int64")
    target.loc[target["target_forward_return"].isna(), "target_upside_flag"] = pd.NA
    downside_threshold = target["forecast_horizon"].map({"1d": -0.02, "5d": -0.04, "20d": -0.07})
    upside_threshold = target["forecast_horizon"].map({"1d": 0.02, "5d": 0.04, "20d": 0.07})
    target["target_downside_risk_flag"] = (target["target_forward_max_drawdown"] <= downside_threshold).astype("Int64")
    target.loc[target["target_forward_max_drawdown"].isna(), "target_downside_risk_flag"] = pd.NA
    target["target_large_upside_flag"] = (target["target_forward_max_runup"] >= upside_threshold).astype("Int64")
    target.loc[target["target_forward_max_runup"].isna(), "target_large_upside_flag"] = pd.NA
    target["target_available_flag"] = target["target_forward_return"].notna().astype(int)
    target["target_schema_version"] = "market_forecast_target_daily.v1"
    target["target_feature_version"] = "qm_market_forecast_target_v1_20260513"
    target["generated_at"] = generated_at
    return target[
        [
            "asof_date",
            "market_scope",
            "forecast_horizon",
            "target_forward_return",
            "target_excess_return_vs_cash",
            "target_excess_return_vs_all",
            "target_forward_max_drawdown",
            "target_forward_max_runup",
            "target_direction_label",
            "target_upside_flag",
            "target_downside_risk_flag",
            "target_large_upside_flag",
            "target_available_flag",
            "target_horizon_trading_days",
            "target_start_close",
            "target_end_asof_date",
            "target_end_close",
            "target_schema_version",
            "target_feature_version",
            "generated_at",
        ]
    ]


def _safe_corr(frame: pd.DataFrame, method: str) -> float | None:
    sample = frame[["market_forecast_score", "target_forward_return"]].dropna()
    if len(sample) < 20:
        return None
    value = sample["market_forecast_score"].corr(sample["target_forward_return"], method=method)
    if pd.isna(value):
        return None
    return round(float(value), 6)


def _summary_stats(frame: pd.DataFrame) -> dict:
    sample = frame.dropna(subset=["target_forward_return", "market_forecast_score"])
    if sample.empty:
        return {
            "rows": 0,
            "mean_forward_return": None,
            "median_forward_return": None,
            "win_rate": None,
            "pearson_corr": None,
            "spearman_corr": None,
        }
    return {
        "rows": int(len(sample)),
        "start_date": str(sample["asof_date"].min()),
        "end_date": str(sample["asof_date"].max()),
        "mean_forward_return": round(float(sample["target_forward_return"].mean()), 8),
        "median_forward_return": round(float(sample["target_forward_return"].median()), 8),
        "std_forward_return": round(float(sample["target_forward_return"].std(ddof=0)), 8),
        "win_rate": round(float((sample["target_forward_return"] > 0).mean()), 6),
        "avg_score": round(float(sample["market_forecast_score"].mean()), 6),
        "pearson_corr": _safe_corr(sample, "pearson"),
        "spearman_corr": _safe_corr(sample, "spearman"),
    }


def _overall_summary(joined: pd.DataFrame) -> list[dict]:
    rows = []
    for (scope, horizon), g in joined.groupby(["market_scope", "forecast_horizon"]):
        item = {
            "market_scope": scope,
            "forecast_horizon": horizon,
            **_summary_stats(g),
        }
        rows.append(item)
    return sorted(rows, key=lambda row: (row["market_scope"], row["forecast_horizon"]))


def _label_summary(joined: pd.DataFrame) -> pd.DataFrame:
    sample = joined.dropna(subset=["target_forward_return", "market_forecast_score"]).copy()
    if sample.empty:
        return pd.DataFrame()
    grouped = (
        sample.groupby(["market_scope", "forecast_horizon", "market_forecast_label"], dropna=False)
        .agg(
            rows=("target_forward_return", "size"),
            avg_score=("market_forecast_score", "mean"),
            mean_forward_return=("target_forward_return", "mean"),
            median_forward_return=("target_forward_return", "median"),
            win_rate=("target_forward_return", lambda s: (s > 0).mean()),
        )
        .reset_index()
    )
    numeric_cols = ["avg_score", "mean_forward_return", "median_forward_return", "win_rate"]
    grouped[numeric_cols] = grouped[numeric_cols].round(8)
    return grouped


def _quintile_summary(joined: pd.DataFrame) -> pd.DataFrame:
    sample = joined.dropna(subset=["target_forward_return", "market_forecast_score"]).copy()
    if sample.empty:
        return pd.DataFrame()
    rows = []
    for (scope, horizon), g in sample.groupby(["market_scope", "forecast_horizon"]):
        if len(g) < 50 or g["market_forecast_score"].nunique() < 5:
            continue
        g = g.copy()
        g["score_quintile"] = pd.qcut(g["market_forecast_score"], 5, labels=["Q1_low", "Q2", "Q3", "Q4", "Q5_high"], duplicates="drop")
        summary = (
            g.groupby("score_quintile", observed=True)
            .agg(
                rows=("target_forward_return", "size"),
                min_score=("market_forecast_score", "min"),
                max_score=("market_forecast_score", "max"),
                mean_forward_return=("target_forward_return", "mean"),
                median_forward_return=("target_forward_return", "median"),
                win_rate=("target_forward_return", lambda s: (s > 0).mean()),
            )
            .reset_index()
        )
        summary.insert(0, "forecast_horizon", horizon)
        summary.insert(0, "market_scope", scope)
        rows.append(summary)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True, sort=False)
    numeric_cols = ["min_score", "max_score", "mean_forward_return", "median_forward_return", "win_rate"]
    out[numeric_cols] = out[numeric_cols].round(8)
    return out


def _top_bottom_spread(quintiles: pd.DataFrame) -> list[dict]:
    if quintiles.empty:
        return []
    rows = []
    for (scope, horizon), g in quintiles.groupby(["market_scope", "forecast_horizon"]):
        low = g[g["score_quintile"].astype(str) == "Q1_low"]
        high = g[g["score_quintile"].astype(str) == "Q5_high"]
        if low.empty or high.empty:
            continue
        rows.append(
            {
                "market_scope": scope,
                "forecast_horizon": horizon,
                "q5_minus_q1_mean_forward_return": round(
                    float(high["mean_forward_return"].iloc[0] - low["mean_forward_return"].iloc[0]),
                    8,
                ),
                "q5_minus_q1_win_rate": round(float(high["win_rate"].iloc[0] - low["win_rate"].iloc[0]), 8),
            }
        )
    return rows


def _write_report_md(report: dict, label_summary: pd.DataFrame, quintile_summary: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Market Forecast Daily Validation",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- source_forecast_db: `{report['source_paths']['market_context_db']}`",
        f"- source_price_db_readonly: `{report['source_paths']['price_db_readonly']}`",
        f"- validation_target: {report['validation_target']}",
        "",
        "## Overall",
        "",
        "| scope | horizon | rows | mean fwd ret | win rate | pearson | spearman |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["overall_summary"]:
        lines.append(
            "| {market_scope} | {forecast_horizon} | {rows} | {mean_forward_return} | "
            "{win_rate} | {pearson_corr} | {spearman_corr} |".format(**row)
        )
    lines.extend(["", "## Top Minus Bottom Quintile", ""])
    for row in report["top_bottom_spread"]:
        lines.append(
            f"- {row['market_scope']} {row['forecast_horizon']}: "
            f"mean_return_spread={row['q5_minus_q1_mean_forward_return']}, "
            f"win_rate_spread={row['q5_minus_q1_win_rate']}"
        )
    lines.extend(["", "## Label Summary", ""])
    if label_summary.empty:
        lines.append("- No label summary available.")
    else:
        lines.extend(
            [
                "| scope | horizon | label | rows | avg score | mean fwd ret | win rate |",
                "|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in label_summary.to_dict("records"):
            lines.append(
                f"| {row['market_scope']} | {row['forecast_horizon']} | {row['market_forecast_label']} | "
                f"{row['rows']} | {row['avg_score']} | {row['mean_forward_return']} | {row['win_rate']} |"
            )
    lines.extend(["", "## Notes", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_validation_mart(forecast: pd.DataFrame, calibrated: pd.DataFrame, target: pd.DataFrame, generated_at: str) -> pd.DataFrame:
    joined = forecast.merge(target, on=["asof_date", "market_scope", "forecast_horizon"], how="left")
    if not calibrated.empty:
        joined = joined.merge(calibrated, on=["asof_date", "market_scope", "forecast_horizon"], how="left")
    else:
        for column in [
            "predicted_forward_return",
            "calibrated_forecast_score",
            "calibrated_forecast_label",
            "calibration_confidence_score",
            "calibration_model_version",
        ]:
            joined[column] = None

    valid = joined["target_available_flag"] == 1
    baseline_hit = (
        ((joined["market_forecast_score"] > 0) & (joined["target_forward_return"] > 0))
        | ((joined["market_forecast_score"] <= 0) & (joined["target_forward_return"] <= 0))
    )
    joined["baseline_direction_hit_flag"] = baseline_hit.astype("Int64")
    joined.loc[~valid, "baseline_direction_hit_flag"] = pd.NA
    joined["baseline_forecast_error"] = joined["market_forecast_score"] - joined["target_forward_return"]
    ai_hit = (
        ((joined["predicted_forward_return"] > 0) & (joined["target_forward_return"] > 0))
        | ((joined["predicted_forward_return"] <= 0) & (joined["target_forward_return"] <= 0))
    )
    joined["ai_direction_hit_flag"] = ai_hit.astype("Int64")
    joined.loc[~valid, "ai_direction_hit_flag"] = pd.NA
    joined["ai_forecast_error"] = joined["predicted_forward_return"] - joined["target_forward_return"]
    joined["validation_schema_version"] = "market_forecast_validation_daily.v1"
    joined["validation_feature_version"] = "qm_market_forecast_validation_v1_20260513"
    joined["generated_at_validation"] = generated_at
    return joined


def _write_current_manifest(output_dir: Path, target: pd.DataFrame, validation: pd.DataFrame) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["market_forecast_target_daily"] = "market_forecast_target_daily_current.csv"
    manifest.setdefault("canonical_files", {})["market_forecast_validation_daily"] = "market_forecast_validation_daily_current.csv"
    manifest.setdefault("tables", {})["market_forecast_target_daily"] = {
        "file": "market_forecast_target_daily_current.csv",
        "row_count": int(len(target)),
        "start_date": str(target["asof_date"].min()) if not target.empty else None,
        "end_date": str(target["asof_date"].max()) if not target.empty else None,
        "duplicate_key_count": int(target.duplicated(["asof_date", "market_scope", "forecast_horizon"]).sum()) if not target.empty else 0,
    }
    manifest.setdefault("tables", {})["market_forecast_validation_daily"] = {
        "file": "market_forecast_validation_daily_current.csv",
        "row_count": int(len(validation)),
        "start_date": str(validation["asof_date"].min()) if not validation.empty else None,
        "end_date": str(validation["asof_date"].max()) if not validation.empty else None,
        "duplicate_key_count": int(validation.duplicated(["asof_date", "market_scope", "forecast_horizon"]).sum()) if not validation.empty else 0,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_market_forecast_daily(
    *,
    market_context_db: Path,
    price_db: Path,
    report_dir: Path,
) -> ForecastValidationResult:
    generated_at = _now_kst()
    forecast = _read_forecast(market_context_db)
    calibrated = _read_calibrated(market_context_db)
    scope_close = _build_scope_close(price_db)
    target = _build_target_mart(scope_close, generated_at)
    validation = _build_validation_mart(forecast, calibrated, target, generated_at)
    joined = validation.dropna(subset=["target_forward_return"]).copy()

    report_dir.mkdir(parents=True, exist_ok=True)
    output_dir = market_context_db.parents[2] / "service_platform" / "ai_training" / "market_context" / "current"
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_csv = report_dir / "market_forecast_validation_detail_latest.csv"
    target_csv = output_dir / "market_forecast_target_daily_current.csv"
    validation_csv = output_dir / "market_forecast_validation_daily_current.csv"
    label_csv = report_dir / "market_forecast_validation_label_summary_latest.csv"
    quintile_csv = report_dir / "market_forecast_validation_quintile_summary_latest.csv"
    report_json = report_dir / "market_forecast_validation_latest.json"
    report_md = report_dir / "market_forecast_validation_latest.md"

    target.to_csv(target_csv, index=False, encoding="utf-8-sig")
    validation.to_csv(validation_csv, index=False, encoding="utf-8-sig")
    label_summary = _label_summary(joined)
    quintiles = _quintile_summary(joined)
    joined.to_csv(detail_csv, index=False, encoding="utf-8-sig")
    label_summary.to_csv(label_csv, index=False, encoding="utf-8-sig")
    quintiles.to_csv(quintile_csv, index=False, encoding="utf-8-sig")
    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS market_forecast_target_daily")
        con.execute("DROP TABLE IF EXISTS market_forecast_validation_daily")
        target.to_sql("market_forecast_target_daily", con, if_exists="replace", index=False)
        validation.to_sql("market_forecast_validation_daily", con, if_exists="replace", index=False)
        con.commit()
    _write_current_manifest(output_dir, target, validation)

    report = {
        "source_name": "QuantMarket market_forecast_daily validation",
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "validation_target": "forward ETF proxy returns by forecast_horizon trading days",
        "source_paths": {
            "market_context_db": str(market_context_db),
            "price_db_readonly": str(price_db),
        },
        "output_paths": {
            "report_json": str(report_json),
            "report_md": str(report_md),
            "detail_csv": str(detail_csv),
            "target_csv": str(target_csv),
            "validation_csv": str(validation_csv),
            "label_csv": str(label_csv),
            "quintile_csv": str(quintile_csv),
        },
        "row_counts": {
            "forecast_rows": int(len(forecast)),
            "target_rows": int(len(target)),
            "validation_rows": int(len(validation)),
            "joined_validation_rows": int(len(joined)),
            "label_summary_rows": int(len(label_summary)),
            "quintile_summary_rows": int(len(quintiles)),
        },
        "overall_summary": _overall_summary(joined),
        "top_bottom_spread": _top_bottom_spread(quintiles),
        "label_summary": label_summary.to_dict("records"),
        "notes": [
            "KOSPI uses KODEX KOSPI proxy ticker 226490; KOSDAQ uses KODEX KOSDAQ150 proxy ticker 229200.",
            "ALL is a synthetic 60% KOSPI proxy + 40% KOSDAQ proxy daily-return composite.",
            "Forward returns are calculated over trading-day steps matching forecast_horizon.",
            "market_forecast_target_daily is the reusable target mart; market_forecast_validation_daily is the reusable prediction-vs-target mart.",
            "This validates directional usefulness only; it is not a public performance claim.",
        ],
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report_md(report, label_summary, quintiles, report_md)
    return ForecastValidationResult(
        report_json=report_json,
        report_md=report_md,
        detail_csv=detail_csv,
        label_csv=label_csv,
        quintile_csv=quintile_csv,
        target_csv=target_csv,
        validation_csv=validation_csv,
        generated_at=generated_at,
    )
