from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import DEFAULT_DB_PATH, ROOT_DIR

AXIS_IDS = [
    "financial_environment",
    "medium_term_model_outlook",
    "short_term_market_condition",
]
HORIZONS = [5, 10, 20, 60]
SCOPES = ["ALL", "KOSPI", "KOSDAQ", "KOSPI200"]
INDEX_CODES = {
    "KOSPI": "1001",
    "KOSDAQ": "2001",
    "KOSPI200": "1028",
}
LABELS = ["strong_down", "mild_down", "sideways", "mild_up", "strong_up"]
LABELS_3CLASS = ["down", "sideways", "up"]
LABEL_3CLASS_MAP = {
    "strong_down": "down",
    "mild_down": "down",
    "sideways": "sideways",
    "mild_up": "up",
    "strong_up": "up",
}


@dataclass(frozen=True)
class DashboardSignalResearchResult:
    generated_at: str
    source_db: Path
    target_db: Path
    output_dir: Path
    report_dir: Path
    row_counts: dict[str, int]
    latest_signal: dict
    model_metrics: list[dict]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def _read_latest_composite(source_db: Path, market: str) -> tuple[str, dict]:
    with _connect(source_db) as con:
        row = con.execute(
            """
            SELECT asof, payload_json
            FROM market_analysis_payload
            WHERE market = ?
              AND payload_type = 'today_bridge'
            ORDER BY asof DESC
            LIMIT 1
            """,
            (market,),
        ).fetchone()
    if row is None:
        raise RuntimeError("market_analysis_payload today_bridge rows are missing.")
    payload = json.loads(row["payload_json"])
    composite = payload.get("market_state_composite") or {}
    if not composite.get("enabled"):
        raise RuntimeError("market_state_composite is missing or disabled in latest payload.")
    return row["asof"], composite


def _build_axis_features(composite: dict) -> pd.DataFrame:
    chart = composite.get("composite_chart") or {}
    series = {item.get("series_id"): item for item in chart.get("series", [])}
    axis_frames = []
    for axis_id in AXIS_IDS:
        points = series.get(axis_id, {}).get("points") or []
        if not points:
            raise RuntimeError(f"market_state_composite axis has no points: {axis_id}")
        frame = pd.DataFrame(points)
        frame = frame[["date", "value"]].copy()
        frame = frame.rename(columns={"date": "asof_date", "value": axis_id})
        frame[axis_id] = pd.to_numeric(frame[axis_id], errors="coerce")
        axis_frames.append(frame)

    features = axis_frames[0]
    for frame in axis_frames[1:]:
        features = features.merge(frame, on="asof_date", how="outer")
    features = features.sort_values("asof_date").drop_duplicates("asof_date", keep="last")
    features["asof_date"] = pd.to_datetime(features["asof_date"]).dt.strftime("%Y-%m-%d")

    features["axis_avg"] = features[AXIS_IDS].mean(axis=1)
    features["axis_min"] = features[AXIS_IDS].min(axis=1)
    features["axis_max"] = features[AXIS_IDS].max(axis=1)
    features["axis_dispersion"] = features[AXIS_IDS].std(axis=1)
    features["env_x_model"] = features["financial_environment"] * features["medium_term_model_outlook"]
    features["env_x_short"] = features["financial_environment"] * features["short_term_market_condition"]
    features["model_x_short"] = features["medium_term_model_outlook"] * features["short_term_market_condition"]
    for axis_id in AXIS_IDS:
        features[f"{axis_id}_delta_1d"] = features[axis_id].diff(1)
        features[f"{axis_id}_delta_5d"] = features[axis_id].diff(5)
        features[f"{axis_id}_ma_5d"] = features[axis_id].rolling(5, min_periods=3).mean()
        features[f"{axis_id}_ma_20d"] = features[axis_id].rolling(20, min_periods=10).mean()
    return features


