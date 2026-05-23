from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KST = timezone(timedelta(hours=9))
SCHEMA_VERSION = "domestic_flow_derivatives_daily.v1"
FEATURE_VERSION = "qm_domestic_flow_derivatives_v2_kiwoom_qm_20260519"
MARKET_SCOPES = ["ALL", "KOSPI", "KOSDAQ"]
INVESTORS = ["외국인", "기관합계", "개인"]
KRW_PER_EOK = 100_000_000.0


@dataclass(frozen=True)
class DomesticFlowDerivativesResult:
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


def _ro_connect(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def _clip(value: float | None, low: float = -3.0, high: float = 3.0) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(max(low, min(high, value)))


def _mean(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None and not pd.isna(value)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _read_date_spine(market_context_db: Path, start: str, end: str) -> list[str]:
    if not market_context_db.exists():
        return []
    with _ro_connect(market_context_db) as con:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_context_daily'"
        ).fetchone()
        if not exists:
            return []
        rows = con.execute(
            """
            SELECT DISTINCT asof_date
            FROM market_context_daily
            WHERE asof_date BETWEEN ? AND ?
            ORDER BY asof_date
            """,
            (start, end),
        ).fetchall()
    return [str(row["asof_date"]) for row in rows]


def _read_market_map(classification_db: Path) -> pd.DataFrame:
    if not classification_db.exists():
        return pd.DataFrame(columns=["ticker", "market"])
    with _ro_connect(classification_db) as con:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='security_classification_master'"
        ).fetchone()
        if not exists:
            return pd.DataFrame(columns=["ticker", "market"])
        df = pd.read_sql_query(
            """
            SELECT ticker, market, asof_date
            FROM security_classification_master
            WHERE is_active = 1
              AND asset_type = 'STOCK'
              AND market IN ('KOSPI', 'KOSDAQ')
            ORDER BY ticker, asof_date
            """,
            con,
        )
    if df.empty:
        return pd.DataFrame(columns=["ticker", "market"])
    return df.sort_values(["ticker", "asof_date"]).drop_duplicates("ticker", keep="last")[["ticker", "market"]]


def _read_investor_flows(ai_feature_ext_db: Path, start: str, end: str, market_map: pd.DataFrame) -> pd.DataFrame:
    if not ai_feature_ext_db.exists() or market_map.empty:
        return pd.DataFrame()
    with _ro_connect(ai_feature_ext_db) as con:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='investor_flows_daily'"
        ).fetchone()
        if not exists:
            return pd.DataFrame()
        flows = pd.read_sql_query(
            """
            SELECT date AS asof_date, ticker, investor, net_value, net_volume, source
            FROM investor_flows_daily
            WHERE date BETWEEN ? AND ?
              AND investor IN ('외국인', '기관합계', '개인')
            """,
            con,
            params=(start, end),
        )
    if flows.empty:
        return flows
    flows["ticker"] = flows["ticker"].astype(str).str.zfill(6)
    flows = flows.merge(market_map, on="ticker", how="inner")
    flows["net_value"] = pd.to_numeric(flows["net_value"], errors="coerce")
    flows["net_volume"] = pd.to_numeric(flows["net_volume"], errors="coerce")
    return flows


def _read_qm_kiwoom_investor_flows(qm_db: Path, start: str, end: str) -> pd.DataFrame:
    if not qm_db.exists():
        return pd.DataFrame()
    with _ro_connect(qm_db) as con:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kiwoom_stock_investor_flow_daily'"
        ).fetchone()
        if not exists:
            return pd.DataFrame()
        flows = pd.read_sql_query(
            """
            SELECT date AS asof_date, ticker, investor, net_value, net_volume,
                   market_scope AS market, source
            FROM kiwoom_stock_investor_flow_daily
            WHERE date BETWEEN ? AND ?
              AND investor IN ('외국인', '기관합계', '개인')
              AND market_scope IN ('KOSPI', 'KOSDAQ')
            """,
            con,
            params=(start, end),
        )
    if flows.empty:
        return flows
    flows["ticker"] = flows["ticker"].astype(str).str.zfill(6)
    flows["net_value"] = pd.to_numeric(flows["net_value"], errors="coerce")
    flows["net_volume"] = pd.to_numeric(flows["net_volume"], errors="coerce")
    return flows


