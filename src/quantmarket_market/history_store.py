from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Iterable

from .db import upsert_many
from .types import MarketFeatures, StateHistory


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def store_market_context_history(
    con,
    *,
    market: str,
    asof: str,
    market_context: dict | None,
    created_at: str,
) -> None:
    market_context = market_context or {}
    upsert_many(
        con,
        table="market_context_history",
        columns=[
            "market",
            "asof",
            "fetched_at",
            "headline_count",
            "risk_headline_count",
            "caution_bias",
            "context_json",
            "created_at",
        ],
        rows=[
            {
                "market": market,
                "asof": asof,
                "fetched_at": market_context.get("fetched_at") or created_at,
                "headline_count": len(market_context.get("headlines") or []),
                "risk_headline_count": len(market_context.get("risk_headlines") or []),
                "caution_bias": 1 if market_context.get("caution_bias") else 0,
                "context_json": _json_text(market_context),
                "created_at": created_at,
            }
        ],
        conflict_columns=["market", "asof"],
    )


def store_ai_brief_history(
    con,
    *,
    market: str,
    asof: str,
    ai_briefs: dict | None,
    summary: dict,
    detail: dict,
    market_context: dict | None,
    created_at: str,
) -> None:
    ai_briefs = ai_briefs or {}
    rows = []
    for provider_entry in ai_briefs.get("providers") or []:
        provider = provider_entry.get("provider") or "unknown"
        source = provider_entry.get("source") or "unknown"
        model_name = source.split(":", 1)[1] if ":" in source else source
        hash_input = {
            "market": market,
            "asof": asof,
            "provider": provider,
            "summary": summary,
            "detail_state": detail.get("state"),
            "detail_signals": {
                "positive": detail.get("positive_points"),
                "warning": detail.get("warning_points"),
                "observation_note": detail.get("observation_note"),
            },
            "market_context": market_context or {},
        }
        input_hash = hashlib.sha256(
            json.dumps(hash_input, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        rows.append(
            {
                "market": market,
                "asof": asof,
                "provider": provider,
                "theme_label": provider_entry.get("theme_label"),
                "model_name": model_name,
                "source": source,
                "input_hash": input_hash,
                "enabled": 1 if provider_entry.get("enabled") else 0,
                "summary_lines_json": _json_text(provider_entry.get("summary_lines") or []),
                "brief_json": _json_text(provider_entry),
                "created_at": created_at,
            }
        )
    if rows:
        upsert_many(
            con,
            table="market_ai_brief_history",
            columns=[
                "market",
                "asof",
                "provider",
                "theme_label",
                "model_name",
                "source",
                "input_hash",
                "enabled",
                "summary_lines_json",
                "brief_json",
                "created_at",
            ],
            rows=rows,
            conflict_columns=["market", "asof", "provider"],
        )


def store_asset_relative_strength(
    con,
    *,
    features: MarketFeatures,
    created_at: str,
) -> None:
    asset_rows = [
        ("KOSPI", features.kospi_20d_ret),
        ("KOSDAQ", features.kosdaq_20d_ret),
        ("USDKRW", features.usdkrw_20d_ret),
        ("BOND", features.bond_20d_ret),
        ("GOLD", features.gold_20d_ret),
        ("INVERSE", features.inverse_20d_ret),
    ]
    values = [float(value) for _, value in asset_rows]
    mean_value = sum(values) / len(values) if values else 0.0
    variance = sum((value - mean_value) ** 2 for value in values) / len(values) if values else 0.0
    std_value = variance ** 0.5

    ranked = sorted(asset_rows, key=lambda item: item[1], reverse=True)
    rank_map = {asset: idx + 1 for idx, (asset, _) in enumerate(ranked)}
    rows = []
    for asset_group, ret_20d in asset_rows:
        strength_score = 0.0 if std_value == 0 else (float(ret_20d) - mean_value) / std_value
        if strength_score >= 0.5:
            strength_label = "강함"
        elif strength_score <= -0.5:
            strength_label = "약함"
        else:
            strength_label = "중립"
        rows.append(
            {
                "market": features.market,
                "asof": features.asof,
                "asset_group": asset_group,
                "ret_20d": ret_20d,
                "strength_score": round(strength_score, 4),
                "strength_rank": rank_map[asset_group],
                "strength_label": strength_label,
                "created_at": created_at,
            }
        )

    upsert_many(
        con,
        table="market_asset_relative_strength_hourly",
        columns=[
            "market",
            "asof",
            "asset_group",
            "ret_20d",
            "strength_score",
            "strength_rank",
            "strength_label",
            "created_at",
        ],
        rows=rows,
        conflict_columns=["market", "asof", "asset_group"],
    )


def _count_transitions(rows: Iterable[tuple[str, str]]) -> int:
    previous_label = None
    transitions = 0
    for _, label in rows:
        if previous_label is not None and label != previous_label:
            transitions += 1
        previous_label = label
    return transitions


def store_state_transition_stats(
    con,
    *,
    market: str,
    asof: str,
    state: StateHistory,
    created_at: str,
) -> None:
    current_dt = _parse_dt(asof)
    if current_dt is None:
        return

    rows_20d = con.execute(
        """
        SELECT asof, state_label
        FROM market_state_history
        WHERE market = ? AND asof <= ? AND asof >= ?
        ORDER BY asof ASC
        """,
        (market, asof, (current_dt - timedelta(days=20)).isoformat()),
    ).fetchall()
    rows_5d = con.execute(
        """
        SELECT asof, state_label
        FROM market_state_history
        WHERE market = ? AND asof <= ? AND asof >= ?
        ORDER BY asof ASC
        """,
        (market, asof, (current_dt - timedelta(days=5)).isoformat()),
    ).fetchall()

    duration_start = current_dt
    streak_rows = con.execute(
        """
        SELECT asof, state_label
        FROM market_state_history
        WHERE market = ? AND asof <= ?
        ORDER BY asof DESC
        """,
        (market, asof),
    ).fetchall()
    for row in streak_rows:
        row_dt = _parse_dt(row[0])
        if row[1] != state.state_label or row_dt is None:
            break
        duration_start = row_dt
    duration_hours = max((current_dt - duration_start).total_seconds() / 3600.0, 0.0)

    transition_count_5d = _count_transitions([(row[0], row[1]) for row in rows_5d])
    transition_count_20d = _count_transitions([(row[0], row[1]) for row in rows_20d])
    duration_component = min(duration_hours / 24.0, 1.0)
    transition_component = max(0.0, 1.0 - (transition_count_20d / 10.0))
    stability_score = round((duration_component * 0.4) + (transition_component * 0.6), 4)

    upsert_many(
        con,
        table="market_state_transition_stats",
        columns=[
            "market",
            "asof",
            "current_state",
            "prev_state",
            "duration_hours",
            "transition_count_5d",
            "transition_count_20d",
            "stability_score",
            "created_at",
        ],
        rows=[
            {
                "market": market,
                "asof": asof,
                "current_state": state.state_label,
                "prev_state": state.prev_state_label,
                "duration_hours": round(duration_hours, 4),
                "transition_count_5d": transition_count_5d,
                "transition_count_20d": transition_count_20d,
                "stability_score": stability_score,
                "created_at": created_at,
            }
        ],
        conflict_columns=["market", "asof"],
    )


def _latest_updated_at_from_publish_result(publish_result: dict) -> str | None:
    updated_values = []
    for meta in (publish_result.get("current_object_meta") or {}).values():
        updated_at = meta.get("updated")
        if updated_at:
            updated_values.append(updated_at)
    return max(updated_values) if updated_values else None


def store_publish_history(
    con,
    *,
    market: str,
    asof: str,
    run_id: str,
    publish_events: list[dict],
    created_at: str,
) -> None:
    rows = []
    for event in publish_events:
        rows.append(
            {
                "market": market,
                "asof": asof,
                "run_id": run_id,
                "publish_target": event.get("publish_target") or "unknown",
                "publish_status": event.get("publish_status") or "unknown",
                "base_url": event.get("base_url"),
                "object_count": int(event.get("object_count") or 0),
                "latest_updated_at": event.get("latest_updated_at"),
                "publish_json": _json_text(event),
                "created_at": created_at,
            }
        )
    if rows:
        upsert_many(
            con,
            table="market_publish_history",
            columns=[
                "market",
                "asof",
                "run_id",
                "publish_target",
                "publish_status",
                "base_url",
                "object_count",
                "latest_updated_at",
                "publish_json",
                "created_at",
            ],
            rows=rows,
            conflict_columns=["market", "run_id", "publish_target"],
        )


def build_publish_events(*, snapshot_dir: str, handoff_dir: str, remote_publish_result: dict) -> list[dict]:
    events = [
        {
            "publish_target": "local_snapshot",
            "publish_status": "ok",
            "base_url": snapshot_dir,
            "object_count": 7,
            "latest_updated_at": None,
        },
        {
            "publish_target": "local_handoff",
            "publish_status": "ok",
            "base_url": handoff_dir,
            "object_count": 9,
            "latest_updated_at": None,
        },
    ]
    if remote_publish_result.get("enabled"):
        current_meta = remote_publish_result.get("current_object_meta") or {}
        events.append(
            {
                "publish_target": f"remote_{remote_publish_result.get('provider') or 'unknown'}_current",
                "publish_status": "ok" if current_meta else "unknown",
                "base_url": remote_publish_result.get("base_url"),
                "object_count": len(remote_publish_result.get("files") or {}),
                "latest_updated_at": _latest_updated_at_from_publish_result(remote_publish_result),
                "run_id": remote_publish_result.get("run_id"),
            }
        )
    else:
        events.append(
            {
                "publish_target": "remote_publish",
                "publish_status": "not_enabled",
                "base_url": None,
                "object_count": 0,
                "latest_updated_at": None,
            }
        )
    return events
