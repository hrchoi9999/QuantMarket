from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

KST = timezone(timedelta(hours=9))

MARKET_SCOPES = ["ALL", "KOSPI", "KOSDAQ"]
MART_SCHEMA_VERSION = "ai_market_context_mart.v1.4"
FEATURE_VERSION = "qm_ai_market_context_features.v1.5"
SOURCE_VERSION = "quantmarket_market_analysis_db.v1+quant_price_db_readonly.v1+fred_global_context.v1+yahoo_external_market_context.v1"

CANONICAL_CURRENT_FILES = {
    "market_context_daily": "market_context_daily_current.csv",
    "theme_context_daily": "theme_context_daily_current.csv",
    "theme_context_daily_quant_bucket": "theme_context_daily_quant_bucket_current.csv",
    "risk_context_daily": "risk_context_daily_current.csv",
    "flow_context_daily": "flow_context_daily_current.csv",
    "global_context_daily": "global_context_daily_current.csv",
    "external_market_context_daily": "external_market_context_daily_current.csv",
    "market_forecast_daily": "market_forecast_daily_current.csv",
    "manifest": "manifest.json",
    "schema": "schema.json",
    "theme_crosswalk": "theme_bucket_crosswalk_current.csv",
}

FORECAST_MODEL_VERSION = "qm_market_forecast_baseline_v0.3_pit_lag_20260513"
FORECAST_HORIZONS = ["1d", "5d", "20d"]

MARKET_PROXY_TICKERS = {
    "KOSPI": "226490",  # KODEX 코스피
    "KOSDAQ": "229200",  # KODEX 코스닥150
}

RISK_PROXY_TICKERS = {
    "USDKRW": "138230",  # KIWOOM 미국달러선물
    "GOLD": "132030",  # KODEX 골드선물(H)
    "BOND": "114260",  # KODEX 국고채3년
    "INVERSE": "114800",  # KODEX 인버스
}

THEME_PROXY_TICKERS = [
    ("sector_it", "IT/반도체·기술", "139260"),
    ("sector_financials", "금융", "139270"),
    ("sector_consumer_discretionary", "경기소비재", "139290"),
    ("sector_industrials", "산업재", "227550"),
    ("sector_consumer_staples", "생활소비재", "227560"),
    ("sector_healthcare", "헬스케어", "227540"),
    ("sector_energy_chemicals", "에너지·화학", "139250"),
    ("sector_steel_materials", "철강·소재", "139240"),
    ("sector_construction", "건설", "139220"),
    ("sector_heavy_industries", "중공업", "139230"),
    ("sector_communication", "커뮤니케이션서비스", "315270"),
]

THEME_PROXY_NAMES = {
    "139260": "TIGER 200 IT",
    "139270": "TIGER 200 금융",
    "139290": "TIGER 200 경기소비재",
    "227550": "TIGER 200 산업재",
    "227560": "TIGER 200 생활소비재",
    "227540": "TIGER 200 헬스케어",
    "139250": "TIGER 200 에너지화학",
    "139240": "TIGER 200 철강소재",
    "139220": "TIGER 200 건설",
    "139230": "TIGER 200 중공업",
    "315270": "TIGER 200 커뮤니케이션서비스",
}

QUANT_THEME_MAPPINGS = [
    ("semiconductor_tech", "sector_it", "IT/반도체·기술", "139260", 0.92, "반도체/기술주는 KOSPI200 IT 섹터 proxy와 방향성이 가장 가깝습니다."),
    ("biotech_healthcare", "sector_healthcare", "헬스케어", "227540", 0.9, "바이오/헬스케어주는 KOSPI200 헬스케어 섹터 proxy로 직접 대응합니다."),
    ("bank_insurance", "sector_financials", "금융", "139270", 0.93, "은행/보험은 금융 섹터 proxy로 직접 대응합니다."),
    ("software_platform", "sector_it", "IT/반도체·기술", "139260", 0.68, "소프트웨어/플랫폼 전용 ETF가 없어 IT 섹터 proxy를 사용합니다."),
    ("battery_chemical", "sector_energy_chemicals", "에너지·화학", "139250", 0.74, "2차전지 소재/화학 노출을 에너지화학 섹터 proxy로 근사합니다."),
    ("steel_machinery", "sector_steel_materials", "철강·소재", "139240", 0.72, "철강은 직접 대응하고 기계는 소재/산업재 중 철강소재 쪽 민감도가 더 높다고 보아 매핑합니다."),
    ("energy_utility_infra", "sector_energy_chemicals", "에너지·화학", "139250", 0.66, "에너지/유틸/인프라 전용 proxy가 없어 에너지화학 섹터로 근사합니다."),
    ("auto_mobility", "sector_consumer_discretionary", "경기소비재", "139290", 0.64, "자동차/모빌리티는 경기민감 소비재 성격을 proxy로 사용합니다."),
    ("electronics_it", "sector_it", "IT/반도체·기술", "139260", 0.9, "전자/IT는 KOSPI200 IT 섹터 proxy로 직접 대응합니다."),
    ("construction_materials", "sector_construction", "건설", "139220", 0.78, "건설/건자재는 건설 섹터 proxy로 대응합니다."),
    ("consumer_retail", "sector_consumer_discretionary", "경기소비재", "139290", 0.82, "유통/소비재는 경기소비재 섹터 proxy와 대응합니다."),
    ("consumer_food", "sector_consumer_staples", "생활소비재", "227560", 0.86, "음식료/필수소비재는 생활소비재 섹터 proxy로 대응합니다."),
    ("shipbuilding_defense", "sector_heavy_industries", "중공업", "139230", 0.76, "조선/방산은 중공업 proxy가 가장 유사합니다."),
    ("media_game_entertainment", "sector_communication", "커뮤니케이션서비스", "315270", 0.75, "미디어/게임/엔터는 커뮤니케이션서비스 섹터 proxy와 대응합니다."),
    ("holding_company", "sector_financials", "금융", "139270", 0.45, "지주사는 전용 proxy가 없어 금융/지주 성격을 임시 근사합니다."),
    ("logistics_transport", "sector_industrials", "산업재", "227550", 0.62, "물류/운송은 산업재 경기민감 proxy로 근사합니다."),
    ("telecom", "sector_communication", "커뮤니케이션서비스", "315270", 0.86, "통신주는 커뮤니케이션서비스 섹터 proxy로 대응합니다."),
]


@dataclass(frozen=True)
class MartBuildResult:
    target_db: Path
    output_dir: Path
    report_json: Path
    report_md: Path
    generated_at: str
    row_counts: dict[str, int]
    date_range: dict[str, dict[str, str | None]]


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


def _clip(value: float | None, low: float = -3.0, high: float = 3.0) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(max(low, min(high, value)))


def _safe_ret(close: pd.Series, periods: int) -> pd.Series:
    return close.pct_change(periods=periods)