def _read_expanded_market_features(source_db: Path, market: str) -> pd.DataFrame:
    with _connect(source_db) as con:
        rows = con.execute(
            """
            WITH latest_features AS (
                SELECT
                    f.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY f.asof_date
                        ORDER BY f.asof DESC
                    ) AS rn
                FROM market_features_hourly f
                WHERE f.market = ?
            )
            SELECT
                f.asof_date,
                f.kospi_1d_ret,
                f.kospi_5d_ret,
                f.kospi_20d_ret,
                f.kospi_60d_ret,
                f.kosdaq_1d_ret,
                f.kosdaq_5d_ret,
                f.kosdaq_20d_ret,
                f.kosdaq_60d_ret,
                f.kospi200_20d_ret,
                f.usdkrw_20d_ret,
                f.rate_cd91_20d_chg,
                f.rate_ktb3y_20d_chg,
                f.above_20dma_ratio,
                f.above_60dma_ratio,
                f.adv_dec_ratio,
                f.new_high_count,
                f.new_low_count,
                f.breadth_universe_count,
                f.realized_vol_20d,
                f.drawdown_5d,
                f.drawdown_20d,
                f.bond_20d_ret,
                f.gold_20d_ret,
                f.inverse_20d_ret,
                f.breadth_proxy_flag,
                f.defensive_proxy_flag,
                f.regime_3m_score,
                c.trend_score,
                c.breadth_score,
                c.risk_score,
                c.defensive_flow_score,
                c.total_score AS production_total_score
            FROM latest_features f
            LEFT JOIN market_component_scores c
              ON c.market = f.market
             AND c.asof = f.asof
            WHERE f.rn = 1
            ORDER BY f.asof_date
            """,
            (market,),
        ).fetchall()
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return frame
    frame["asof_date"] = pd.to_datetime(frame["asof_date"]).dt.strftime("%Y-%m-%d")
    for col in frame.columns:
        if col != "asof_date":
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["new_high_low_balance"] = frame["new_high_count"] - frame["new_low_count"]
    frame["breadth_minus_risk"] = frame["breadth_score"] - frame["risk_score"]
    frame["trend_x_breadth"] = frame["trend_score"] * frame["breadth_score"]
    frame["risk_x_defensive"] = frame["risk_score"] * frame["defensive_flow_score"]
    return frame