def _combine_investor_flows(
    quant_flows: pd.DataFrame,
    qm_kiwoom_flows: pd.DataFrame,
) -> pd.DataFrame:
    if quant_flows.empty:
        return qm_kiwoom_flows
    if qm_kiwoom_flows.empty:
        return quant_flows
    quant_flows = quant_flows.copy()
    quant_flows["_source_priority"] = 0
    qm_kiwoom_flows = qm_kiwoom_flows.copy()
    qm_kiwoom_flows["_source_priority"] = 1
    combined = pd.concat([quant_flows, qm_kiwoom_flows], ignore_index=True, sort=False)
    combined = (
        combined.sort_values(["asof_date", "ticker", "investor", "_source_priority"])
        .drop_duplicates(["asof_date", "ticker", "investor"], keep="last")
        .drop(columns=["_source_priority"])
    )
    return combined


def _scope_frames(flows: pd.DataFrame) -> pd.DataFrame:
    if flows.empty:
        return pd.DataFrame()
    frames = [flows.copy()]
    frames[0]["market_scope"] = frames[0]["market"]
    all_frame = flows.copy()
    all_frame["market_scope"] = "ALL"
    frames.append(all_frame)
    return pd.concat(frames, ignore_index=True, sort=False)


def _build_investor_daily_features(flows: pd.DataFrame) -> pd.DataFrame:
    scoped = _scope_frames(flows)
    if scoped.empty:
        return pd.DataFrame()

    source_map = (
        scoped.groupby(["asof_date", "market_scope"])["source"]
        .apply(lambda s: ",".join(sorted(set(str(v) for v in s.dropna())))[:200])
        .to_dict()
    )
    grouped = (
        scoped.groupby(["asof_date", "market_scope", "investor"], as_index=False)
        .agg(
            net_value=("net_value", "sum"),
            net_volume=("net_volume", "sum"),
            stock_count=("ticker", "nunique"),
            positive_count=("net_value", lambda s: int((pd.to_numeric(s, errors="coerce") > 0).sum())),
            source=("source", lambda s: ",".join(sorted(set(str(v) for v in s.dropna())))[:200]),
        )
    )
    pivot_value = grouped.pivot(index=["asof_date", "market_scope"], columns="investor", values="net_value")
    pivot_volume = grouped.pivot(index=["asof_date", "market_scope"], columns="investor", values="net_volume")
    pivot_count = grouped.pivot(index=["asof_date", "market_scope"], columns="investor", values="stock_count")
    pivot_pos = grouped.pivot(index=["asof_date", "market_scope"], columns="investor", values="positive_count")

    rows: list[dict] = []
    for key in sorted(set(pivot_value.index)):
        asof_date, scope = key
        values = {investor: pivot_value.loc[key].get(investor) if key in pivot_value.index else None for investor in INVESTORS}
        volumes = {investor: pivot_volume.loc[key].get(investor) if key in pivot_volume.index else None for investor in INVESTORS}
        denom = sum(abs(float(v)) for v in values.values() if v is not None and not pd.isna(v))
        foreign = values.get("외국인")
        inst = values.get("기관합계")
        retail = values.get("개인")

        def ratio(value: float | None) -> float | None:
            return float(value) / denom if denom and value is not None and not pd.isna(value) else None

        def breadth(investor: str) -> float | None:
            count = pivot_count.loc[key].get(investor) if key in pivot_count.index else None
            pos = pivot_pos.loc[key].get(investor) if key in pivot_pos.index else None
            if count is None or pd.isna(count) or float(count) <= 0:
                return None
            return float(pos) / float(count)

        smart_money = None
        if denom and foreign is not None and not pd.isna(foreign) and inst is not None and not pd.isna(inst):
            smart_money = (float(foreign) + float(inst) - (float(retail) if retail is not None and not pd.isna(retail) else 0.0)) / denom

        rows.append(
            {
                "asof_date": asof_date,
                "market_scope": scope,
                "foreign_net_buy_value_krw": foreign,
                "institution_net_buy_value_krw": inst,
                "retail_net_buy_value_krw": retail,
                "foreign_net_buy_volume": volumes.get("외국인"),
                "institution_net_buy_volume": volumes.get("기관합계"),
                "retail_net_buy_volume": volumes.get("개인"),
                "total_abs_net_value_krw": denom if denom else None,
                "foreign_net_buy_ratio": ratio(foreign),
                "institution_net_buy_ratio": ratio(inst),
                "retail_net_buy_ratio": ratio(retail),
                "foreign_buying_breadth": breadth("외국인"),
                "institution_buying_breadth": breadth("기관합계"),
                "retail_buying_breadth": breadth("개인"),
                "flow_concentration_score": max([abs(r) for r in [ratio(foreign), ratio(inst), ratio(retail)] if r is not None], default=None),
                "smart_money_score": smart_money,
                "investor_flow_available": 1 if denom else 0,
                "investor_flow_source": source_map.get(key),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values(["market_scope", "asof_date"]).reset_index(drop=True)
    for scope, idx in out.groupby("market_scope").groups.items():
        g = out.loc[idx].sort_values("asof_date")
        denom_5 = g["total_abs_net_value_krw"].rolling(5, min_periods=1).sum()
        denom_20 = g["total_abs_net_value_krw"].rolling(20, min_periods=1).sum()
        for investor, prefix in [("foreign", "foreign"), ("institution", "institution"), ("retail", "retail")]:
            col = f"{prefix}_net_buy_value_krw"
            out.loc[g.index, f"{prefix}_net_buy_value_5d_krw"] = g[col].rolling(5, min_periods=1).sum()
            out.loc[g.index, f"{prefix}_net_buy_value_20d_krw"] = g[col].rolling(20, min_periods=1).sum()
            out.loc[g.index, f"{prefix}_net_buy_ratio_5d"] = out.loc[g.index, f"{prefix}_net_buy_value_5d_krw"] / denom_5
            out.loc[g.index, f"{prefix}_net_buy_ratio_20d"] = out.loc[g.index, f"{prefix}_net_buy_value_20d_krw"] / denom_20
        out.loc[g.index, "foreign_net_buy_days_5d"] = (g["foreign_net_buy_value_krw"] > 0).rolling(5, min_periods=1).sum()
        out.loc[g.index, "institution_net_buy_days_5d"] = (g["institution_net_buy_value_krw"] > 0).rolling(5, min_periods=1).sum()
        out.loc[g.index, "smart_money_score_5d"] = g["smart_money_score"].rolling(5, min_periods=1).mean()
        out.loc[g.index, "smart_money_score_20d"] = g["smart_money_score"].rolling(20, min_periods=1).mean()
    return out


def _read_intraday_derivatives(qm_db: Path, start: str, end: str) -> pd.DataFrame:
    if not qm_db.exists():
        return pd.DataFrame()
    with _ro_connect(qm_db) as con:
        futures_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_intraday_futures_snapshot'"
        ).fetchone()
        flow_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_intraday_flow_signal'"
        ).fetchone()
        futures = pd.DataFrame()
        flow = pd.DataFrame()
        if futures_exists:
            futures = pd.read_sql_query(
                """
                SELECT session_date AS asof_date, asof, price AS futures_price,
                       change_pct AS futures_change_pct, volume AS futures_volume,
                       value_million AS futures_value_million, source AS futures_source
                FROM market_intraday_futures_snapshot
                WHERE market = 'KR'
                  AND session_date BETWEEN ? AND ?
                  AND is_fallback = 0
                ORDER BY session_date, asof
                """,
                con,
                params=(start, end),
            )
        if flow_exists:
            flow = pd.read_sql_query(
                """
                SELECT session_date AS asof_date, asof, signal_code, metric_value
                FROM market_intraday_flow_signal
                WHERE market = 'KR'
                  AND session_date BETWEEN ? AND ?
                  AND signal_code IN ('PROGRAM_TOTAL_NET', 'PROGRAM_NONARB_NET', 'FOREIGNER_NET', 'INSTITUTION_NET', 'INDIVIDUAL_NET')
                  AND is_fallback = 0
                ORDER BY session_date, asof
                """,
                con,
                params=(start, end),
            )
    latest_futures = pd.DataFrame()
    if not futures.empty:
        latest_futures = futures.sort_values(["asof_date", "asof"]).groupby("asof_date", as_index=False).tail(1)
        latest_futures = latest_futures.drop(columns=["asof"])
    latest_flow = pd.DataFrame()
    if not flow.empty:
        latest = flow.sort_values(["asof_date", "asof"]).groupby(["asof_date", "signal_code"], as_index=False).tail(1)
        latest_flow = latest.pivot(index="asof_date", columns="signal_code", values="metric_value").reset_index()
        latest_flow = latest_flow.rename(
            columns={
                "PROGRAM_TOTAL_NET": "program_total_net_eok",
                "PROGRAM_NONARB_NET": "program_nonarb_net_eok",
                "FOREIGNER_NET": "intraday_foreign_net_eok",
                "INSTITUTION_NET": "intraday_institution_net_eok",
                "INDIVIDUAL_NET": "intraday_retail_net_eok",
            }
        )
    if latest_futures.empty and latest_flow.empty:
        return pd.DataFrame()
    if latest_futures.empty:
        out = latest_flow
    elif latest_flow.empty:
        out = latest_futures
    else:
        out = latest_futures.merge(latest_flow, on="asof_date", how="outer")
    for col in [
        "futures_change_pct",
        "futures_volume",
        "futures_value_million",
        "program_total_net_eok",
        "program_nonarb_net_eok",
        "intraday_foreign_net_eok",
        "intraday_institution_net_eok",
        "intraday_retail_net_eok",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["program_total_net_krw"] = out.get("program_total_net_eok") * KRW_PER_EOK if "program_total_net_eok" in out else None
    out["program_nonarb_net_krw"] = out.get("program_nonarb_net_eok") * KRW_PER_EOK if "program_nonarb_net_eok" in out else None
    out["futures_direction_score"] = out.get("futures_change_pct").map(lambda v: _clip(float(v) * 50.0) if v is not None and not pd.isna(v) else None)
    out["program_pressure_score"] = out.get("program_total_net_krw").map(lambda v: _clip(float(v) / 1_000_000_000_000.0) if v is not None and not pd.isna(v) else None)
    out["derivatives_pressure_score"] = [
        _clip(_mean([fut, program]))
        for fut, program in zip(out["futures_direction_score"], out["program_pressure_score"], strict=False)
    ]
    out["derivatives_context_available"] = 1
    return out


def _empty_base(date_spine: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"asof_date": date, "market_scope": scope} for date in date_spine for scope in MARKET_SCOPES]
    )


