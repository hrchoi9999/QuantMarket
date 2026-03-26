from __future__ import annotations

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS market_index_daily (
    market TEXT NOT NULL,
    index_code TEXT NOT NULL,
    index_name TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume REAL,
    value REAL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, index_code, date)
);

CREATE INDEX IF NOT EXISTS idx_market_index_daily_lookup
    ON market_index_daily (market, index_code, date);

CREATE TABLE IF NOT EXISTS market_fx_daily (
    market TEXT NOT NULL,
    series_code TEXT NOT NULL,
    series_name TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, series_code, date)
);

CREATE INDEX IF NOT EXISTS idx_market_fx_daily_lookup
    ON market_fx_daily (market, series_code, date);

CREATE TABLE IF NOT EXISTS market_rates_daily (
    market TEXT NOT NULL,
    rate_code TEXT NOT NULL,
    rate_name TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, rate_code, date)
);

CREATE INDEX IF NOT EXISTS idx_market_rates_daily_lookup
    ON market_rates_daily (market, rate_code, date);

CREATE TABLE IF NOT EXISTS market_features_hourly (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    asof_date TEXT NOT NULL,
    kospi_1d_ret REAL,
    kospi_5d_ret REAL,
    kospi_20d_ret REAL,
    kospi_60d_ret REAL,
    kosdaq_1d_ret REAL,
    kosdaq_5d_ret REAL,
    kosdaq_20d_ret REAL,
    kosdaq_60d_ret REAL,
    kospi200_20d_ret REAL,
    usdkrw_20d_ret REAL,
    rate_cd91_20d_chg REAL,
    rate_ktb3y_20d_chg REAL,
    above_20dma_ratio REAL,
    above_60dma_ratio REAL,
    adv_dec_ratio REAL,
    new_high_count REAL,
    new_low_count REAL,
    breadth_universe_count INTEGER,
    realized_vol_20d REAL,
    drawdown_5d REAL,
    drawdown_20d REAL,
    bond_20d_ret REAL,
    gold_20d_ret REAL,
    inverse_20d_ret REAL,
    breadth_proxy_flag INTEGER NOT NULL DEFAULT 0,
    defensive_proxy_flag INTEGER NOT NULL DEFAULT 0,
    regime_3m_score REAL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof)
);

CREATE TABLE IF NOT EXISTS market_component_scores (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    trend_score REAL NOT NULL,
    breadth_score REAL NOT NULL,
    risk_score REAL NOT NULL,
    defensive_flow_score REAL NOT NULL,
    total_score REAL NOT NULL,
    state_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof)
);

CREATE TABLE IF NOT EXISTS market_state_history (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    state_label TEXT NOT NULL,
    state_score REAL NOT NULL,
    prev_state_label TEXT,
    state_change_direction TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof)
);

CREATE TABLE IF NOT EXISTS market_analysis_payload (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    payload_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, payload_type)
);

CREATE TABLE IF NOT EXISTS market_analysis_ai_notes (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    note_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, provider, model_name, input_hash)
);

CREATE TABLE IF NOT EXISTS market_context_history (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    headline_count INTEGER NOT NULL DEFAULT 0,
    risk_headline_count INTEGER NOT NULL DEFAULT 0,
    caution_bias INTEGER NOT NULL DEFAULT 0,
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof)
);

CREATE INDEX IF NOT EXISTS idx_market_context_history_asof
    ON market_context_history (market, asof);

CREATE TABLE IF NOT EXISTS market_ai_brief_history (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    provider TEXT NOT NULL,
    theme_label TEXT,
    model_name TEXT NOT NULL,
    source TEXT,
    input_hash TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    summary_lines_json TEXT NOT NULL,
    brief_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, provider)
);

CREATE INDEX IF NOT EXISTS idx_market_ai_brief_history_asof
    ON market_ai_brief_history (market, asof);

CREATE TABLE IF NOT EXISTS market_publish_history (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    run_id TEXT NOT NULL,
    publish_target TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    base_url TEXT,
    object_count INTEGER NOT NULL DEFAULT 0,
    latest_updated_at TEXT,
    publish_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, run_id, publish_target)
);

CREATE INDEX IF NOT EXISTS idx_market_publish_history_asof
    ON market_publish_history (market, asof);