def _read_flow_features(source_db: Path, market: str) -> pd.DataFrame:
    with _connect(source_db) as con:
        market_rows = con.execute(
            """
            SELECT date AS asof_date, market_scope, investor, net_buy_value
            FROM market_investor_flow_daily
            WHERE market = ?
              AND market_scope IN ('ALL', 'KOSPI', 'KOSDAQ')
              AND investor IN ('외국인', '기관합계', '개인')
            ORDER BY date, market_scope, investor
            """,
            (market,),
        ).fetchall()
        kiwoom_rows = con.execute(
            """
            SELECT date AS asof_date, market_scope, investor, ticker, net_value
            FROM kiwoom_stock_investor_flow_daily
            WHERE market_scope IN ('KOSPI', 'KOSDAQ')
              AND investor IN ('외국인', '기관합계', '개인', '연기금', '금융투자', '투신', '사모')
            ORDER BY date, market_scope, investor, ticker
            """
        ).fetchall()

    market_frame = pd.DataFrame([dict(row) for row in market_rows])
    kiwoom_frame = pd.DataFrame([dict(row) for row in kiwoom_rows])
    frames = []

    if not market_frame.empty:
        market_frame["net_buy_value"] = pd.to_numeric(market_frame["net_buy_value"], errors="coerce")
        pivot = market_frame.pivot_table(
            index=["asof_date", "market_scope"],
            columns="investor",
            values="net_buy_value",
            aggfunc="sum",
        ).reset_index()
        rename = {
            "외국인": "flow_foreign_net_eok",
            "기관합계": "flow_institution_net_eok",
            "개인": "flow_individual_net_eok",
        }
        pivot = pivot.rename(columns=rename)
        for col in rename.values():
            if col not in pivot.columns:
                pivot[col] = 0.0
            pivot[col] = pd.to_numeric(pivot[col], errors="coerce") / 100_000_000.0
        pivot["flow_smart_money_net_eok"] = pivot["flow_foreign_net_eok"] + pivot["flow_institution_net_eok"]
        pivot["flow_foreign_minus_individual_eok"] = pivot["flow_foreign_net_eok"] - pivot["flow_individual_net_eok"]
        pivot["flow_institution_minus_individual_eok"] = (
            pivot["flow_institution_net_eok"] - pivot["flow_individual_net_eok"]
        )
        pivot = pivot.sort_values(["market_scope", "asof_date"])
        for base in [
            "flow_foreign_net_eok",
            "flow_institution_net_eok",
            "flow_individual_net_eok",
            "flow_smart_money_net_eok",
        ]:
            for window in (3, 5):
                pivot[f"{base}_{window}d_sum"] = pivot.groupby("market_scope")[base].transform(
                    lambda s: s.rolling(window, min_periods=1).sum()
                )
        frames.append(pivot)

    if not kiwoom_frame.empty:
        kiwoom_frame["net_value"] = pd.to_numeric(kiwoom_frame["net_value"], errors="coerce")
        grouped = kiwoom_frame.groupby(["asof_date", "market_scope", "investor"], dropna=False)
        breadth = grouped.agg(
            net_value_sum=("net_value", "sum"),
            positive_count=("net_value", lambda s: int((s > 0).sum())),
            negative_count=("net_value", lambda s: int((s < 0).sum())),
            ticker_count=("ticker", "nunique"),
        ).reset_index()
        breadth["positive_ratio"] = breadth["positive_count"] / breadth["ticker_count"].replace({0: pd.NA})
        breadth["net_value_sum_eok"] = breadth["net_value_sum"] / 100_000_000.0
        value_pivot = breadth.pivot_table(
            index=["asof_date", "market_scope"],
            columns="investor",
            values="net_value_sum_eok",
            aggfunc="sum",
        ).reset_index()
        ratio_pivot = breadth.pivot_table(
            index=["asof_date", "market_scope"],
            columns="investor",
            values="positive_ratio",
            aggfunc="mean",
        ).reset_index()
        value_pivot = value_pivot.rename(
            columns={
                "외국인": "kiwoom_foreign_net_eok",
                "기관합계": "kiwoom_institution_net_eok",
                "개인": "kiwoom_individual_net_eok",
                "연기금": "kiwoom_pension_net_eok",
                "금융투자": "kiwoom_financial_invest_net_eok",
                "투신": "kiwoom_trust_net_eok",
                "사모": "kiwoom_private_fund_net_eok",
            }
        )
        ratio_pivot = ratio_pivot.rename(
            columns={
                "외국인": "kiwoom_foreign_positive_ratio",
                "기관합계": "kiwoom_institution_positive_ratio",
                "개인": "kiwoom_individual_positive_ratio",
                "연기금": "kiwoom_pension_positive_ratio",
                "금융투자": "kiwoom_financial_invest_positive_ratio",
                "투신": "kiwoom_trust_positive_ratio",
                "사모": "kiwoom_private_fund_positive_ratio",
            }
        )
        kiwoom_features = value_pivot.merge(ratio_pivot, on=["asof_date", "market_scope"], how="outer")
        for col in [
            "kiwoom_foreign_net_eok",
            "kiwoom_institution_net_eok",
            "kiwoom_individual_net_eok",
            "kiwoom_pension_net_eok",
        ]:
            if col not in kiwoom_features.columns:
                kiwoom_features[col] = 0.0
        kiwoom_features["kiwoom_smart_money_net_eok"] = (
            kiwoom_features["kiwoom_foreign_net_eok"] + kiwoom_features["kiwoom_institution_net_eok"]
        )
        kiwoom_features["kiwoom_foreign_minus_individual_eok"] = (
            kiwoom_features["kiwoom_foreign_net_eok"] - kiwoom_features["kiwoom_individual_net_eok"]
        )
        kiwoom_features["kiwoom_pension_plus_institution_eok"] = (
            kiwoom_features["kiwoom_pension_net_eok"] + kiwoom_features["kiwoom_institution_net_eok"]
        )
        kiwoom_features = kiwoom_features.sort_values(["market_scope", "asof_date"])
        for base in [
            "kiwoom_foreign_net_eok",
            "kiwoom_institution_net_eok",
            "kiwoom_individual_net_eok",
            "kiwoom_smart_money_net_eok",
        ]:
            for window in (3, 5):
                kiwoom_features[f"{base}_{window}d_sum"] = kiwoom_features.groupby("market_scope")[base].transform(
                    lambda s: s.rolling(window, min_periods=1).sum()
                )
        frames.append(kiwoom_features)

    if not frames:
        return pd.DataFrame()

    result = frames[0]
    for frame in frames[1:]:
        result = result.merge(frame, on=["asof_date", "market_scope"], how="outer")
    kospi_for_kospi200 = result[result["market_scope"] == "KOSPI"].copy()
    if not kospi_for_kospi200.empty:
        kospi_for_kospi200["market_scope"] = "KOSPI200"
        result = pd.concat([result, kospi_for_kospi200], ignore_index=True)
    result["asof_date"] = pd.to_datetime(result["asof_date"]).dt.strftime("%Y-%m-%d")
    for col in result.columns:
        if col not in {"asof_date", "market_scope"}:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result.sort_values(["market_scope", "asof_date"]).drop_duplicates(
        ["asof_date", "market_scope"],
        keep="last",
    )


