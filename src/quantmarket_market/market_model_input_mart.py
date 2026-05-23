from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KST = timezone(timedelta(hours=9))

SCHEMA_VERSION = "market_model_input_daily.v7"
FEATURE_VERSION = "qm_market_model_input_features.v7_macro_surprise_20260514"

CORE_FEATURE_GROUPS = {
    "forecast_context": [
        "market_forecast_score",
        "expected_volatility_score",
        "drawdown_risk_score",
        "upside_participation_score",
        "confidence_score",
        "baseline_market_state_score",
        "baseline_trend_score",
        "baseline_breadth_score",
        "baseline_risk_on_score",
        "baseline_risk_off_score",
        "baseline_global_risk_on_score",
        "baseline_external_asset_risk_on_score",
        "baseline_external_macro_pressure_score",
        "baseline_smart_money_score",
    ],
    "domestic_market_context": [
        "market_state_score",
        "trend_score",
        "breadth_score",
        "risk_score",
        "defensive_flow_score",
        "market_vol_20d",
        "market_mdd_3m",
        "market_breadth_ret_pos_1m",
        "market_breadth_above_sma20",
        "market_breadth_above_sma60",
        "market_breadth_above_sma120",
        "new_high_ratio_20d",
        "new_low_ratio_20d",
        "trading_value_expansion_ratio",
        "risk_on_score",
        "risk_off_score",
    ],
    "risk_context": [
        "defensive_asset_strength_score",
        "market_stress_score",
        "drawdown_pressure_score",
        "crash_warning_flag",
    ],
    "flow_context": [
        "foreign_net_buy_ratio",
        "institution_net_buy_ratio",
        "retail_net_buy_ratio",
        "flow_concentration_score",
        "smart_money_score",
    ],
    "domestic_flow_derivatives_context": [
        "domestic_flow_derivatives_score",
        "foreign_net_buy_value_krw",
        "institution_net_buy_value_krw",
        "retail_net_buy_value_krw",
        "foreign_net_buy_ratio_5d",
        "foreign_net_buy_ratio_20d",
        "institution_net_buy_ratio_5d",
        "institution_net_buy_ratio_20d",
        "foreign_buying_breadth",
        "institution_buying_breadth",
        "smart_money_score_5d",
        "smart_money_score_20d",
        "futures_change_pct",
        "futures_direction_score",
        "program_pressure_score",
        "derivatives_pressure_score",
    ],
    "macro_event_context": [
        "macro_event_pressure_score",
        "macro_event_count",
        "scheduled_macro_event_count",
        "macro_shock_event_count",
        "major_macro_event_flag",
        "macro_event_risk_window_flag",
        "pre_macro_event_1d_flag",
        "post_macro_event_1d_flag",
        "days_since_scheduled_macro_event",
        "days_to_next_scheduled_macro_event",
        "macro_event_density_5d",
        "inflation_release_flag",
        "employment_release_flag",
        "policy_rate_release_flag",
        "rate_shock_event_flag",
        "fx_shock_event_flag",
        "vix_shock_event_flag",
        "credit_shock_event_flag",
    ],
    "macro_surprise_context": [
        "macro_surprise_risk_off_score",
        "macro_surprise_pressure_score",
        "macro_surprise_relief_score",
        "macro_surprise_event_count",
        "macro_surprise_abs_zscore_max",
        "inflation_surprise_risk_off_score",
        "employment_surprise_risk_off_score",
        "policy_surprise_risk_off_score",
        "wage_surprise_risk_off_score",
        "macro_surprise_event_density_63d",
        "macro_surprise_proxy_available_flag",
        "macro_surprise_consensus_available_flag",
    ],
    "global_macro_context": [
        "rate_pressure_score",
        "usd_pressure_score",
        "credit_stress_score",
        "risk_aversion_score",
        "inflation_pressure_score",
        "commodity_pressure_score",
        "global_risk_on_score",
        "external_macro_pressure_score",
        "yield_curve_10y_2y",
        "yield_curve_10y_3m",
        "us_10y_rate",
        "us_2y_rate",
        "vix_level",
        "hy_spread",
        "ig_spread",
        "dxy_level",
        "usdkrw_level",
        "wti_level",
        "cpi_yoy",
        "core_cpi_yoy",
        "unrate",
        "payrolls_3m_change",
    ],
    "external_market_context": [
        "external_asset_risk_on_score",
        "us_equity_momentum_score",
        "us_growth_risk_score",
        "us_smallcap_risk_score",
        "us_sector_risk_on_score",
        "us_defensive_sector_score",
        "global_breadth_proxy_score",
        "korea_proxy_momentum_score",
        "credit_proxy_score",
        "safe_haven_pressure_score",
        "commodity_risk_score",
        "dollar_risk_score",
        "vix_market_stress_score",
        "semiconductor_momentum_score",
        "global_ex_us_momentum_score",
        "em_vs_dm_score",
        "asia_risk_on_score",
        "bank_stress_relief_score",
        "rate_sensitive_cyclical_score",
        "transport_cyclical_score",
        "low_vol_defensive_pressure_score",
        "crypto_risk_appetite_score",
        "spy_ret_1m",
        "spy_ret_3m",
        "qqq_ret_1m",
        "qqq_ret_3m",
        "iwm_ret_1m",
        "ewy_ret_1m",
        "ewy_ret_3m",
        "sector_cyclical_vs_defensive_1m",
        "sector_positive_ratio_1m",
        "sector_above_sma60_ratio",
        "hyg_lqd_ret_spread_1m",
        "tlt_ret_1m",
        "gld_ret_1m",
        "uso_ret_1m",
        "uup_ret_1m",
        "vix_ret_1m",
        "soxx_ret_1m",
        "soxx_ret_3m",
        "acwx_ret_1m",
        "efa_ret_1m",
        "eem_ret_1m",
        "fxi_ret_1m",
        "ewj_ret_1m",
        "ewt_ret_1m",
        "inda_ret_1m",
        "kre_ret_1m",
        "xhb_ret_1m",
        "iyt_ret_1m",
        "usmv_ret_1m",
        "dxy_ret_1m",
        "btcusd_ret_1m",
    ],
    "ai_calibration_context": [
        "predicted_forward_return",
        "calibrated_forecast_score",
        "calibration_confidence_score",
        "training_sample_count",
    ],
    "regime_change_context": [
        "market_state_score_delta_1d",
        "market_state_score_delta_5d",
        "market_state_score_delta_20d",
        "trend_score_delta_5d",
        "breadth_score_delta_5d",
        "risk_score_delta_5d",
        "risk_on_score_delta_5d",
        "risk_off_score_delta_5d",
        "global_risk_on_score_delta_5d",
        "external_asset_risk_on_score_delta_5d",
        "market_forecast_score_delta_5d",
        "market_forecast_score_acceleration_5d",
        "state_change_flag",
        "transition_count_5d",
        "transition_count_20d",
        "days_since_state_change",
        "regime_stability_score",
    ],
}


