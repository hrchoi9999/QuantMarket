from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path(r"D:\QuantMarket\data\db\market_analysis.db")
SNAP = Path(r"D:\QuantMarket\service_platform\web\public_data\current")

con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
latest = con.execute("SELECT market, asof, state_label, state_score, prev_state_label, state_change_direction FROM market_state_history ORDER BY asof DESC LIMIT 1").fetchone()
counts = {
    table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    for table in [
        "market_index_daily",
        "market_fx_daily",
        "market_rates_daily",
        "market_features_hourly",
        "market_component_scores",
        "market_state_history",
        "market_analysis_payload",
    ]
}
print(json.dumps({
    "latest_state": dict(latest) if latest else None,
    "table_counts": counts,
    "snapshot_files": sorted(p.name for p in SNAP.glob('market_analysis_*.json')),
}, ensure_ascii=False, indent=2))