def _read_index_returns(source_db: Path) -> pd.DataFrame:
    with _connect(source_db) as con:
        rows = con.execute(
            """
            SELECT index_code, index_name, date, close
            FROM market_index_daily
            WHERE market = 'KR'
              AND index_code IN ('1001', '2001', '1028')
              AND source != 'sample_seed'
            ORDER BY index_code, date
            """
        ).fetchall()
    raw = pd.DataFrame([dict(row) for row in rows])
    if raw.empty:
        raise RuntimeError("market_index_daily index rows are missing.")
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")

    scope_frames = []
    for scope, code in INDEX_CODES.items():
        item = raw[raw["index_code"] == code].copy().sort_values("date")
        item["market_scope"] = scope
        for horizon in HORIZONS:
            item[f"forward_return_{horizon}d"] = item["close"].shift(-horizon) / item["close"] - 1.0
        scope_frames.append(item[["date", "market_scope", *[f"forward_return_{h}d" for h in HORIZONS]]])

    wide = None
    for scope, code in INDEX_CODES.items():
        item = raw[raw["index_code"] == code].copy().sort_values("date")
        item = item[["date", "close"]].rename(columns={"close": scope})
        wide = item if wide is None else wide.merge(item, on="date", how="outer")
    wide = wide.sort_values("date")
    all_returns = pd.DataFrame({"date": wide["date"], "market_scope": "ALL"})
    for horizon in HORIZONS:
        kospi = wide["KOSPI"].shift(-horizon) / wide["KOSPI"] - 1.0
        kosdaq = wide["KOSDAQ"].shift(-horizon) / wide["KOSDAQ"] - 1.0
        all_returns[f"forward_return_{horizon}d"] = pd.concat([kospi, kosdaq], axis=1).mean(axis=1)
    scope_frames.append(all_returns)

    targets = pd.concat(scope_frames, ignore_index=True)
    targets = targets.rename(columns={"date": "asof_date"})
    return targets


def _label_from_thresholds(value: float, thresholds: dict[str, float]) -> str | None:
    if pd.isna(value):
        return None
    if value <= thresholds["q20"]:
        return "strong_down"
    if value <= thresholds["q40"]:
        return "mild_down"
    if value <= thresholds["q60"]:
        return "sideways"
    if value <= thresholds["q80"]:
        return "mild_up"
    return "strong_up"


def _label_to_3class(label: str | None) -> str | None:
    if label is None or pd.isna(label):
        return None
    return LABEL_3CLASS_MAP.get(str(label))


def _build_dataset(features: pd.DataFrame, targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dataset = features.merge(targets, on="asof_date", how="inner")
    thresholds = []
    for scope in SCOPES:
        scope_mask = dataset["market_scope"] == scope
        for horizon in HORIZONS:
            col = f"forward_return_{horizon}d"
            values = dataset.loc[scope_mask, col].dropna()
            if values.empty:
                continue
            quantiles = values.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
            row = {
                "market_scope": scope,
                "forecast_horizon": f"{horizon}d",
                "q20": float(quantiles[0.2]),
                "q40": float(quantiles[0.4]),
                "q60": float(quantiles[0.6]),
                "q80": float(quantiles[0.8]),
                "sample_count": int(values.shape[0]),
            }
            thresholds.append(row)
            label_col = f"direction_label_{horizon}d"
            th = {k: row[k] for k in ("q20", "q40", "q60", "q80")}
            dataset.loc[scope_mask, label_col] = dataset.loc[scope_mask, col].apply(
                lambda value: _label_from_thresholds(value, th)
            )
            dataset.loc[scope_mask, f"direction_label_3class_{horizon}d"] = dataset.loc[
                scope_mask, label_col
            ].apply(_label_to_3class)
    return dataset, pd.DataFrame(thresholds)


def _axis_bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "missing"
    if value >= 0.3:
        return "positive"
    if value <= -0.3:
        return "negative"
    return "neutral"


def _predictive_power(dataset: pd.DataFrame) -> pd.DataFrame:
    feature_cols = _model_feature_columns(dataset)
    rows = []
    for scope in SCOPES:
        scoped = dataset[dataset["market_scope"] == scope]
        for horizon in HORIZONS:
            target = f"forward_return_{horizon}d"
            for feature in feature_cols:
                valid = scoped[[feature, target]].dropna()
                if valid.shape[0] < 30 or valid[feature].nunique() < 2 or valid[target].nunique() < 2:
                    continue
                rows.append(
                    {
                        "market_scope": scope,
                        "forecast_horizon": f"{horizon}d",
                        "feature": feature,
                        "sample_count": int(valid.shape[0]),
                        "pearson_corr": float(valid[feature].corr(valid[target], method="pearson")),
                        "spearman_corr": float(valid[feature].corr(valid[target], method="spearman")),
                    }
                )
    return pd.DataFrame(rows)


def _combo_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    frame = dataset.copy()
    for axis_id in AXIS_IDS:
        frame[f"{axis_id}_bucket"] = frame[axis_id].apply(_axis_bucket)
    frame["axis_combo"] = (
        frame["financial_environment_bucket"]
        + "|"
        + frame["medium_term_model_outlook_bucket"]
        + "|"
        + frame["short_term_market_condition_bucket"]
    )
    rows = []
    for (scope, combo), group in frame.groupby(["market_scope", "axis_combo"], dropna=False):
        for horizon in HORIZONS:
            col = f"forward_return_{horizon}d"
            values = group[col].dropna()
            if values.shape[0] < 10:
                continue
            rows.append(
                {
                    "market_scope": scope,
                    "axis_combo": combo,
                    "forecast_horizon": f"{horizon}d",
                    "sample_count": int(values.shape[0]),
                    "avg_forward_return": float(values.mean()),
                    "median_forward_return": float(values.median()),
                    "positive_rate": float((values > 0).mean()),
                    "strong_loss_rate_5pct": float((values <= -0.05).mean()),
                }
            )
    return pd.DataFrame(rows)


def _model_feature_columns(dataset: pd.DataFrame) -> list[str]:
    excluded_prefixes = ("forward_return_", "direction_label_")
    excluded = {"asof_date", "market_scope"}
    cols = []
    for col in dataset.columns:
        if col in excluded or col.startswith(excluded_prefixes):
            continue
        if pd.api.types.is_numeric_dtype(dataset[col]):
            cols.append(col)
    return cols


def _usable_feature_columns(frame: pd.DataFrame, feature_cols: list[str], *, min_observed: int = 30) -> list[str]:
    usable = []
    for col in feature_cols:
        if col not in frame.columns:
            continue
        values = frame[col].dropna()
        if values.shape[0] >= min_observed and values.nunique() > 1:
            usable.append(col)
    return usable


def _sklearn_pipeline():
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=2000, class_weight="balanced"),
    )