def _rolling_mdd(close: pd.Series, window: int = 60) -> pd.Series:
    peak = close.rolling(window, min_periods=max(20, window // 3)).max()
    drawdown = close / peak - 1.0
    return drawdown.rolling(window, min_periods=max(20, window // 3)).min()


def _score_from_return(ret_1m: float | None, ret_3m: float | None) -> float | None:
    if ret_1m is None or ret_3m is None or pd.isna(ret_1m) or pd.isna(ret_3m):
        return None
    return round(_clip(float(ret_1m) * 18.0 + float(ret_3m) * 8.0), 4)


def _breadth_score(above20: float | None, above60: float | None, above120: float | None, ret_pos: float | None) -> float | None:
    values = [v for v in [above20, above60, above120, ret_pos] if v is not None and not pd.isna(v)]
    if not values:
        return None
    centered = (sum(values) / len(values) - 0.5) * 6.0
    return round(_clip(centered), 4)


def _stress_score(vol_20d: float | None, mdd_3m: float | None) -> float | None:
    if vol_20d is None or mdd_3m is None or pd.isna(vol_20d) or pd.isna(mdd_3m):
        return None
    vol_pressure = max(0.0, (float(vol_20d) - 0.12) / 0.18)
    dd_pressure = max(0.0, abs(min(float(mdd_3m), 0.0)) / 0.15)
    return round(_clip((vol_pressure + dd_pressure) * 1.5, 0.0, 3.0), 4)


def _market_state_label(score: float | None) -> str | None:
    if score is None or pd.isna(score):
        return None
    if score >= 1.5:
        return "strong_up"
    if score >= 0.4:
        return "up"
    if score <= -1.5:
        return "strong_down"
    if score <= -0.4:
        return "down"
    return "neutral"


def _volatility_label(vol_20d: float | None) -> str | None:
    if vol_20d is None or pd.isna(vol_20d):
        return None
    if vol_20d < 0.12:
        return "low"
    if vol_20d < 0.22:
        return "normal"
    if vol_20d < 0.35:
        return "high"
    return "stress"


def _read_price_panel(price_db: Path, tickers: Iterable[str], start: str, end: str) -> pd.DataFrame:
    tickers = sorted(set(tickers))
    if not tickers:
        return pd.DataFrame()
    start_buffer = (pd.Timestamp(start) - pd.Timedelta(days=520)).strftime("%Y-%m-%d")
    placeholders = ",".join(["?"] * len(tickers))
    with _ro_connect(price_db) as con:
        df = pd.read_sql_query(
            f"""
            SELECT ticker, date, open, high, low, close, volume, value
            FROM prices_daily
            WHERE ticker IN ({placeholders})
              AND date BETWEEN ? AND ?
              AND close IS NOT NULL
            ORDER BY ticker, date
            """,
            con,
            params=[*tickers, start_buffer, end],
            parse_dates=["date"],
        )
    if df.empty:
        return df
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    for col in ["open", "high", "low", "close", "volume", "value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["ticker", "date", "close"])


def _single_proxy_features(df: pd.DataFrame, scope: str) -> pd.DataFrame:
    g = df.sort_values("date").copy()
    close = g["close"]
    daily_ret = close.pct_change()
    g["asof_date"] = g["date"].dt.strftime("%Y-%m-%d")
    g["market_scope"] = scope
    g["ret_1m"] = _safe_ret(close, 20)
    g["ret_3m"] = _safe_ret(close, 60)
    g["vol_20d"] = daily_ret.rolling(20, min_periods=10).std() * math.sqrt(252.0)
    g["mdd_3m"] = _rolling_mdd(close, 60)
    g["above_sma20"] = (close > close.rolling(20, min_periods=10).mean()).astype(float)
    g["above_sma60"] = (close > close.rolling(60, min_periods=20).mean()).astype(float)
    g["above_sma120"] = (close > close.rolling(120, min_periods=40).mean()).astype(float)
    g["ret_pos_1m"] = (g["ret_1m"] > 0).astype(float)
    roll_high = close.rolling(20, min_periods=10).max()
    roll_low = close.rolling(20, min_periods=10).min()
    g["new_high_ratio_20d"] = (close >= roll_high).astype(float)
    g["new_low_ratio_20d"] = (close <= roll_low).astype(float)
    value_ma = g["value"].rolling(20, min_periods=10).mean()
    g["trading_value_expansion_ratio"] = g["value"] / value_ma
    return g[
        [
            "asof_date",
            "market_scope",
            "close",
            "value",
            "ret_1m",
            "ret_3m",
            "vol_20d",
            "mdd_3m",
            "ret_pos_1m",
            "above_sma20",
            "above_sma60",
            "above_sma120",
            "new_high_ratio_20d",
            "new_low_ratio_20d",
            "trading_value_expansion_ratio",
        ]
    ]


def _composite_all_features(kospi: pd.DataFrame, kosdaq: pd.DataFrame) -> pd.DataFrame:
    k = kospi.set_index("asof_date")
    q = kosdaq.set_index("asof_date")
    idx = k.index.intersection(q.index)
    if idx.empty:
        return pd.DataFrame()
    daily_ret = (
        k.loc[idx, "close"].pct_change().fillna(0.0) * 0.6
        + q.loc[idx, "close"].pct_change().fillna(0.0) * 0.4
    )
    close = (1.0 + daily_ret).cumprod() * 100.0
    value = k.loc[idx, "value"].fillna(0.0) + q.loc[idx, "value"].fillna(0.0)
    g = pd.DataFrame({"asof_date": idx, "close": close.values, "value": value.values})
    g["date"] = pd.to_datetime(g["asof_date"])
    featured = _single_proxy_features(g.assign(ticker="ALL"), "ALL")
    for col in [
        "ret_pos_1m",
        "above_sma20",
        "above_sma60",
        "above_sma120",
        "new_high_ratio_20d",
        "new_low_ratio_20d",
    ]:
        featured[col] = (k.loc[idx, col].values + q.loc[idx, col].values) / 2.0
    return featured


def _build_market_context(price_db: Path, start: str, end: str, generated_at: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    tickers = [*MARKET_PROXY_TICKERS.values(), *RISK_PROXY_TICKERS.values()]
    prices = _read_price_panel(price_db, tickers, start, end)
    if prices.empty:
        raise RuntimeError(f"No price rows loaded from {price_db}")

    kospi = _single_proxy_features(prices[prices["ticker"] == MARKET_PROXY_TICKERS["KOSPI"]], "KOSPI")
    kosdaq = _single_proxy_features(prices[prices["ticker"] == MARKET_PROXY_TICKERS["KOSDAQ"]], "KOSDAQ")
    all_scope = _composite_all_features(kospi, kosdaq)
    market_features = pd.concat([all_scope, kospi, kosdaq], ignore_index=True, sort=False)
    market_features = market_features[market_features["asof_date"].between(start, end)].copy()

    kospi_returns = kospi.set_index("asof_date")[["ret_1m", "ret_3m"]].rename(
        columns={"ret_1m": "kospi_ret_1m", "ret_3m": "kospi_ret_3m"}
    )
    kosdaq_returns = kosdaq.set_index("asof_date")[["ret_1m", "ret_3m"]].rename(
        columns={"ret_1m": "kosdaq_ret_1m", "ret_3m": "kosdaq_ret_3m"}
    )
    joined_returns = kospi_returns.join(kosdaq_returns, how="outer")
    market_features = market_features.join(joined_returns, on="asof_date")

    risk = _build_risk_context_from_prices(prices, all_scope, start, end, generated_at)
    defensive = risk.set_index("asof_date")["defensive_asset_strength_score"] if not risk.empty else pd.Series(dtype=float)

    rows = []
    for row in market_features.itertuples(index=False):
        trend_score = _score_from_return(row.ret_1m, row.ret_3m)
        breadth_score = _breadth_score(row.above_sma20, row.above_sma60, row.above_sma120, row.ret_pos_1m)
        stress = _stress_score(row.vol_20d, row.mdd_3m)
        risk_score = round(-stress, 4) if stress is not None else None
        defensive_flow_score = defensive.get(row.asof_date)
        if pd.isna(defensive_flow_score):
            defensive_flow_score = None
        components = [trend_score, breadth_score, risk_score]
        if defensive_flow_score is not None:
            components.append(float(defensive_flow_score))
        market_state_score = round(sum(v for v in components if v is not None) / len([v for v in components if v is not None]), 4) if any(v is not None for v in components) else None
        risk_on_score = None
        risk_off_score = None
        if trend_score is not None and breadth_score is not None and stress is not None:
            risk_on_score = round(_clip((trend_score + breadth_score) / 2.0 - stress, 0.0, 3.0), 4)
            risk_off_score = round(_clip(stress - (trend_score + breadth_score) / 4.0, 0.0, 3.0), 4)
        rows.append(
            {
                "asof_date": row.asof_date,
                "market_scope": row.market_scope,
                "market_state_label": _market_state_label(market_state_score),
                "market_state_score": market_state_score,
                "trend_score": trend_score,
                "breadth_score": breadth_score,
                "risk_score": risk_score,
                "defensive_flow_score": round(float(defensive_flow_score), 4) if defensive_flow_score is not None else None,
                "kospi_ret_1m": row.kospi_ret_1m,
                "kospi_ret_3m": row.kospi_ret_3m,
                "kosdaq_ret_1m": row.kosdaq_ret_1m,
                "kosdaq_ret_3m": row.kosdaq_ret_3m,
                "market_vol_20d": row.vol_20d,
                "market_mdd_3m": row.mdd_3m,
                "market_breadth_ret_pos_1m": row.ret_pos_1m,
                "market_breadth_above_sma20": row.above_sma20,
                "market_breadth_above_sma60": row.above_sma60,
                "market_breadth_above_sma120": row.above_sma120,
                "new_high_ratio_20d": row.new_high_ratio_20d,
                "new_low_ratio_20d": row.new_low_ratio_20d,
                "trading_value_expansion_ratio": row.trading_value_expansion_ratio,
                "risk_on_score": risk_on_score,
                "risk_off_score": risk_off_score,
                "source_quality": "etf_proxy_point_in_time",
                "schema_version": MART_SCHEMA_VERSION,
                "feature_version": FEATURE_VERSION,
                "generated_at": generated_at,
            }
        )
    return pd.DataFrame(rows), risk


def _build_risk_context_from_prices(
    prices: pd.DataFrame,
    all_scope: pd.DataFrame,
    start: str,
    end: str,
    generated_at: str,
) -> pd.DataFrame:
    frames: dict[str, pd.DataFrame] = {}
    for key, ticker in RISK_PROXY_TICKERS.items():
        g = prices[prices["ticker"] == ticker].sort_values("date").copy()
        if g.empty:
            continue
        g["asof_date"] = g["date"].dt.strftime("%Y-%m-%d")
        g[f"{key.lower()}_ret_1m"] = g["close"].pct_change(20)
        frames[key] = g[["asof_date", f"{key.lower()}_ret_1m"]]

    base_dates = all_scope[["asof_date", "vol_20d", "mdd_3m"]].copy()
    base_dates = base_dates[base_dates["asof_date"].between(start, end)]
    out = base_dates
    for frame in frames.values():
        out = out.merge(frame, on="asof_date", how="left")
    rename = {
        "usdkrw_ret_1m": "usdkrw_ret_1m",
        "gold_ret_1m": "gold_proxy_ret_1m",
        "bond_ret_1m": "bond_proxy_ret_1m",
        "inverse_ret_1m": "inverse_etf_ret_1m",
    }
    out = out.rename(columns=rename)
    for col in ["gold_proxy_ret_1m", "bond_proxy_ret_1m", "inverse_etf_ret_1m"]:
        if col not in out.columns:
            out[col] = None

    defensive_scores = []
    for row in out.itertuples(index=False):
        vals = [
            getattr(row, "gold_proxy_ret_1m", None),
            getattr(row, "bond_proxy_ret_1m", None),
            getattr(row, "inverse_etf_ret_1m", None),
        ]
        vals = [float(v) for v in vals if v is not None and not pd.isna(v)]
        defensive_scores.append(round(_clip(sum(vals) / len(vals) * 30.0), 4) if vals else None)
    out["defensive_asset_strength_score"] = defensive_scores
    out["market_stress_score"] = [_stress_score(v, d) for v, d in zip(out["vol_20d"], out["mdd_3m"], strict=False)]
    out["drawdown_pressure_score"] = [
        round(_clip(abs(min(float(v), 0.0)) / 0.15 * 3.0, 0.0, 3.0), 4) if v is not None and not pd.isna(v) else None
        for v in out["mdd_3m"]
    ]
    out["crash_warning_flag"] = [
        int((stress is not None and not pd.isna(stress) and stress >= 2.2) or (mdd is not None and not pd.isna(mdd) and mdd <= -0.15))
        for stress, mdd in zip(out["market_stress_score"], out["mdd_3m"], strict=False)
    ]
    out["volatility_regime_label"] = [_volatility_label(v) for v in out["vol_20d"]]
    out["schema_version"] = MART_SCHEMA_VERSION
    out["feature_version"] = FEATURE_VERSION
    out["generated_at"] = generated_at
    keep = [
        "asof_date",
        "usdkrw_ret_1m",
        "gold_proxy_ret_1m",
        "bond_proxy_ret_1m",
        "inverse_etf_ret_1m",
        "defensive_asset_strength_score",
        "market_stress_score",
        "drawdown_pressure_score",
        "crash_warning_flag",
        "volatility_regime_label",
        "schema_version",
        "feature_version",
        "generated_at",
    ]
    for col in keep:
        if col not in out.columns:
            out[col] = None
    return out[keep]


def _persistence_days(flag: pd.Series) -> pd.Series:
    count = 0
    values: list[int | None] = []
    for item in flag:
        if pd.isna(item):
            values.append(None)
            count = 0
        elif bool(item):
            count += 1
            values.append(count)
        else:
            count = 0
            values.append(0)
    return pd.Series(values, index=flag.index)


def _build_theme_context(price_db: Path, start: str, end: str, generated_at: str) -> pd.DataFrame:
    tickers = [ticker for _, _, ticker in THEME_PROXY_TICKERS]
    prices = _read_price_panel(price_db, tickers, start, end)
    if prices.empty:
        return pd.DataFrame(columns=_theme_columns())
    frames = []
    for bucket, name_kr, ticker in THEME_PROXY_TICKERS:
        g = prices[prices["ticker"] == ticker].sort_values("date").copy()
        if g.empty:
            continue
        close = g["close"]
        g["asof_date"] = g["date"].dt.strftime("%Y-%m-%d")
        g["theme_bucket"] = bucket
        g["theme_name_kr"] = name_kr
        g["theme_ret_1w"] = close.pct_change(5)
        g["theme_ret_1m"] = close.pct_change(20)
        g["theme_ret_3m"] = close.pct_change(60)
        g["above_sma60"] = close > close.rolling(60, min_periods=20).mean()
        value_ma = g["value"].rolling(20, min_periods=10).mean()
        g["theme_trading_value_expansion_ratio"] = g["value"] / value_ma
        g["theme_persistence_days"] = _persistence_days(g["theme_ret_1m"] > 0)
        g["theme_breadth_positive_ratio"] = (g["theme_ret_1m"] > 0).astype(float)
        g["theme_above_sma60_ratio"] = g["above_sma60"].astype(float)
        frames.append(g)
    if not frames:
        return pd.DataFrame(columns=_theme_columns())
    out = pd.concat(frames, ignore_index=True, sort=False)
    out = out[out["asof_date"].between(start, end)].copy()
    out["raw_momentum"] = out["theme_ret_1m"].fillna(0.0) * 0.65 + out["theme_ret_3m"].fillna(0.0) * 0.35
    out["theme_momentum_score"] = out.groupby("asof_date")["raw_momentum"].transform(
        lambda s: ((s - s.mean()) / s.std(ddof=0)).clip(-3, 3) if len(s.dropna()) > 1 and s.std(ddof=0) else 0.0
    )
    out = out.sort_values(["theme_bucket", "asof_date"])
    out["theme_rotation_score"] = out.groupby("theme_bucket")["theme_momentum_score"].diff(20)
    total_value = out.groupby("asof_date")["value"].transform("sum")
    out["theme_concentration_score"] = out["value"] / total_value
    out["leading_theme_rank"] = out.groupby("asof_date")["theme_momentum_score"].rank(method="first", ascending=False)
    out["schema_version"] = MART_SCHEMA_VERSION
    out["feature_version"] = FEATURE_VERSION
    out["generated_at"] = generated_at
    return out[_theme_columns()]


def _theme_columns() -> list[str]:
    return [
        "asof_date",
        "theme_bucket",
        "theme_name_kr",
        "theme_ret_1w",
        "theme_ret_1m",
        "theme_ret_3m",
        "theme_momentum_score",
        "theme_rotation_score",
        "theme_persistence_days",
        "theme_breadth_positive_ratio",
        "theme_above_sma60_ratio",
        "theme_trading_value_expansion_ratio",
        "theme_concentration_score",
        "leading_theme_rank",
        "schema_version",
        "feature_version",
        "generated_at",
    ]


def _build_flow_context(qm_db: Path, start: str, end: str, generated_at: str, date_spine: list[str]) -> pd.DataFrame:
    base_rows = [
        {
            "asof_date": asof_date,
            "market_scope": scope,
            "foreign_net_buy_ratio": None,
            "institution_net_buy_ratio": None,
            "retail_net_buy_ratio": None,
            "foreign_buying_breadth": None,
            "institution_buying_breadth": None,
            "flow_concentration_score": None,
            "smart_money_score": None,
            "flow_context_available": 0,
            "flow_source_start_date": None,
            "flow_coverage_flag": 0,
            "source_quality": "not_available",
            "schema_version": MART_SCHEMA_VERSION,
            "feature_version": FEATURE_VERSION,
            "generated_at": generated_at,
        }
        for asof_date in date_spine
        for scope in MARKET_SCOPES
        if start <= asof_date <= end
    ]
    base = pd.DataFrame(base_rows, columns=_flow_columns())
    if not qm_db.exists():
        return base
    try:
        with _ro_connect(qm_db) as con:
            df = pd.read_sql_query(
                """
                SELECT session_date, asof, signal_code, metric_value
                FROM market_intraday_flow_signal
                WHERE session_date BETWEEN ? AND ?
                  AND signal_code IN ('FOREIGNER_NET', 'INSTITUTION_NET', 'INDIVIDUAL_NET')
                ORDER BY session_date, asof
                """,
                con,
                params=[start, end],
            )
    except sqlite3.Error:
        return base
    if df.empty:
        return base
    source_start = str(df["session_date"].min())
    base["flow_source_start_date"] = source_start
    latest = df.sort_values(["session_date", "asof"]).groupby(["session_date", "signal_code"], as_index=False).tail(1)
    pivot = latest.pivot(index="session_date", columns="signal_code", values="metric_value").reset_index()
    rows = []
    for row in pivot.itertuples(index=False):
        foreign = getattr(row, "FOREIGNER_NET", None)
        inst = getattr(row, "INSTITUTION_NET", None)
        retail = getattr(row, "INDIVIDUAL_NET", None)
        vals = [v for v in [foreign, inst, retail] if v is not None and not pd.isna(v)]
        denom = sum(abs(float(v)) for v in vals) if vals else None
        foreign_ratio = float(foreign) / denom if denom and foreign is not None and not pd.isna(foreign) else None
        inst_ratio = float(inst) / denom if denom and inst is not None and not pd.isna(inst) else None
        retail_ratio = float(retail) / denom if denom and retail is not None and not pd.isna(retail) else None
        smart_money = None
        if denom and foreign is not None and not pd.isna(foreign) and inst is not None and not pd.isna(inst):
            smart_base = float(foreign) + float(inst)
            smart_money = smart_base / denom
            if retail is not None and not pd.isna(retail):
                smart_money = (smart_base - float(retail)) / denom
        rows.append(
            {
                "asof_date": row.session_date,
                "market_scope": "ALL",
                "foreign_net_buy_ratio": foreign_ratio,
                "institution_net_buy_ratio": inst_ratio,
                "retail_net_buy_ratio": retail_ratio,
                "foreign_buying_breadth": None,
                "institution_buying_breadth": None,
                "flow_concentration_score": max(abs(float(v)) / denom for v in vals) if denom else None,
                "smart_money_score": smart_money,
                "flow_context_available": 1 if denom else 0,
                "flow_source_start_date": source_start,
                "flow_coverage_flag": 1 if denom else 0,
                "source_quality": "intraday_aggregate_recent_only",
                "schema_version": MART_SCHEMA_VERSION,
                "feature_version": FEATURE_VERSION,
                "generated_at": generated_at,
            }
        )
    actual = pd.DataFrame(rows, columns=_flow_columns())
    if actual.empty:
        return base
    actual_idx = actual.set_index(["asof_date", "market_scope"])
    base_idx = base.set_index(["asof_date", "market_scope"])
    base_idx.update(actual_idx)
    out = base_idx.reset_index()[_flow_columns()]
    for col in [
        "foreign_net_buy_ratio",
        "institution_net_buy_ratio",
        "retail_net_buy_ratio",
        "foreign_buying_breadth",
        "institution_buying_breadth",
        "flow_concentration_score",
        "smart_money_score",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ["flow_context_available", "flow_coverage_flag"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
    return out


def _flow_columns() -> list[str]:
    return [
        "asof_date",
        "market_scope",
        "foreign_net_buy_ratio",
        "institution_net_buy_ratio",
        "retail_net_buy_ratio",
        "foreign_buying_breadth",
        "institution_buying_breadth",
        "flow_concentration_score",
        "smart_money_score",
        "flow_context_available",
        "flow_source_start_date",
        "flow_coverage_flag",
        "source_quality",
        "schema_version",
        "feature_version",
        "generated_at",
    ]


def _first_number(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isnan(number):
            return number
    return None


def _forecast_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 1.1:
        return "bullish"
    if score >= 0.35:
        return "mild_bullish"
    if score > -0.35:
        return "neutral"
    if score > -1.1:
        return "mild_bearish"
    return "bearish"


def _risk_regime_label(*, risk_off: float | None, external_pressure: float | None, risk_on: float | None) -> str | None:
    components = [value for value in [risk_off, external_pressure] if value is not None]
    if not components:
        return None
    pressure = sum(components) / len(components)
    if pressure >= 1.6:
        return "risk_off_high"
    if pressure >= 0.65:
        return "risk_off_moderate"
    if risk_on is not None and risk_on >= 1.2 and pressure <= 0.2:
        return "risk_on_moderate"
    if risk_on is not None and risk_on >= 2.0 and pressure <= -0.2:
        return "risk_on_high"
    return "neutral"


def _forecast_horizon_weights(horizon: str) -> dict[str, float]:
    if horizon == "1d":
        return {
            "state": 0.24,
            "trend": 0.12,
            "breadth": 0.10,
            "risk_on": 0.16,
            "risk_off": -0.18,
            "global_risk_on": 0.16,
            "external_asset_risk_on": 0.18,
            "external_pressure": -0.14,
            "smart_money": 0.10,
        }
    if horizon == "20d":
        return {
            "state": 0.30,
            "trend": 0.24,
            "breadth": 0.20,
            "risk_on": 0.12,
            "risk_off": -0.12,
            "global_risk_on": 0.10,
            "external_asset_risk_on": 0.12,
            "external_pressure": -0.10,
            "smart_money": 0.04,
        }
    return {
        "state": 0.28,
        "trend": 0.18,
        "breadth": 0.16,
        "risk_on": 0.15,
        "risk_off": -0.15,
        "global_risk_on": 0.14,
        "external_asset_risk_on": 0.16,
        "external_pressure": -0.12,
        "smart_money": 0.07,
    }


def _build_market_forecast_context(
    *,
    market_context: pd.DataFrame,
    risk_context: pd.DataFrame,
    flow_context: pd.DataFrame,
    global_context: pd.DataFrame,
    external_market_context: pd.DataFrame,
    generated_at: str,
) -> pd.DataFrame:
    columns = [
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
        "baseline_market_state_score",
        "baseline_trend_score",
        "baseline_breadth_score",
        "baseline_risk_on_score",
        "baseline_risk_off_score",
        "baseline_global_risk_on_score",
        "baseline_external_asset_risk_on_score",
        "baseline_external_macro_pressure_score",
        "baseline_smart_money_score",
        "forecast_model_version",
        "schema_version",
        "feature_version",
        "generated_at",
    ]
    if market_context.empty:
        return pd.DataFrame(columns=columns)

    base = market_context.copy()
    if not risk_context.empty:
        risk_cols = [
            "asof_date",
            "market_stress_score",
            "drawdown_pressure_score",
            "volatility_regime_label",
        ]
        base = base.merge(risk_context[risk_cols], on="asof_date", how="left")
    else:
        base["market_stress_score"] = None
        base["drawdown_pressure_score"] = None
        base["volatility_regime_label"] = None

    if not global_context.empty:
        global_cols = [
            "asof_date",
            "global_risk_on_score",
            "external_macro_pressure_score",
            "risk_aversion_score",
        ]
        base = base.merge(global_context[global_cols], on="asof_date", how="left")
    else:
        base["global_risk_on_score"] = None
        base["external_macro_pressure_score"] = None
        base["risk_aversion_score"] = None

    if not external_market_context.empty:
        external_cols = ["asof_date", "external_asset_risk_on_score", "korea_proxy_momentum_score"]
        base = base.merge(external_market_context[external_cols], on="asof_date", how="left")
    else:
        base["external_asset_risk_on_score"] = None
        base["korea_proxy_momentum_score"] = None

    if not flow_context.empty:
        flow_cols = ["asof_date", "market_scope", "smart_money_score"]
        base = base.merge(flow_context[flow_cols], on=["asof_date", "market_scope"], how="left")
    else:
        base["smart_money_score"] = None

    rows: list[dict] = []
    for row in base.itertuples(index=False):
        market_state = _first_number(getattr(row, "market_state_score", None))
        trend = _first_number(getattr(row, "trend_score", None))
        breadth = _first_number(getattr(row, "breadth_score", None))
        risk_on = _first_number(getattr(row, "risk_on_score", None))
        risk_off = _first_number(getattr(row, "risk_off_score", None))
        global_risk_on = _first_number(getattr(row, "global_risk_on_score", None))
        external_asset_risk_on = _first_number(getattr(row, "external_asset_risk_on_score", None))
        external_pressure = _first_number(getattr(row, "external_macro_pressure_score", None))
        smart_money = _first_number(getattr(row, "smart_money_score", None))
        market_stress = _first_number(getattr(row, "market_stress_score", None))
        risk_aversion = _first_number(getattr(row, "risk_aversion_score", None))
        drawdown_pressure = _first_number(getattr(row, "drawdown_pressure_score", None))

        volatility_components = [value for value in [market_stress, risk_aversion] if value is not None]
        expected_volatility = (
            round(_clip(sum(volatility_components) / len(volatility_components), 0.0, 3.0), 4)
            if volatility_components
            else None
        )
        upside_participation = None
        if trend is not None or breadth is not None:
            parts = [value for value in [trend, breadth] if value is not None]
            upside_participation = round(_clip(sum(parts) / len(parts), -3.0, 3.0), 4)

        for horizon in FORECAST_HORIZONS:
            weights = _forecast_horizon_weights(horizon)
            terms = {
                "state": market_state,
                "trend": trend,
                "breadth": breadth,
                "risk_on": risk_on,
                "risk_off": risk_off,
                "global_risk_on": global_risk_on,
                "external_asset_risk_on": external_asset_risk_on,
                "external_pressure": external_pressure,
                "smart_money": smart_money,
            }
            weighted_values = [
                (value, weights[key])
                for key, value in terms.items()
                if value is not None and weights.get(key) is not None
            ]
            if weighted_values:
                weight_sum = sum(abs(weight) for _, weight in weighted_values)
                raw_score = sum(value * weight for value, weight in weighted_values) / weight_sum if weight_sum else None
                forecast_score = round(_clip(raw_score), 4) if raw_score is not None else None
            else:
                forecast_score = None
            availability = len(weighted_values) / len(terms)
            conviction = min(abs(forecast_score or 0.0) / 2.0, 1.0)
            volatility_penalty = min((expected_volatility or 0.0) / 3.0, 1.0) if expected_volatility is not None else 0.35
            confidence = round(max(0.0, min(1.0, availability * 0.62 + conviction * 0.25 + (1.0 - volatility_penalty) * 0.13)), 4)
            rows.append(
                {
                    "asof_date": row.asof_date,
                    "market_scope": row.market_scope,
                    "forecast_horizon": horizon,
                    "market_forecast_score": forecast_score,
                    "market_forecast_label": _forecast_label(forecast_score),
                    "risk_regime_label": _risk_regime_label(risk_off=risk_off, external_pressure=external_pressure, risk_on=risk_on),
                    "expected_volatility_score": expected_volatility,
                    "drawdown_risk_score": round(_clip(drawdown_pressure, 0.0, 3.0), 4) if drawdown_pressure is not None else None,
                    "upside_participation_score": upside_participation,
                    "confidence_score": confidence,
                    "baseline_market_state_score": market_state,
                    "baseline_trend_score": trend,
                    "baseline_breadth_score": breadth,
                    "baseline_risk_on_score": risk_on,
                    "baseline_risk_off_score": risk_off,
                    "baseline_global_risk_on_score": global_risk_on,
                    "baseline_external_asset_risk_on_score": external_asset_risk_on,
                    "baseline_external_macro_pressure_score": external_pressure,
                    "baseline_smart_money_score": smart_money,
                    "forecast_model_version": FORECAST_MODEL_VERSION,
                    "schema_version": MART_SCHEMA_VERSION,
                    "feature_version": FEATURE_VERSION,
                    "generated_at": generated_at,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def _write_table(con: sqlite3.Connection, name: str, df: pd.DataFrame) -> None:
    con.execute(f"DROP TABLE IF EXISTS {name}")
    df.to_sql(name, con, if_exists="replace", index=False)


def _date_range(df: pd.DataFrame) -> dict[str, str | None]:
    if df.empty or "asof_date" not in df.columns:
        return {"start": None, "end": None}
    return {"start": str(df["asof_date"].min()), "end": str(df["asof_date"].max())}


def _missing_rates(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {}
    return {col: round(float(df[col].isna().mean()), 6) for col in df.columns}


def _duplicate_key_count(df: pd.DataFrame, keys: list[str]) -> int:
    if df.empty or any(key not in df.columns for key in keys):
        return 0
    return int(df.duplicated(keys, keep=False).sum())


def _missing_date_count(df: pd.DataFrame, expected_dates: list[str]) -> int:
    if df.empty or "asof_date" not in df.columns:
        return len(expected_dates)
    actual = set(df["asof_date"].dropna().astype(str).unique().tolist())
    return int(sum(1 for date in expected_dates if date not in actual))


def _next_kst_business_date(source_date: str) -> str:
    return (pd.Timestamp(source_date) + pd.offsets.BDay(1)).strftime("%Y-%m-%d")


def _start_buffer_for_pit(start: str) -> str:
    return (pd.Timestamp(start) - pd.offsets.BDay(10)).strftime("%Y-%m-%d")


def _market_scope_coverage(df: pd.DataFrame) -> list[dict]:
    if df.empty or "market_scope" not in df.columns:
        return []
    return (
        df.groupby("market_scope", as_index=False)
        .agg(start=("asof_date", "min"), end=("asof_date", "max"), rows=("asof_date", "count"))
        .sort_values("market_scope")
        .to_dict("records")
    )


def _schema_contract() -> dict:
    def col(
        name: str,
        data_type: str,
        *,
        nullable: bool,
        value_range: str,
        direction: str = "identifier_or_metadata",
        labels: list[str] | None = None,
        null_policy: str = "Leave null when source data or rolling lookback is unavailable.",
    ) -> dict:
        out = {
            "column_name": name,
            "data_type": data_type,
            "nullable": nullable,
            "value_range": value_range,
            "score_direction": direction,
            "null_policy": null_policy,
        }
        if labels:
            out["categorical_label_values"] = labels
        return out

    ratio = "ratio, not percent. Example 0.05 means +5%."
    score = "approximately -3 to +3 unless stated otherwise."
    return {
        "source_name": "QuantMarket AI training market context mart",
        "schema_version": MART_SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "source_version": SOURCE_VERSION,
        "timezone": "Asia/Seoul",
        "canonical_files": CANONICAL_CURRENT_FILES,
        "point_in_time_policy": {
            "asof_date": "Each row uses only values available at or before the asof_date close for daily ETF proxy data.",
            "daily_proxy_cutoff": "Daily proxy features are treated as available after the corresponding Korean market close and should be joined to next model training sample only when the model's PIT convention allows same-day close data.",
            "overwrite_policy": "Current mart files are overwritten on rebuild. Historical feature definitions are fixed by schema_version and feature_version.",
            "revision_policy": "If historical data is restated or proxy logic changes, feature_version must be incremented and the mart regenerated.",
        },
        "tables": {
            "market_context_daily": {
                "primary_key": ["asof_date", "market_scope"],
                "join_keys": ["asof_date", "market_scope"],
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2017-01-01 or later"),
                    col("market_scope", "string", nullable=False, value_range="ALL/KOSPI/KOSDAQ", labels=MARKET_SCOPES),
                    col("market_state_label", "string", nullable=True, value_range="fixed categorical", labels=["strong_up", "up", "neutral", "down", "strong_down"], direction="higher implied by market_state_score is more risk-on"),
                    col("market_state_score", "float", nullable=True, value_range=score, direction="higher is more risk-on / constructive"),
                    col("trend_score", "float", nullable=True, value_range=score, direction="higher is stronger price trend"),
                    col("breadth_score", "float", nullable=True, value_range=score, direction="higher is broader participation"),
                    col("risk_score", "float", nullable=True, value_range=score, direction="higher is less risk pressure; negative means risk pressure"),
                    col("defensive_flow_score", "float", nullable=True, value_range=score, direction="higher means defensive assets are stronger / more risk-off"),
                    col("kospi_ret_1m", "float", nullable=True, value_range=ratio, direction="higher is stronger KOSPI proxy return"),
                    col("kospi_ret_3m", "float", nullable=True, value_range=ratio, direction="higher is stronger KOSPI proxy return"),
                    col("kosdaq_ret_1m", "float", nullable=True, value_range=ratio, direction="higher is stronger KOSDAQ proxy return"),
                    col("kosdaq_ret_3m", "float", nullable=True, value_range=ratio, direction="higher is stronger KOSDAQ proxy return"),
                    col("market_vol_20d", "float", nullable=True, value_range="annualized volatility ratio", direction="higher is more volatile / riskier"),
                    col("market_mdd_3m", "float", nullable=True, value_range="negative drawdown ratio, 0 or below", direction="lower is worse drawdown pressure"),
                    col("market_breadth_ret_pos_1m", "float", nullable=True, value_range="0 to 1", direction="higher is broader positive 1m return"),
                    col("market_breadth_above_sma20", "float", nullable=True, value_range="0 to 1", direction="higher is broader short-term uptrend"),
                    col("market_breadth_above_sma60", "float", nullable=True, value_range="0 to 1", direction="higher is broader medium-term uptrend"),
                    col("market_breadth_above_sma120", "float", nullable=True, value_range="0 to 1", direction="higher is broader long-term uptrend"),
                    col("new_high_ratio_20d", "float", nullable=True, value_range="0 to 1", direction="higher is stronger upside breakout"),
                    col("new_low_ratio_20d", "float", nullable=True, value_range="0 to 1", direction="higher is weaker downside pressure"),
                    col("trading_value_expansion_ratio", "float", nullable=True, value_range="positive ratio around 1", direction="higher is larger trading value versus 20d average"),
                    col("risk_on_score", "float", nullable=True, value_range="0 to 3", direction="higher is more risk-on"),
                    col("risk_off_score", "float", nullable=True, value_range="0 to 3", direction="higher is more risk-off"),
                    col("source_quality", "string", nullable=False, value_range="source quality label"),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
            "theme_context_daily": {
                "primary_key": ["asof_date", "theme_bucket"],
                "join_keys": ["asof_date", "theme_bucket"],
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2017-01-01 or later"),
                    col("theme_bucket", "string", nullable=False, value_range="fixed sector proxy bucket"),
                    col("theme_name_kr", "string", nullable=False, value_range="Korean display name"),
                    col("theme_ret_1w", "float", nullable=True, value_range=ratio, direction="higher is stronger 1w theme return"),
                    col("theme_ret_1m", "float", nullable=True, value_range=ratio, direction="higher is stronger 1m theme return"),
                    col("theme_ret_3m", "float", nullable=True, value_range=ratio, direction="higher is stronger 3m theme return"),
                    col("theme_momentum_score", "float", nullable=True, value_range=score, direction="higher is stronger cross-theme momentum"),
                    col("theme_rotation_score", "float", nullable=True, value_range=score, direction="higher means improving relative momentum"),
                    col("theme_persistence_days", "integer", nullable=True, value_range="0 or positive integer", direction="higher means longer positive 1m-return persistence"),
                    col("theme_breadth_positive_ratio", "float", nullable=True, value_range="0 to 1", direction="higher means theme proxy has positive 1m return"),
                    col("theme_above_sma60_ratio", "float", nullable=True, value_range="0 to 1", direction="higher means theme proxy is above 60d SMA"),
                    col("theme_trading_value_expansion_ratio", "float", nullable=True, value_range="positive ratio around 1", direction="higher means higher trading value versus 20d average"),
                    col("theme_concentration_score", "float", nullable=True, value_range="0 to 1", direction="higher means more concentrated theme proxy trading value"),
                    col("leading_theme_rank", "float", nullable=True, value_range="1 is strongest", direction="lower rank is stronger"),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
            "theme_context_daily_quant_bucket": {
                "primary_key": ["asof_date", "quant_theme_bucket"],
                "join_keys": ["asof_date", "quant_theme_bucket"],
                "mapping_policy": "Quant model STOCK theme_bucket is mapped to QuantMarket ETF proxy bucket using theme_bucket_crosswalk_current.csv.",
                "crosswalk_schema_version": "theme_bucket_crosswalk.v1",
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2017-01-01 or later"),
                    col("quant_theme_bucket", "string", nullable=False, value_range="Quant model STOCK theme_bucket"),
                    col("quantmarket_theme_bucket", "string", nullable=False, value_range="QuantMarket sector/theme proxy bucket"),
                    col("theme_name_kr", "string", nullable=False, value_range="Korean display name"),
                    col("theme_ret_1w", "float", nullable=True, value_range=ratio, direction="higher is stronger 1w mapped theme return"),
                    col("theme_ret_1m", "float", nullable=True, value_range=ratio, direction="higher is stronger 1m mapped theme return"),
                    col("theme_ret_3m", "float", nullable=True, value_range=ratio, direction="higher is stronger 3m mapped theme return"),
                    col("theme_momentum_score", "float", nullable=True, value_range=score, direction="higher is stronger mapped theme momentum"),
                    col("theme_rotation_score", "float", nullable=True, value_range=score, direction="higher means improving mapped theme momentum"),
                    col("theme_persistence_days", "integer", nullable=True, value_range="0 or positive integer", direction="higher means longer positive 1m-return persistence"),
                    col("theme_breadth_positive_ratio", "float", nullable=True, value_range="0 to 1", direction="higher means mapped theme proxy has positive 1m return"),
                    col("theme_above_sma60_ratio", "float", nullable=True, value_range="0 to 1", direction="higher means mapped theme proxy is above 60d SMA"),
                    col("theme_trading_value_expansion_ratio", "float", nullable=True, value_range="positive ratio around 1", direction="higher means higher trading value versus 20d average"),
                    col("theme_concentration_score", "float", nullable=True, value_range="0 to 1", direction="higher means more concentrated mapped proxy trading value"),
                    col("leading_theme_rank", "float", nullable=True, value_range="1 is strongest", direction="lower rank is stronger"),
                    col("mapping_confidence", "float", nullable=False, value_range="0 to 1", direction="higher means stronger semantic mapping confidence"),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
            "risk_context_daily": {
                "primary_key": ["asof_date"],
                "join_keys": ["asof_date"],
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2017-01-01 or later"),
                    col("usdkrw_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means USD/KRW proxy stronger, typically risk-off for KR equities"),
                    col("gold_proxy_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means gold proxy stronger, defensive/risk-off"),
                    col("bond_proxy_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means bond proxy stronger, defensive/risk-off"),
                    col("inverse_etf_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means inverse ETF stronger, risk-off"),
                    col("defensive_asset_strength_score", "float", nullable=True, value_range=score, direction="higher means defensive assets stronger"),
                    col("market_stress_score", "float", nullable=True, value_range="0 to 3", direction="higher means more stress"),
                    col("drawdown_pressure_score", "float", nullable=True, value_range="0 to 3", direction="higher means larger drawdown pressure"),
                    col("crash_warning_flag", "integer", nullable=False, value_range="0 or 1", direction="1 means stress/drawdown warning"),
                    col("volatility_regime_label", "string", nullable=True, value_range="fixed categorical", labels=["low", "normal", "high", "stress"], direction="higher label severity means more volatility risk"),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
            "flow_context_daily": {
                "primary_key": ["asof_date", "market_scope"],
                "join_keys": ["asof_date", "market_scope"],
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2017-01-01 or later"),
                    col("market_scope", "string", nullable=False, value_range="ALL/KOSPI/KOSDAQ", labels=MARKET_SCOPES),
                    col("foreign_net_buy_ratio", "float", nullable=True, value_range="-1 to 1", direction="higher means more foreign net buying"),
                    col("institution_net_buy_ratio", "float", nullable=True, value_range="-1 to 1", direction="higher means more institution net buying"),
                    col("retail_net_buy_ratio", "float", nullable=True, value_range="-1 to 1", direction="higher means more retail net buying"),
                    col("foreign_buying_breadth", "float", nullable=True, value_range="0 to 1", direction="higher means broader foreign buying"),
                    col("institution_buying_breadth", "float", nullable=True, value_range="0 to 1", direction="higher means broader institution buying"),
                    col("flow_concentration_score", "float", nullable=True, value_range="0 to 1", direction="higher means flow is concentrated in one investor group"),
                    col("smart_money_score", "float", nullable=True, value_range="-1 to 1", direction="higher means foreign+institution flow is stronger"),
                    col("flow_context_available", "integer", nullable=False, value_range="0 or 1", direction="1 means flow values are available"),
                    col("flow_source_start_date", "date string YYYY-MM-DD", nullable=True, value_range="first QM flow source date"),
                    col("flow_coverage_flag", "integer", nullable=False, value_range="0 or 1", direction="1 means this row has usable flow coverage"),
                    col("source_quality", "string", nullable=False, value_range="not_available/intraday_aggregate_recent_only"),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
            "global_context_daily": {
                "primary_key": ["asof_date"],
                "join_keys": ["asof_date"],
                "source_policy": "FRED based external macro/risk data. asof_date is the KST-safe PIT available date; global_source_asof_date preserves the original FRED/source date.",
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2000-01-01 or later"),
                    col("global_source_asof_date", "date string YYYY-MM-DD", nullable=False, value_range="original FRED/source date"),
                    col("global_pit_available_date", "date string YYYY-MM-DD", nullable=False, value_range="first KST business date allowed for model use"),
                    col("global_pit_lag_rule", "string", nullable=False, value_range="fixed PIT lag policy text"),
                    col("rate_pressure_score", "float", nullable=True, value_range=score, direction="higher means higher US rate burden / risk-off pressure"),
                    col("usd_pressure_score", "float", nullable=True, value_range=score, direction="higher means stronger USD or USD/KRW pressure"),
                    col("credit_stress_score", "float", nullable=True, value_range=score, direction="higher means wider credit spread / risk-off pressure"),
                    col("risk_aversion_score", "float", nullable=True, value_range=score, direction="higher means higher volatility / risk-off pressure"),
                    col("inflation_pressure_score", "float", nullable=True, value_range=score, direction="higher means stronger inflation pressure"),
                    col("commodity_pressure_score", "float", nullable=True, value_range=score, direction="higher means stronger commodity cost or volatility pressure"),
                    col("global_risk_on_score", "float", nullable=True, value_range=score, direction="higher means more favorable global risk appetite"),
                    col("external_macro_pressure_score", "float", nullable=True, value_range=score, direction="higher means less favorable external macro condition"),
                    col("yield_curve_10y_2y", "float", nullable=True, value_range="percentage point spread", direction="higher means steeper US 10Y-2Y curve"),
                    col("yield_curve_10y_3m", "float", nullable=True, value_range="percentage point spread", direction="higher means steeper US 10Y-3M curve"),
                    col("us_10y_rate", "float", nullable=True, value_range="percent level", direction="higher means higher US 10Y yield"),
                    col("us_2y_rate", "float", nullable=True, value_range="percent level", direction="higher means higher US 2Y yield"),
                    col("us_real_10y_rate", "float", nullable=True, value_range="percent level", direction="higher means higher US real yield"),
                    col("breakeven_10y", "float", nullable=True, value_range="percent level", direction="higher means higher market implied inflation"),
                    col("vix_level", "float", nullable=True, value_range="index level", direction="higher means higher equity volatility"),
                    col("hy_spread", "float", nullable=True, value_range="percent spread", direction="higher means higher high-yield credit stress"),
                    col("ig_spread", "float", nullable=True, value_range="percent spread", direction="higher means higher investment-grade credit stress"),
                    col("dxy_level", "float", nullable=True, value_range="index level", direction="higher means stronger broad USD"),
                    col("usdkrw_level", "float", nullable=True, value_range="KRW per USD", direction="higher means weaker KRW"),
                    col("wti_level", "float", nullable=True, value_range="USD per barrel", direction="higher means higher oil price"),
                    col("cpi_yoy", "float", nullable=True, value_range=ratio, direction="higher means higher US headline CPI inflation"),
                    col("core_cpi_yoy", "float", nullable=True, value_range=ratio, direction="higher means higher US core CPI inflation"),
                    col("ppi_yoy", "float", nullable=True, value_range=ratio, direction="higher means higher US PPI inflation"),
                    col("unrate", "float", nullable=True, value_range="percent level", direction="higher means higher US unemployment"),
                    col("payrolls_3m_change", "float", nullable=True, value_range="thousand persons change", direction="higher means stronger US payroll growth"),
                    col("monthly_macro_release_lag_days", "integer", nullable=True, value_range="21", direction="conservative release lag applied to monthly macro observations"),
                    col("global_feature_version", "string", nullable=False, value_range="FRED global context feature version"),
                    col("global_schema_version", "string", nullable=False, value_range="FRED global context schema version"),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
            "external_market_context_daily": {
                "primary_key": ["asof_date"],
                "join_keys": ["asof_date"],
                "source_policy": "Yahoo daily ETF/proxy based external market risk-on/risk-off context. asof_date is the KST-safe PIT available date; external_source_asof_date preserves the original US market date.",
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2017-01-01 or later"),
                    col("external_source_asof_date", "date string YYYY-MM-DD", nullable=False, value_range="original US market/Yahoo date"),
                    col("external_pit_available_date", "date string YYYY-MM-DD", nullable=False, value_range="first KST business date allowed for model use"),
                    col("external_pit_lag_rule", "string", nullable=False, value_range="fixed PIT lag policy text"),
                    col("us_equity_momentum_score", "float", nullable=True, value_range=score, direction="higher means stronger US equity momentum"),
                    col("us_growth_risk_score", "float", nullable=True, value_range=score, direction="higher means stronger US growth/tech risk appetite"),
                    col("us_smallcap_risk_score", "float", nullable=True, value_range=score, direction="higher means stronger US small-cap appetite"),
                    col("us_sector_risk_on_score", "float", nullable=True, value_range=score, direction="higher means cyclicals outperform defensives"),
                    col("us_defensive_sector_score", "float", nullable=True, value_range=score, direction="higher means defensive sectors are stronger"),
                    col("global_breadth_proxy_score", "float", nullable=True, value_range=score, direction="higher means broader US sector participation"),
                    col("korea_proxy_momentum_score", "float", nullable=True, value_range=score, direction="higher means stronger US-listed Korea ETF proxy momentum"),
                    col("credit_proxy_score", "float", nullable=True, value_range=score, direction="higher means stronger high-yield credit appetite versus IG"),
                    col("safe_haven_pressure_score", "float", nullable=True, value_range=score, direction="higher means stronger safe-haven pressure"),
                    col("commodity_risk_score", "float", nullable=True, value_range=score, direction="higher means stronger oil/commodity pressure"),
                    col("dollar_risk_score", "float", nullable=True, value_range=score, direction="higher means stronger dollar pressure"),
                    col("vix_market_stress_score", "float", nullable=True, value_range=score, direction="higher means stronger volatility stress"),
                    col("semiconductor_momentum_score", "float", nullable=True, value_range=score, direction="higher means stronger semiconductor-led risk appetite"),
                    col("global_ex_us_momentum_score", "float", nullable=True, value_range=score, direction="higher means stronger global ex-US equity momentum"),
                    col("em_vs_dm_score", "float", nullable=True, value_range=score, direction="higher means EM outperforms developed ex-US equities"),
                    col("asia_risk_on_score", "float", nullable=True, value_range=score, direction="higher means stronger Asia equity risk appetite"),
                    col("bank_stress_relief_score", "float", nullable=True, value_range=score, direction="higher means regional bank stress is easing"),
                    col("rate_sensitive_cyclical_score", "float", nullable=True, value_range=score, direction="higher means rate-sensitive cyclicals are stronger"),
                    col("transport_cyclical_score", "float", nullable=True, value_range=score, direction="higher means transportation cyclicals are stronger"),
                    col("low_vol_defensive_pressure_score", "float", nullable=True, value_range=score, direction="higher means low-vol defensive equity is outperforming"),
                    col("crypto_risk_appetite_score", "float", nullable=True, value_range=score, direction="higher means speculative risk appetite is stronger"),
                    col("external_asset_risk_on_score", "float", nullable=True, value_range=score, direction="higher means stronger external market risk-on condition"),
                    col("spy_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means stronger S&P500 proxy return"),
                    col("spy_ret_3m", "float", nullable=True, value_range=ratio, direction="higher means stronger S&P500 proxy return"),
                    col("qqq_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means stronger Nasdaq proxy return"),
                    col("qqq_ret_3m", "float", nullable=True, value_range=ratio, direction="higher means stronger Nasdaq proxy return"),
                    col("iwm_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means stronger Russell 2000 proxy return"),
                    col("ewy_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means stronger US-listed Korea ETF return"),
                    col("ewy_ret_3m", "float", nullable=True, value_range=ratio, direction="higher means stronger US-listed Korea ETF return"),
                    col("sector_cyclical_vs_defensive_1m", "float", nullable=True, value_range=ratio, direction="higher means cyclicals outperform defensives"),
                    col("sector_positive_ratio_1m", "float", nullable=True, value_range="0 to 1", direction="higher means more sectors have positive 1m return"),
                    col("sector_above_sma60_ratio", "float", nullable=True, value_range="0 to 1", direction="higher means more sectors are above 60d SMA"),
                    col("hyg_lqd_ret_spread_1m", "float", nullable=True, value_range=ratio, direction="higher means high-yield credit outperforms IG credit"),
                    col("tlt_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means long Treasury proxy stronger"),
                    col("gld_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means gold proxy stronger"),
                    col("uso_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means oil proxy stronger"),
                    col("uup_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means dollar proxy stronger"),
                    col("vix_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means VIX increased"),
                    col("soxx_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means semiconductor ETF stronger"),
                    col("soxx_ret_3m", "float", nullable=True, value_range=ratio, direction="higher means semiconductor ETF stronger"),
                    col("acwx_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means global ex-US ETF stronger"),
                    col("efa_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means developed ex-US ETF stronger"),
                    col("eem_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means EM ETF stronger"),
                    col("fxi_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means China ETF stronger"),
                    col("ewj_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means Japan ETF stronger"),
                    col("ewt_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means Taiwan ETF stronger"),
                    col("inda_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means India ETF stronger"),
                    col("kre_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means regional bank ETF stronger"),
                    col("xhb_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means homebuilder ETF stronger"),
                    col("iyt_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means transportation ETF stronger"),
                    col("usmv_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means minimum-volatility ETF stronger"),
                    col("dxy_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means direct dollar index stronger"),
                    col("btcusd_ret_1m", "float", nullable=True, value_range=ratio, direction="higher means Bitcoin stronger"),
                    col("external_market_feature_version", "string", nullable=False, value_range="Yahoo external market context feature version"),
                    col("external_market_schema_version", "string", nullable=False, value_range="Yahoo external market context schema version"),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
            "market_forecast_daily": {
                "primary_key": ["asof_date", "market_scope", "forecast_horizon"],
                "join_keys": ["asof_date", "market_scope", "forecast_horizon"],
                "model_policy": "Baseline QM market forecast feature. This is a quantitative model input, not public investment advice or a deterministic market call.",
                "columns": [
                    col("asof_date", "date string YYYY-MM-DD", nullable=False, value_range="2017-01-01 or later"),
                    col("market_scope", "string", nullable=False, value_range="ALL/KOSPI/KOSDAQ", labels=MARKET_SCOPES),
                    col("forecast_horizon", "string", nullable=False, value_range="fixed categorical", labels=FORECAST_HORIZONS),
                    col("market_forecast_score", "float", nullable=True, value_range=score, direction="higher means more constructive expected market bias"),
                    col("market_forecast_label", "string", nullable=True, value_range="fixed categorical", labels=["bullish", "mild_bullish", "neutral", "mild_bearish", "bearish"], direction="ordered from bearish to bullish"),
                    col("risk_regime_label", "string", nullable=True, value_range="fixed categorical", labels=["risk_on_high", "risk_on_moderate", "neutral", "risk_off_moderate", "risk_off_high"], direction="risk_off labels indicate less favorable regime"),
                    col("expected_volatility_score", "float", nullable=True, value_range="0 to 3", direction="higher means higher expected volatility burden"),
                    col("drawdown_risk_score", "float", nullable=True, value_range="0 to 3", direction="higher means larger drawdown risk"),
                    col("upside_participation_score", "float", nullable=True, value_range=score, direction="higher means stronger trend/breadth participation"),
                    col("confidence_score", "float", nullable=False, value_range="0 to 1", direction="higher means stronger model input completeness/conviction"),
                    col("baseline_market_state_score", "float", nullable=True, value_range=score, direction="higher is more constructive QM market state"),
                    col("baseline_trend_score", "float", nullable=True, value_range=score, direction="higher is stronger price trend"),
                    col("baseline_breadth_score", "float", nullable=True, value_range=score, direction="higher is broader participation"),
                    col("baseline_risk_on_score", "float", nullable=True, value_range="0 to 3", direction="higher is more risk-on"),
                    col("baseline_risk_off_score", "float", nullable=True, value_range="0 to 3", direction="higher is more risk-off"),
                    col("baseline_global_risk_on_score", "float", nullable=True, value_range=score, direction="higher is more favorable global risk appetite"),
                    col("baseline_external_asset_risk_on_score", "float", nullable=True, value_range=score, direction="higher is stronger external market risk-on condition"),
                    col("baseline_external_macro_pressure_score", "float", nullable=True, value_range=score, direction="higher is larger external macro pressure"),
                    col("baseline_smart_money_score", "float", nullable=True, value_range="-1 to 1", direction="higher means stronger foreign+institution flow"),
                    col("forecast_model_version", "string", nullable=False, value_range=FORECAST_MODEL_VERSION),
                    col("schema_version", "string", nullable=False, value_range=MART_SCHEMA_VERSION),
                    col("feature_version", "string", nullable=False, value_range=FEATURE_VERSION),
                    col("generated_at", "datetime string ISO8601 +09:00", nullable=False, value_range="Asia/Seoul timestamp"),
                ],
            },
        },
    }


def _theme_crosswalk() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quant_theme_bucket": quant_bucket,
                "quantmarket_theme_bucket": qm_bucket,
                "theme_name_kr": name_kr,
                "proxy_ticker": ticker,
                "proxy_name": THEME_PROXY_NAMES.get(ticker),
                "mapping_confidence": confidence,
                "mapping_reason": reason,
                "is_active": 1,
            }
            for quant_bucket, qm_bucket, name_kr, ticker, confidence, reason in QUANT_THEME_MAPPINGS
        ]
    )


def _build_quant_bucket_theme_context(theme_context: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    if theme_context.empty or crosswalk.empty:
        return pd.DataFrame(columns=_theme_quant_bucket_columns())
    active = crosswalk[crosswalk["is_active"].astype(int) == 1].copy()
    out = theme_context.merge(
        active,
        left_on="theme_bucket",
        right_on="quantmarket_theme_bucket",
        how="inner",
        suffixes=("_qm", "_mapped"),
    )
    out = out.rename(columns={"theme_bucket": "quantmarket_theme_bucket_source"})
    out["quantmarket_theme_bucket"] = out["quantmarket_theme_bucket"].fillna(out["quantmarket_theme_bucket_source"])
    out["theme_name_kr"] = out["theme_name_kr_mapped"].fillna(out["theme_name_kr_qm"])
    return out[_theme_quant_bucket_columns()]


def _build_global_context(global_context_db: Path, start: str, end: str, generated_at: str) -> pd.DataFrame:
    columns = [
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
        "us_real_10y_rate",
        "breakeven_10y",
        "vix_level",
        "hy_spread",
        "ig_spread",
        "dxy_level",
        "usdkrw_level",
        "wti_level",
        "cpi_yoy",
        "core_cpi_yoy",
        "ppi_yoy",
        "unrate",
        "payrolls_3m_change",
        "monthly_macro_release_lag_days",
        "global_feature_version",
        "global_schema_version",
        "schema_version",
        "feature_version",
        "generated_at",
    ]
    if not global_context_db.exists():
        return pd.DataFrame(columns=columns)

    with _ro_connect(global_context_db) as con:
        source = pd.read_sql_query(
            """
            SELECT *
            FROM global_context_daily
            WHERE asof_date >= ?
              AND asof_date <= ?
            ORDER BY asof_date
            """,
            con,
            params=(_start_buffer_for_pit(start), end),
        )
    if source.empty:
        return pd.DataFrame(columns=columns)

    source = source.rename(
        columns={
            "feature_version": "global_feature_version",
            "schema_version": "global_schema_version",
        }
    )
    source["global_source_asof_date"] = source["asof_date"].astype(str)
    source["global_pit_available_date"] = source["global_source_asof_date"].map(_next_kst_business_date)
    source["global_pit_lag_rule"] = "US/FRED daily source date + 1 business day KST; monthly macro values use conservative source month + 21 calendar days before feature use"
    if "monthly_macro_release_lag_days" not in source.columns:
        source["monthly_macro_release_lag_days"] = 21
    source["asof_date"] = source["global_pit_available_date"]
    source = source[source["asof_date"].between(start, end)].copy()
    source = source.sort_values(["asof_date", "global_source_asof_date"]).drop_duplicates("asof_date", keep="last")
    source["schema_version"] = MART_SCHEMA_VERSION
    source["feature_version"] = FEATURE_VERSION
    source["generated_at"] = generated_at
    return source[columns]


def _build_external_market_context(global_context_db: Path, start: str, end: str, generated_at: str) -> pd.DataFrame:
    columns = [
        "asof_date",
        "external_source_asof_date",
        "external_pit_available_date",
        "external_pit_lag_rule",
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
        "external_asset_risk_on_score",
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
        "external_market_feature_version",
        "external_market_schema_version",
        "schema_version",
        "feature_version",
        "generated_at",
    ]
    if not global_context_db.exists():
        return pd.DataFrame(columns=columns)

    with _ro_connect(global_context_db) as con:
        source = pd.read_sql_query(
            """
            SELECT *
            FROM external_market_context_daily
            WHERE asof_date >= ?
              AND asof_date <= ?
            ORDER BY asof_date
            """,
            con,
            params=(_start_buffer_for_pit(start), end),
        )
    if source.empty:
        return pd.DataFrame(columns=columns)
    source = source.rename(
        columns={
            "feature_version": "external_market_feature_version",
            "schema_version": "external_market_schema_version",
        }
    )
    source["external_source_asof_date"] = source["asof_date"].astype(str)
    source["external_pit_available_date"] = source["external_source_asof_date"].map(_next_kst_business_date)
    source["external_pit_lag_rule"] = "US Yahoo ETF source date + 1 business day KST before Korean model use"
    source["asof_date"] = source["external_pit_available_date"]
    source = source[source["asof_date"].between(start, end)].copy()
    source = source.sort_values(["asof_date", "external_source_asof_date"]).drop_duplicates("asof_date", keep="last")
    source["schema_version"] = MART_SCHEMA_VERSION
    source["feature_version"] = FEATURE_VERSION
    source["generated_at"] = generated_at
    return source[columns]


def _theme_quant_bucket_columns() -> list[str]:
    return [
        "asof_date",
        "quant_theme_bucket",
        "quantmarket_theme_bucket",
        "theme_name_kr",
        "theme_ret_1w",
        "theme_ret_1m",
        "theme_ret_3m",
        "theme_momentum_score",
        "theme_rotation_score",
        "theme_persistence_days",
        "theme_breadth_positive_ratio",
        "theme_above_sma60_ratio",
        "theme_trading_value_expansion_ratio",
        "theme_concentration_score",
        "leading_theme_rank",
        "mapping_confidence",
        "feature_version",
        "schema_version",
        "generated_at",
    ]


def _quant_theme_stock_coverage(classification_db: Path, crosswalk: pd.DataFrame) -> dict:
    mapped = set(crosswalk.loc[crosswalk["is_active"].astype(int) == 1, "quant_theme_bucket"].astype(str))
    if not classification_db.exists():
        return {
            "source_db": str(classification_db),
            "available": False,
            "latest_asof_date": None,
            "quant_theme_bucket_count": len(mapped),
            "mapped_bucket_count": len(mapped),
            "unmapped_bucket_list": [],
            "mapped_stock_row_coverage": None,
            "bucket_rows": [],
            "low_confidence_mapping_list": crosswalk[crosswalk["mapping_confidence"] < 0.7].to_dict("records"),
        }
    with _ro_connect(classification_db) as con:
        row = con.execute(
            "SELECT MAX(asof_date) AS asof_date FROM security_classification_master WHERE asset_type='STOCK'"
        ).fetchone()
        asof_date = row["asof_date"] if row else None
        if not asof_date:
            return {
                "source_db": str(classification_db),
                "available": False,
                "latest_asof_date": None,
                "quant_theme_bucket_count": len(mapped),
                "mapped_bucket_count": len(mapped),
                "unmapped_bucket_list": [],
                "mapped_stock_row_coverage": None,
                "bucket_rows": [],
                "low_confidence_mapping_list": crosswalk[crosswalk["mapping_confidence"] < 0.7].to_dict("records"),
            }
        rows = con.execute(
            """
            SELECT theme_bucket, COUNT(1) AS stock_rows
            FROM security_classification_master
            WHERE asset_type='STOCK'
              AND asof_date=?
            GROUP BY theme_bucket
            ORDER BY theme_bucket
            """,
            (asof_date,),
        ).fetchall()
    bucket_rows = [dict(row) for row in rows]
    actual = {str(row["theme_bucket"]) for row in bucket_rows}
    mapped_actual = actual & mapped
    total_rows = sum(int(row["stock_rows"]) for row in bucket_rows)
    covered_rows = sum(int(row["stock_rows"]) for row in bucket_rows if str(row["theme_bucket"]) in mapped)
    return {
        "source_db": str(classification_db),
        "available": True,
        "latest_asof_date": asof_date,
        "quant_theme_bucket_count": len(actual),
        "mapped_bucket_count": len(mapped_actual),
        "unmapped_bucket_list": sorted(actual - mapped),
        "mapped_stock_row_coverage": round(covered_rows / total_rows, 6) if total_rows else None,
        "stock_rows_total": total_rows,
        "stock_rows_mapped": covered_rows,
        "bucket_rows": bucket_rows,
        "low_confidence_mapping_list": crosswalk[crosswalk["mapping_confidence"] < 0.7].to_dict("records"),
    }


def _report(
    *,
    market_context: pd.DataFrame,
    theme_context: pd.DataFrame,
    theme_context_quant_bucket: pd.DataFrame,
    risk_context: pd.DataFrame,
    flow_context: pd.DataFrame,
    global_context: pd.DataFrame,
    external_market_context: pd.DataFrame,
    market_forecast: pd.DataFrame,
    theme_crosswalk: pd.DataFrame,
    quant_theme_coverage: dict,
    generated_at: str,
    source_price_db: Path,
    source_qm_db: Path,
    source_global_context_db: Path,
    target_db: Path,
    output_dir: Path,
) -> dict:
    tables = {
        "market_context_daily": market_context,
        "theme_context_daily": theme_context,
        "theme_context_daily_quant_bucket": theme_context_quant_bucket,
        "risk_context_daily": risk_context,
        "flow_context_daily": flow_context,
        "global_context_daily": global_context,
        "external_market_context_daily": external_market_context,
        "market_forecast_daily": market_forecast,
    }
    expected_dates = sorted(market_context["asof_date"].dropna().astype(str).unique().tolist()) if not market_context.empty else []
    primary_keys = {
        "market_context_daily": ["asof_date", "market_scope"],
        "theme_context_daily": ["asof_date", "theme_bucket"],
        "theme_context_daily_quant_bucket": ["asof_date", "quant_theme_bucket"],
        "risk_context_daily": ["asof_date"],
        "flow_context_daily": ["asof_date", "market_scope"],
        "global_context_daily": ["asof_date"],
        "external_market_context_daily": ["asof_date"],
        "market_forecast_daily": ["asof_date", "market_scope", "forecast_horizon"],
    }
    market_label_distribution = (
        market_context["market_state_label"].value_counts(dropna=False).rename_axis("market_state_label").reset_index(name="rows").to_dict("records")
        if not market_context.empty
        else []
    )
    theme_coverage = (
        theme_context.groupby("theme_bucket", as_index=False)
        .agg(start=("asof_date", "min"), end=("asof_date", "max"), rows=("asof_date", "count"))
        .sort_values("theme_bucket")
        .to_dict("records")
        if not theme_context.empty
        else []
    )
    return {
        "source_name": "QuantMarket AI training market context mart",
        "schema_version": MART_SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "source_version": SOURCE_VERSION,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "point_in_time_policy": "All rolling domestic features use data at or before asof_date. US/FRED/Yahoo external features are shifted to the first KST business date after the source date before joining. Monthly FRED macro observations are used only after a conservative 21 calendar day release lag. Historical market/theme/risk proxies are ETF price histories read-only referenced from D:\\Quant\\data\\db\\price.db and written only to D:\\QuantMarket.",
        "null_policy": "Unavailable features remain null. They are not zero-filled.",
        "label_sets": {
            "market_state_label": ["strong_up", "up", "neutral", "down", "strong_down"],
            "volatility_regime_label": ["low", "normal", "high", "stress"],
            "market_forecast_label": ["bullish", "mild_bullish", "neutral", "mild_bearish", "bearish"],
            "risk_regime_label": ["risk_on_high", "risk_on_moderate", "neutral", "risk_off_moderate", "risk_off_high"],
        },
        "source_paths": {
            "price_db_readonly": str(source_price_db),
            "qm_db_readonly": str(source_qm_db),
            "global_context_db_readonly": str(source_global_context_db),
            "quant_security_classification_db_readonly": quant_theme_coverage.get("source_db"),
        },
        "output_paths": {
            "target_db": str(target_db),
            "output_dir": str(output_dir),
            "manifest": str(output_dir / CANONICAL_CURRENT_FILES["manifest"]),
            "schema": str(output_dir / CANONICAL_CURRENT_FILES["schema"]),
            "theme_crosswalk": str(output_dir / CANONICAL_CURRENT_FILES["theme_crosswalk"]),
        },
        "canonical_files": CANONICAL_CURRENT_FILES,
        "tables": {
            name: {
                "rows": int(len(df)),
                "date_range": _date_range(df),
                "missing_rates": _missing_rates(df),
                "duplicate_key_count": _duplicate_key_count(df, primary_keys[name]),
                "missing_date_count": _missing_date_count(df, expected_dates),
                "market_scope_coverage": _market_scope_coverage(df),
            }
            for name, df in tables.items()
        },
        "market_state_label_distribution": market_label_distribution,
        "theme_bucket_coverage": theme_coverage,
        "quant_theme_mapping_coverage": quant_theme_coverage,
        "theme_bucket_crosswalk": theme_crosswalk.to_dict("records"),
        "known_limitations": [
            "KOSPI/KOSDAQ historical market features use listed ETF proxies, not official index total market breadth.",
            "theme_context_daily uses sector ETF proxies and can only start after each ETF listing date.",
            "theme_context_daily_quant_bucket maps Quant model stock themes to broad ETF proxy buckets; low-confidence mappings should be reviewed before high-stakes model use.",
            "flow_context_daily is available only for recent QM intraday aggregate flow snapshots; historical investor breadth is not yet available.",
            "global_context_daily asof_date is KST PIT-safe after US/FRED source-date lag; original source date is preserved in global_source_asof_date.",
            "global_context_daily credit spread coverage can be shorter than rate/FX coverage depending on FRED API availability.",
            "external_market_context_daily asof_date is KST PIT-safe after US market source-date lag; original source date is preserved in external_source_asof_date.",
            "market_forecast_daily is a baseline score-combination forecast mart for model features; it is not yet an outcome-trained predictive model.",
            "D:\\Quant is read only; all mart outputs are stored under D:\\QuantMarket.",
        ],
    }


def _write_report_md(report: dict, path: Path) -> None:
    lines = [
        "# QuantMarket AI Training Market Context Mart Reply",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- schema_version: {report['schema_version']}",
        f"- feature_version: {report['feature_version']}",
        f"- target_db: `{report['output_paths']['target_db']}`",
        f"- output_dir: `{report['output_paths']['output_dir']}`",
        f"- manifest: `{report['output_paths']['manifest']}`",
        f"- schema: `{report['output_paths']['schema']}`",
        "",
        "## Table Summary",
        "",
        "| table | rows | start | end | duplicate keys | missing dates |",
        "|---|---:|---|---|---:|---:|",
    ]
    for name, meta in report["tables"].items():
        dr = meta["date_range"]
        lines.append(
            f"| {name} | {meta['rows']} | {dr['start']} | {dr['end']} | "
            f"{meta['duplicate_key_count']} | {meta['missing_date_count']} |"
        )
    lines.extend(["", "## Market State Label Distribution", ""])
    for row in report["market_state_label_distribution"]:
        lines.append(f"- {row['market_state_label']}: {row['rows']}")
    lines.extend(["", "## Theme Bucket Coverage", ""])
    for row in report["theme_bucket_coverage"]:
        lines.append(f"- {row['theme_bucket']}: {row['rows']} rows ({row['start']} ~ {row['end']})")
    qcov = report.get("quant_theme_mapping_coverage", {})
    lines.extend(["", "## Quant Theme Mapping Coverage", ""])
    lines.append(f"- latest_asof_date: {qcov.get('latest_asof_date')}")
    lines.append(f"- quant_theme_bucket_count: {qcov.get('quant_theme_bucket_count')}")
    lines.append(f"- mapped_bucket_count: {qcov.get('mapped_bucket_count')}")
    lines.append(f"- mapped_stock_row_coverage: {qcov.get('mapped_stock_row_coverage')}")
    lines.append(f"- unmapped_bucket_list: {qcov.get('unmapped_bucket_list')}")
    lines.append(f"- low_confidence_mapping_count: {len(qcov.get('low_confidence_mapping_list') or [])}")
    lines.extend(["", "## Known Limitations", ""])
    for item in report["known_limitations"]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _manifest_from_report(report: dict) -> dict:
    market_meta = report["tables"].get("market_context_daily", {})
    date_range = market_meta.get("date_range", {})
    return {
        "source_name": report["source_name"],
        "as_of_date": date_range.get("end"),
        "generated_at": report["generated_at"],
        "timezone": report["timezone"],
        "schema_version": report["schema_version"],
        "source_version": report["source_version"],
        "feature_version": report["feature_version"],
        "canonical_files": report["canonical_files"],
        "tables": {
            name: {
                "file": report["canonical_files"].get(name),
                "row_count": meta["rows"],
                "start_date": meta["date_range"]["start"],
                "end_date": meta["date_range"]["end"],
                "duplicate_key_count": meta["duplicate_key_count"],
                "missing_date_count": meta["missing_date_count"],
            }
            for name, meta in report["tables"].items()
        },
        "warnings": report["known_limitations"],
        "label_sets": report["label_sets"],
        "point_in_time_policy": report["point_in_time_policy"],
        "null_policy": report["null_policy"],
    }


def build_ai_training_context_mart(
    *,
    source_qm_db: Path,
    source_price_db: Path,
    source_classification_db: Path,
    source_global_context_db: Path,
    target_db: Path,
    output_dir: Path,
    report_dir: Path,
    start: str = "2017-01-01",
    end: str | None = None,
) -> MartBuildResult:
    generated_at = _now_kst()
    if end is None:
        with _ro_connect(source_price_db) as con:
            row = con.execute("SELECT MAX(date) AS max_date FROM prices_daily").fetchone()
            end = row["max_date"]
    if end is None:
        raise RuntimeError("Unable to determine end date from price DB.")

    market_context, risk_context = _build_market_context(source_price_db, start, end, generated_at)
    theme_context = _build_theme_context(source_price_db, start, end, generated_at)
    crosswalk = _theme_crosswalk()
    theme_context_quant_bucket = _build_quant_bucket_theme_context(theme_context, crosswalk)
    quant_theme_coverage = _quant_theme_stock_coverage(source_classification_db, crosswalk)
    global_context = _build_global_context(source_global_context_db, start, end, generated_at)
    external_market_context = _build_external_market_context(source_global_context_db, start, end, generated_at)
    date_spine = sorted(market_context["asof_date"].dropna().astype(str).unique().tolist())
    flow_context = _build_flow_context(source_qm_db, start, end, generated_at, date_spine)
    market_forecast = _build_market_forecast_context(
        market_context=market_context,
        risk_context=risk_context,
        flow_context=flow_context,
        global_context=global_context,
        external_market_context=external_market_context,
        generated_at=generated_at,
    )

    target_db.parent.mkdir(parents=True, exist_ok=True)
    with _connect(target_db) as con:
        _write_table(con, "market_context_daily", market_context)
        _write_table(con, "theme_context_daily", theme_context)
        _write_table(con, "theme_context_daily_quant_bucket", theme_context_quant_bucket)
        _write_table(con, "risk_context_daily", risk_context)
        _write_table(con, "flow_context_daily", flow_context)
        _write_table(con, "global_context_daily", global_context)
        _write_table(con, "external_market_context_daily", external_market_context)
        _write_table(con, "market_forecast_daily", market_forecast)
        con.execute("DROP TABLE IF EXISTS mart_metadata")
        pd.DataFrame(
            [
                {
                    "source_name": "QuantMarket AI training market context mart",
                    "schema_version": MART_SCHEMA_VERSION,
                    "feature_version": FEATURE_VERSION,
                    "source_version": SOURCE_VERSION,
                    "generated_at": generated_at,
                    "start_date": start,
                    "end_date": end,
                    "source_price_db_readonly": str(source_price_db),
                    "source_qm_db_readonly": str(source_qm_db),
                    "source_classification_db_readonly": str(source_classification_db),
                    "source_global_context_db_readonly": str(source_global_context_db),
                }
            ]
        ).to_sql("mart_metadata", con, if_exists="replace", index=False)
        con.commit()

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in {
        "market_context_daily": market_context,
        "theme_context_daily": theme_context,
        "theme_context_daily_quant_bucket": theme_context_quant_bucket,
        "risk_context_daily": risk_context,
        "flow_context_daily": flow_context,
        "global_context_daily": global_context,
        "external_market_context_daily": external_market_context,
        "market_forecast_daily": market_forecast,
    }.items():
        df.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
        df.to_csv(output_dir / CANONICAL_CURRENT_FILES[name], index=False, encoding="utf-8-sig")

    schema = _schema_contract()
    crosswalk.to_csv(output_dir / CANONICAL_CURRENT_FILES["theme_crosswalk"], index=False, encoding="utf-8-sig")

    report = _report(
        market_context=market_context,
        theme_context=theme_context,
        theme_context_quant_bucket=theme_context_quant_bucket,
        risk_context=risk_context,
        flow_context=flow_context,
        global_context=global_context,
        external_market_context=external_market_context,
        market_forecast=market_forecast,
        theme_crosswalk=crosswalk,
        quant_theme_coverage=quant_theme_coverage,
        generated_at=generated_at,
        source_price_db=source_price_db,
        source_qm_db=source_qm_db,
        source_global_context_db=source_global_context_db,
        target_db=target_db,
        output_dir=output_dir,
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    report_json = report_dir / "ai_training_market_context_mart_coverage_latest.json"
    report_md = report_dir / "ai_training_market_context_mart_reply_latest.md"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report_md(report, report_md)
    (output_dir / CANONICAL_CURRENT_FILES["manifest"]).write_text(
        json.dumps(_manifest_from_report(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / CANONICAL_CURRENT_FILES["schema"]).write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (report_dir / "ai_training_market_context_schema_latest.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    crosswalk.to_csv(report_dir / "theme_bucket_crosswalk_latest.csv", index=False, encoding="utf-8-sig")

    return MartBuildResult(
        target_db=target_db,
        output_dir=output_dir,
        report_json=report_json,
        report_md=report_md,
        generated_at=generated_at,
        row_counts={name: meta["rows"] for name, meta in report["tables"].items()},
        date_range={name: meta["date_range"] for name, meta in report["tables"].items()},
    )
