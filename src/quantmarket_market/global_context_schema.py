from __future__ import annotations

GLOBAL_CONTEXT_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS global_series_registry (
    source TEXT NOT NULL,
    series_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit TEXT,
    frequency TEXT,
    market_relevance TEXT,
    score_direction TEXT,
    transform_hint TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, series_id)
);

CREATE TABLE IF NOT EXISTS global_observation (
    source TEXT NOT NULL,
    series_id TEXT NOT NULL,
    asof_date TEXT NOT NULL,
    value REAL,
    raw_value TEXT,
    realtime_start TEXT,
    realtime_end TEXT,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (source, series_id, asof_date, realtime_start, realtime_end)
);

CREATE INDEX IF NOT EXISTS idx_global_observation_lookup
    ON global_observation (source, series_id, asof_date);

CREATE TABLE IF NOT EXISTS global_collection_run_log (
    run_id TEXT NOT NULL PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    requested_series_count INTEGER NOT NULL DEFAULT 0,
    inserted_or_updated_rows INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS global_context_daily (
    asof_date TEXT NOT NULL PRIMARY KEY,
    rate_pressure_score REAL,
    usd_pressure_score REAL,
    credit_stress_score REAL,
    risk_aversion_score REAL,
    inflation_pressure_score REAL,
    commodity_pressure_score REAL,
    global_risk_on_score REAL,
    external_macro_pressure_score REAL,
    yield_curve_10y_2y REAL,
    yield_curve_10y_3m REAL,
    us_10y_rate REAL,
    us_2y_rate REAL,
    us_real_10y_rate REAL,
    breakeven_10y REAL,
    vix_level REAL,
    hy_spread REAL,
    ig_spread REAL,
    dxy_level REAL,
    usdkrw_level REAL,
    wti_level REAL,
    cpi_yoy REAL,
    core_cpi_yoy REAL,
    ppi_yoy REAL,
    unrate REAL,
    payrolls_3m_change REAL,
    monthly_macro_release_lag_days INTEGER,
    feature_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS global_asset_registry (
    source TEXT NOT NULL,
    asset_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    display_name TEXT NOT NULL,
    asset_group TEXT NOT NULL,
    region TEXT,
    currency TEXT,
    market_relevance TEXT,
    score_direction TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, asset_code)
);

CREATE TABLE IF NOT EXISTS global_asset_daily (
    source TEXT NOT NULL,
    asset_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asof_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adj_close REAL,
    volume REAL,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (source, asset_code, asof_date)
);

CREATE INDEX IF NOT EXISTS idx_global_asset_daily_lookup
    ON global_asset_daily (source, asset_code, asof_date);

CREATE TABLE IF NOT EXISTS global_asset_intraday_snapshot (
    source TEXT NOT NULL,
    asset_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asof TEXT NOT NULL,
    session_date TEXT NOT NULL,
    price REAL,
    change_value REAL,
    change_pct REAL,
    open REAL,
    high REAL,
    low REAL,
    prev_close REAL,
    volume REAL,
    quote_time TEXT,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (source, asset_code, asof)
);

CREATE INDEX IF NOT EXISTS idx_global_asset_intraday_snapshot_lookup
    ON global_asset_intraday_snapshot (source, asset_code, asof);

CREATE TABLE IF NOT EXISTS external_market_context_daily (
    asof_date TEXT NOT NULL PRIMARY KEY,
    us_equity_momentum_score REAL,
    us_growth_risk_score REAL,
    us_smallcap_risk_score REAL,
    us_sector_risk_on_score REAL,
    us_defensive_sector_score REAL,
    global_breadth_proxy_score REAL,
    korea_proxy_momentum_score REAL,
    credit_proxy_score REAL,
    safe_haven_pressure_score REAL,
    commodity_risk_score REAL,
    dollar_risk_score REAL,
    vix_market_stress_score REAL,
    semiconductor_momentum_score REAL,
    global_ex_us_momentum_score REAL,
    em_vs_dm_score REAL,
    asia_risk_on_score REAL,
    bank_stress_relief_score REAL,
    rate_sensitive_cyclical_score REAL,
    transport_cyclical_score REAL,
    low_vol_defensive_pressure_score REAL,
    crypto_risk_appetite_score REAL,
    external_asset_risk_on_score REAL,
    spy_ret_1m REAL,
    spy_ret_3m REAL,
    qqq_ret_1m REAL,
    qqq_ret_3m REAL,
    iwm_ret_1m REAL,
    ewy_ret_1m REAL,
    ewy_ret_3m REAL,
    sector_cyclical_vs_defensive_1m REAL,
    sector_positive_ratio_1m REAL,
    sector_above_sma60_ratio REAL,
    hyg_lqd_ret_spread_1m REAL,
    tlt_ret_1m REAL,
    gld_ret_1m REAL,
    uso_ret_1m REAL,
    uup_ret_1m REAL,
    vix_ret_1m REAL,
    soxx_ret_1m REAL,
    soxx_ret_3m REAL,
    acwx_ret_1m REAL,
    efa_ret_1m REAL,
    eem_ret_1m REAL,
    fxi_ret_1m REAL,
    ewj_ret_1m REAL,
    ewt_ret_1m REAL,
    inda_ret_1m REAL,
    kre_ret_1m REAL,
    xhb_ret_1m REAL,
    iyt_ret_1m REAL,
    usmv_ret_1m REAL,
    dxy_ret_1m REAL,
    btcusd_ret_1m REAL,
    feature_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    generated_at TEXT NOT NULL
);
"""