@dataclass(frozen=True)
class ModelInputMartResult:
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


def _read_table(con: sqlite3.Connection, name: str) -> pd.DataFrame:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    if not exists:
        return pd.DataFrame()
    return pd.read_sql_query(f"SELECT * FROM {name}", con)


def _select_existing(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = None
    return df[columns].copy()


def _missing_rates(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {}
    return {column: round(float(df[column].isna().mean()), 6) for column in df.columns}


def _coverage_quality_label(ratio: float) -> str:
    if ratio >= 0.85:
        return "high"
    if ratio >= 0.65:
        return "medium"
    if ratio >= 0.35:
        return "low"
    return "very_low"


def _regime_direction(delta: float | None, threshold: float = 0.1) -> str:
    if delta is None or pd.isna(delta):
        return "unknown"
    if delta > threshold:
        return "improving"
    if delta < -threshold:
        return "deteriorating"
    return "unchanged"


def _regime_momentum_label(delta_5d: float | None, acceleration_5d: float | None) -> str:
    if delta_5d is None or pd.isna(delta_5d):
        return "unknown"
    accel = 0.0 if acceleration_5d is None or pd.isna(acceleration_5d) else float(acceleration_5d)
    if delta_5d > 0.2 and accel > 0.0:
        return "improving_accelerating"
    if delta_5d > 0.2:
        return "improving"
    if delta_5d < -0.2 and accel < 0.0:
        return "deteriorating_accelerating"
    if delta_5d < -0.2:
        return "deteriorating"
    return "stable"


def _days_since_change(flags: pd.Series) -> list[int | None]:
    days: list[int | None] = []
    current: int | None = None
    for flag in flags.fillna(0).astype(int):
        if current is None:
            current = 0
        elif flag == 1:
            current = 0
        else:
            current += 1
        days.append(current)
    return days


def _add_regime_change_features(out: pd.DataFrame) -> pd.DataFrame:
    frame = out.sort_values(["market_scope", "forecast_horizon", "asof_date"]).copy()
    groups = frame.groupby(["market_scope", "forecast_horizon"], sort=False)

    delta_specs = {
        "market_state_score": [1, 5, 20],
        "trend_score": [5, 20],
        "breadth_score": [5, 20],
        "risk_score": [5, 20],
        "risk_on_score": [5, 20],
        "risk_off_score": [5, 20],
        "global_risk_on_score": [5, 20],
        "external_asset_risk_on_score": [5, 20],
        "market_forecast_score": [1, 5, 20],
        "calibrated_forecast_score": [5, 20],
    }
    for column, windows in delta_specs.items():
        if column not in frame.columns:
            continue
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        for window in windows:
            frame[f"{column}_delta_{window}d"] = groups[column].diff(window).round(6)

    if "market_forecast_score_delta_5d" in frame.columns:
        frame["market_forecast_score_acceleration_5d"] = groups["market_forecast_score_delta_5d"].diff(5).round(6)
    else:
        frame["market_forecast_score_acceleration_5d"] = None

    previous_label = groups["market_state_label"].shift(1) if "market_state_label" in frame.columns else pd.Series(index=frame.index, dtype=object)
    frame["previous_market_state_label"] = previous_label
    frame["state_change_flag"] = (
        (frame["market_state_label"].notna())
        & (previous_label.notna())
        & (frame["market_state_label"] != previous_label)
    ).astype(int)
    frame["state_change_direction"] = frame["market_state_score_delta_1d"].map(_regime_direction)
    frame["transition_count_5d"] = groups["state_change_flag"].transform(lambda s: s.rolling(5, min_periods=1).sum()).astype(int)
    frame["transition_count_20d"] = groups["state_change_flag"].transform(lambda s: s.rolling(20, min_periods=1).sum()).astype(int)
    frame["days_since_state_change"] = groups["state_change_flag"].transform(_days_since_change).astype(int)
    frame["regime_stability_score"] = (1.0 - (frame["transition_count_20d"] / 5.0).clip(lower=0.0, upper=1.0)).round(6)
    frame["regime_momentum_label"] = [
        _regime_momentum_label(delta, accel)
        for delta, accel in zip(
            frame.get("market_state_score_delta_5d", pd.Series(index=frame.index, dtype=float)),
            frame["market_forecast_score_acceleration_5d"],
            strict=False,
        )
    ]
    return frame.sort_values(["asof_date", "market_scope", "forecast_horizon"]).reset_index(drop=True)


def _add_coverage_flags(out: pd.DataFrame) -> pd.DataFrame:
    frame = out.copy()
    group_ratio_columns = []
    group_null_count_columns = []
    for group_name, columns in CORE_FEATURE_GROUPS.items():
        existing = [column for column in columns if column in frame.columns]
        available_column = f"{group_name}_available_flag"
        ratio_column = f"{group_name}_coverage_ratio"
        null_count_column = f"{group_name}_null_count"
        expected_count_column = f"{group_name}_expected_feature_count"

        if existing:
            non_null = frame[existing].notna()
            frame[available_column] = non_null.any(axis=1).astype(int)
            frame[ratio_column] = non_null.mean(axis=1).round(6)
            frame[null_count_column] = frame[existing].isna().sum(axis=1).astype(int)
            frame[expected_count_column] = len(existing)
        else:
            frame[available_column] = 0
            frame[ratio_column] = 0.0
            frame[null_count_column] = 0
            frame[expected_count_column] = 0

        group_ratio_columns.append(ratio_column)
        group_null_count_columns.append(null_count_column)

    frame["source_group_available_count"] = frame[
        [f"{group_name}_available_flag" for group_name in CORE_FEATURE_GROUPS]
    ].sum(axis=1)
    frame["source_group_expected_count"] = len(CORE_FEATURE_GROUPS)
    frame["overall_feature_coverage_ratio"] = frame[group_ratio_columns].mean(axis=1).round(6)
    frame["overall_null_count"] = frame[group_null_count_columns].sum(axis=1).astype(int)
    frame["coverage_quality_label"] = frame["overall_feature_coverage_ratio"].map(_coverage_quality_label)
    frame["coverage_policy"] = (
        "available_flag=1 means at least one core feature in the source group is present; "
        "coverage_ratio is non-null core features divided by expected core features; null values are preserved."
    )
    return frame


def _dtype_for_series(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "number"
    return "string"


def _score_direction(column: str) -> str | None:
    risk_on_columns = {
        "market_forecast_score",
        "calibrated_forecast_score",
        "market_state_score",
        "trend_score",
        "breadth_score",
        "defensive_flow_score",
        "risk_on_score",
        "baseline_external_asset_risk_on_score",
        "external_asset_risk_on_score",
        "us_equity_momentum_score",
        "us_sector_risk_on_score",
        "global_breadth_proxy_score",
        "korea_proxy_momentum_score",
        "credit_proxy_score",
        "semiconductor_momentum_score",
        "global_ex_us_momentum_score",
        "em_vs_dm_score",
        "asia_risk_on_score",
        "bank_stress_relief_score",
        "rate_sensitive_cyclical_score",
        "transport_cyclical_score",
        "crypto_risk_appetite_score",
        "domestic_flow_derivatives_score",
        "smart_money_score_5d",
        "smart_money_score_20d",
        "futures_direction_score",
        "program_pressure_score",
        "derivatives_pressure_score",
        "macro_event_pressure_score",
        "macro_surprise_relief_score",
        "global_risk_on_score",
        "liquidity_score",
        "global_growth_score",
        "policy_easing_score",
    }
    risk_off_columns = {
        "risk_score",
        "risk_off_score",
        "expected_volatility_score",
        "drawdown_risk_score",
        "drawdown_pressure_score",
        "market_stress_score",
        "us_growth_risk_score",
        "us_smallcap_risk_score",
        "us_defensive_sector_score",
        "safe_haven_pressure_score",
        "commodity_risk_score",
        "dollar_risk_score",
        "vix_market_stress_score",
        "low_vol_defensive_pressure_score",
        "rate_pressure_score",
        "usd_pressure_score",
        "credit_stress_score",
        "risk_aversion_score",
        "inflation_pressure_score",
        "commodity_pressure_score",
        "external_macro_pressure_score",
        "macro_shock_event_count",
        "macro_event_density_5d",
        "macro_surprise_risk_off_score",
        "macro_surprise_pressure_score",
        "macro_surprise_abs_zscore_max",
        "inflation_surprise_risk_off_score",
        "policy_surprise_risk_off_score",
        "wage_surprise_risk_off_score",
    }
    if column in risk_on_columns:
        return "higher_is_more_risk_on"
    if column in risk_off_columns:
        return "higher_is_more_risk_off"
    return None


def _update_schema(output_dir: Path, out: pd.DataFrame) -> None:
    schema_path = output_dir / "schema.json"
    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            schema = {}
    else:
        schema = {}

    schema.setdefault("schema_version", SCHEMA_VERSION)
    schema.setdefault("tables", {})
    schema["tables"]["market_model_input_daily"] = {
        "description": (
            "Quant 모델 학습/추론용 wide market input mart. 국내 market/risk/flow, "
            "FRED macro, 해외 ETF proxy, baseline forecast, AI calibrated forecast를 "
            "asof_date 기준으로 point-in-time 조인한 소비 계약 테이블입니다."
        ),
        "primary_key": ["asof_date", "market_scope", "forecast_horizon"],
        "join_keys": ["asof_date", "market_scope", "forecast_horizon"],
        "timezone": "Asia/Seoul",
        "point_in_time_policy": (
            "각 row는 asof_date 당시 확보 가능한 장마감/공개 확정 데이터와 "
            "PIT lag가 적용된 외부 지표만 사용합니다. US/FRED/Yahoo source date는 "
            "KST 다음 영업일 이후에만 조인되며, 월간 FRED macro는 보수적 21일 "
            "release lag 이후에만 사용됩니다. realized target 수익률은 검증 전용 "
            "컬럼이며 학습 feature로 사용할 때 제외해야 합니다."
        ),
        "coverage_policy": (
            "각 source group별 `*_available_flag`, `*_coverage_ratio`, `*_null_count`, "
            "`*_expected_feature_count`를 제공합니다. null은 원천 부재 또는 lookback 부족을 "
            "나타내며 0으로 대체하지 않습니다."
        ),
        "regime_change_policy": (
            "국면 변화 feature는 동일 market_scope + forecast_horizon 시계열 내 과거 row만 사용해 "
            "delta, 전환 횟수, 안정성 점수를 계산합니다. 미래 수익률이나 미래 상태는 사용하지 않습니다."
        ),
        "feature_version": FEATURE_VERSION,
        "columns": [
            {
                "column_name": column,
                "data_type": _dtype_for_series(out[column]),
                "nullable": bool(out[column].isna().any()),
                "score_direction": _score_direction(column),
            }
            for column in out.columns
        ],
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")


def build_market_model_input_mart(
    *,
    market_context_db: Path,
    output_dir: Path,
    report_dir: Path,
) -> ModelInputMartResult:
    generated_at = _now_kst()
    with _connect(market_context_db) as con:
        market = _read_table(con, "market_context_daily")
        risk = _read_table(con, "risk_context_daily")
        flow = _read_table(con, "flow_context_daily")
        domestic_flow_derivatives = _read_table(con, "domestic_flow_derivatives_daily")
        macro_event_calendar = _read_table(con, "macro_event_calendar_daily")
        macro_surprise_context = _read_table(con, "macro_surprise_context_daily")
        global_context = _read_table(con, "global_context_daily")
        external = _read_table(con, "external_market_context_daily")
        forecast = _read_table(con, "market_forecast_daily")
        calibrated = _read_table(con, "market_forecast_ai_calibrated_daily")

    if forecast.empty:
        raise RuntimeError("market_forecast_daily is required to build market_model_input_daily.")

    out = _select_existing(
        forecast,
        [
            "asof_date",
            "market_scope",
            "forecast_horizon",
            "market_forecast_score",
            "market_forecast_label",
            "risk_regime_label",
            "expected_volatility_score",
            "drawdown_risk_score",
            "upside_participation_score",
            "confidence_score",
            "baseline_external_asset_risk_on_score",
            "forecast_model_version",
        ],
    )

    market_cols = [
        "asof_date",
        "market_scope",
        "market_state_label",
        "market_state_score",
        "trend_score",
        "breadth_score",
        "risk_score",
        "defensive_flow_score",
        "market_vol_20d",
        "market_mdd_3m",
        "market_breadth_ret_pos_1m",
        "market_breadth_above_sma20",
        "market_breadth_above_sma60",
        "market_breadth_above_sma120",
        "new_high_ratio_20d",
        "new_low_ratio_20d",
        "trading_value_expansion_ratio",
        "risk_on_score",
        "risk_off_score",
    ]
    out = out.merge(_select_existing(market, market_cols), on=["asof_date", "market_scope"], how="left")

    risk_cols = [
        "asof_date",
        "defensive_asset_strength_score",
        "market_stress_score",
        "drawdown_pressure_score",
        "crash_warning_flag",
        "volatility_regime_label",
    ]
    out = out.merge(_select_existing(risk, risk_cols), on="asof_date", how="left")

    flow_cols = [
        "asof_date",
        "market_scope",
        "foreign_net_buy_ratio",
        "institution_net_buy_ratio",
        "retail_net_buy_ratio",
        "flow_concentration_score",
        "smart_money_score",
        "flow_context_available",
        "flow_coverage_flag",
    ]
    out = out.merge(_select_existing(flow, flow_cols), on=["asof_date", "market_scope"], how="left")

    domestic_flow_derivatives_cols = [
        "asof_date",
        "market_scope",
        "domestic_flow_derivatives_score",
        "foreign_net_buy_value_krw",
        "institution_net_buy_value_krw",
        "retail_net_buy_value_krw",
        "foreign_net_buy_volume",
        "institution_net_buy_volume",
        "retail_net_buy_volume",
        "total_abs_net_value_krw",
        "foreign_net_buy_ratio_5d",
        "foreign_net_buy_ratio_20d",
        "institution_net_buy_ratio_5d",
        "institution_net_buy_ratio_20d",
        "foreign_buying_breadth",
        "institution_buying_breadth",
        "retail_net_buy_ratio_5d",
        "retail_net_buy_ratio_20d",
        "retail_buying_breadth",
        "foreign_net_buy_days_5d",
        "institution_net_buy_days_5d",
        "smart_money_score_5d",
        "smart_money_score_20d",
        "futures_price",
        "futures_change_pct",
        "futures_volume",
        "futures_value_million",
        "program_total_net_krw",
        "program_nonarb_net_krw",
        "futures_direction_score",
        "program_pressure_score",
        "derivatives_pressure_score",
        "investor_flow_available",
        "derivatives_context_available",
        "domestic_flow_available",
    ]
    out = out.merge(
        _select_existing(domestic_flow_derivatives, domestic_flow_derivatives_cols),
        on=["asof_date", "market_scope"],
        how="left",
    )

    macro_event_cols = [
        "asof_date",
        "macro_event_pressure_score",
        "macro_event_count",
        "scheduled_macro_event_count",
        "macro_shock_event_count",
        "major_macro_event_flag",
        "macro_event_risk_window_flag",
        "pre_macro_event_1d_flag",
        "post_macro_event_1d_flag",
        "days_since_scheduled_macro_event",
        "days_to_next_scheduled_macro_event",
        "macro_event_density_5d",
        "inflation_release_flag",
        "employment_release_flag",
        "policy_rate_release_flag",
        "producer_price_release_flag",
        "wage_release_flag",
        "rate_shock_event_flag",
        "fx_shock_event_flag",
        "vix_shock_event_flag",
        "credit_shock_event_flag",
        "commodity_shock_event_flag",
        "macro_event_source_count",
        "macro_event_pit_lag_rule",
    ]
    out = out.merge(_select_existing(macro_event_calendar, macro_event_cols), on="asof_date", how="left")

    macro_surprise_cols = [
        "asof_date",
        "macro_surprise_risk_off_score",
        "macro_surprise_pressure_score",
        "macro_surprise_relief_score",
        "macro_surprise_event_count",
        "macro_surprise_has_consensus_count",
        "macro_surprise_abs_zscore_max",
        "inflation_surprise_risk_off_score",
        "employment_surprise_risk_off_score",
        "policy_surprise_risk_off_score",
        "wage_surprise_risk_off_score",
        "macro_surprise_event_density_63d",
        "macro_surprise_proxy_available_flag",
        "macro_surprise_consensus_available_flag",
        "macro_surprise_pit_lag_rule",
        "macro_surprise_source_policy",
    ]
    out = out.merge(_select_existing(macro_surprise_context, macro_surprise_cols), on="asof_date", how="left")

    global_cols = [
        "asof_date",
        "global_source_asof_date",
        "global_pit_available_date",
        "global_pit_lag_rule",
        "rate_pressure_score",
        "usd_pressure_score",
        "credit_stress_score",
        "risk_aversion_score",
        "inflation_pressure_score",
        "commodity_pressure_score",
        "global_risk_on_score",
        "external_macro_pressure_score",
        "yield_curve_10y_2y",
        "yield_curve_10y_3m",
        "us_10y_rate",
        "us_2y_rate",
        "vix_level",
        "hy_spread",
        "ig_spread",
        "dxy_level",
        "usdkrw_level",
        "wti_level",
        "cpi_yoy",
        "core_cpi_yoy",
        "unrate",
        "payrolls_3m_change",
        "monthly_macro_release_lag_days",
    ]
    out = out.merge(_select_existing(global_context, global_cols), on="asof_date", how="left")

    external_cols = [
        "asof_date",
        "external_source_asof_date",
        "external_pit_available_date",
        "external_pit_lag_rule",
        "external_asset_risk_on_score",
        "us_equity_momentum_score",
        "us_growth_risk_score",
        "us_smallcap_risk_score",
        "us_sector_risk_on_score",
        "us_defensive_sector_score",
        "global_breadth_proxy_score",
        "korea_proxy_momentum_score",
        "credit_proxy_score",
        "safe_haven_pressure_score",
        "commodity_risk_score",
        "dollar_risk_score",
        "vix_market_stress_score",
        "semiconductor_momentum_score",
        "global_ex_us_momentum_score",
        "em_vs_dm_score",
        "asia_risk_on_score",
        "bank_stress_relief_score",
        "rate_sensitive_cyclical_score",
        "transport_cyclical_score",
        "low_vol_defensive_pressure_score",
        "crypto_risk_appetite_score",
        "spy_ret_1m",
        "spy_ret_3m",
        "qqq_ret_1m",
        "qqq_ret_3m",
        "iwm_ret_1m",
        "ewy_ret_1m",
        "ewy_ret_3m",
        "sector_cyclical_vs_defensive_1m",
        "sector_positive_ratio_1m",
        "sector_above_sma60_ratio",
        "hyg_lqd_ret_spread_1m",
        "tlt_ret_1m",
        "gld_ret_1m",
        "uso_ret_1m",
        "uup_ret_1m",
        "vix_ret_1m",
        "soxx_ret_1m",
        "soxx_ret_3m",
        "acwx_ret_1m",
        "efa_ret_1m",
        "eem_ret_1m",
        "fxi_ret_1m",
        "ewj_ret_1m",
        "ewt_ret_1m",
        "inda_ret_1m",
        "kre_ret_1m",
        "xhb_ret_1m",
        "iyt_ret_1m",
        "usmv_ret_1m",
        "dxy_ret_1m",
        "btcusd_ret_1m",
    ]
    out = out.merge(_select_existing(external, external_cols), on="asof_date", how="left")

    calibrated_cols = [
        "asof_date",
        "market_scope",
        "forecast_horizon",
        "predicted_forward_return",
        "calibrated_forecast_score",
        "calibrated_forecast_label",
        "calibration_confidence_score",
        "training_sample_count",
        "calibration_model_version",
        "calibration_schema_version",
    ]
    out = out.merge(
        _select_existing(calibrated, calibrated_cols),
        on=["asof_date", "market_scope", "forecast_horizon"],
        how="left",
    )

    out = _add_regime_change_features(out)
    out = _add_coverage_flags(out)
    out["schema_version"] = SCHEMA_VERSION
    out["feature_version"] = FEATURE_VERSION
    out["generated_at"] = generated_at
    out = out.sort_values(["asof_date", "market_scope", "forecast_horizon"]).reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "market_model_input_daily_current.csv"
    output_csv_full = output_dir / "market_model_input_daily.csv"
    report_json = report_dir / "market_model_input_daily_latest.json"
    report_md = report_dir / "market_model_input_daily_latest.md"
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    out.to_csv(output_csv_full, index=False, encoding="utf-8-sig")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS market_model_input_daily")
        out.to_sql("market_model_input_daily", con, if_exists="replace", index=False)
        con.commit()

    date_range = {
        "start": str(out["asof_date"].min()) if not out.empty else None,
        "end": str(out["asof_date"].max()) if not out.empty else None,
    }
    duplicate_key_count = int(out.duplicated(["asof_date", "market_scope", "forecast_horizon"], keep=False).sum())
    coverage_summary = {
        group_name: {
            "available_rate": round(float(out[f"{group_name}_available_flag"].mean()), 6),
            "avg_coverage_ratio": round(float(out[f"{group_name}_coverage_ratio"].mean()), 6),
            "avg_null_count": round(float(out[f"{group_name}_null_count"].mean()), 6),
            "expected_feature_count": int(out[f"{group_name}_expected_feature_count"].max()),
        }
        for group_name in CORE_FEATURE_GROUPS
    }
    coverage_quality_distribution = (
        out["coverage_quality_label"].value_counts(dropna=False).rename_axis("coverage_quality_label").reset_index(name="rows").to_dict("records")
    )
    regime_momentum_distribution = (
        out["regime_momentum_label"].value_counts(dropna=False).rename_axis("regime_momentum_label").reset_index(name="rows").to_dict("records")
    )
    state_change_summary = (
        out.groupby(["market_scope", "forecast_horizon"], as_index=False)
        .agg(
            state_changes=("state_change_flag", "sum"),
            avg_transition_count_20d=("transition_count_20d", "mean"),
            avg_regime_stability_score=("regime_stability_score", "mean"),
        )
        .round(6)
        .to_dict("records")
    )
    report = {
        "source_name": "QuantMarket market model input mart",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "primary_key": ["asof_date", "market_scope", "forecast_horizon"],
        "join_policy": "Use this wide mart when Quant model wants one canonical market feature table. Theme context remains a separate asof_date + quant_theme_bucket join.",
        "source_tables": [
            "market_context_daily",
            "risk_context_daily",
            "flow_context_daily",
            "domestic_flow_derivatives_daily",
            "macro_event_calendar_daily",
            "macro_surprise_context_daily",
            "global_context_daily",
            "external_market_context_daily",
            "market_forecast_daily",
            "market_forecast_ai_calibrated_daily",
        ],
        "row_count": int(len(out)),
        "column_count": int(len(out.columns)),
        "date_range": date_range,
        "duplicate_key_count": duplicate_key_count,
        "coverage_summary": coverage_summary,
        "coverage_quality_distribution": coverage_quality_distribution,
        "regime_momentum_distribution": regime_momentum_distribution,
        "state_change_summary": state_change_summary,
        "missing_rates": _missing_rates(out),
        "output_paths": {
            "db": str(market_context_db),
            "table": "market_model_input_daily",
            "csv": str(output_csv),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
        "recommended_features": [
            "predicted_forward_return",
            "calibrated_forecast_score",
            "calibration_confidence_score",
            "overall_feature_coverage_ratio",
            "coverage_quality_label",
            "market_state_score_delta_5d",
            "market_state_score_delta_20d",
            "market_forecast_score_acceleration_5d",
            "transition_count_20d",
            "regime_stability_score",
            "regime_momentum_label",
            "market_forecast_score",
            "external_asset_risk_on_score",
            "korea_proxy_momentum_score",
            "global_risk_on_score",
            "external_macro_pressure_score",
            "risk_regime_label",
            "volatility_regime_label",
            "domestic_flow_derivatives_score",
            "smart_money_score_5d",
            "smart_money_score_20d",
            "futures_direction_score",
            "program_pressure_score",
            "derivatives_pressure_score",
            "macro_event_pressure_score",
            "macro_event_risk_window_flag",
            "macro_surprise_risk_off_score",
            "macro_surprise_pressure_score",
            "macro_surprise_relief_score",
            "macro_shock_event_count",
            "days_to_next_scheduled_macro_event",
        ],
        "notes": [
            "This is a wide consumer mart for Quant model training and is not intended for public website display.",
            "Theme context is intentionally excluded because it joins by quant_theme_bucket, not only market_scope.",
            "Null values are preserved; do not zero-fill without a model-side imputation policy.",
            "Use coverage flags and ratios before imputation so the model can distinguish source unavailability from neutral numeric values.",
            "Regime change features are backward-looking deltas and transition counts; they are safe to use as PIT features.",
            "Domestic flow/derivatives features use Quant read-only daily investor flow where available and QuantMarket intraday futures/program context with availability flags.",
            "Macro event calendar features are PIT-safe event flags; V1 does not include realized macro surprise values.",
            "Macro surprise features are FRED actual-only proxy surprise values; consensus fields are reserved but not yet populated.",
            "US/FRED/Yahoo source dates are PIT-shifted before joining; source dates remain visible in global_source_asof_date/external_source_asof_date.",
        ],
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# QuantMarket Market Model Input Mart",
        "",
        f"- generated_at: {generated_at}",
        f"- schema_version: {SCHEMA_VERSION}",
        f"- feature_version: {FEATURE_VERSION}",
        f"- rows: {len(out)}",
        f"- columns: {len(out.columns)}",
        f"- date_range: {date_range['start']} ~ {date_range['end']}",
        f"- duplicate_key_count: {duplicate_key_count}",
        f"- csv: `{output_csv}`",
        "",
        "## Recommended Features",
        "",
    ]
    lines.extend(f"- `{feature}`" for feature in report["recommended_features"])
    lines.extend(["", "## Coverage Summary", ""])
    lines.append("| source group | available rate | avg coverage | avg nulls | expected features |")
    lines.append("|---|---:|---:|---:|---:|")
    for group_name, meta in coverage_summary.items():
        lines.append(
            f"| {group_name} | {meta['available_rate']} | {meta['avg_coverage_ratio']} | "
            f"{meta['avg_null_count']} | {meta['expected_feature_count']} |"
        )
    lines.extend(["", "## Coverage Quality Distribution", ""])
    for row in coverage_quality_distribution:
        lines.append(f"- {row['coverage_quality_label']}: {row['rows']}")
    lines.extend(["", "## Regime Momentum Distribution", ""])
    for row in regime_momentum_distribution:
        lines.append(f"- {row['regime_momentum_label']}: {row['rows']}")
    lines.extend(["", "## State Change Summary", ""])
    lines.append("| scope | horizon | state changes | avg transition 20d | avg stability |")
    lines.append("|---|---|---:|---:|---:|")
    for row in state_change_summary:
        lines.append(
            f"| {row['market_scope']} | {row['forecast_horizon']} | {int(row['state_changes'])} | "
            f"{row['avg_transition_count_20d']} | {row['avg_regime_stability_score']} |"
        )
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {}
    manifest.setdefault("canonical_files", {})["market_model_input_daily"] = output_csv.name
    manifest.setdefault("tables", {})["market_model_input_daily"] = {
        "file": output_csv.name,
        "row_count": int(len(out)),
        "start_date": date_range["start"],
        "end_date": date_range["end"],
        "duplicate_key_count": duplicate_key_count,
        "missing_date_count": None,
        "coverage_quality_distribution": coverage_quality_distribution,
        "regime_momentum_distribution": regime_momentum_distribution,
    }
    manifest.setdefault("warnings", []).append(
        "market_model_input_daily is a wide Quant model consumer mart; theme context still requires separate theme_bucket join."
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _update_schema(output_dir, out)

    return ModelInputMartResult(
        output_csv=output_csv,
        report_json=report_json,
        report_md=report_md,
        generated_at=generated_at,
        row_count=int(len(out)),
    )