def _train_label_models(
    dataset: pd.DataFrame,
    latest_features: pd.DataFrame,
    *,
    label_kind: str,
    label_column_template: str,
) -> tuple[pd.DataFrame, dict]:
    try:
        from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
    except Exception as exc:  # pragma: no cover - environment dependent
        return pd.DataFrame([{"status": "skipped", "reason": str(exc)}]), {}

    feature_cols = _model_feature_columns(dataset)
    metrics = []
    latest_predictions: dict[str, dict] = {}
    for scope in SCOPES:
        scoped = dataset[dataset["market_scope"] == scope].sort_values("asof_date")
        latest_feature = scoped[scoped[feature_cols].notna().any(axis=1)].sort_values("asof_date").tail(1)
        if latest_feature.empty:
            continue
        for horizon in HORIZONS:
            label_col = label_column_template.format(horizon=horizon)
            trainable = scoped.dropna(subset=[label_col]).copy()
            trainable = trainable[trainable[feature_cols].notna().any(axis=1)]
            if trainable.shape[0] < 200 or trainable[label_col].nunique() < 3:
                continue
            split = max(int(trainable.shape[0] * 0.8), trainable.shape[0] - 500)
            split = min(split, trainable.shape[0] - 50)
            if split <= 0:
                continue
            train = trainable.iloc[:split]
            test = trainable.iloc[split:]
            usable_features = _usable_feature_columns(train, feature_cols)
            if not usable_features:
                continue
            model = _sklearn_pipeline()
            model.fit(train[usable_features], train[label_col])
            pred = model.predict(test[usable_features])
            baseline = test[label_col].mode().iloc[0]
            metrics.append(
                {
                    "status": "ok",
                    "label_kind": label_kind,
                    "market_scope": scope,
                    "forecast_horizon": f"{horizon}d",
                    "train_start": train["asof_date"].min(),
                    "train_end": train["asof_date"].max(),
                    "test_start": test["asof_date"].min(),
                    "test_end": test["asof_date"].max(),
                    "train_count": int(train.shape[0]),
                    "test_count": int(test.shape[0]),
                    "feature_count": int(len(usable_features)),
                    "accuracy": float(accuracy_score(test[label_col], pred)),
                    "balanced_accuracy": float(balanced_accuracy_score(test[label_col], pred)),
                    "macro_f1": float(f1_score(test[label_col], pred, average="macro")),
                    "baseline_accuracy": float(accuracy_score(test[label_col], [baseline] * test.shape[0])),
                }
            )
            probs = model.predict_proba(latest_feature[usable_features])[0]
            classes = list(model.classes_)
            latest_predictions[f"{scope}_{horizon}d"] = {
                "market_scope": scope,
                "forecast_horizon": f"{horizon}d",
                "asof_date": latest_feature["asof_date"].iloc[0],
                "predicted_label": str(model.predict(latest_feature[usable_features])[0]),
                "class_probabilities": {
                    str(label): round(float(prob), 6) for label, prob in zip(classes, probs)
                },
            }
    return pd.DataFrame(metrics), latest_predictions


