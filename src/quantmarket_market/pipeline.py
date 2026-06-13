from __future__ import annotations

from datetime import datetime
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
from .dart_disclosures import collect_market_dart_summary
from .history_store import (
    build_publish_events,
    store_ai_brief_history,
    store_asset_relative_strength,
    store_market_context_history,
    store_publish_history,
    store_state_transition_stats,
)
from .history_payloads import (
    build_market_asset_strength_history_payload,
    build_market_breadth_detail_history_payload,
    build_market_dart_summary_history_payload,
    build_market_state_transition_history_payload,
    build_market_timeline_history_payload,
    build_market_us_macro_panel_history_payload,
    build_next_day_preview_history_payload,
)
from .intraday_bridge import build_state_intraday_bridge, load_latest_intraday_context
from .intraday_market import collect_intraday_market_snapshot
from .official_market_data import collect_official_market_data
from .market_context import fetch_market_context
from .market_analysis_menu_payloads import (
    build_market_analysis_tabs_payload,
    build_market_data_guide_payload,
    build_market_live_context_payload,
)
from .market_analysis_extension_payloads import (
    build_market_breadth_detail_payload,
    build_market_dart_summary_payload,
    build_market_index_panel_payload,
    build_market_us_macro_panel_payload,
)
from .market_environment_indicators import (
    build_market_environment_indicators_manifest,
    build_market_environment_indicators_payload,
)
from .market_state_composite import build_market_state_composite
from .next_day_preview import build_next_day_preview_outputs
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


def _is_intraday_context_stale(intraday_context: dict | None, *, asof: str, max_age_minutes: int = 45) -> bool:
    if not intraday_context:
        return True
    state = intraday_context.get("state") or {}
    intraday_asof = state.get("asof")
    if not intraday_asof:
        return True
    try:
        intraday_dt = datetime.fromisoformat(str(intraday_asof))
        asof_dt = datetime.fromisoformat(str(asof))
    except ValueError:
        return True
    return (asof_dt - intraday_dt).total_seconds() > max_age_minutes * 60