CREATE TABLE IF NOT EXISTS market_asset_relative_strength_hourly (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    asset_group TEXT NOT NULL,
    ret_20d REAL,
    strength_score REAL,
    strength_rank INTEGER,
    strength_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, asset_group)
);

CREATE INDEX IF NOT EXISTS idx_market_asset_relative_strength_hourly_asof
    ON market_asset_relative_strength_hourly (market, asof);

CREATE TABLE IF NOT EXISTS market_state_transition_stats (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    current_state TEXT NOT NULL,
    prev_state TEXT,
    duration_hours REAL NOT NULL,
    transition_count_5d INTEGER NOT NULL DEFAULT 0,
    transition_count_20d INTEGER NOT NULL DEFAULT 0,
    stability_score REAL NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof)
);

CREATE INDEX IF NOT EXISTS idx_market_state_transition_stats_asof
    ON market_state_transition_stats (market, asof);
CREATE TABLE IF NOT EXISTS market_intraday_index_snapshot (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    session_date TEXT NOT NULL,
    index_code TEXT NOT NULL,
    index_name TEXT NOT NULL,
    price REAL NOT NULL,
    change_value REAL,
    change_pct REAL,
    open REAL,
    high REAL,
    low REAL,
    prev_close REAL,
    volume REAL,
    source TEXT NOT NULL,
    is_fallback INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, index_code)
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_index_snapshot_asof
    ON market_intraday_index_snapshot (market, asof);


CREATE TABLE IF NOT EXISTS market_intraday_fx_snapshot (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    session_date TEXT NOT NULL,
    series_code TEXT NOT NULL,
    series_name TEXT NOT NULL,
    price REAL NOT NULL,
    change_value REAL,
    change_pct REAL,
    open REAL,
    high REAL,
    low REAL,
    prev_close REAL,
    source TEXT NOT NULL,
    is_fallback INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, series_code)
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_fx_snapshot_asof
    ON market_intraday_fx_snapshot (market, asof);

CREATE TABLE IF NOT EXISTS market_intraday_futures_snapshot (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    session_date TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    contract_name TEXT NOT NULL,
    price REAL NOT NULL,
    change_value REAL,
    change_pct REAL,
    open REAL,
    high REAL,
    low REAL,
    prev_close REAL,
    volume REAL,
    value_million REAL,
    source TEXT NOT NULL,
    is_fallback INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, contract_code)
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_futures_snapshot_asof
    ON market_intraday_futures_snapshot (market, asof);

CREATE TABLE IF NOT EXISTS market_intraday_breadth (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    session_date TEXT NOT NULL,
    universe_code TEXT NOT NULL,
    advancers INTEGER NOT NULL DEFAULT 0,
    decliners INTEGER NOT NULL DEFAULT 0,
    flat_count INTEGER NOT NULL DEFAULT 0,
    adv_dec_ratio REAL NOT NULL DEFAULT 1.0,
    positive_ratio REAL NOT NULL DEFAULT 0.0,
    source TEXT NOT NULL,
    is_fallback INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, universe_code)
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_breadth_asof
    ON market_intraday_breadth (market, asof);

CREATE TABLE IF NOT EXISTS market_intraday_flow_signal (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    session_date TEXT NOT NULL,
    signal_code TEXT NOT NULL,
    signal_name TEXT NOT NULL,
    metric_value REAL,
    metric_unit TEXT NOT NULL,
    direction_label TEXT NOT NULL,
    strength_label TEXT NOT NULL,
    source TEXT NOT NULL,
    is_fallback INTEGER NOT NULL DEFAULT 0,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof, signal_code)
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_flow_signal_asof
    ON market_intraday_flow_signal (market, asof);

CREATE TABLE IF NOT EXISTS market_intraday_state (
    market TEXT NOT NULL,
    asof TEXT NOT NULL,
    session_date TEXT NOT NULL,
    session_status TEXT NOT NULL,
    direction_label TEXT NOT NULL,
    direction_score REAL NOT NULL,
    breadth_score REAL NOT NULL,
    risk_score REAL NOT NULL,
    total_score REAL NOT NULL,
    summary_line TEXT NOT NULL,
    reference_close_date TEXT,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (market, asof)
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_state_asof
    ON market_intraday_state (market, asof);

"""