def _walk_forward_metrics(
    dataset: pd.DataFrame,
    *,
    label_kind: str,
    label_column_template: str,
    first_test_year: int = 2020,
) -> pd.DataFrame:
    try:
        from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
    except Exception as exc:  # pragma: no cover - environment dependent
        return pd.DataFrame([{"status": "skipped", "reason": str(exc)}])

    feature_cols = _model_feature_columns(dataset)
    frame = dataset.copy()
    frame["year"] = pd.to_datetime(frame["asof_date"]).dt.year
    rows = []
    for scope in SCOPES:
        scoped = frame[frame["market_scope"] == scope].sort_values("asof_date")
        years = [int(year) for year in sorted(scoped["year"].dropna().unique()) if int(year) >= first_test_year]
        for horizon in HORIZONS:
            label_col = label_column_template.format(horizon=horizon)
            for test_year in years:
                train = scoped[(scoped["year"] < test_year) & scoped[label_col].notna()].copy()
                test = scoped[(scoped["year"] == test_year) & scoped[label_col].notna()].copy()
                train = train[train[feature_cols].notna().any(axis=1)]
                test = test[test[feature_cols].notna().any(axis=1)]
                if train.shape[0] < 500 or test.shape[0] < 30 or train[label_col].nunique() < 3:
                    continue
                usable_features = _usable_feature_columns(train, feature_cols)
                if not usable_features:
                    continue
                model = _sklearn_pipeline()
                model.fit(train[usable_features], train[label_col])
                pred = model.predict(test[usable_features])
                baseline = test[label_col].mode().iloc[0]
                rows.append(
                    {
                        "status": "ok",
                        "label_kind": label_kind,
                        "market_scope": scope,
                        "forecast_horizon": f"{horizon}d",
                        "test_year": int(test_year),
                        "train_start": train["asof_date"].min(),
                        "train_end": train["asof_date"].max(),
                        "test_start": test["asof_date"].min(),
                        "test_end": test["asof_date"].max(),
                        "train_count": int(train.shape[0]),
                        "test_count": int(test.shape[0]),
                        "feature_count": int(len(usable_features)),
                        "accuracy": float(accuracy_score(test[label_col], pred)),
                        "balanced_accuracy": float(balanced_accuracy_score(test[label_col], pred)),
                        "macro_f1": float(f1_score(test[label_col], pred, average="macro")),
                        "baseline_accuracy": float(accuracy_score(test[label_col], [baseline] * test.shape[0])),
                    }
                )
    return pd.DataFrame(rows)


def _horizon_scorecard(metrics: pd.DataFrame, walk_forward: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return metrics
    rows = []
    for _, row in metrics.iterrows():
        if walk_forward.empty or "label_kind" not in walk_forward.columns:
            walk = pd.DataFrame()
        else:
            walk = walk_forward[
                (walk_forward["label_kind"] == row.get("label_kind"))
                & (walk_forward["market_scope"] == row.get("market_scope"))
                & (walk_forward["forecast_horizon"] == row.get("forecast_horizon"))
                & (walk_forward["status"] == "ok")
            ]
        rows.append(
            {
                "label_kind": row.get("label_kind"),
                "market_scope": row.get("market_scope"),
                "forecast_horizon": row.get("forecast_horizon"),
                "holdout_balanced_accuracy": row.get("balanced_accuracy"),
                "holdout_macro_f1": row.get("macro_f1"),
                "holdout_baseline_accuracy": row.get("baseline_accuracy"),
                "walk_forward_years": int(walk.shape[0]) if not walk.empty else 0,
                "walk_forward_balanced_accuracy_avg": float(walk["balanced_accuracy"].mean()) if not walk.empty else None,
                "walk_forward_macro_f1_avg": float(walk["macro_f1"].mean()) if not walk.empty else None,
                "walk_forward_baseline_accuracy_avg": float(walk["baseline_accuracy"].mean()) if not walk.empty else None,
            }
        )
    return pd.DataFrame(rows)


def _write_sqlite(target_db: Path, tables: dict[str, pd.DataFrame]) -> None:
    target_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target_db)) as con:
        for table, frame in tables.items():
            frame.to_sql(table, con, if_exists="replace", index=False)


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    text_frame = frame.copy()
    for col in text_frame.columns:
        text_frame[col] = text_frame[col].map(lambda value: "" if pd.isna(value) else str(value))
    header = "| " + " | ".join(text_frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_frame.columns)) + " |"
    rows = [
        "| " + " | ".join(str(row[col]) for col in text_frame.columns) + " |"
        for _, row in text_frame.iterrows()
    ]
    return "\n".join([header, separator, *rows])


