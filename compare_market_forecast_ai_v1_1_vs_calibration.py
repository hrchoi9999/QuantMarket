from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _metrics(df: pd.DataFrame, pred_col: str, target_col: str) -> dict:
    sample = df.dropna(subset=[pred_col, target_col]).copy()
    if sample.empty:
        return {
            "rows": 0,
            "prediction_corr": None,
            "directional_hit_rate": None,
            "mae": None,
            "rmse": None,
            "mean_predicted": None,
            "mean_realized": None,
        }
    err = sample[pred_col] - sample[target_col]
    corr = sample[pred_col].corr(sample[target_col])
    return {
        "rows": int(len(sample)),
        "start_date": str(sample["asof_date"].min()),
        "end_date": str(sample["asof_date"].max()),
        "prediction_corr": None if pd.isna(corr) else round(float(corr), 6),
        "directional_hit_rate": round(float((sample[pred_col].gt(0) == sample[target_col].gt(0)).mean()), 6),
        "mae": round(float(err.abs().mean()), 8),
        "rmse": round(float((err.pow(2).mean()) ** 0.5), 8),
        "mean_predicted": round(float(sample[pred_col].mean()), 8),
        "mean_realized": round(float(sample[target_col].mean()), 8),
    }


def main() -> None:
    generated_at = _now_kst()
    v11_path = ROOT / "reports" / "market_forecast_ai_model_v1_1" / "market_forecast_ai_v1_1_validation_latest.csv"
    cal_path = ROOT / "reports" / "market_forecast_ai_calibration" / "market_forecast_ai_calibration_validation_latest.csv"
    report_dir = ROOT / "reports" / "market_forecast_ai_comparison"
    report_dir.mkdir(parents=True, exist_ok=True)

    v11 = pd.read_csv(v11_path)
    cal = pd.read_csv(cal_path)
    cal = cal.rename(
        columns={
            "predicted_forward_return": "ridge_calibration_predicted_forward_return",
            "realized_forward_return": "target_forward_return_calibration",
        }
    )
    joined = v11.merge(
        cal[
            [
                "asof_date",
                "market_scope",
                "forecast_horizon",
                "ridge_calibration_predicted_forward_return",
                "target_forward_return_calibration",
            ]
        ],
        on=["asof_date", "market_scope", "forecast_horizon"],
        how="inner",
    )
    joined["target_forward_return"] = joined["target_forward_return"].combine_first(joined["target_forward_return_calibration"])

    rows = []
    for (scope, horizon), group in joined.groupby(["market_scope", "forecast_horizon"]):
        v11_metrics = _metrics(group, "ai_v1_1_predicted_forward_return", "target_forward_return")
        cal_metrics = _metrics(group, "ridge_calibration_predicted_forward_return", "target_forward_return")
        rows.append(
            {
                "market_scope": scope,
                "forecast_horizon": horizon,
                "overlap_rows": int(len(group.dropna(subset=["ai_v1_1_predicted_forward_return", "ridge_calibration_predicted_forward_return", "target_forward_return"]))),
                "v1_1_corr": v11_metrics["prediction_corr"],
                "ridge_corr": cal_metrics["prediction_corr"],
                "corr_diff_v1_1_minus_ridge": (
                    round(v11_metrics["prediction_corr"] - cal_metrics["prediction_corr"], 6)
                    if v11_metrics["prediction_corr"] is not None and cal_metrics["prediction_corr"] is not None
                    else None
                ),
                "v1_1_hit": v11_metrics["directional_hit_rate"],
                "ridge_hit": cal_metrics["directional_hit_rate"],
                "hit_diff_v1_1_minus_ridge": (
                    round(v11_metrics["directional_hit_rate"] - cal_metrics["directional_hit_rate"], 6)
                    if v11_metrics["directional_hit_rate"] is not None and cal_metrics["directional_hit_rate"] is not None
                    else None
                ),
                "v1_1_mae": v11_metrics["mae"],
                "ridge_mae": cal_metrics["mae"],
                "mae_diff_v1_1_minus_ridge": (
                    round(v11_metrics["mae"] - cal_metrics["mae"], 8)
                    if v11_metrics["mae"] is not None and cal_metrics["mae"] is not None
                    else None
                ),
            }
        )
    comparison = pd.DataFrame(rows).sort_values(["market_scope", "forecast_horizon"])
    csv_path = report_dir / "market_forecast_ai_v1_1_vs_ridge_calibration_latest.csv"
    json_path = report_dir / "market_forecast_ai_v1_1_vs_ridge_calibration_latest.json"
    md_path = report_dir / "market_forecast_ai_v1_1_vs_ridge_calibration_latest.md"
    comparison.to_csv(csv_path, index=False, encoding="utf-8-sig")

    focus_20d = comparison[comparison["forecast_horizon"] == "20d"].copy()
    winner_20d = {
        "corr": int((focus_20d["corr_diff_v1_1_minus_ridge"] > 0).sum()),
        "hit": int((focus_20d["hit_diff_v1_1_minus_ridge"] > 0).sum()),
        "mae": int((focus_20d["mae_diff_v1_1_minus_ridge"] < 0).sum()),
        "total": int(len(focus_20d)),
    }
    decision = (
        "v1_1_promote_candidate"
        if winner_20d["corr"] >= 2 and winner_20d["hit"] >= 2
        else "keep_ridge_as_primary"
    )
    report = {
        "generated_at": generated_at,
        "comparison_basis": "overlapping validation rows only",
        "decision": decision,
        "winner_20d": winner_20d,
        "rows": comparison.to_dict("records"),
        "paths": {"csv": str(csv_path), "json": str(json_path), "md": str(md_path)},
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# AI v1.1 vs Ridge Calibration Comparison",
        "",
        f"- generated_at: {generated_at}",
        "- basis: overlapping validation rows only",
        f"- decision: {decision}",
        "",
        "| scope | horizon | rows | v1.1 corr | ridge corr | corr diff | v1.1 hit | ridge hit | hit diff | v1.1 mae | ridge mae | mae diff |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison.to_dict("records"):
        lines.append(
            f"| {row['market_scope']} | {row['forecast_horizon']} | {row['overlap_rows']} | "
            f"{row['v1_1_corr']} | {row['ridge_corr']} | {row['corr_diff_v1_1_minus_ridge']} | "
            f"{row['v1_1_hit']} | {row['ridge_hit']} | {row['hit_diff_v1_1_minus_ridge']} | "
            f"{row['v1_1_mae']} | {row['ridge_mae']} | {row['mae_diff_v1_1_minus_ridge']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "decision": decision, "md": str(md_path), "csv": str(csv_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
