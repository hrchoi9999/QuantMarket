from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.market_dashboard_signal_research import HORIZONS, INDEX_CODES  # noqa: E402

OUTPUT_DIR = ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current"
REPORT_DIR = ROOT / "reports" / "market_dashboard_signal_research" / "flow_model"
DB_PATH = ROOT / "data" / "db" / "market_analysis.db"

PREDICTIONS_PATH = OUTPUT_DIR / "dashboard_axis_flow_model_predictions_current.csv"
THRESHOLD_SCORECARD_PATH = OUTPUT_DIR / "dashboard_axis_flow_threshold_tuning_scorecard_current.csv"
THRESHOLDS_PATH = OUTPUT_DIR / "dashboard_axis_flow_threshold_tuning_thresholds_current.csv"

LABEL_PROBS = ["prob_down", "prob_sideways", "prob_up"]
EXPOSURE_MAP = {"down": 0.0, "sideways": 0.5, "up": 1.0}
INVESTABLE_SCOPES = ["KOSPI", "KOSDAQ", "KOSPI200"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _argmax_label(frame: pd.DataFrame) -> pd.Series:
    return frame[LABEL_PROBS].idxmax(axis=1).str.replace("prob_", "", regex=False)


def _threshold_label(frame: pd.DataFrame, down_threshold: float, up_threshold: float) -> pd.Series:
    labels = pd.Series("sideways", index=frame.index, dtype="object")
    down_mask = (frame["prob_down"] >= down_threshold) & (frame["prob_down"] >= frame["prob_up"])
    up_mask = (frame["prob_up"] >= up_threshold) & (frame["prob_up"] > frame["prob_down"])
    labels.loc[down_mask] = "down"
    labels.loc[up_mask] = "up"
    return labels


def _build_ensemble_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    key_cols = ["label_policy", "market_scope", "forecast_horizon", "test_year"]
    for key, group in predictions.groupby(key_cols, dropna=False):
        label_policy, scope, horizon, test_year = key
        actual = group[["asof_date", "actual_label"]].drop_duplicates().sort_values("asof_date")
        model_groups = {
            model: g.set_index("asof_date")[LABEL_PROBS].sort_index()
            for model, g in group.groupby("model")
        }
        if len(model_groups) < 2:
            continue
        models = sorted(model_groups)
        combined = sum(model_groups[model].loc[actual["asof_date"]].to_numpy() for model in models) / len(models)
        for pos, (_, row) in enumerate(actual.iterrows()):
            rows.append(
                {
                    "model": "ensemble_mean_all",
                    "label_policy": label_policy,
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "test_year": int(test_year),
                    "asof_date": row["asof_date"],
                    "actual_label": row["actual_label"],
                    "prob_down": float(combined[pos][0]),
                    "prob_sideways": float(combined[pos][1]),
                    "prob_up": float(combined[pos][2]),
                }
            )
    return pd.DataFrame(rows)


def _load_predictions(scopes: list[str]) -> pd.DataFrame:
    predictions = pd.read_csv(PREDICTIONS_PATH)
    predictions["asof_date"] = pd.to_datetime(predictions["asof_date"]).dt.strftime("%Y-%m-%d")
    predictions = predictions[predictions["market_scope"].isin(scopes)].copy()
    ensemble = _build_ensemble_predictions(predictions)
    if not ensemble.empty:
        predictions = pd.concat([predictions, ensemble], ignore_index=True)
    predictions["argmax_label"] = _argmax_label(predictions)
    return predictions


def _load_next_day_returns(db_path: Path, scopes: list[str]) -> pd.DataFrame:
    with sqlite3.connect(str(db_path)) as con:
        raw = pd.read_sql_query(
            """
            SELECT index_code, index_name, date, close
            FROM market_index_daily
            WHERE market = 'KR'
              AND index_code IN ('1001', '2001', '1028')
              AND source != 'sample_seed'
            ORDER BY index_code, date
            """,
            con,
        )
    raw["date"] = pd.to_datetime(raw["date"]).dt.strftime("%Y-%m-%d")
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")

    frames = []
    for scope, code in INDEX_CODES.items():
        if scope not in scopes:
            continue
        item = raw[raw["index_code"] == code].copy().sort_values("date")
        item["market_scope"] = scope
        item["next_1d_return"] = item["close"].shift(-1) / item["close"] - 1.0
        frames.append(item[["date", "market_scope", "next_1d_return"]])

    if "ALL" in scopes:
        wide = None
        for scope, code in {"KOSPI": "1001", "KOSDAQ": "2001"}.items():
            item = raw[raw["index_code"] == code][["date", "close"]].copy().rename(columns={"close": scope})
            wide = item if wide is None else wide.merge(item, on="date", how="outer")
        wide = wide.sort_values("date")
        all_frame = pd.DataFrame({"date": wide["date"], "market_scope": "ALL"})
        kospi_ret = wide["KOSPI"].shift(-1) / wide["KOSPI"] - 1.0
        kosdaq_ret = wide["KOSDAQ"].shift(-1) / wide["KOSDAQ"] - 1.0
        all_frame["next_1d_return"] = pd.concat([kospi_ret, kosdaq_ret], axis=1).mean(axis=1)
        frames.append(all_frame)

    returns = pd.concat(frames, ignore_index=True)
    return returns.rename(columns={"date": "asof_date"})


def _select_candidates(scorecard: pd.DataFrame, scopes: list[str]) -> pd.DataFrame:
    rows = []
    for scope in scopes:
        for horizon in [f"{h}d" for h in HORIZONS]:
            group = scorecard[(scorecard["market_scope"] == scope) & (scorecard["forecast_horizon"] == horizon)]
            if group.empty:
                continue
            tuned = group.sort_values(
                ["tuned_balanced_accuracy_avg", "tuned_macro_f1_avg", "tuned_accuracy_avg"],
                ascending=False,
            ).iloc[0]
            argmax = group.sort_values(
                ["argmax_balanced_accuracy_avg", "argmax_macro_f1_avg", "argmax_accuracy_avg"],
                ascending=False,
            ).iloc[0]
            for candidate_type, method, item in [
                ("threshold_best", "threshold", tuned),
                ("argmax_best", "argmax", argmax),
            ]:
                rows.append(
                    {
                        "candidate_type": candidate_type,
                        "decision_method": method,
                        "market_scope": scope,
                        "forecast_horizon": horizon,
                        "label_policy": item["label_policy"],
                        "model": item["model"],
                        "selection_balanced_accuracy": float(
                            item["tuned_balanced_accuracy_avg"]
                            if method == "threshold"
                            else item["argmax_balanced_accuracy_avg"]
                        ),
                        "selection_macro_f1": float(
                            item["tuned_macro_f1_avg"] if method == "threshold" else item["argmax_macro_f1_avg"]
                        ),
                        "selection_accuracy": float(
                            item["tuned_accuracy_avg"] if method == "threshold" else item["argmax_accuracy_avg"]
                        ),
                        "balanced_accuracy_lift_vs_argmax": float(item["balanced_accuracy_lift_vs_argmax"]),
                    }
                )
            selected_method = "threshold" if float(tuned["balanced_accuracy_lift_vs_argmax"]) > 0 else "argmax"
            selected = tuned if selected_method == "threshold" else argmax
            rows.append(
                {
                    "candidate_type": "selected",
                    "decision_method": selected_method,
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "label_policy": selected["label_policy"],
                    "model": selected["model"],
                    "selection_balanced_accuracy": float(
                        selected["tuned_balanced_accuracy_avg"]
                        if selected_method == "threshold"
                        else selected["argmax_balanced_accuracy_avg"]
                    ),
                    "selection_macro_f1": float(
                        selected["tuned_macro_f1_avg"]
                        if selected_method == "threshold"
                        else selected["argmax_macro_f1_avg"]
                    ),
                    "selection_accuracy": float(
                        selected["tuned_accuracy_avg"] if selected_method == "threshold" else selected["argmax_accuracy_avg"]
                    ),
                    "balanced_accuracy_lift_vs_argmax": float(selected["balanced_accuracy_lift_vs_argmax"]),
                }
            )
    return pd.DataFrame(rows)


def _candidate_predictions(
    predictions: pd.DataFrame,
    candidates: pd.DataFrame,
    thresholds: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    threshold_index = thresholds.set_index(
        ["label_policy", "model", "market_scope", "forecast_horizon", "test_year"]
    )
    for _, candidate in candidates.iterrows():
        mask = (
            (predictions["label_policy"] == candidate["label_policy"])
            & (predictions["model"] == candidate["model"])
            & (predictions["market_scope"] == candidate["market_scope"])
            & (predictions["forecast_horizon"] == candidate["forecast_horizon"])
        )
        group = predictions[mask].copy().sort_values("asof_date")
        if group.empty:
            continue
        if candidate["decision_method"] == "argmax":
            group["predicted_direction"] = group["argmax_label"]
            group["down_threshold"] = np.nan
            group["up_threshold"] = np.nan
        else:
            labels = []
            down_thresholds = []
            up_thresholds = []
            for _, row in group.iterrows():
                key = (
                    row["label_policy"],
                    row["model"],
                    row["market_scope"],
                    row["forecast_horizon"],
                    int(row["test_year"]),
                )
                if key not in threshold_index.index:
                    labels.append(row["argmax_label"])
                    down_thresholds.append(np.nan)
                    up_thresholds.append(np.nan)
                    continue
                th = threshold_index.loc[key]
                labels.append(
                    _threshold_label(
                        pd.DataFrame([row]),
                        float(th["down_threshold"]),
                        float(th["up_threshold"]),
                    ).iloc[0]
                )
                down_thresholds.append(float(th["down_threshold"]))
                up_thresholds.append(float(th["up_threshold"]))
            group["predicted_direction"] = labels
            group["down_threshold"] = down_thresholds
            group["up_threshold"] = up_thresholds
        group["candidate_type"] = candidate["candidate_type"]
        group["decision_method"] = candidate["decision_method"]
        group["confidence"] = group[LABEL_PROBS].max(axis=1)
        group["exposure"] = group["predicted_direction"].map(EXPOSURE_MAP).astype(float)
        rows.append(group)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _max_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _metric_row(group: pd.DataFrame, cost_bps: float) -> dict:
    returns = group["strategy_return"].fillna(0.0)
    buyhold = group["buyhold_return"].fillna(0.0)
    n = int(group.shape[0])
    ann_factor = 252 / n if n else np.nan
    cum_return = float((1.0 + returns).prod() - 1.0)
    buyhold_cum_return = float((1.0 + buyhold).prod() - 1.0)
    ann_return = float((1.0 + cum_return) ** ann_factor - 1.0) if n and cum_return > -1 else np.nan
    buyhold_ann_return = (
        float((1.0 + buyhold_cum_return) ** ann_factor - 1.0) if n and buyhold_cum_return > -1 else np.nan
    )
    ann_vol = float(returns.std(ddof=0) * np.sqrt(252)) if n else np.nan
    buyhold_ann_vol = float(buyhold.std(ddof=0) * np.sqrt(252)) if n else np.nan
    sharpe = float(ann_return / ann_vol) if ann_vol and not np.isnan(ann_vol) else np.nan
    buyhold_sharpe = float(buyhold_ann_return / buyhold_ann_vol) if buyhold_ann_vol else np.nan
    return {
        "candidate_type": group["candidate_type"].iloc[0],
        "decision_method": group["decision_method"].iloc[0],
        "market_scope": group["market_scope"].iloc[0],
        "forecast_horizon": group["forecast_horizon"].iloc[0],
        "label_policy": group["label_policy"].iloc[0],
        "model": group["model"].iloc[0],
        "start_date": group["asof_date"].min(),
        "end_date": group["asof_date"].max(),
        "days": n,
        "cost_bps": cost_bps,
        "cumulative_return": cum_return,
        "annualized_return": ann_return,
        "annualized_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(returns),
        "buyhold_cumulative_return": buyhold_cum_return,
        "buyhold_annualized_return": buyhold_ann_return,
        "buyhold_annualized_vol": buyhold_ann_vol,
        "buyhold_sharpe": buyhold_sharpe,
        "buyhold_max_drawdown": _max_drawdown(buyhold),
        "excess_cumulative_return": cum_return - buyhold_cum_return,
        "avg_exposure": float(group["exposure"].mean()),
        "avg_turnover": float(group["turnover"].mean()),
        "low_confidence_ratio": float(group["low_confidence_ratio"].mean())
        if "low_confidence_ratio" in group.columns
        else 0.0,
        "up_signal_ratio": float((group["predicted_direction"] == "up").mean()),
        "sideways_signal_ratio": float((group["predicted_direction"] == "sideways").mean()),
        "down_signal_ratio": float((group["predicted_direction"] == "down").mean()),
    }


def _run_backtest(predictions: pd.DataFrame, returns: pd.DataFrame, cost_bps: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = predictions.merge(returns, on=["asof_date", "market_scope"], how="inner")
    data = data.dropna(subset=["next_1d_return", "exposure"]).copy()
    data = data.sort_values(
        ["candidate_type", "market_scope", "forecast_horizon", "label_policy", "model", "asof_date"]
    )
    key_cols = ["candidate_type", "market_scope", "forecast_horizon", "label_policy", "model"]
    data["prev_exposure"] = data.groupby(key_cols)["exposure"].shift(1).fillna(0.0)
    data["turnover"] = (data["exposure"] - data["prev_exposure"]).abs()
    data["cost_return"] = data["turnover"] * cost_bps / 10000.0
    data["strategy_return"] = data["exposure"] * data["next_1d_return"] - data["cost_return"]
    data["buyhold_return"] = data["next_1d_return"]
    data["strategy_equity"] = data.groupby(key_cols)["strategy_return"].transform(lambda s: (1.0 + s).cumprod())
    data["buyhold_equity"] = data.groupby(key_cols)["buyhold_return"].transform(lambda s: (1.0 + s).cumprod())

    scorecard = pd.DataFrame([_metric_row(group, cost_bps) for _, group in data.groupby(key_cols, dropna=False)])
    scorecard = scorecard.sort_values(
        ["candidate_type", "forecast_horizon", "market_scope", "sharpe", "excess_cumulative_return"],
        ascending=[True, True, True, False, False],
    )
    return data, scorecard


def _write_markdown_report(scorecard: pd.DataFrame, path: Path) -> None:
    selected = scorecard[scorecard["candidate_type"] == "selected"].copy()
    cols = [
        "market_scope",
        "forecast_horizon",
        "decision_method",
        "label_policy",
        "model",
        "cumulative_return",
        "buyhold_cumulative_return",
        "excess_cumulative_return",
        "sharpe",
        "max_drawdown",
        "avg_exposure",
    ]
    table = selected[cols].copy()
    for col in [
        "cumulative_return",
        "buyhold_cumulative_return",
        "excess_cumulative_return",
        "sharpe",
        "max_drawdown",
        "avg_exposure",
    ]:
        table[col] = table[col].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")

    def markdown_table(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "No rows."
        text = frame.fillna("").astype(str)
        header = "| " + " | ".join(text.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(text.columns)) + " |"
        rows = ["| " + " | ".join(row) + " |" for row in text.to_numpy()]
        return "\n".join([header, separator, *rows])

    lines = [
        "# Market Dashboard Flow Signal Backtest",
        "",
        f"- generated_at: {_now_iso()}",
        "- rule: up=100%, sideways=50%, down=0%, daily close-to-next-close rebalance",
        "- universe: walk-forward out-of-sample predictions from 2022 onward",
        "",
        "## Selected Candidate Backtest",
        "",
        markdown_table(table),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_backtest(cost_bps: float, scopes: list[str] | None = None) -> dict:
    scopes = scopes or INVESTABLE_SCOPES
    predictions = _load_predictions(scopes)
    threshold_scorecard = pd.read_csv(THRESHOLD_SCORECARD_PATH)
    threshold_scorecard = threshold_scorecard[threshold_scorecard["market_scope"].isin(scopes)].copy()
    thresholds = pd.read_csv(THRESHOLDS_PATH)
    thresholds = thresholds[thresholds["market_scope"].isin(scopes)].copy()
    candidates = _select_candidates(threshold_scorecard, scopes)
    candidate_preds = _candidate_predictions(predictions, candidates, thresholds)
    returns = _load_next_day_returns(DB_PATH, scopes)
    trades, scorecard = _run_backtest(candidate_preds, returns, cost_bps)

    candidate_path = OUTPUT_DIR / "dashboard_axis_flow_backtest_candidate_set_current.csv"
    prediction_path = OUTPUT_DIR / "dashboard_axis_flow_backtest_predictions_current.csv"
    trade_path = OUTPUT_DIR / "dashboard_axis_flow_backtest_trades_current.csv"
    scorecard_path = OUTPUT_DIR / "dashboard_axis_flow_backtest_scorecard_current.csv"
    summary_path = REPORT_DIR / "dashboard_axis_flow_backtest_summary_latest.json"
    report_path = REPORT_DIR / "dashboard_axis_flow_backtest_latest.md"

    candidates.to_csv(candidate_path, index=False, encoding="utf-8-sig")
    candidate_preds.to_csv(prediction_path, index=False, encoding="utf-8-sig")
    trades.to_csv(trade_path, index=False, encoding="utf-8-sig")
    scorecard.to_csv(scorecard_path, index=False, encoding="utf-8-sig")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _write_markdown_report(scorecard, report_path)

    summary = {
        "status": "ok",
        "generated_at": _now_iso(),
        "rule": "up=100%, sideways=50%, down=0%, daily close-to-next-close rebalance",
        "scope_policy": "investable_only",
        "scopes": scopes,
        "cost_bps": cost_bps,
        "row_counts": {
            "source_predictions": int(predictions.shape[0]),
            "candidate_set": int(candidates.shape[0]),
            "candidate_predictions": int(candidate_preds.shape[0]),
            "trades": int(trades.shape[0]),
            "scorecard": int(scorecard.shape[0]),
        },
        "outputs": {
            "candidate_set": str(candidate_path),
            "candidate_predictions": str(prediction_path),
            "trades": str(trade_path),
            "scorecard": str(scorecard_path),
            "report": str(report_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest selected market dashboard flow signal candidates.")
    parser.add_argument("--cost-bps", type=float, default=5.0, help="One-way turnover cost in basis points.")
    parser.add_argument(
        "--scopes",
        default=",".join(INVESTABLE_SCOPES),
        help="Comma-separated market scopes. Default excludes ALL.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scopes = [item.strip() for item in args.scopes.split(",") if item.strip()]
    summary = run_backtest(cost_bps=args.cost_bps, scopes=scopes)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
