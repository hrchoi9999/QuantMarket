from __future__ import annotations

from pathlib import Path

from .admin_payloads import (
    build_admin_manifest,
    build_admin_market_timeline_payload,
    build_admin_asset_strength_payload,
    build_admin_model_background_payload,
    build_admin_state_transition_payload,
)
from .ai_generation import refresh_ai_briefs
from .analytics import build_market_features, build_state_history, format_kst, normalize_asof_kst, now_kst, persist_feature_bundle, score_market_state
from .config import (
    ADMIN_HANDOFF_DIR,
    ADMIN_SNAPSHOT_DIR,
    DEFAULT_DB_PATH,
    QUANTSERVICE_HANDOFF_DIR,
    QUANT_PRICE_DB_PATH,
    QUANT_REGIME_DB_PATH,
    REPORT_DIR,
    SNAPSHOT_DIR,
    ensure_runtime_dirs,
)
from .db import connect, init_db, upsert_payload
from .history_store import (
    build_publish_events,
    store_ai_brief_history,
    store_asset_relative_strength,
    store_market_context_history,
    store_publish_history,
    store_state_transition_stats,
)
from .intraday_bridge import build_state_intraday_bridge, load_latest_intraday_context
from .official_market_data import collect_official_market_data
from .market_context import fetch_market_context
from .payloads import (
    build_api_response,
    build_detail_payload,
    build_manifest,
    build_quantservice_home_payload,
    build_quantservice_manifest,
    build_quantservice_page_payload,
    build_quantservice_today_payload,
    build_summary_payload,
    build_today_bridge_payload,
    write_payload_file,
)
from .public_briefing_payloads import (
    build_public_market_asset_strength_payload,
    build_public_market_model_background_payload,
    build_public_market_state_transition_payload,
    build_public_market_timeline_payload,
)
from .quant_readonly import load_quant_reference_inputs
from .remote_publish import RemotePublishConfig, publish_remote_handoff
from .sample_data import seed_sample_official_data


