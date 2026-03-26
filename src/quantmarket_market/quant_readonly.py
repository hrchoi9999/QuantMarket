from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .config import QUANT_PRICE_DB_PATH, QUANT_REGIME_DB_PATH, QUANT_UNIVERSE_DIR

PREFERRED_ETFS = {
    "bond": ["114260", "114820", "114100", "114470", "114460", "459580"],
    "gold": ["411060", "132030", "319640", "139320"],
    "inverse": ["114800", "123310", "145670", "252670"],
}


def _ro_connect(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def _load_universe_tickers(asof_date: str) -> list[str]:
    candidates = [
        QUANT_UNIVERSE_DIR / "universe_mix_top400_latest_priceready.csv",
        QUANT_UNIVERSE_DIR / f"universe_mix_top400_{asof_date.replace('-', '')}_priceready.csv",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        return [row["ticker"].strip() for row in reader if row.get("ticker")]


def _chunked(values: list[str], size: int = 300):
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


def _load_price_history(con: sqlite3.Connection, tickers: list[str], start_date: str, end_date: str) -> dict[str, list[tuple[str, float]]]:
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    if not tickers:
        return result
    for chunk in _chunked(tickers):
        placeholders = ",".join("?" for _ in chunk)
        sql = f"""
        SELECT ticker, date, close
        FROM prices_daily
        WHERE ticker IN ({placeholders})
          AND date BETWEEN ? AND ?
        ORDER BY ticker, date
        """
        params = [*chunk, start_date, end_date]
        for row in con.execute(sql, params):
            if row["close"] is None:
                continue
            result[row["ticker"]].append((row["date"], float(row["close"])))
    return result


def _ret(series: list[float], lag: int) -> float:
    if len(series) <= lag or series[-(lag + 1)] == 0:
        return 0.0
    return float(series[-1] / series[-(lag + 1)] - 1.0)


def _compute_breadth_metrics(price_history: dict[str, list[tuple[str, float]]]) -> dict[str, float]:
    eligible = 0
    above20 = 0
    above60 = 0
    adv = 0
    dec = 0
    new_high = 0
    new_low = 0

    for series in price_history.values():
        closes = [close for _, close in series]
        if len(closes) < 60:
            continue
        eligible += 1
        latest = closes[-1]
        prev = closes[-2]
        ma20 = sum(closes[-20:]) / 20.0
        ma60 = sum(closes[-60:]) / 60.0
        lookback = closes[-252:] if len(closes) >= 252 else closes
        if latest >= ma20:
            above20 += 1
        if latest >= ma60:
            above60 += 1
        if latest >= prev:
            adv += 1
        else:
            dec += 1
        if latest >= max(lookback):
            new_high += 1
        if latest <= min(lookback):
            new_low += 1

    if eligible == 0:
        return {
            "above_20dma_ratio": 0.5,
            "above_60dma_ratio": 0.5,
            "adv_dec_ratio": 1.0,
            "new_high_count": 0.0,
            "new_low_count": 0.0,
            "breadth_universe_count": 0,
            "breadth_proxy_flag": 1,
        }
    return {
        "above_20dma_ratio": above20 / eligible,
        "above_60dma_ratio": above60 / eligible,
        "adv_dec_ratio": (adv + 1) / (dec + 1),
        "new_high_count": float(new_high),
        "new_low_count": float(new_low),
        "breadth_universe_count": eligible,
        "breadth_proxy_flag": 0,
    }


def _latest_etf_asof(con: sqlite3.Connection) -> str | None:
    row = con.execute("SELECT MAX(asof) FROM etf_meta").fetchone()
    return row[0] if row and row[0] else None


def _select_representative_etf(con: sqlite3.Connection, group: str) -> dict | None:
    asof = _latest_etf_asof(con)
    if asof is None:
        return None
    preferred = PREFERRED_ETFS[group]
    placeholders = ",".join("?" for _ in preferred)
    sql = f"""
    SELECT e.ticker, i.name, e.group_key, e.liquidity_20d_value
    FROM etf_meta e
    LEFT JOIN instrument_master i ON i.ticker = e.ticker
    WHERE e.asof = ? AND e.ticker IN ({placeholders})
    ORDER BY CASE e.ticker
        {" ".join(f"WHEN '{ticker}' THEN {idx}" for idx, ticker in enumerate(preferred, start=1))}
        ELSE 999 END,
        e.liquidity_20d_value DESC
    LIMIT 1
    """
    row = con.execute(sql, [asof, *preferred]).fetchone()
    return dict(row) if row else None


def _load_single_series_return(con: sqlite3.Connection, ticker: str, asof_date: str, lag: int = 20) -> float:
    start = (datetime.strptime(asof_date, "%Y-%m-%d").date() - timedelta(days=120)).isoformat()
    rows = con.execute(
        """
        SELECT date, close
        FROM prices_daily
        WHERE ticker = ? AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        (ticker, start, asof_date),
    ).fetchall()
    closes = [float(row["close"]) for row in rows if row["close"] is not None]
    return _ret(closes, lag)


def _load_regime_reference(asof_date: str, universe_tickers: list[str]) -> float | None:
    if not QUANT_REGIME_DB_PATH.exists() or not universe_tickers:
        return None
    with _ro_connect(QUANT_REGIME_DB_PATH) as con:
        scores: list[float] = []
        for chunk in _chunked(universe_tickers):
            placeholders = ",".join("?" for _ in chunk)
            sql = f"""
            SELECT score
            FROM regime_history
            WHERE horizon='3m'
              AND date <= ?
              AND ticker IN ({placeholders})
              AND date = (
                  SELECT MAX(date) FROM regime_history WHERE horizon='3m' AND date <= ?
              )
            """
            params = [asof_date, *chunk, asof_date]
            scores.extend(float(row["score"]) for row in con.execute(sql, params) if row["score"] is not None)
        if not scores:
            return None
        return sum(scores) / len(scores)


def load_quant_reference_inputs(asof_date: str) -> dict:
    if not QUANT_PRICE_DB_PATH.exists():
        return {}

    start_date = (datetime.strptime(asof_date, "%Y-%m-%d").date() - timedelta(days=380)).isoformat()
    with _ro_connect(QUANT_PRICE_DB_PATH) as con:
        universe_tickers = _load_universe_tickers(asof_date)
        if not universe_tickers:
            universe_tickers = [
                row[0]
                for row in con.execute(
                    "SELECT ticker FROM instrument_master WHERE asset_type='STOCK' AND is_active=1 ORDER BY ticker"
                )
            ]
        breadth_history = _load_price_history(con, universe_tickers, start_date, asof_date)
        breadth = _compute_breadth_metrics(breadth_history)

        selected = {
            "bond": _select_representative_etf(con, "bond"),
            "gold": _select_representative_etf(con, "gold"),
            "inverse": _select_representative_etf(con, "inverse"),
        }
        defensive = {
            "bond_20d_ret": _load_single_series_return(con, selected["bond"]["ticker"], asof_date) if selected["bond"] else 0.0,
            "gold_20d_ret": _load_single_series_return(con, selected["gold"]["ticker"], asof_date) if selected["gold"] else 0.0,
            "inverse_20d_ret": _load_single_series_return(con, selected["inverse"]["ticker"], asof_date) if selected["inverse"] else 0.0,
            "defensive_proxy_flag": 0 if all(selected.values()) else 1,
        }

    return {
        **breadth,
        **defensive,
        "representative_assets": selected,
        "regime_3m_score": _load_regime_reference(asof_date, universe_tickers),
    }
