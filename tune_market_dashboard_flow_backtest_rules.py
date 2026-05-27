from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest_market_dashboard_flow_signals import (  # noqa: E402
    INVESTABLE_SCOPES,
    OUTPUT_DIR,
    REPORT_DIR,
    THRESHOLD_SCORECARD_PATH,
    THRESHOLDS_PATH,
    _candidate_predictions,
    _load_next_day_returns,
    _load_predictions,
    _run_backtest,
    _select_candidates,
    DB_PATH,
)

RULE_PROFILES = {
    "baseline_100_50_0": {"up": 1.0, "sideways": 0.5, "down": 0.0, "fallback": 0.5},
    "defensive_100_30_0": {"up": 1.0, "sideways": 0.3, "down": 0.0, "fallback": 0.3},
    "moderate_80_40_0": {"up": 0.8, "sideways": 0.4, "down": 0.0, "fallback": 0.4},
    "cash_heavy_70_20_0": {"up": 0.7, "sideways": 0.2, "down": 0.0, "fallback": 0.2},
    "up_only_100_0_0": {"up": 1.0, "sideways": 0.0, "down": 0.0, "fallback": 0.0},
}
CONFIDENCE_FLOORS = [0.0, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
SHARPE_NEAR_BEST_TOLERANCE = 0.05


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _apply_rule(candidate_predictions: pd.DataFrame, rule_name: str, profile: dict, confidence_floor: float) -> pd.DataFrame:
    frame = candidate_predictions.copy()
    base_exposure = frame["predicted_direction"].map(
        {
            "up": profile["up"],
            "sideways": profile["sideways"],
            "down": profile["down"],
        }
    )
    low_confidence = frame["confidence"] < confidence_floor
    frame["exposure"] = base_exposure.astype(float)
    frame.loc[low_confidence, "exposure"] = float(profile["fallback"])
    frame["rule_name"] = rule_name
    frame["confidence_floor"] = confidence_floor
    frame["low_confidence_ratio"] = float(low_confidence.mean())
    return frame


def _add_relative_metrics(scorecard: pd.DataFrame) -> pd.DataFrame:
    scorecard = scorecard.copy()
    scorecard["sharpe_lift"] = scorecard["sharpe"] - scorecard["buyhold_sharpe"]
    scorecard["mdd_improvement"] = scorecard["max_drawdown"] - scorecard["buyhold_max_drawdown"]
    scorecard["return_capture"] = scorecard["cumulative_return"] / scorecard["buyhold_cumulative_return"].replace(
        {0.0: pd.NA}
    )
    return scorecard


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows."
    text = frame.fillna("").astype(str)
    header = "| " + " | ".join(text.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text.to_numpy()]
    return "\n".join([header, separator, *rows])


def _write_report(best: pd.DataFrame, path: Path) -> None:
    cols = [
        "market_scope",
        "forecast_horizon",
        "candidate_type",
        "decision_method",
        "label_policy",
        "model",
        "rule_name",
        "confidence_floor",
        "cumulative_return",
        "buyhold_cumulative_return",
        "sharpe",
        "buyhold_sharpe",
        "sharpe_lift",
        "max_drawdown",
        "buyhold_max_drawdown",
        "mdd_improvement",
        "avg_exposure",
        "low_confidence_ratio",
    ]
    table = best[cols].copy()
    for col in [
        "confidence_floor",
        "cumulative_return",
        "buyhold_cumulative_return",
        "sharpe",
        "buyhold_sharpe",
        "sharpe_lift",
        "max_drawdown",
        "buyhold_max_drawdown",
        "mdd_improvement",
        "avg_exposure",
        "low_confidence_ratio",
    ]:
        table[col] = table[col].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    lines = [
        "# Market Dashboard Flow Backtest Rule Tuning",
        "",
        f"- generated_at: {_now_iso()}",
        "- scope_policy: investable_only",
        "- markets: KOSPI, KOSDAQ, KOSPI200",
        f"- selection: lowest low-confidence fallback ratio among candidates within {SHARPE_NEAR_BEST_TOLERANCE:.2f} Sharpe of best, then higher Sharpe",
        "",
        "## Best Rules",
        "",
        _markdown_table(table),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_rule_tuning(cost_bps: float, scopes: list[str] | None = None) -> dict:
    scopes = scopes or INVESTABLE_SCOPES
    predictions = _load_predictions(scopes)
    threshold_scorecard = pd.read_csv(THRESHOLD_SCORECARD_PATH)
    threshold_scorecard = threshold_scorecard[threshold_scorecard["market_scope"].isin(scopes)].copy()
    thresholds = pd.read_csv(THRESHOLDS_PATH)
    thresholds = thresholds[thresholds["market_scope"].isin(scopes)].copy()
    candidates = _select_candidates(threshold_scorecard, scopes)
    candidate_preds = _candidate_predictions(predictions, candidates, thresholds)
    returns = _load_next_day_returns(DB_PATH, scopes)

    all_trades = []
    all_scorecards = []
    for rule_name, profile in RULE_PROFILES.items():
        for confidence_floor in CONFIDENCE_FLOORS:
            ruled = _apply_rule(candidate_preds, rule_name, profile, confidence_floor)
            trades, scorecard = _run_backtest(ruled, returns, cost_bps)
            trades["rule_name"] = rule_name
            trades["confidence_floor"] = confidence_floor
            scorecard["rule_name"] = rule_name
            scorecard["confidence_floor"] = confidence_floor
            all_trades.append(trades)
            all_scorecards.append(scorecard)

    trades_frame = pd.concat(all_trades, ignore_index=True)
    scorecard = _add_relative_metrics(pd.concat(all_scorecards, ignore_index=True))
    best_rows = []
    for _, group in scorecard.groupby(["market_scope", "forecast_horizon"], dropna=False):
        best_sharpe = float(group["sharpe"].max())
        eligible = group[group["sharpe"] >= best_sharpe - SHARPE_NEAR_BEST_TOLERANCE].copy()
        if eligible.empty:
            eligible = group.copy()
        selected = eligible.sort_values(
            ["low_confidence_ratio", "sharpe", "max_drawdown", "cumulative_return"],
            ascending=[True, False, False, False],
        ).iloc[0]
        best_rows.append(selected.to_dict())
    best = pd.DataFrame(best_rows).sort_values(["forecast_horizon", "market_scope"])

    scorecard_path = OUTPUT_DIR / "dashboard_axis_flow_backtest_rule_tuning_scorecard_current.csv"
    best_path = OUTPUT_DIR / "dashboard_axis_flow_backtest_rule_tuning_best_current.csv"
    trades_path = OUTPUT_DIR / "dashboard_axis_flow_backtest_rule_tuning_trades_current.csv"
    report_path = REPORT_DIR / "dashboard_axis_flow_backtest_rule_tuning_latest.md"
    summary_path = REPORT_DIR / "dashboard_axis_flow_backtest_rule_tuning_summary_latest.json"

    scorecard.to_csv(scorecard_path, index=False, encoding="utf-8-sig")
    best.to_csv(best_path, index=False, encoding="utf-8-sig")
    trades_frame.to_csv(trades_path, index=False, encoding="utf-8-sig")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _write_report(best, report_path)

    summary = {
        "status": "ok",
        "generated_at": _now_iso(),
        "scope_policy": "investable_only",
        "scopes": scopes,
        "cost_bps": cost_bps,
        "rule_profiles": list(RULE_PROFILES),
        "confidence_floors": CONFIDENCE_FLOORS,
        "selection_policy": {
            "name": "near_best_sharpe_low_confidence_first",
            "sharpe_near_best_tolerance": SHARPE_NEAR_BEST_TOLERANCE,
        },
        "row_counts": {
            "candidate_set": int(candidates.shape[0]),
            "candidate_predictions": int(candidate_preds.shape[0]),
            "scorecard": int(scorecard.shape[0]),
            "best": int(best.shape[0]),
            "trades": int(trades_frame.shape[0]),
        },
        "outputs": {
            "scorecard": str(scorecard_path),
            "best": str(best_path),
            "trades": str(trades_path),
            "report": str(report_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune backtest exposure rules for investable flow signals.")
    parser.add_argument("--cost-bps", type=float, default=5.0)
    parser.add_argument(
        "--scopes",
        default=",".join(INVESTABLE_SCOPES),
        help="Comma-separated market scopes. Default excludes ALL.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scopes = [item.strip() for item in args.scopes.split(",") if item.strip()]
    print(json.dumps(run_rule_tuning(cost_bps=args.cost_bps, scopes=scopes), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