def _attach_next_day_signal_test(composite: dict, next_day_preview: dict) -> None:
    if not composite or not next_day_preview:
        return
    score = next_day_preview.get("preview_score")
    reference_session = str(next_day_preview.get("reference_session") or "").strip()
    if score is None or not reference_session:
        return
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        return
    preview_label = str(next_day_preview.get("preview_label") or "익일 신호 테스트").strip()
    position_pct = max(0.0, min(100.0, (numeric_score + 3.0) / 6.0 * 100.0))
    biases = next_day_preview.get("biases") if isinstance(next_day_preview.get("biases"), dict) else {}

    def clamp_score(value: float) -> float:
        return max(-3.0, min(3.0, float(value)))

    def numeric_bias(key: str) -> float:
        try:
            return float(biases.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    environment_score = clamp_score(
        numeric_bias("global_risk_bias") * 0.65
        + numeric_bias("overnight_fx_bias") * 0.35
    )
    short_term_score = clamp_score(numeric_bias("overnight_futures_bias"))

    signal = {
        "enabled": True,
        "label": "익일 신호 테스트",
        "reference_session": reference_session,
        "preview_label": preview_label,
        "preview_score": round(numeric_score, 4),
        "environment_score": round(environment_score, 4),
        "short_term_score": round(short_term_score, 4),
        "official_score_impact": False,
        "experiment_status": next_day_preview.get("experiment_status") or "validation_required",
    }
    composite["next_day_signal_test"] = signal
    chart = composite.get("composite_chart") if isinstance(composite.get("composite_chart"), dict) else {}
    series = chart.get("series") if isinstance(chart.get("series"), list) else []

    score_by_axis = {
        "financial_environment": environment_score,
        "medium_term_model_outlook": numeric_score,
        "short_term_market_condition": short_term_score,
    }
    label_by_axis = {
        "financial_environment": "익일 금융환경 테스트",
        "medium_term_model_outlook": "익일 종합 신호 테스트",
        "short_term_market_condition": "익일 단기상황 테스트",
    }
    chart_preview_points = [
        point
        for point in (chart.get("preview_points") if isinstance(chart.get("preview_points"), list) else [])
        if point.get("date") != reference_session
    ]
    for item in series:
        series_id = item.get("series_id")
        if series_id not in score_by_axis:
            continue
        points = item.get("points") if isinstance(item.get("points"), list) else []
        item["points"] = [
            point
            for point in points
            if not (
                point.get("date") == reference_session
                and point.get("point_role") == "next_day_signal_test"
            )
        ]
        axis_score = round(float(score_by_axis[series_id]), 4)
        preview_point = {
            "date": reference_session,
            "value": axis_score,
            "label": "익일",
            "point_role": "next_day_signal_test",
            "display_label": label_by_axis[series_id],
            "preview_label": preview_label,
            "official_score_impact": False,
            "experiment_status": signal["experiment_status"],
            "color": item.get("color"),
            "rendering_hint": {
                "date_axis_policy": "exclude_from_main_axis",
                "point_color_policy": "same_as_parent_series",
                "tooltip_policy": "same_as_regular_point",
                "line_style_policy": "same_as_parent_series",
            },
        }
        item["preview_points"] = [
            point
            for point in (item.get("preview_points") if isinstance(item.get("preview_points"), list) else [])
            if point.get("date") != reference_session
        ]
        item["preview_points"].append(preview_point)
        item["next_day_signal_test"] = {
            "enabled": True,
            "reference_session": reference_session,
            "label": label_by_axis[series_id],
            "score": axis_score,
            "preview_label": preview_label,
            "official_score_impact": False,
            "date_axis_policy": "exclude_from_main_axis",
            "point_color_policy": "same_as_parent_series",
            "tooltip_policy": "same_as_regular_point",
        }
        chart_preview_points.append(
            {
                "date": reference_session,
                "value": axis_score,
                "label": "익일",
                "series_id": series_id,
                "point_role": "next_day_signal_test",
                "display_label": label_by_axis[series_id],
                "preview_label": preview_label,
                "official_score_impact": False,
                "experiment_status": signal["experiment_status"],
                "color": item.get("color"),
                "date_axis_policy": "exclude_from_main_axis",
                "point_color_policy": "same_as_parent_series",
                "tooltip_policy": "same_as_regular_point",
            }
        )
    chart["series"] = series
    chart["next_day_signal_test"] = {
        "enabled": True,
        "reference_session": reference_session,
        "date_label": f"{reference_session} 익일",
        "date_axis_policy": "exclude_from_main_axis",
        "point_color_policy": "same_as_parent_series",
        "tooltip_policy": "same_as_regular_point",
        "attached_axis_series": [
            "financial_environment",
            "medium_term_model_outlook",
            "short_term_market_condition",
        ],
        "summary_score": round(numeric_score, 4),
        "environment_score": round(environment_score, 4),
        "short_term_score": round(short_term_score, 4),
        "official_score_impact": False,
    }
    chart["preview_points"] = chart_preview_points
    composite["composite_chart"] = chart
    rules = composite.get("interpretation_rules") if isinstance(composite.get("interpretation_rules"), list) else []
    rule = "익일 신호 테스트는 야간/장외 스트레스 참고값이며 정식 3축 점수에는 반영하지 않습니다."
    if rule not in rules:
        rules.append(rule)
    composite["interpretation_rules"] = rules


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
        asof_hour = int(asof[11:13]) if len(asof) >= 13 else now.hour
        intraday_session_date = ((intraday_context or {}).get("state") or {}).get("session_date")
        needs_intraday_refresh = (
            market == "KR"
            and 8 <= asof_hour <= 18
            and (
                intraday_session_date != asof[:10]
                or _is_intraday_context_stale(intraday_context, asof=asof)
            )
        )
        if needs_intraday_refresh:
            try:
                collect_intraday_market_snapshot(
                    con,
                    market=market,
                    asof=asof,
                    snapshot_dir=admin_snapshot_dir,
                    handoff_dir=admin_handoff_dir,
                )
                intraday_context = load_latest_intraday_context(con, market=market, asof=asof)
            except Exception:
                intraday_context = load_latest_intraday_context(con, market=market, asof=asof)
        summary = build_summary_payload(features=features, scores=scores, state=state)
        detail = build_detail_payload(features=features, scores=scores, state=state, quant_context=quant_context)
        state_intraday_bridge = build_state_intraday_bridge(summary=summary, detail=detail, intraday_context=intraday_context)
        summary["state_intraday_bridge"] = state_intraday_bridge
        detail["state_intraday_bridge"] = state_intraday_bridge
        market_state_composite = build_market_state_composite(
            features=features,
            scores=scores,
            state_intraday_bridge=state_intraday_bridge,
        )
        summary["market_state_composite"] = market_state_composite
        detail["market_state_composite"] = market_state_composite
        today_bridge = build_today_bridge_payload(features=features, scores=scores)
        today_bridge["state_intraday_bridge"] = state_intraday_bridge
        today_bridge["market_state_composite"] = market_state_composite
        manifest = build_manifest(features=features, db_path=db_path)
        market_context = fetch_market_context(market=market, fetched_at=created_at)
        collect_market_dart_summary(
            con,
            market=market,
            asof=asof,
            created_at=created_at,
        )
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

        next_day_preview_outputs = build_next_day_preview_outputs(
            con,
            market=market,
            asof=asof,
            summary=summary,
            detail=detail,
            snapshot_dir=snapshot_dir,
            handoff_dir=handoff_dir,
        )
        _attach_next_day_signal_test(market_state_composite, next_day_preview_outputs["preview"])
        summary["market_state_composite"] = market_state_composite
        detail["market_state_composite"] = market_state_composite
        today_bridge["market_state_composite"] = market_state_composite

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
        public_timeline_history = build_market_timeline_history_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        public_asset_strength_history = build_market_asset_strength_history_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        public_state_transition_history = build_market_state_transition_history_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
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
        next_day_preview_history = build_next_day_preview_history_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_dart_summary_history = build_market_dart_summary_history_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_breadth_detail_history = build_market_breadth_detail_history_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_us_macro_panel_history = build_market_us_macro_panel_history_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_analysis_tabs = build_market_analysis_tabs_payload(
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_live_context = build_market_live_context_payload(
            market=market,
            asof=asof,
            summary=summary,
            detail=detail,
            today_bridge=today_bridge,
            next_day_preview=next_day_preview_outputs["quantservice"],
        )
        market_data_guide = build_market_data_guide_payload(
            market=market,
            asof=asof,
            detail=detail,
        )
        market_index_panel = build_market_index_panel_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_breadth_detail = build_market_breadth_detail_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_us_macro_panel = build_market_us_macro_panel_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_dart_summary = build_market_dart_summary_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_environment_indicators = build_market_environment_indicators_payload(
            con,
            market=market,
            asof=asof,
            generated_at=created_at,
        )
        market_environment_indicators_manifest = build_market_environment_indicators_manifest(
            market=market,
            asof=asof,
            generated_at=created_at,
            payload=market_environment_indicators,
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
        api_timeline_history = build_api_response(
            endpoint=f"/api/v1/market-analysis/timeline/history?market={market}",
            market=market,
            asof=asof,
            payload=public_timeline_history,
        )
        api_asset_strength_history = build_api_response(
            endpoint=f"/api/v1/market-analysis/asset-strength/history?market={market}",
            market=market,
            asof=asof,
            payload=public_asset_strength_history,
        )
        api_state_transition_history = build_api_response(
            endpoint=f"/api/v1/market-analysis/state-transition/history?market={market}",
            market=market,
            asof=asof,
            payload=public_state_transition_history,
        )
        api_model_background = build_api_response(
            endpoint=f"/api/v1/market-analysis/model-background?market={market}",
            market=market,
            asof=asof,
            payload=public_model_background,
        )
        api_next_day_preview_history = build_api_response(
            endpoint=f"/api/v1/market-analysis/next-day-preview/history?market={market}",
            market=market,
            asof=asof,
            payload=next_day_preview_history,
        )
        api_market_analysis_tabs = build_api_response(
            endpoint=f"/api/v1/market-analysis/tabs?market={market}",
            market=market,
            asof=asof,
            payload=market_analysis_tabs,
        )
        api_market_live_context = build_api_response(
            endpoint=f"/api/v1/market-analysis/live-context?market={market}",
            market=market,
            asof=asof,
            payload=market_live_context,
        )
        api_market_data_guide = build_api_response(
            endpoint=f"/api/v1/market-analysis/data-guide?market={market}",
            market=market,
            asof=asof,
            payload=market_data_guide,
        )
        api_market_index_panel = build_api_response(
            endpoint=f"/api/v1/market-analysis/index-panel?market={market}",
            market=market,
            asof=asof,
            payload=market_index_panel,
        )
        api_market_breadth_detail = build_api_response(
            endpoint=f"/api/v1/market-analysis/breadth-detail?market={market}",
            market=market,
            asof=asof,
            payload=market_breadth_detail,
        )
        api_market_breadth_detail_history = build_api_response(
            endpoint=f"/api/v1/market-analysis/breadth-detail/history?market={market}",
            market=market,
            asof=asof,
            payload=market_breadth_detail_history,
        )
        api_market_us_macro_panel = build_api_response(
            endpoint=f"/api/v1/market-analysis/us-macro-panel?market={market}",
            market=market,
            asof=asof,
            payload=market_us_macro_panel,
        )
        api_market_us_macro_panel_history = build_api_response(
            endpoint=f"/api/v1/market-analysis/us-macro-panel/history?market={market}",
            market=market,
            asof=asof,
            payload=market_us_macro_panel_history,
        )
        api_market_dart_summary = build_api_response(
            endpoint=f"/api/v1/market-analysis/dart-summary?market={market}",
            market=market,
            asof=asof,
            payload=market_dart_summary,
        )
        api_market_dart_summary_history = build_api_response(
            endpoint=f"/api/v1/market-analysis/dart-summary/history?market={market}",
            market=market,
            asof=asof,
            payload=market_dart_summary_history,
        )
        api_market_environment_indicators = build_api_response(
            endpoint=f"/api/v1/market-environment-indicators?market={market}",
            market=market,
            asof=asof,
            payload=market_environment_indicators,
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
            ("public_timeline_history", public_timeline_history),
            ("public_asset_strength_history", public_asset_strength_history),
            ("public_state_transition_history", public_state_transition_history),
            ("public_model_background", public_model_background),
            ("api_home", api_home),
            ("api_page", api_page),
            ("api_summary", api_summary),
            ("api_detail", api_detail),
            ("api_today_bridge", api_today_bridge),
            ("api_timeline", api_timeline),
            ("api_asset_strength", api_asset_strength),
            ("api_state_transition", api_state_transition),
            ("api_timeline_history", api_timeline_history),
            ("api_asset_strength_history", api_asset_strength_history),
            ("api_state_transition_history", api_state_transition_history),
            ("api_model_background", api_model_background),
            ("next_day_preview", next_day_preview_outputs["preview"]),
            ("quantservice_next_day_preview", next_day_preview_outputs["quantservice"]),
            ("api_next_day_preview", next_day_preview_outputs["api"]),
            ("next_day_preview_history", next_day_preview_history),
            ("api_next_day_preview_history", api_next_day_preview_history),
            ("market_analysis_tabs", market_analysis_tabs),
            ("market_live_context", market_live_context),
            ("market_data_guide", market_data_guide),
            ("market_index_panel", market_index_panel),
            ("market_breadth_detail", market_breadth_detail),
            ("market_breadth_detail_history", market_breadth_detail_history),
            ("market_us_macro_panel", market_us_macro_panel),
            ("market_us_macro_panel_history", market_us_macro_panel_history),
            ("market_dart_summary", market_dart_summary),
            ("market_dart_summary_history", market_dart_summary_history),
            ("market_environment_indicators", market_environment_indicators),
            ("market_environment_indicators_manifest", market_environment_indicators_manifest),
            ("api_market_analysis_tabs", api_market_analysis_tabs),
            ("api_market_live_context", api_market_live_context),
            ("api_market_data_guide", api_market_data_guide),
            ("api_market_index_panel", api_market_index_panel),
            ("api_market_breadth_detail", api_market_breadth_detail),
            ("api_market_breadth_detail_history", api_market_breadth_detail_history),
            ("api_market_us_macro_panel", api_market_us_macro_panel),
            ("api_market_us_macro_panel_history", api_market_us_macro_panel_history),
            ("api_market_dart_summary", api_market_dart_summary),
            ("api_market_dart_summary_history", api_market_dart_summary_history),
            ("api_market_environment_indicators", api_market_environment_indicators),
            ("next_day_preview_manifest", next_day_preview_outputs["manifest"]),
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
        write_payload_file(handoff_dir / "quantservice_market_timeline_history.json", public_timeline_history)
        write_payload_file(handoff_dir / "quantservice_market_asset_strength_history.json", public_asset_strength_history)
        write_payload_file(handoff_dir / "quantservice_market_state_transition_history.json", public_state_transition_history)
        write_payload_file(handoff_dir / "quantservice_market_model_background.json", public_model_background)
        write_payload_file(handoff_dir / "api_v1_market_analysis_timeline.json", api_timeline)
        write_payload_file(handoff_dir / "api_v1_market_analysis_asset_strength.json", api_asset_strength)
        write_payload_file(handoff_dir / "api_v1_market_analysis_state_transition.json", api_state_transition)
        write_payload_file(handoff_dir / "api_v1_market_analysis_timeline_history.json", api_timeline_history)
        write_payload_file(handoff_dir / "api_v1_market_analysis_asset_strength_history.json", api_asset_strength_history)
        write_payload_file(handoff_dir / "api_v1_market_analysis_state_transition_history.json", api_state_transition_history)
        write_payload_file(handoff_dir / "api_v1_market_analysis_model_background.json", api_model_background)
        write_payload_file(handoff_dir / "quantservice_market_next_day_preview_history.json", next_day_preview_history)
        write_payload_file(handoff_dir / "api_v1_market_analysis_next_day_preview_history.json", api_next_day_preview_history)
        write_payload_file(handoff_dir / "quantservice_market_dart_summary_history.json", market_dart_summary_history)
        write_payload_file(handoff_dir / "api_v1_market_analysis_dart_summary_history.json", api_market_dart_summary_history)
        write_payload_file(handoff_dir / "quantservice_market_analysis_tabs.json", market_analysis_tabs)
        write_payload_file(handoff_dir / "quantservice_market_live_context.json", market_live_context)
        write_payload_file(handoff_dir / "quantservice_market_data_guide.json", market_data_guide)
        write_payload_file(handoff_dir / "quantservice_market_index_panel.json", market_index_panel)
        write_payload_file(handoff_dir / "quantservice_market_breadth_detail.json", market_breadth_detail)
        write_payload_file(handoff_dir / "quantservice_market_breadth_detail_history.json", market_breadth_detail_history)
        write_payload_file(handoff_dir / "quantservice_market_us_macro_panel.json", market_us_macro_panel)
        write_payload_file(handoff_dir / "quantservice_market_us_macro_panel_history.json", market_us_macro_panel_history)
        write_payload_file(handoff_dir / "quantservice_market_dart_summary.json", market_dart_summary)
        write_payload_file(handoff_dir / "quantservice_market_environment_indicators.json", market_environment_indicators)
        write_payload_file(
            handoff_dir / "quantservice_market_environment_indicators_manifest.json",
            market_environment_indicators_manifest,
        )
        write_payload_file(handoff_dir / "api_v1_market_analysis_tabs.json", api_market_analysis_tabs)
        write_payload_file(handoff_dir / "api_v1_market_analysis_live_context.json", api_market_live_context)
        write_payload_file(handoff_dir / "api_v1_market_analysis_data_guide.json", api_market_data_guide)
        write_payload_file(handoff_dir / "api_v1_market_analysis_index_panel.json", api_market_index_panel)
        write_payload_file(handoff_dir / "api_v1_market_analysis_breadth_detail.json", api_market_breadth_detail)
        write_payload_file(handoff_dir / "api_v1_market_analysis_breadth_detail_history.json", api_market_breadth_detail_history)
        write_payload_file(handoff_dir / "api_v1_market_analysis_us_macro_panel.json", api_market_us_macro_panel)
        write_payload_file(handoff_dir / "api_v1_market_analysis_us_macro_panel_history.json", api_market_us_macro_panel_history)
        write_payload_file(handoff_dir / "api_v1_market_analysis_dart_summary.json", api_market_dart_summary)
        write_payload_file(
            handoff_dir / "api_v1_market_environment_indicators.json",
            api_market_environment_indicators,
        )
        write_payload_file(snapshot_dir / "market_briefing_timeline.json", public_timeline)
        write_payload_file(snapshot_dir / "market_briefing_asset_strength.json", public_asset_strength)
        write_payload_file(snapshot_dir / "market_briefing_state_transition.json", public_state_transition)
        write_payload_file(snapshot_dir / "market_briefing_timeline_history.json", public_timeline_history)
        write_payload_file(snapshot_dir / "market_briefing_asset_strength_history.json", public_asset_strength_history)
        write_payload_file(snapshot_dir / "market_briefing_state_transition_history.json", public_state_transition_history)
        write_payload_file(snapshot_dir / "market_briefing_model_background.json", public_model_background)
        write_payload_file(snapshot_dir / "market_next_day_preview_history.json", next_day_preview_history)
        write_payload_file(snapshot_dir / "market_dart_summary_history.json", market_dart_summary_history)
        write_payload_file(snapshot_dir / "market_analysis_tabs.json", market_analysis_tabs)
        write_payload_file(snapshot_dir / "market_live_context.json", market_live_context)
        write_payload_file(snapshot_dir / "market_data_guide.json", market_data_guide)
        write_payload_file(snapshot_dir / "market_index_panel.json", market_index_panel)
        write_payload_file(snapshot_dir / "market_breadth_detail.json", market_breadth_detail)
        write_payload_file(snapshot_dir / "market_breadth_detail_history.json", market_breadth_detail_history)
        write_payload_file(snapshot_dir / "market_us_macro_panel.json", market_us_macro_panel)
        write_payload_file(snapshot_dir / "market_us_macro_panel_history.json", market_us_macro_panel_history)
        write_payload_file(snapshot_dir / "market_dart_summary.json", market_dart_summary)
        write_payload_file(snapshot_dir / "market_environment_indicators.json", market_environment_indicators)
        write_payload_file(
            snapshot_dir / "market_environment_indicators_manifest.json",
            market_environment_indicators_manifest,
        )
        write_payload_file(
            snapshot_dir / "api_v1_market_environment_indicators.json",
            api_market_environment_indicators,
        )

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