def build_market_dashboard_signal_research(
    *,
    source_db: Path = DEFAULT_DB_PATH,
    target_db: Path = ROOT_DIR / "data" / "db" / "market_dashboard_signal_research.db",
    output_dir: Path = ROOT_DIR / "service_platform" / "research" / "market_dashboard_signal" / "current",
    report_dir: Path = ROOT_DIR / "reports" / "market_dashboard_signal_research",
    market: str = "KR",
) -> DashboardSignalResearchResult:
    generated_at = _now_iso()
    latest_asof, composite = _read_latest_composite(source_db, market)
    axis_features = _build_axis_features(composite)
    expanded_features = _read_expanded_market_features(source_db, market)
    if not expanded_features.empty:
        axis_features = axis_features.merge(expanded_features, on="asof_date", how="left")
    targets = _read_index_returns(source_db)
    dataset, thresholds = _build_dataset(axis_features, targets)
    flow_features = _read_flow_features(source_db, market)
    if not flow_features.empty:
        dataset = dataset.merge(flow_features, on=["asof_date", "market_scope"], how="left")
    predictive = _predictive_power(dataset)
    combo = _combo_summary(dataset)
    model_metrics, latest_predictions = _train_label_models(
        dataset,
        axis_features,
        label_kind="5class",
        label_column_template="direction_label_{horizon}d",
    )
    model_metrics_3class, latest_predictions_3class = _train_label_models(
        dataset,
        axis_features,
        label_kind="3class",
        label_column_template="direction_label_3class_{horizon}d",
    )
    walk_forward_metrics = _walk_forward_metrics(
        dataset,
        label_kind="3class",
        label_column_template="direction_label_3class_{horizon}d",
    )
    scorecard = _horizon_scorecard(model_metrics_3class, walk_forward_metrics)

    latest_axis = axis_features.sort_values("asof_date").iloc[-1].to_dict()
    latest_signal = {
        "schema_version": "market_dashboard_signal_research.v2",
        "generated_at": generated_at,
        "source_payload_asof": latest_asof,
        "latest_axis_asof_date": latest_axis.get("asof_date"),
        "axis_ids": AXIS_IDS,
        "axis_values": {
            axis_id: None if pd.isna(latest_axis.get(axis_id)) else round(float(latest_axis.get(axis_id)), 6)
            for axis_id in AXIS_IDS
        },
        "axis_combo_bucket": "|".join(_axis_bucket(latest_axis.get(axis_id)) for axis_id in AXIS_IDS),
        "model_predictions": latest_predictions,
        "model_predictions_3class": latest_predictions_3class,
        "label_policy": {
            "type": "per_scope_horizon_quantile_5class_and_collapsed_3class",
            "labels": LABELS,
            "labels_3class": LABELS_3CLASS,
            "display_mapping": {
                "down": ["strong_down", "mild_down"],
                "sideways": ["sideways"],
                "up": ["mild_up", "strong_up"],
            },
        },
        "feature_policy": {
            "base": "market_state_composite 3-axis",
            "expanded": [
                "market_features_hourly latest daily features",
                "market_component_scores production component scores",
                "market_investor_flow_daily official/proxy flow aggregates",
                "kiwoom_stock_investor_flow_daily stock-level flow breadth aggregates",
            ],
            "feature_count": len(_model_feature_columns(dataset)),
            "flow_feature_available_dates": {
                "min": None if flow_features.empty else str(flow_features["asof_date"].min()),
                "max": None if flow_features.empty else str(flow_features["asof_date"].max()),
                "rows": int(flow_features.shape[0]) if not flow_features.empty else 0,
            },
        },
        "notes": [
            "Production market analysis mart is not modified.",
            "ALL forward return is the equal-weight average of KOSPI and KOSDAQ forward returns.",
            "Metrics are research diagnostics, not production trading signals.",
        ],
    }

    tables = {
        "dashboard_axis_feature_daily": axis_features,
        "dashboard_axis_flow_feature_daily": flow_features,
        "dashboard_axis_target_daily": targets,
        "dashboard_axis_model_dataset": dataset,
        "dashboard_axis_label_thresholds": thresholds,
        "dashboard_axis_predictive_power": predictive,
        "dashboard_axis_combo_summary": combo,
        "dashboard_axis_model_metrics": model_metrics,
        "dashboard_axis_model_metrics_3class": model_metrics_3class,
        "dashboard_axis_walk_forward_metrics": walk_forward_metrics,
        "dashboard_axis_horizon_scorecard": scorecard,
    }
    _write_sqlite(target_db, tables)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "dashboard_axis_model_dataset_current.csv", dataset)
    _write_csv(output_dir / "dashboard_axis_flow_feature_daily_current.csv", flow_features)
    _write_csv(output_dir / "dashboard_axis_label_thresholds_current.csv", thresholds)
    _write_csv(output_dir / "dashboard_axis_predictive_power_current.csv", predictive)
    _write_csv(output_dir / "dashboard_axis_combo_summary_current.csv", combo)
    _write_csv(output_dir / "dashboard_axis_model_metrics_current.csv", model_metrics)
    _write_csv(output_dir / "dashboard_axis_model_metrics_3class_current.csv", model_metrics_3class)
    _write_csv(output_dir / "dashboard_axis_walk_forward_metrics_current.csv", walk_forward_metrics)
    _write_csv(output_dir / "dashboard_axis_horizon_scorecard_current.csv", scorecard)
    (output_dir / "dashboard_axis_signal_latest.json").write_text(
        json.dumps(latest_signal, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "market_dashboard_signal_research_manifest.v1",
        "generated_at": generated_at,
        "source_db": str(source_db),
        "source_payload_asof": latest_asof,
        "target_db": str(target_db),
        "output_dir": str(output_dir),
        "report_dir": str(report_dir),
        "row_counts": {name: int(frame.shape[0]) for name, frame in tables.items()},
        "files": {
            "dataset": "dashboard_axis_model_dataset_current.csv",
            "flow_features": "dashboard_axis_flow_feature_daily_current.csv",
            "thresholds": "dashboard_axis_label_thresholds_current.csv",
            "predictive_power": "dashboard_axis_predictive_power_current.csv",
            "combo_summary": "dashboard_axis_combo_summary_current.csv",
            "model_metrics": "dashboard_axis_model_metrics_current.csv",
            "model_metrics_3class": "dashboard_axis_model_metrics_3class_current.csv",
            "walk_forward_metrics": "dashboard_axis_walk_forward_metrics_current.csv",
            "horizon_scorecard": "dashboard_axis_horizon_scorecard_current.csv",
            "latest_signal": "dashboard_axis_signal_latest.json",
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "market_dashboard_signal_research_latest.json").write_text(
        json.dumps({**manifest, "latest_signal": latest_signal}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    top_predictive = predictive.copy()
    if not top_predictive.empty:
        top_predictive["abs_spearman_corr"] = top_predictive["spearman_corr"].abs()
        top_predictive = top_predictive.sort_values(
            ["market_scope", "forecast_horizon", "abs_spearman_corr"],
            ascending=[True, True, False],
        ).groupby(["market_scope", "forecast_horizon"]).head(5)
    report_md = [
        "# Market Dashboard Signal Research",
        "",
        f"- generated_at: {generated_at}",
        f"- source_payload_asof: {latest_asof}",
        f"- latest_axis_asof_date: {latest_signal['latest_axis_asof_date']}",
        f"- target_db: {target_db}",
        "",
        "## Latest Signal",
        "",
        "```json",
        json.dumps(latest_signal, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Top Predictive Features",
        "",
        _markdown_table(top_predictive) if not top_predictive.empty else "No predictive feature rows.",
        "",
        "## Model Metrics",
        "",
        _markdown_table(model_metrics) if not model_metrics.empty else "No model metrics.",
        "",
        "## 3-Class Model Metrics",
        "",
        _markdown_table(model_metrics_3class) if not model_metrics_3class.empty else "No 3-class model metrics.",
        "",
        "## 3-Class Horizon Scorecard",
        "",
        _markdown_table(scorecard) if not scorecard.empty else "No scorecard rows.",
        "",
        "## 3-Class Walk-Forward Metrics",
        "",
        _markdown_table(walk_forward_metrics) if not walk_forward_metrics.empty else "No walk-forward rows.",
    ]
    (report_dir / "market_dashboard_signal_research_latest.md").write_text(
        "\n".join(report_md),
        encoding="utf-8",
    )

    return DashboardSignalResearchResult(
        generated_at=generated_at,
        source_db=source_db,
        target_db=target_db,
        output_dir=output_dir,
        report_dir=report_dir,
        row_counts={name: int(frame.shape[0]) for name, frame in tables.items()},
        latest_signal=latest_signal,
        model_metrics=model_metrics_3class.to_dict("records"),
    )
