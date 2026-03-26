from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping

from .schema import SCHEMA_SQL

FEATURE_MIGRATIONS = {
    "kospi_60d_ret": "ALTER TABLE market_features_hourly ADD COLUMN kospi_60d_ret REAL",
    "kosdaq_60d_ret": "ALTER TABLE market_features_hourly ADD COLUMN kosdaq_60d_ret REAL",
    "breadth_universe_count": "ALTER TABLE market_features_hourly ADD COLUMN breadth_universe_count INTEGER",
    "regime_3m_score": "ALTER TABLE market_features_hourly ADD COLUMN regime_3m_score REAL",
}


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as con:
        con.executescript(SCHEMA_SQL)
        cols = _table_columns(con, "market_features_hourly")
        for column, sql in FEATURE_MIGRATIONS.items():
            if column not in cols:
                con.execute(sql)
        con.commit()


def upsert_many(
    con: sqlite3.Connection,
    table: str,
    columns: list[str],
    rows: Iterable[Mapping[str, object]],
    conflict_columns: list[str],
) -> None:
    rows = list(rows)
    if not rows:
        return
    placeholders = ", ".join(f":{col}" for col in columns)
    updates = ", ".join(f"{col}=excluded.{col}" for col in columns if col not in conflict_columns)
    sql = f"""
    INSERT INTO {table} ({", ".join(columns)})
    VALUES ({placeholders})
    ON CONFLICT ({", ".join(conflict_columns)}) DO UPDATE SET
        {updates}
    """
    con.executemany(sql, rows)
    con.commit()


def upsert_payload(
    con: sqlite3.Connection,
    *,
    market: str,
    asof: str,
    payload_type: str,
    payload: dict,
    created_at: str,
) -> None:
    upsert_many(
        con,
        table="market_analysis_payload",
        columns=["market", "asof", "payload_type", "payload_json", "created_at"],
        rows=[
            {
                "market": market,
                "asof": asof,
                "payload_type": payload_type,
                "payload_json": json.dumps(payload, ensure_ascii=False, indent=2),
                "created_at": created_at,
            }
        ],
        conflict_columns=["market", "asof", "payload_type"],
    )