def build_domestic_flow_derivatives_daily(
    *,
    market_context_db: Path,
    ai_feature_ext_db: Path,
    source_qm_db: Path,
    source_classification_db: Path,
    output_dir: Path,
    report_dir: Path,
    start: str = "2017-01-01",
    end: str | None = None,
) -> DomesticFlowDerivativesResult:
    generated_at = _now_kst()
    if end is None:
        with _ro_connect(market_context_db) as con:
            row = con.execute("SELECT MAX(asof_date) AS max_date FROM market_context_daily").fetchone()
            end = row["max_date"]
    if end is None:
        raise RuntimeError("Unable to determine end date for domestic_flow_derivatives_daily.")

    date_spine = _read_date_spine(market_context_db, start, end)
    market_map = _read_market_map(source_classification_db)
    investor_flows = _combine_investor_flows(
        _read_investor_flows(ai_feature_ext_db, start, end, market_map),
        _read_qm_kiwoom_investor_flows(source_qm_db, start, end),
    )
    investor = _build_investor_daily_features(investor_flows)
    intraday = _read_intraday_derivatives(source_qm_db, start, end)

    out = _empty_base(date_spine)
    if not investor.empty:
        out = out.merge(investor, on=["asof_date", "market_scope"], how="left")
    if not intraday.empty:
        out = out.merge(intraday, on="asof_date", how="left")

    for col in ["investor_flow_available", "derivatives_context_available"]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    # Recent intraday aggregate can fill ALL-scope ratios while official daily investor mart lags.
    all_mask = (out["market_scope"] == "ALL") & (out["investor_flow_available"] == 0)
    intraday_cols = ["intraday_foreign_net_eok", "intraday_institution_net_eok", "intraday_retail_net_eok"]
    if all(col in out.columns for col in intraday_cols):
        for idx, row in out.loc[all_mask].iterrows():
            values = [row.get(col) for col in intraday_cols]
            denom = sum(abs(float(v)) for v in values if v is not None and not pd.isna(v))
            if not denom:
                continue
            foreign = row.get("intraday_foreign_net_eok")
            inst = row.get("intraday_institution_net_eok")
            retail = row.get("intraday_retail_net_eok")
            out.loc[idx, "foreign_net_buy_ratio"] = float(foreign) / denom if foreign is not None and not pd.isna(foreign) else None
            out.loc[idx, "institution_net_buy_ratio"] = float(inst) / denom if inst is not None and not pd.isna(inst) else None
            out.loc[idx, "retail_net_buy_ratio"] = float(retail) / denom if retail is not None and not pd.isna(retail) else None
            out.loc[idx, "smart_money_score"] = (
                (float(foreign or 0.0) + float(inst or 0.0) - float(retail or 0.0)) / denom
            )
            out.loc[idx, "flow_concentration_score"] = max(
                abs(float(v) / denom) for v in values if v is not None and not pd.isna(v)
            )
            out.loc[idx, "investor_flow_available"] = 1
            out.loc[idx, "investor_flow_source"] = "quantmarket_intraday_flow_signal_fallback"

    out["domestic_flow_derivatives_score"] = [
        _clip(_mean([
            (float(smart) * 1.5) if smart is not None and not pd.isna(smart) else None,
            fut,
            program,
        ]))
        for smart, fut, program in zip(
            out.get("smart_money_score", pd.Series(index=out.index, dtype=float)),
            out.get("futures_direction_score", pd.Series(index=out.index, dtype=float)),
            out.get("program_pressure_score", pd.Series(index=out.index, dtype=float)),
            strict=False,
        )
    ]
    out["domestic_flow_available"] = ((out["investor_flow_available"] == 1) | (out["derivatives_context_available"] == 1)).astype(int)
    out["schema_version"] = SCHEMA_VERSION
    out["feature_version"] = FEATURE_VERSION
    out["generated_at"] = generated_at

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "domestic_flow_derivatives_daily_current.csv"
    full_csv = output_dir / "domestic_flow_derivatives_daily.csv"
    report_json = report_dir / "domestic_flow_derivatives_daily_latest.json"
    report_md = report_dir / "domestic_flow_derivatives_daily_latest.md"
    out = out.sort_values(["asof_date", "market_scope"]).reset_index(drop=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    out.to_csv(full_csv, index=False, encoding="utf-8-sig")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS domestic_flow_derivatives_daily")
        out.to_sql("domestic_flow_derivatives_daily", con, if_exists="replace", index=False)
        con.commit()

    source_ranges = {
        "investor_flows_daily": {
            "start": str(investor["asof_date"].min()) if not investor.empty else None,
            "end": str(investor["asof_date"].max()) if not investor.empty else None,
            "rows": int(len(investor)),
        },
        "intraday_derivatives": {
            "start": str(intraday["asof_date"].min()) if not intraday.empty else None,
            "end": str(intraday["asof_date"].max()) if not intraday.empty else None,
            "rows": int(len(intraday)),
        },
    }
    report = {
        "source_name": "QuantMarket domestic flow derivatives daily",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "row_count": int(len(out)),
        "date_range": {"start": str(out["asof_date"].min()) if not out.empty else None, "end": str(out["asof_date"].max()) if not out.empty else None},
        "source_ranges": source_ranges,
        "coverage": {
            "domestic_flow_available_rate": round(float(out["domestic_flow_available"].mean()), 6) if not out.empty else 0.0,
            "investor_flow_available_rate": round(float(out["investor_flow_available"].mean()), 6) if not out.empty else 0.0,
            "derivatives_context_available_rate": round(float(out["derivatives_context_available"].mean()), 6) if not out.empty else 0.0,
        },
        "primary_key": ["asof_date", "market_scope"],
        "source_paths": {
            "market_context_db": str(market_context_db),
            "ai_feature_ext_db_readonly": str(ai_feature_ext_db),
            "qm_db_readonly": str(source_qm_db),
            "classification_db_readonly": str(source_classification_db),
        },
        "output_paths": {
            "csv": str(output_csv),
            "db_table": "domestic_flow_derivatives_daily",
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
        "null_policy": "Unavailable investor/derivatives fields remain null. Intraday aggregate flow can fill ALL-scope recent dates when daily investor mart lags.",
        "pit_policy": "Daily investor flow uses date-level values known after market close. Intraday derivative fields are latest observed same-session snapshots and should be treated as recent/partial when used before close.",
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Domestic Flow Derivatives Daily",
        "",
        f"- generated_at: {generated_at}",
        f"- schema_version: {SCHEMA_VERSION}",
        f"- feature_version: {FEATURE_VERSION}",
        f"- rows: {len(out)}",
        f"- date_range: {report['date_range']['start']} ~ {report['date_range']['end']}",
        f"- csv: `{output_csv}`",
        "",
        "## Coverage",
        "",
    ]
    for key, value in report["coverage"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Source Ranges", ""])
    for key, value in source_ranges.items():
        lines.append(f"- {key}: {value['rows']} rows ({value['start']} ~ {value['end']})")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["domestic_flow_derivatives_daily"] = output_csv.name
    manifest.setdefault("tables", {})["domestic_flow_derivatives_daily"] = {
        "file": output_csv.name,
        "row_count": int(len(out)),
        "start_date": report["date_range"]["start"],
        "end_date": report["date_range"]["end"],
        "duplicate_key_count": int(out.duplicated(["asof_date", "market_scope"]).sum()) if not out.empty else 0,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    schema_path = output_dir / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {"tables": {}}
    schema.setdefault("tables", {})["domestic_flow_derivatives_daily"] = {
        "primary_key": ["asof_date", "market_scope"],
        "join_keys": ["asof_date", "market_scope"],
        "feature_version": FEATURE_VERSION,
        "score_direction": {
            "domestic_flow_derivatives_score": "higher is more risk-on domestic flow/derivatives pressure",
            "smart_money_score": "higher means foreign+institution stronger than retail",
            "futures_direction_score": "higher means stronger KOSPI200 futures direction",
            "program_pressure_score": "higher means stronger program net buying",
        },
        "null_policy": report["null_policy"],
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    return DomesticFlowDerivativesResult(
        output_csv=output_csv,
        report_json=report_json,
        report_md=report_md,
        generated_at=generated_at,
        row_count=int(len(out)),
    )