def run_market_analysis_pipeline(
    *,
    market: str = "KR",
    asof: str | None = None,
    db_path: Path | None = None,
    snapshot_dir: Path | None = None,
    handoff_dir: Path | None = None,
    admin_snapshot_dir: Path | None = None,
    admin_handoff_dir: Path | None = None,
    seed_sample: bool = False,
    use_quant_readonly: bool = True,
    collect_official: bool = True,
    remote_publish_config: RemotePublishConfig | None = None,
) -> dict:
    ensure_runtime_dirs()
    db_path = db_path or DEFAULT_DB_PATH
    snapshot_dir = snapshot_dir or SNAPSHOT_DIR
    handoff_dir = handoff_dir or QUANTSERVICE_HANDOFF_DIR
    admin_snapshot_dir = admin_snapshot_dir or ADMIN_SNAPSHOT_DIR
    admin_handoff_dir = admin_handoff_dir or ADMIN_HANDOFF_DIR
    now = now_kst()
    asof = normalize_asof_kst(asof, now=now)
    created_at = format_kst(now)
    run_id = now.strftime("%Y%m%dT%H%M%S")

    init_db(db_path)
    with connect(db_path) as con:
        collection_stats = {"index_rows": 0, "fx_rows": 0, "rate_rows": 0}
        if collect_official:
            collection_stats = collect_official_market_data(
                con,
                market=market,
                asof_date=asof[:10],
                updated_at=created_at,
            )
        if seed_sample:
            seed_sample_official_data(con, market=market, asof_date=asof[:10], updated_at=created_at)

        quant_inputs = load_quant_reference_inputs(asof[:10]) if use_quant_readonly and market == "KR" else {}
        features = build_market_features(con, market=market, asof=asof, created_at=created_at, quant_inputs=quant_inputs)
        scores = score_market_state(features, created_at=created_at)
        state = build_state_history(con, scores=scores, created_at=created_at)
        persist_feature_bundle(con, features=features, scores=scores, state=state)
        store_asset_relative_strength(con, features=features, created_at=created_at)
        store_state_transition_stats(con, market=market, asof=asof, state=state, created_at=created_at)

        quant_context = {
            "price_db": QUANT_PRICE_DB_PATH if use_quant_readonly else None,
            "regime_db": QUANT_REGIME_DB_PATH if use_quant_readonly else None,
            "representative_assets": quant_inputs.get("representative_assets") if quant_inputs else None,
        }
        intraday_context = load_latest_intraday_context(con, market=market, asof=asof)
        summary = build_summary_payload(features=features, scores=scores, state=state)
        detail = build_detail_payload(features=features, scores=scores, state=state, quant_context=quant_context)
        state_intraday_bridge = build_state_intraday_bridge(summary=summary, detail=detail, intraday_context=intraday_context)
        summary["state_intraday_bridge"] = state_intraday_bridge
        detail["state_intraday_bridge"] = state_intraday_bridge
        today_bridge = build_today_bridge_payload(features=features, scores=scores)
        today_bridge["state_intraday_bridge"] = state_intraday_bridge
        manifest = build_manifest(features=features, db_path=db_path)
        market_context = fetch_market_context(market=market, fetched_at=created_at)
        store_market_context_history(
            con,
            market=market,
            asof=asof,
            market_context=market_context,
            created_at=created_at,
        )
        ai_briefs = refresh_ai_briefs(
            market=market,
            asof=asof,
            summary=summary,
            detail=detail,
            generated_at=created_at,
            market_context=market_context,
            intraday_context=intraday_context,
        )

        store_ai_brief_history(
            con,
            market=market,
            asof=asof,
            ai_briefs=ai_briefs,
            summary=summary,
            detail=detail,
            market_context=market_context,
            created_at=created_at,
        )

        quantservice_home = build_quantservice_home_payload(
            summary=summary,
            detail=detail,
            today_bridge=today_bridge,
        )
        quantservice_today = build_quantservice_today_payload(
            summary=summary,
            today_bridge=today_bridge,
        )
        quantservice_page = build_quantservice_page_payload(
            detail=detail,
            summary=summary,
            ai_briefs=ai_briefs,
        )
        quantservice_manifest = build_quantservice_manifest(
            features=features,
            db_path=db_path,
            source_snapshot_dir=snapshot_dir,
            handoff_dir=handoff_dir,
        )
        public_timeline = build_public_market_timeline_payload(con, market=market, asof=asof)
        public_asset_strength = build_public_market_asset_strength_payload(con, market=market, asof=asof)
        public_state_transition = build_public_market_state_transition_payload(con, market=market, asof=asof)
        public_model_background = build_public_market_model_background_payload(
            market=market,
            asof=asof,
            summary=summary,
            detail=detail,
            today_bridge=today_bridge,
            timeline=public_timeline,
            asset_strength=public_asset_strength,
            state_transition=public_state_transition,
        )
        admin_timeline = build_admin_market_timeline_payload(con, market=market, asof=asof)
        admin_asset_strength = build_admin_asset_strength_payload(con, market=market, asof=asof)
        admin_state_transition = build_admin_state_transition_payload(con, market=market, asof=asof)
        admin_model_background = build_admin_model_background_payload(
            market=market,
            asof=asof,
            summary=summary,
            detail=detail,
            today_bridge=today_bridge,
            timeline=admin_timeline,
            asset_strength=admin_asset_strength,
            state_transition=admin_state_transition,
        )
        admin_manifest = build_admin_manifest(
            market=market,
            asof=asof,
            admin_snapshot_dir=str(admin_snapshot_dir),
            admin_handoff_dir=str(admin_handoff_dir),
        )

        api_summary = build_api_response(
            endpoint=f"/api/v1/market-analysis/summary?market={market}",
            market=market,
            asof=asof,
            payload=summary,
        )
        api_detail = build_api_response(
            endpoint=f"/api/v1/market-analysis/detail?market={market}",
            market=market,
            asof=asof,
            payload=detail,
        )
        api_today_bridge = build_api_response(
            endpoint=f"/api/v1/market-analysis/today-bridge?market={market}",
            market=market,
            asof=asof,
            payload=today_bridge,
        )
        api_home = build_api_response(
            endpoint=f"/api/v1/market-analysis/home?market={market}",
            market=market,
            asof=asof,
            payload=quantservice_home,
        )
        api_page = build_api_response(
            endpoint=f"/api/v1/market-analysis/page?market={market}",
            market=market,
            asof=asof,
            payload=quantservice_page,
        )
        api_timeline = build_api_response(
            endpoint=f"/api/v1/market-analysis/timeline?market={market}",
            market=market,
            asof=asof,
            payload=public_timeline,
        )
        api_asset_strength = build_api_response(
            endpoint=f"/api/v1/market-analysis/asset-strength?market={market}",
            market=market,
            asof=asof,
            payload=public_asset_strength,
        )
        api_state_transition = build_api_response(
            endpoint=f"/api/v1/market-analysis/state-transition?market={market}",
            market=market,
            asof=asof,
            payload=public_state_transition,
        )
        api_model_background = build_api_response(
            endpoint=f"/api/v1/market-analysis/model-background?market={market}",
            market=market,
            asof=asof,
            payload=public_model_background,
        )

        for payload_type, payload in (
            ("summary", summary),
            ("detail", detail),
            ("today_bridge", today_bridge),
            ("quantservice_home", quantservice_home),
            ("quantservice_today", quantservice_today),
            ("quantservice_page", quantservice_page),
            ("quantservice_manifest", quantservice_manifest),
            ("public_timeline", public_timeline),
            ("public_asset_strength", public_asset_strength),
            ("public_state_transition", public_state_transition),
            ("public_model_background", public_model_background),
            ("api_home", api_home),
            ("api_page", api_page),
            ("api_summary", api_summary),
            ("api_detail", api_detail),
            ("api_today_bridge", api_today_bridge),
            ("api_timeline", api_timeline),
            ("api_asset_strength", api_asset_strength),
            ("api_state_transition", api_state_transition),
            ("api_model_background", api_model_background),
            ("admin_timeline", admin_timeline),
            ("admin_asset_strength", admin_asset_strength),
            ("admin_state_transition", admin_state_transition),
            ("admin_model_background", admin_model_background),
            ("admin_manifest", admin_manifest),
        ):
            upsert_payload(
                con,
                market=market,
                asof=asof,
                payload_type=payload_type,
                payload=payload,
                created_at=created_at,
            )

        write_payload_file(snapshot_dir / "market_analysis_summary.json", summary)
        write_payload_file(snapshot_dir / "market_analysis_detail.json", detail)
        write_payload_file(snapshot_dir / "market_analysis_today_bridge.json", today_bridge)
        write_payload_file(snapshot_dir / "market_analysis_manifest.json", manifest)
        write_payload_file(snapshot_dir / "api_v1_market_analysis_summary.json", api_summary)
        write_payload_file(snapshot_dir / "api_v1_market_analysis_detail.json", api_detail)
        write_payload_file(snapshot_dir / "api_v1_market_analysis_today_bridge.json", api_today_bridge)
        write_payload_file(handoff_dir / "quantservice_market_home.json", quantservice_home)
        write_payload_file(handoff_dir / "quantservice_market_today.json", quantservice_today)
        write_payload_file(handoff_dir / "quantservice_market_page.json", quantservice_page)
        write_payload_file(handoff_dir / "quantservice_market_manifest.json", quantservice_manifest)
        write_payload_file(handoff_dir / "api_v1_market_analysis_home.json", api_home)
        write_payload_file(handoff_dir / "api_v1_market_analysis_page.json", api_page)
        write_payload_file(handoff_dir / "api_v1_market_analysis_summary.json", api_summary)
        write_payload_file(handoff_dir / "api_v1_market_analysis_detail.json", api_detail)
        write_payload_file(handoff_dir / "api_v1_market_analysis_today_bridge.json", api_today_bridge)
        write_payload_file(handoff_dir / "quantservice_market_timeline.json", public_timeline)
        write_payload_file(handoff_dir / "quantservice_market_asset_strength.json", public_asset_strength)
        write_payload_file(handoff_dir / "quantservice_market_state_transition.json", public_state_transition)
        write_payload_file(handoff_dir / "quantservice_market_model_background.json", public_model_background)
        write_payload_file(handoff_dir / "api_v1_market_analysis_timeline.json", api_timeline)
        write_payload_file(handoff_dir / "api_v1_market_analysis_asset_strength.json", api_asset_strength)
        write_payload_file(handoff_dir / "api_v1_market_analysis_state_transition.json", api_state_transition)
        write_payload_file(handoff_dir / "api_v1_market_analysis_model_background.json", api_model_background)
        write_payload_file(snapshot_dir / "market_briefing_timeline.json", public_timeline)
        write_payload_file(snapshot_dir / "market_briefing_asset_strength.json", public_asset_strength)
        write_payload_file(snapshot_dir / "market_briefing_state_transition.json", public_state_transition)
        write_payload_file(snapshot_dir / "market_briefing_model_background.json", public_model_background)

        write_payload_file(admin_snapshot_dir / "admin_market_timeline.json", admin_timeline)
        write_payload_file(admin_snapshot_dir / "admin_market_asset_strength.json", admin_asset_strength)
        write_payload_file(admin_snapshot_dir / "admin_market_state_transition.json", admin_state_transition)
        write_payload_file(admin_snapshot_dir / "admin_market_model_background.json", admin_model_background)
        write_payload_file(admin_snapshot_dir / "admin_market_manifest.json", admin_manifest)
        write_payload_file(admin_handoff_dir / "admin_market_timeline.json", admin_timeline)
        write_payload_file(admin_handoff_dir / "admin_market_asset_strength.json", admin_asset_strength)
        write_payload_file(admin_handoff_dir / "admin_market_state_transition.json", admin_state_transition)
        write_payload_file(admin_handoff_dir / "admin_market_model_background.json", admin_model_background)
        write_payload_file(admin_handoff_dir / "admin_market_manifest.json", admin_manifest)

    remote_publish_result = {"enabled": False}
    if remote_publish_config and remote_publish_config.enabled:
        remote_publish_result = publish_remote_handoff(
            handoff_dir=handoff_dir,
            run_id=run_id,
            asof=asof,
            config=remote_publish_config,
        )
        write_payload_file(REPORT_DIR / "remote_publish_status_latest.json", remote_publish_result)
        write_payload_file(REPORT_DIR / f"remote_publish_{run_id}.json", remote_publish_result)

    publish_events = build_publish_events(
        snapshot_dir=str(snapshot_dir),
        handoff_dir=str(handoff_dir),
        remote_publish_result=remote_publish_result,
    )
    with connect(db_path) as con:
        store_publish_history(
            con,
            market=market,
            asof=asof,
            run_id=run_id,
            publish_events=publish_events,
            created_at=created_at,
        )

    return {
        "market": market,
        "asof": asof,
        "db_path": str(db_path),
        "snapshot_dir": str(snapshot_dir),
        "handoff_dir": str(handoff_dir),
        "admin_snapshot_dir": str(admin_snapshot_dir),
        "admin_handoff_dir": str(admin_handoff_dir),
        "state_label": scores.state_label,
        "state_score": scores.total_score,
        "breadth_proxy_flag": features.breadth_proxy_flag,
        "defensive_proxy_flag": features.defensive_proxy_flag,
        "breadth_universe_count": features.breadth_universe_count,
        "collection_stats": collection_stats,
        "remote_publish": remote_publish_result,
        "ai_briefs_enabled": ai_briefs.get("enabled", False),
    }
