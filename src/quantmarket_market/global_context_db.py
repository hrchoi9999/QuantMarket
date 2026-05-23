from __future__ import annotations

import sqlite3
from pathlib import Path

from .global_context_schema import GLOBAL_CONTEXT_SCHEMA_SQL


DEFAULT_GLOBAL_CONTEXT_DB_PATH = Path("D:/QuantMarket/data/db/global_market_context.db")


def connect_global_context(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_GLOBAL_CONTEXT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    return con


def init_global_context_db(db_path: Path | None = None) -> None:
    with connect_global_context(db_path) as con:
        con.executescript(GLOBAL_CONTEXT_SCHEMA_SQL)
        _ensure_column(con, "global_context_daily", "monthly_macro_release_lag_days", "INTEGER")
        for column in [
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
        ]:
            _ensure_column(con, "external_market_context_daily", column, "REAL")
        con.commit()


def _ensure_column(con: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
