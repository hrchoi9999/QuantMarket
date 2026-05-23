from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .global_context_db import connect_global_context, init_global_context_db

KST = timezone(timedelta(hours=9))
SCHEMA_VERSION = "external_market_context_daily_v2"
FEATURE_VERSION = "yahoo_external_market_context_v2_global_risk_assets_20260514"

CYCLICAL_SECTORS = ["XLK", "XLY", "XLI", "XLF", "XLE", "XLB", "XLC", "XLRE"]
DEFENSIVE_SECTORS = ["XLV", "XLP", "XLU"]
SECTOR_ASSETS = CYCLICAL_SECTORS + DEFENSIVE_SECTORS


def _now_iso() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _clip(value: float | None, low: float = -3.0, high: float = 3.0) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(max(low, min(high, value)))


def _mean(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None and not pd.isna(value)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _score_return(*values: float | None, scale: float = 15.0) -> float | None:
    value = _mean(list(values))
    if value is None:
        return None
    return round(_clip(value * scale), 4)


def _read_asset_panel(con, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    where = ["source = 'YAHOO'"]
    params: list[str] = []
    if start_date:
        where.append("asof_date >= ?")
        params.append(start_date)
    if end_date:
        where.append("asof_date <= ?")
        params.append(end_date)
    return pd.read_sql_query(
        f"""
        SELECT asset_code, symbol, asof_date, adj_close, close, volume
        FROM global_asset_daily
        WHERE {' AND '.join(where)}
        ORDER BY asset_code, asof_date
        """,
        con,
        params=params,
    )


def _asset_features(panel: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for asset_code, g in panel.groupby("asset_code"):
        g = g.sort_values("asof_date").copy()
        price = pd.to_numeric(g["adj_close"], errors="coerce").fillna(pd.to_numeric(g["close"], errors="coerce"))
        g["price"] = price
        g["ret_1m"] = price.pct_change(20)
        g["ret_3m"] = price.pct_change(60)
        g["above_sma60"] = price > price.rolling(60, min_periods=20).mean()
        frames.append(g[["asof_date", "asset_code", "price", "ret_1m", "ret_3m", "above_sma60"]])
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _pivot(features: pd.DataFrame, column: str) -> pd.DataFrame:
    return features.pivot(index="asof_date", columns="asset_code", values=column)


def build_external_market_context_rows(con, *, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    panel = _read_asset_panel(con, start_date, end_date)
    if panel.empty:
        return []
    features = _asset_features(panel)
    ret_1m = _pivot(features, "ret_1m")
    ret_3m = _pivot(features, "ret_3m")
    above_sma60 = _pivot(features, "above_sma60")
    dates = sorted(set(features["asof_date"].astype(str)))
    generated_at = _now_iso()
    rows: list[dict] = []
    for asof_date in dates:
        r1 = ret_1m.loc[asof_date] if asof_date in ret_1m.index else pd.Series(dtype=float)
        r3 = ret_3m.loc[asof_date] if asof_date in ret_3m.index else pd.Series(dtype=float)
        sma = above_sma60.loc[asof_date] if asof_date in above_sma60.index else pd.Series(dtype=float)

        spy_ret_1m = r1.get("SPY")
        spy_ret_3m = r3.get("SPY")
        qqq_ret_1m = r1.get("QQQ")
        qqq_ret_3m = r3.get("QQQ")
        iwm_ret_1m = r1.get("IWM")
        ewy_ret_1m = r1.get("EWY")
        ewy_ret_3m = r3.get("EWY")
        hyg_ret_1m = r1.get("HYG")
        lqd_ret_1m = r1.get("LQD")
        tlt_ret_1m = r1.get("TLT")
        gld_ret_1m = r1.get("GLD")
        uso_ret_1m = r1.get("USO")
        uup_ret_1m = r1.get("UUP")
        vix_ret_1m = r1.get("VIX")
        soxx_ret_1m = r1.get("SOXX")
        soxx_ret_3m = r3.get("SOXX")
        acwx_ret_1m = r1.get("ACWX")
        efa_ret_1m = r1.get("EFA")
        eem_ret_1m = r1.get("EEM")
        fxi_ret_1m = r1.get("FXI")
        ewj_ret_1m = r1.get("EWJ")
        ewt_ret_1m = r1.get("EWT")
        inda_ret_1m = r1.get("INDA")
        kre_ret_1m = r1.get("KRE")
        xhb_ret_1m = r1.get("XHB")
        iyt_ret_1m = r1.get("IYT")
        usmv_ret_1m = r1.get("USMV")
        dxy_ret_1m = r1.get("DXY")
        btcusd_ret_1m = r1.get("BTCUSD")

        cyclical_ret = _mean([r1.get(asset) for asset in CYCLICAL_SECTORS])
        defensive_ret = _mean([r1.get(asset) for asset in DEFENSIVE_SECTORS])
        sector_cyclical_vs_defensive_1m = (
            float(cyclical_ret) - float(defensive_ret)
            if cyclical_ret is not None and defensive_ret is not None
            else None
        )
        sector_returns = [r1.get(asset) for asset in SECTOR_ASSETS]
        sector_positive_values = [float(value) > 0 for value in sector_returns if value is not None and not pd.isna(value)]
        sector_positive_ratio_1m = (
            sum(1 for value in sector_positive_values if value) / len(sector_positive_values)
            if sector_positive_values
            else None
        )
        sector_sma_values = [sma.get(asset) for asset in SECTOR_ASSETS if asset in sma.index and not pd.isna(sma.get(asset))]
        sector_above_sma60_ratio = (
            sum(1 for value in sector_sma_values if bool(value)) / len(sector_sma_values)
            if sector_sma_values
            else None
        )
        hyg_lqd_ret_spread_1m = (
            float(hyg_ret_1m) - float(lqd_ret_1m)
            if hyg_ret_1m is not None and not pd.isna(hyg_ret_1m) and lqd_ret_1m is not None and not pd.isna(lqd_ret_1m)
            else None
        )

        us_equity_momentum_score = _score_return(spy_ret_1m, spy_ret_3m, scale=10.0)
        us_growth_risk_score = _score_return(qqq_ret_1m, qqq_ret_3m, scale=10.0)
        us_smallcap_risk_score = _score_return(iwm_ret_1m, scale=15.0)
        us_sector_risk_on_score = _score_return(sector_cyclical_vs_defensive_1m, scale=20.0)
        us_defensive_sector_score = _score_return(defensive_ret, scale=15.0)
        global_breadth_proxy_score = None
        if sector_positive_ratio_1m is not None and sector_above_sma60_ratio is not None:
            global_breadth_proxy_score = round(_clip(((sector_positive_ratio_1m - 0.5) + (sector_above_sma60_ratio - 0.5)) * 3.0), 4)
        korea_proxy_momentum_score = _score_return(ewy_ret_1m, ewy_ret_3m, scale=10.0)
        credit_proxy_score = _score_return(hyg_lqd_ret_spread_1m, scale=25.0)
        safe_haven_pressure_score = _score_return(tlt_ret_1m, gld_ret_1m, uup_ret_1m, scale=12.0)
        commodity_risk_score = _score_return(uso_ret_1m, scale=12.0)
        dollar_risk_score = _score_return(uup_ret_1m, dxy_ret_1m, scale=18.0)
        vix_market_stress_score = _score_return(vix_ret_1m, scale=10.0)
        semiconductor_momentum_score = _score_return(soxx_ret_1m, soxx_ret_3m, scale=10.0)
        global_ex_us_momentum_score = _score_return(acwx_ret_1m, efa_ret_1m, eem_ret_1m, scale=12.0)
        em_vs_dm_score = (
            round(_clip((float(eem_ret_1m) - float(efa_ret_1m)) * 20.0), 4)
            if eem_ret_1m is not None and not pd.isna(eem_ret_1m) and efa_ret_1m is not None and not pd.isna(efa_ret_1m)
            else None
        )
        asia_risk_on_score = _score_return(fxi_ret_1m, ewj_ret_1m, ewt_ret_1m, inda_ret_1m, ewy_ret_1m, scale=12.0)
        bank_stress_relief_score = _score_return(kre_ret_1m, scale=15.0)
        rate_sensitive_cyclical_score = _score_return(xhb_ret_1m, scale=15.0)
        transport_cyclical_score = _score_return(iyt_ret_1m, scale=15.0)
        low_vol_defensive_pressure_score = (
            round(_clip((float(usmv_ret_1m) - float(spy_ret_1m)) * 20.0), 4)
            if usmv_ret_1m is not None and not pd.isna(usmv_ret_1m) and spy_ret_1m is not None and not pd.isna(spy_ret_1m)
            else None
        )
        crypto_risk_appetite_score = _score_return(btcusd_ret_1m, scale=5.0)
        external_asset_risk_on_score = _mean(
            [
                us_equity_momentum_score,
                us_growth_risk_score,
                us_smallcap_risk_score,
                us_sector_risk_on_score,
                global_breadth_proxy_score,
                korea_proxy_momentum_score,
                semiconductor_momentum_score,
                global_ex_us_momentum_score,
                em_vs_dm_score,
                asia_risk_on_score,
                bank_stress_relief_score,
                rate_sensitive_cyclical_score,
                transport_cyclical_score,
                crypto_risk_appetite_score,
                credit_proxy_score,
                -safe_haven_pressure_score if safe_haven_pressure_score is not None else None,
                -dollar_risk_score if dollar_risk_score is not None else None,
                -vix_market_stress_score if vix_market_stress_score is not None else None,
                -low_vol_defensive_pressure_score if low_vol_defensive_pressure_score is not None else None,
            ]
        )

        rows.append(
            {
                "asof_date": asof_date,
                "us_equity_momentum_score": us_equity_momentum_score,
                "us_growth_risk_score": us_growth_risk_score,
                "us_smallcap_risk_score": us_smallcap_risk_score,
                "us_sector_risk_on_score": us_sector_risk_on_score,
                "us_defensive_sector_score": us_defensive_sector_score,
                "global_breadth_proxy_score": global_breadth_proxy_score,
                "korea_proxy_momentum_score": korea_proxy_momentum_score,
                "credit_proxy_score": credit_proxy_score,
                "safe_haven_pressure_score": safe_haven_pressure_score,
                "commodity_risk_score": commodity_risk_score,
                "dollar_risk_score": dollar_risk_score,
                "vix_market_stress_score": vix_market_stress_score,
                "semiconductor_momentum_score": semiconductor_momentum_score,
                "global_ex_us_momentum_score": global_ex_us_momentum_score,
                "em_vs_dm_score": em_vs_dm_score,
                "asia_risk_on_score": asia_risk_on_score,
                "bank_stress_relief_score": bank_stress_relief_score,
                "rate_sensitive_cyclical_score": rate_sensitive_cyclical_score,
                "transport_cyclical_score": transport_cyclical_score,
                "low_vol_defensive_pressure_score": low_vol_defensive_pressure_score,
                "crypto_risk_appetite_score": crypto_risk_appetite_score,
                "external_asset_risk_on_score": round(_clip(external_asset_risk_on_score), 4) if external_asset_risk_on_score is not None else None,
                "spy_ret_1m": spy_ret_1m,
                "spy_ret_3m": spy_ret_3m,
                "qqq_ret_1m": qqq_ret_1m,
                "qqq_ret_3m": qqq_ret_3m,
                "iwm_ret_1m": iwm_ret_1m,
                "ewy_ret_1m": ewy_ret_1m,
                "ewy_ret_3m": ewy_ret_3m,
                "sector_cyclical_vs_defensive_1m": sector_cyclical_vs_defensive_1m,
                "sector_positive_ratio_1m": sector_positive_ratio_1m,
                "sector_above_sma60_ratio": sector_above_sma60_ratio,
                "hyg_lqd_ret_spread_1m": hyg_lqd_ret_spread_1m,
                "tlt_ret_1m": tlt_ret_1m,
                "gld_ret_1m": gld_ret_1m,
                "uso_ret_1m": uso_ret_1m,
                "uup_ret_1m": uup_ret_1m,
                "vix_ret_1m": vix_ret_1m,
                "soxx_ret_1m": soxx_ret_1m,
                "soxx_ret_3m": soxx_ret_3m,
                "acwx_ret_1m": acwx_ret_1m,
                "efa_ret_1m": efa_ret_1m,
                "eem_ret_1m": eem_ret_1m,
                "fxi_ret_1m": fxi_ret_1m,
                "ewj_ret_1m": ewj_ret_1m,
                "ewt_ret_1m": ewt_ret_1m,
                "inda_ret_1m": inda_ret_1m,
                "kre_ret_1m": kre_ret_1m,
                "xhb_ret_1m": xhb_ret_1m,
                "iyt_ret_1m": iyt_ret_1m,
                "usmv_ret_1m": usmv_ret_1m,
                "dxy_ret_1m": dxy_ret_1m,
                "btcusd_ret_1m": btcusd_ret_1m,
                "feature_version": FEATURE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
            }
        )
    return rows


def upsert_external_market_context_rows(con, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join(f":{column}" for column in columns)
    updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "asof_date")
    con.executemany(
        f"""
        INSERT INTO external_market_context_daily ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(asof_date) DO UPDATE SET
            {updates}
        """,
        rows,
    )
    con.commit()


def write_current_outputs(*, rows: list[dict], output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "external_market_context_daily_current.csv"
    manifest_path = output_dir / "external_market_context_manifest.json"
    schema_path = output_dir / "external_market_context_schema.json"
    if rows:
        columns = list(rows[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")
    manifest = {
        "source_name": "QuantMarket external market context",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": _now_iso(),
        "row_count": len(rows),
        "start_date": rows[0]["asof_date"] if rows else None,
        "end_date": rows[-1]["asof_date"] if rows else None,
        "files": {
            "external_market_context_daily_current": csv_path.name,
            "manifest": manifest_path.name,
            "schema": schema_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    schema = {
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "primary_key": ["asof_date"],
        "join_keys": ["asof_date"],
        "score_direction": {
            "external_asset_risk_on_score": "higher means stronger external market risk-on condition",
            "korea_proxy_momentum_score": "higher means stronger US-listed Korea ETF momentum",
            "safe_haven_pressure_score": "higher means stronger defensive/safe-haven pressure",
            "dollar_risk_score": "higher means stronger dollar pressure",
            "commodity_risk_score": "higher means stronger oil/commodity pressure",
            "vix_market_stress_score": "higher means stronger volatility stress",
            "semiconductor_momentum_score": "higher means stronger semiconductor-led risk appetite",
            "global_ex_us_momentum_score": "higher means stronger global ex-US equity momentum",
            "em_vs_dm_score": "higher means emerging markets outperform developed ex-US markets",
            "asia_risk_on_score": "higher means stronger Asia equity risk appetite",
            "bank_stress_relief_score": "higher means regional bank stress is easing",
            "rate_sensitive_cyclical_score": "higher means rate-sensitive cyclicals are stronger",
            "transport_cyclical_score": "higher means cyclical demand proxy is stronger",
            "low_vol_defensive_pressure_score": "higher means low-vol defensive equity is outperforming",
            "crypto_risk_appetite_score": "higher means speculative risk appetite is stronger",
        },
        "null_policy": "insufficient lookback or unavailable asset observations remain null",
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_and_store_external_market_context(
    *,
    db_path: Path,
    output_dir: Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    init_global_context_db(db_path)
    with connect_global_context(db_path) as con:
        rows = build_external_market_context_rows(con, start_date=start_date, end_date=end_date)
        upsert_external_market_context_rows(con, rows)
    manifest = write_current_outputs(rows=rows, output_dir=output_dir)
    manifest["db_path"] = str(db_path)
    return manifest
