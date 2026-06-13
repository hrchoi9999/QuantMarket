from __future__ import annotations

import csv
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .config import DEFAULT_DB_PATH, ROOT_DIR
from .types import ComponentScores, MarketFeatures

CURRENT_CONTEXT_DIR = ROOT_DIR / "service_platform" / "ai_training" / "market_context" / "current"
MODEL_INPUT_CSV = CURRENT_CONTEXT_DIR / "market_model_input_daily_current.csv"
CALIBRATED_FORECAST_CSV = CURRENT_CONTEXT_DIR / "market_forecast_ai_calibrated_daily_current.csv"
DEFAULT_CHART_START_DATE = "2017-01-02"

REFERENCE_INDEX_SPECS = [
    {"index_code": "1001", "label": "KOSPI", "color": "#111827"},
    {"index_code": "2001", "label": "KOSDAQ", "color": "#64748b"},
    {"index_code": "1028", "label": "KOSPI200", "color": "#475569"},
]

STATE_SCALE = [
    {"label": "강하락", "min_score": -3.0, "max_score": -2.0, "tone": "strong_bad"},
    {"label": "하락", "min_score": -2.0, "max_score": -1.0, "tone": "bad"},
    {"label": "약보합", "min_score": -1.0, "max_score": -0.3, "tone": "weak_bad"},
    {"label": "중립", "min_score": -0.3, "max_score": 0.3, "tone": "neutral"},
    {"label": "강보합", "min_score": 0.3, "max_score": 1.0, "tone": "weak_good"},
    {"label": "상승", "min_score": 1.0, "max_score": 2.0, "tone": "good"},
    {"label": "강상승", "min_score": 2.0, "max_score": 3.0, "tone": "strong_good"},
]


def _float(value) -> float | None:
    if value in (None, "", "nan", "NaN"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, ndigits: int = 4) -> float | None:
    return round(value, ndigits) if value is not None else None


def _pct(value: float | None) -> float | None:
    return round(value * 100.0, 2) if value is not None else None


def _clip(value: float, lo: float = -3.0, hi: float = 3.0) -> float:
    return max(lo, min(hi, value))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _append_calendar_carry_forward_points(
    points: list[dict],
    *,
    end_date: str,
    value_keys: tuple[str, ...],
    source_date_key: str,
    point_type: str,
    source_note: str,
) -> None:
    if not points:
        return
    last_date = _parse_date(points[-1].get("date"))
    target_date = _parse_date(end_date)
    if last_date is None or target_date is None or last_date >= target_date:
        return
    source_point = dict(points[-1])
    source_date = source_point.get(source_date_key) or source_point.get("date")
    current = last_date + timedelta(days=1)
    while current <= target_date:
        carry_point = {
            "date": current.isoformat(),
            "point_type": point_type,
            "carry_forward_from": source_date,
            "source_note": source_note,
        }
        for key in value_keys:
            if key in source_point:
                carry_point[key] = source_point[key]
        points.append(carry_point)
        current += timedelta(days=1)


def _gauge_value(score: float | None, *, lo: float = -3.0, hi: float = 3.0) -> float | None:
    if score is None:
        return None
    return round((_clip(score, lo, hi) - lo) / (hi - lo) * 100.0, 1)


def _tone(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 1.0:
        return "good"
    if score >= 0.3:
        return "weak_good"
    if score > -0.3:
        return "neutral"
    if score > -1.0:
        return "weak_bad"
    return "bad"


def _score_band(score: float | None) -> dict:
    if score is None:
        return {
            "label": "데이터 확인 중",
            "level": 0,
            "tone": "unknown",
            "color": "#94a3b8",
            "range_text": "N/A",
            "plain_text": "현재 점수 위치를 판단할 데이터가 부족합니다.",
        }
    if score <= -2.0:
        return {
            "label": "매우 나쁨",
            "level": 1,
            "tone": "strong_bad",
            "color": "#1e3a8a",
            "range_text": "-3.0 ~ -2.0",
            "plain_text": "강한 경계 구간입니다.",
        }
    if score <= -1.0:
        return {
            "label": "나쁨",
            "level": 2,
            "tone": "bad",
            "color": "#2563eb",
            "range_text": "-2.0 ~ -1.0",
            "plain_text": "부담이 우세한 구간입니다.",
        }
    if score <= -0.3:
        return {
            "label": "다소 나쁨",
            "level": 3,
            "tone": "weak_bad",
            "color": "#60a5fa",
            "range_text": "-1.0 ~ -0.3",
            "plain_text": "주의가 필요한 약세 구간입니다.",
        }
    if score < 0.3:
        return {
            "label": "중립",
            "level": 4,
            "tone": "neutral",
            "color": "#94a3b8",
            "range_text": "-0.3 ~ +0.3",
            "plain_text": "뚜렷한 우위가 없는 중립권입니다.",
        }
    if score < 1.0:
        return {
            "label": "다소 좋음",
            "level": 5,
            "tone": "weak_good",
            "color": "#fca5a5",
            "range_text": "+0.3 ~ +1.0",
            "plain_text": "우호 신호가 조금 우세한 구간입니다.",
        }
    if score < 2.0:
        return {
            "label": "좋음",
            "level": 6,
            "tone": "good",
            "color": "#ef4444",
            "range_text": "+1.0 ~ +2.0",
            "plain_text": "우호 신호가 뚜렷한 구간입니다.",
        }
    return {
        "label": "매우 좋음",
        "level": 7,
        "tone": "strong_good",
        "color": "#b91c1c",
        "range_text": "+2.0 ~ +3.0",
        "plain_text": "강한 우호 구간입니다.",
    }


def _score_visual(score: float | None) -> dict:
    band = _score_band(score)
    return {
        "score": _round(score),
        "position_pct": _gauge_value(score),
        "scale_min": -3.0,
        "scale_max": 3.0,
        "neutral_min": -0.3,
        "neutral_max": 0.3,
        "band": band,
        "display_text": f"{_round(score, 2)}점, {band['label']}" if score is not None else band["label"],
        "explain_text": band["plain_text"],
    }


def _status_label(score: float | None, *, positive: str, neutral: str, negative: str) -> str:
    if score is None:
        return "데이터 확인 중"
    if score >= 0.3:
        return positive
    if score <= -0.3:
        return negative
    return neutral


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _latest_model_input_row(asof_date: str) -> dict:
    rows = [
        row for row in _read_csv_rows(MODEL_INPUT_CSV)
        if row.get("market_scope") == "ALL"
        and row.get("forecast_horizon") == "20d"
        and row.get("asof_date")
        and row.get("asof_date") <= asof_date
    ]
    if not rows:
        return {}
    return sorted(rows, key=lambda row: row["asof_date"])[-1]


def _model_input_rows(asof_date: str, *, start_date: str = DEFAULT_CHART_START_DATE) -> list[dict]:
    rows = [
        row for row in _read_csv_rows(MODEL_INPUT_CSV)
        if row.get("market_scope") == "ALL"
        and row.get("forecast_horizon") == "20d"
        and row.get("asof_date")
        and row.get("asof_date") >= start_date
        and row.get("asof_date") <= asof_date
    ]
    return sorted(rows, key=lambda row: row["asof_date"])


def _forecast_rows(asof_date: str) -> list[dict]:
    rows = [
        row for row in _read_csv_rows(CALIBRATED_FORECAST_CSV)
        if row.get("forecast_horizon") == "20d"
        and row.get("asof_date")
        and row.get("asof_date") <= asof_date
        and row.get("market_scope") in {"ALL", "KOSPI", "KOSDAQ"}
    ]
    if not rows:
        return []
    latest_date = sorted({row["asof_date"] for row in rows})[-1]
    return [row for row in rows if row.get("asof_date") == latest_date]


def _avg(values: list[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def _environment_scores(row: dict) -> dict:
    opportunity_score = _avg([
        _float(row.get("global_risk_on_score")),
        _float(row.get("external_asset_risk_on_score")),
        _float(row.get("us_equity_momentum_score")),
        _float(row.get("korea_proxy_momentum_score")),
    ])
    risk_pressure_score = _avg([
        _float(row.get("external_macro_pressure_score")),
        _float(row.get("rate_pressure_score")),
        _float(row.get("commodity_pressure_score")),
        _float(row.get("risk_aversion_score")),
        _float(row.get("credit_stress_score")),
    ])
    net_score = None
    if opportunity_score is not None and risk_pressure_score is not None:
        net_score = _clip(opportunity_score - risk_pressure_score * 0.7)
    return {
        "opportunity_score": opportunity_score,
        "risk_pressure_score": risk_pressure_score,
        "net_score": net_score,
    }


def _latest_intraday_environment(asof: str) -> dict | None:
    if not DEFAULT_DB_PATH.exists():
        return None
    asof_date = asof[:10]
    with sqlite3.connect(str(DEFAULT_DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        latest_asof = con.execute(
            """
            SELECT MAX(asof)
            FROM market_intraday_state
            WHERE market = 'KR'
              AND session_date = ?
              AND asof <= ?
              AND session_status = 'live'
            """,
            (asof_date, asof),
        ).fetchone()[0]
        if not latest_asof:
            return None
        state = con.execute(
            """
            SELECT total_score, risk_score, direction_label, summary_line
            FROM market_intraday_state
            WHERE market = 'KR' AND asof = ?
            """,
            (latest_asof,),
        ).fetchone()
        index_rows = con.execute(
            """
            SELECT index_code, index_name, change_pct
            FROM market_intraday_index_snapshot
            WHERE market = 'KR' AND asof = ?
              AND index_code IN ('1001', '2001', '1028')
            """,
            (latest_asof,),
        ).fetchall()
        fx = con.execute(
            """
            SELECT price, change_pct
            FROM market_intraday_fx_snapshot
            WHERE market = 'KR' AND asof = ? AND series_code = 'USDKRW'
            """,
            (latest_asof,),
        ).fetchone()
        future = con.execute(
            """
            SELECT price, change_pct
            FROM market_intraday_futures_snapshot
            WHERE market = 'KR' AND asof = ? AND contract_code = 'FUT'
            """,
            (latest_asof,),
        ).fetchone()

    index_scores = [
        _clip(float(row["change_pct"]) * 20.0)
        for row in index_rows
        if row["change_pct"] is not None
    ]
    futures_score = _clip(float(future["change_pct"]) * 18.0) if future and future["change_pct"] is not None else None
    fx_score = _clip(-float(fx["change_pct"]) * 80.0) if fx and fx["change_pct"] is not None else None
    risk_score = _float(state["risk_score"]) if state else None
    intraday_score = _avg([_avg(index_scores), futures_score, fx_score, risk_score])
    if intraday_score is None:
        return None
    return {
        "asof": latest_asof,
        "score": _round(_clip(intraday_score), 4),
        "index_avg_score": _round(_avg(index_scores), 4),
        "futures_score": _round(futures_score, 4),
        "fx_score": _round(fx_score, 4),
        "risk_score": _round(risk_score, 4),
        "usdk_rw_change_pct": _round(float(fx["change_pct"]), 6) if fx and fx["change_pct"] is not None else None,
        "kospi_change_pct": _round(
            next((float(row["change_pct"]) for row in index_rows if row["index_code"] == "1001" and row["change_pct"] is not None), None),
            6,
        ),
        "direction_label": state["direction_label"] if state else None,
        "summary_line": state["summary_line"] if state else None,
        "source": "market_intraday_index_snapshot + market_intraday_fx_snapshot + market_intraday_futures_snapshot + market_intraday_state",
    }


def _medium_model_score(row: dict) -> float | None:
    forecast_score = _float(row.get("market_forecast_score"))
    if forecast_score is not None:
        return forecast_score
    return _float(row.get("market_state_score"))


def _short_term_row_score(row: dict) -> float | None:
    values = [
        _float(row.get("futures_direction_score")),
        _float(row.get("derivatives_pressure_score")),
        _float(row.get("smart_money_score_5d")),
    ]
    delta = _float(row.get("market_state_score_delta_5d"))
    if delta is not None:
        values.append(_clip(delta * 2.0))
    score = _avg(values)
    return _clip(score) if score is not None else None


def _build_chart_series(
    rows: list[dict],
    *,
    current_date: str,
    current_environment_score: float | None,
    current_short_score: float | None,
) -> list[dict]:
    specs = [
        {
            "series_id": "financial_environment",
            "label": "금융시장 환경",
            "color": "#2563eb",
            "description": "글로벌 위험선호와 금리·달러·원자재 부담을 합친 환경 점수입니다.",
            "getter": lambda row: _environment_scores(row)["net_score"],
        },
        {
            "series_id": "medium_term_model_outlook",
            "label": "퀀트모델 시장전망",
            "color": "#dc2626",
            "description": "기존 7단계 시장분석과 연결되는 중기 전망 점수입니다. AI 보정 전망값은 핵심지표에서 별도 참고값으로 제공합니다.",
            "source_field_priority": ["market_forecast_score", "market_state_score"],
            "excluded_from_main_chart": ["calibrated_forecast_score"],
            "getter": _medium_model_score,
        },
        {
            "series_id": "short_term_market_condition",
            "label": "단기 시장상황",
            "color": "#16a34a",
            "description": "최근 수급·선물·상태 변화와 오늘 장중 흐름을 반영한 단기 점수입니다.",
            "getter": _short_term_row_score,
        },
    ]
    series = []
    latest_date = rows[-1].get("asof_date") if rows else None
    for spec in specs:
        points = []
        for row in rows:
            value = spec["getter"](row)
            if (
                spec["series_id"] == "financial_environment"
                and row.get("asof_date") == current_date
                and current_environment_score is not None
            ):
                value = current_environment_score
            if (
                spec["series_id"] == "short_term_market_condition"
                and row.get("asof_date") == current_date
                and current_short_score is not None
            ):
                value = current_short_score
            if value is None:
                continue
            points.append({"date": row.get("asof_date"), "value": _round(_clip(value), 4)})
        latest_value = points[-1]["value"] if points else None
        if points and current_date and points[-1]["date"] < current_date:
            has_current_override = (
                spec["series_id"] == "financial_environment"
                and current_environment_score is not None
            ) or (
                spec["series_id"] == "short_term_market_condition"
                and current_short_score is not None
            )
            carry_end_date = current_date
            if has_current_override:
                parsed_current = _parse_date(current_date)
                carry_end_date = (
                    (parsed_current - timedelta(days=1)).isoformat()
                    if parsed_current is not None
                    else current_date
                )
            _append_calendar_carry_forward_points(
                points,
                end_date=carry_end_date,
                value_keys=("value",),
                source_date_key="carry_forward_from",
                point_type="calendar_carry_forward",
                source_note="비거래일에는 직전 기준일의 3축 점수를 이월 표시합니다.",
            )
            if spec["series_id"] == "financial_environment" and current_environment_score is not None:
                latest_value = _round(_clip(current_environment_score), 4)
                if points[-1]["date"] < current_date:
                    points.append({
                        "date": current_date,
                        "value": latest_value,
                        "point_type": "current_intraday_environment",
                        "source_note": "실행시점 장중 지수·환율·선물·리스크를 반영한 금융환경 현재 포인트입니다.",
                    })
                else:
                    points[-1]["value"] = latest_value
                    points[-1]["point_type"] = "current_intraday_environment"
                    points[-1]["source_note"] = "실행시점 장중 지수·환율·선물·리스크를 반영한 금융환경 현재 포인트입니다."
            elif spec["series_id"] == "short_term_market_condition" and current_short_score is not None:
                latest_value = _round(_clip(current_short_score), 4)
                if points[-1]["date"] < current_date:
                    points.append({
                        "date": current_date,
                        "value": latest_value,
                        "point_type": "current_intraday_blend",
                        "source_note": "실행시점 장중 단기값을 반영한 현재 포인트입니다.",
                    })
                else:
                    points[-1]["value"] = latest_value
                    points[-1]["point_type"] = "current_intraday_blend"
                    points[-1]["source_note"] = "실행시점 장중 단기값을 반영한 현재 포인트입니다."
            else:
                latest_value = points[-1]["value"]
        elif points and spec["series_id"] == "financial_environment" and current_environment_score is not None:
            latest_value = _round(_clip(current_environment_score), 4)
            points[-1]["value"] = latest_value
            points[-1]["point_type"] = "current_intraday_environment"
            points[-1]["source_note"] = "실행시점 장중 지수·환율·선물·리스크를 반영한 금융환경 현재 포인트입니다."
        elif points and spec["series_id"] == "short_term_market_condition" and current_short_score is not None:
            latest_value = _round(_clip(current_short_score), 4)
            points[-1]["value"] = latest_value
            points[-1]["point_type"] = "current_intraday_blend"
            points[-1]["source_note"] = "실행시점 장중 단기값을 반영한 현재 포인트입니다."
        series.append({
            "series_id": spec["series_id"],
            "label": spec["label"],
            "color": spec["color"],
            "unit": "score",
            "description": spec["description"],
            "source_field_priority": spec.get("source_field_priority"),
            "excluded_from_main_chart": spec.get("excluded_from_main_chart"),
            "latest_value": latest_value,
            "latest_gauge_value": _gauge_value(latest_value),
            "latest_tone": _tone(latest_value),
            "latest_visual": _score_visual(latest_value),
            "points": points,
        })
    return series


def _latest_intraday_index_quotes(asof: str) -> dict[str, sqlite3.Row]:
    if not DEFAULT_DB_PATH.exists():
        return {}
    asof_date = asof[:10]
    with sqlite3.connect(str(DEFAULT_DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        latest_asof = con.execute(
            """
            SELECT MAX(asof)
            FROM market_intraday_index_snapshot
            WHERE market = 'KR'
              AND session_date = ?
              AND asof <= ?
            """,
            (asof_date, asof),
        ).fetchone()[0]
        if not latest_asof:
            return {}
        rows = con.execute(
            """
            SELECT index_code, index_name, price, change_value, change_pct, source, is_fallback, asof
            FROM market_intraday_index_snapshot
            WHERE market = 'KR'
              AND session_date = ?
              AND asof = ?
            """,
            (asof_date, latest_asof),
        ).fetchall()
    return {row["index_code"]: row for row in rows if row["price"] is not None}


def _reference_index_series(asof: str, *, start_date: str = DEFAULT_CHART_START_DATE) -> list[dict]:
    if not DEFAULT_DB_PATH.exists():
        return []
    asof_date = asof[:10]
    intraday_quotes = _latest_intraday_index_quotes(asof)
    series: list[dict] = []
    with sqlite3.connect(str(DEFAULT_DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        for spec in REFERENCE_INDEX_SPECS:
            db_rows = con.execute(
                """
                SELECT date, close, source
                FROM market_index_daily
                WHERE market = ?
                  AND index_code = ?
                  AND date >= ?
                  AND date <= ?
                  AND close IS NOT NULL
                ORDER BY date
                """,
                ("KR", spec["index_code"], start_date, asof_date),
            ).fetchall()
            if not db_rows:
                continue
            base = float(db_rows[0]["close"])
            if base == 0:
                continue
            points = [
                {
                    "date": row["date"],
                    "value": _round(float(row["close"]) / base * 100.0, 4),
                    "raw_close": _round(float(row["close"]), 4),
                }
                for row in db_rows
            ]
            intraday = intraday_quotes.get(spec["index_code"])
            carry_end_date = asof_date
            if intraday is not None:
                parsed_asof = _parse_date(asof_date)
                carry_end_date = (
                    (parsed_asof - timedelta(days=1)).isoformat()
                    if parsed_asof is not None
                    else asof_date
                )
            _append_calendar_carry_forward_points(
                points,
                end_date=carry_end_date,
                value_keys=("value", "raw_close"),
                source_date_key="source_date",
                point_type="calendar_carry_forward_close",
                source_note="비거래일에는 직전 거래일 종가를 기준지수 선에 이월 표시합니다.",
            )
            if intraday is not None and points[-1]["date"] < asof_date:
                intraday_price = float(intraday["price"])
                points.append({
                    "date": asof_date,
                    "value": _round(intraday_price / base * 100.0, 4),
                    "raw_close": _round(intraday_price, 4),
                    "change_value": _round(_float(intraday["change_value"]), 4),
                    "change_pct": _round(_float(intraday["change_pct"]), 6),
                    "point_type": "current_intraday_quote",
                    "source": intraday["source"],
                    "quote_asof": intraday["asof"],
                    "is_fallback": bool(intraday["is_fallback"]),
                    "source_note": "실행시점 장중 지수값을 기준지수 선의 현재 포인트로 표시합니다.",
                })
            latest = points[-1]
            series.append({
                "series_id": f"reference_index_{spec['label'].lower()}",
                "label": f"{spec['label']} 기준지수",
                "color": spec["color"],
                "unit": "indexed_100",
                "base_date": db_rows[0]["date"],
                "base_value": 100.0,
                "latest_date": latest["date"],
                "latest_value": latest["value"],
                "latest_close": latest["raw_close"],
                "latest_change_value": latest.get("change_value"),
                "latest_change_pct": latest.get("change_pct"),
                "latest_point_type": latest.get("point_type", "daily_close"),
                "quote_asof": latest.get("quote_asof"),
                "source": latest.get("source") or db_rows[-1]["source"],
                "description": f"{spec['label']} 실제 종가를 {db_rows[0]['date']}=100으로 환산한 기준선입니다.",
                "points": points,
            })
    return series


def _build_composite_chart(
    rows: list[dict],
    *,
    asof: str,
    asof_date: str,
    current_environment_score: float | None,
    current_short_score: float | None,
) -> dict:
    return {
        "graph_type": "multi_line",
        "title": "시장 흐름 3축 추이",
        "subtitle": "금융시장 환경, 퀀트모델 시장전망, 단기 시장상황을 같은 축에서 비교합니다.",
        "score_range": {"min": -3.0, "max": 3.0},
        "neutral_band": {"min": -0.3, "max": 0.3, "label": "중립권"},
        "start_date": DEFAULT_CHART_START_DATE,
        "period_label": f"{DEFAULT_CHART_START_DATE} 이후",
        "history_policy": "full_available_history_from_2017_01_02",
        "x_axis": {"type": "date", "label": "기준일"},
        "y_axis": {"type": "score", "label": "점수", "min": -3.0, "max": 3.0},
        "secondary_y_axis": {"type": "indexed_100", "label": "주가지수 기준선", "base": 100.0},
        "series": _build_chart_series(
            rows,
            current_date=asof_date,
            current_environment_score=current_environment_score,
            current_short_score=current_short_score,
        ),
        "reference_indices": _reference_index_series(asof),
        "rendering_hint": {
            "preferred": "one_chart_three_colored_lines",
            "show_legend": True,
            "show_latest_marker": True,
            "show_neutral_band": True,
            "show_reference_indices": True,
            "reference_indices_axis": "secondary_y_axis",
            "show_current_intraday_point": True,
            "show_current_environment_point": True,
            "show_current_reference_index_point": True,
            "carry_forward_daily_axes_to_current_date": True,
            "avoid_three_separate_bar_charts": True,
        },
    }


def _build_environment_axis(row: dict, intraday_environment: dict | None = None) -> dict:
    env = _environment_scores(row)
    opportunity_score = env["opportunity_score"]
    risk_pressure_score = env["risk_pressure_score"]
    daily_net_score = env["net_score"]
    net_score = intraday_environment.get("score") if intraday_environment else daily_net_score

    return {
        "axis_id": "financial_environment",
        "title": "금융시장 환경",
        "subtitle": "기회와 리스크",
        "graph_type": "dual_gauge",
        "score": _round(net_score),
        "gauge_value": _gauge_value(net_score),
        "score_visual": _score_visual(net_score),
        "status_label": _status_label(net_score, positive="기회 우위", neutral="혼재", negative="리스크 우위"),
        "tone": _tone(net_score),
        "opportunity_score": _round(opportunity_score),
        "risk_pressure_score": _round(risk_pressure_score),
        "daily_score": _round(daily_net_score),
        "today": intraday_environment or {
            "enabled": False,
            "source_note": "장중 금융환경 참고값이 없어 일별 확정값을 표시합니다.",
        },
        "key_numbers": [
            {"label": "VIX", "value": _round(_float(row.get("vix_level")), 2), "unit": "pt"},
            {"label": "미국 10년 금리", "value": _round(_float(row.get("us_10y_rate")), 2), "unit": "%"},
            {"label": "달러지수", "value": _round(_float(row.get("dxy_level")), 2), "unit": "pt"},
            {"label": "WTI", "value": _round(_float(row.get("wti_level")), 2), "unit": "USD"},
        ],
        "basis": [
            f"위험선호 점수 {_round(opportunity_score, 2)}",
            f"매크로/금리/원자재 부담 {_round(risk_pressure_score, 2)}",
            f"커버리지 {row.get('coverage_quality_label') or '확인 중'}",
        ],
        "source": "market_model_input_daily_current.csv",
        "source_asof_date": row.get("asof_date"),
    }


def _build_medium_axis(scores: ComponentScores, forecasts: list[dict]) -> dict:
    forecast_items = []
    for scope in ("ALL", "KOSPI", "KOSDAQ"):
        row = next((item for item in forecasts if item.get("market_scope") == scope), None)
        if not row:
            continue
        forecast_items.append({
            "market_scope": scope,
            "forecast_horizon": "20d",
            "predicted_forward_return_pct": _pct(_float(row.get("predicted_forward_return"))),
            "forecast_score": _round(_float(row.get("calibrated_forecast_score"))),
            "forecast_label": row.get("calibrated_forecast_label"),
            "confidence_score": _round(_float(row.get("calibration_confidence_score")), 3),
        })
    return {
        "axis_id": "medium_term_model_outlook",
        "title": "퀀트모델 시장 전망",
        "subtitle": "1~6개월 흐름",
        "graph_type": "seven_step_bar",
        "state_label": scores.state_label,
        "score": scores.total_score,
        "gauge_value": _gauge_value(scores.total_score),
        "score_visual": _score_visual(scores.total_score),
        "tone": _tone(scores.total_score),
        "scale": STATE_SCALE,
        "components": [
            {"label": "추세", "score": scores.trend_score, "gauge_value": _gauge_value(scores.trend_score)},
            {"label": "확산", "score": scores.breadth_score, "gauge_value": _gauge_value(scores.breadth_score)},
            {"label": "변동성", "score": scores.risk_score, "gauge_value": _gauge_value(scores.risk_score)},
            {"label": "방어자산", "score": scores.defensive_flow_score, "gauge_value": _gauge_value(scores.defensive_flow_score)},
        ],
        "forecast_20d": forecast_items,
        "basis": [
            f"7단계 현재값: {scores.state_label}({scores.total_score})",
            "추세, 확산, 변동성, 방어자산 선호를 종합한 중기 모델 판단입니다.",
        ],
        "source": "market_component_scores + market_forecast_ai_calibrated_daily_current.csv",
    }


def _short_term_score(features: MarketFeatures, intraday: dict | None) -> float:
    intraday_score = _float((intraday or {}).get("total_score"))
    close_score = _clip((features.kospi_1d_ret * 0.6 + features.kosdaq_1d_ret * 0.4) * 120.0)
    week_score = _clip(
        (features.kospi_5d_ret * 18.0)
        + (features.kosdaq_5d_ret * 12.0)
        + (features.kospi_1d_ret * 10.0)
    )
    if intraday_score is None:
        return round(_clip(close_score * 0.55 + week_score * 0.45), 4)
    if (intraday or {}).get("session_status") == "live":
        return round(_clip(week_score * 0.20 + intraday_score * 0.80), 4)
    return round(_clip(week_score * 0.45 + intraday_score * 0.55), 4)


def _build_short_axis(features: MarketFeatures, bridge: dict | None) -> dict:
    intraday = (bridge or {}).get("intraday") or {}
    score = _short_term_score(features, intraday)
    return {
        "axis_id": "short_term_market_condition",
        "title": "단기 시장 상황",
        "subtitle": "최근 1주일 + 오늘",
        "graph_type": "linear_gauge",
        "score": score,
        "gauge_value": _gauge_value(score),
        "score_visual": _score_visual(score),
        "status_label": _status_label(score, positive="단기 강세", neutral="혼조", negative="단기 약세"),
        "tone": _tone(score),
        "weekly": {
            "kospi_5d_ret_pct": _pct(features.kospi_5d_ret),
            "kosdaq_5d_ret_pct": _pct(features.kosdaq_5d_ret),
            "kospi_1d_ret_pct": _pct(features.kospi_1d_ret),
        },
        "today": {
            "enabled": bool(intraday),
            "session_status": intraday.get("session_status"),
            "intraday_state_label": intraday.get("intraday_state_label") or intraday.get("direction_label"),
            "intraday_score": _round(_float(intraday.get("total_score"))),
            "close_score": _round(_clip((features.kospi_1d_ret * 0.6 + features.kosdaq_1d_ret * 0.4) * 120.0)),
            "futures_change_pct": _pct(_float((intraday.get("futures") or {}).get("change_pct"))),
            "foreigner_net": _round(_float((intraday.get("flow") or {}).get("foreigner_net")), 1),
            "program_total_net": _round(_float((intraday.get("flow") or {}).get("program_total_net")), 1),
        },
        "basis": [
            f"코스피 1주일 {_pct(features.kospi_5d_ret)}%",
            f"코스닥 1주일 {_pct(features.kosdaq_5d_ret)}%",
            intraday.get("summary_line") or "장중 데이터는 확인 가능한 경우에만 반영합니다.",
        ],
        "source": "market_features_hourly + market_intraday_state",
    }


def _forecast_item(forecasts: list[dict], scope: str) -> dict | None:
    return next((item for item in forecasts if item.get("market_scope") == scope), None)


def _build_key_indicators(model_row: dict, forecasts: list[dict], features: MarketFeatures, short_axis: dict, env_axis: dict, medium_axis: dict) -> dict:
    all_forecast = _forecast_item(forecasts, "ALL")
    kospi_forecast = _forecast_item(forecasts, "KOSPI")
    kosdaq_forecast = _forecast_item(forecasts, "KOSDAQ")
    return {
        "title": "핵심 판단 숫자",
        "groups": [
            {
                "group_id": "financial_environment",
                "title": "금융시장 환경",
                "items": [
                    {"label": "환경 종합점수", "value": env_axis.get("score"), "unit": "score", "tone": env_axis.get("tone")},
                    {"label": "환경 점수 위치", "value": env_axis.get("score_visual", {}).get("band", {}).get("label"), "unit": "label", "tone": env_axis.get("tone")},
                    {"label": "기회 점수", "value": env_axis.get("opportunity_score"), "unit": "score"},
                    {"label": "리스크 부담", "value": env_axis.get("risk_pressure_score"), "unit": "score"},
                    {"label": "VIX", "value": _round(_float(model_row.get("vix_level")), 2), "unit": "pt"},
                    {"label": "미국 10년 금리", "value": _round(_float(model_row.get("us_10y_rate")), 2), "unit": "%"},
                    {"label": "달러지수", "value": _round(_float(model_row.get("dxy_level")), 2), "unit": "pt"},
                    {"label": "WTI", "value": _round(_float(model_row.get("wti_level")), 2), "unit": "USD"},
                    {"label": "하이일드 스프레드", "value": _round(_float(model_row.get("hy_spread")), 2), "unit": "%p"},
                ],
            },
            {
                "group_id": "medium_term_model_outlook",
                "title": "퀀트모델 시장전망",
                "items": [
                    {"label": "7단계 시장상태", "value": medium_axis.get("state_label"), "unit": "label", "tone": medium_axis.get("tone")},
                    {"label": "시장상태 점수", "value": medium_axis.get("score"), "unit": "score"},
                    {"label": "시장상태 위치", "value": medium_axis.get("score_visual", {}).get("band", {}).get("label"), "unit": "label", "tone": medium_axis.get("tone")},
                    {"label": "ALL 20거래일 전망 참고값", "value": _pct(_float((all_forecast or {}).get("predicted_forward_return"))), "unit": "%"},
                    {"label": "KOSPI 20거래일 전망 참고값", "value": _pct(_float((kospi_forecast or {}).get("predicted_forward_return"))), "unit": "%"},
                    {"label": "KOSDAQ 20거래일 전망 참고값", "value": _pct(_float((kosdaq_forecast or {}).get("predicted_forward_return"))), "unit": "%"},
                    {"label": "전망 신뢰도", "value": _round(_float((all_forecast or {}).get("calibration_confidence_score")), 3), "unit": "score"},
                    {"label": "시장 변동성", "value": _round(_float(model_row.get("market_vol_20d")), 3), "unit": "score"},
                    {"label": "낙폭 부담", "value": _round(_float(model_row.get("drawdown_risk_score")), 3), "unit": "score"},
                ],
            },
            {
                "group_id": "short_term_market_condition",
                "title": "단기 시장상황",
                "items": [
                    {"label": "단기 종합점수", "value": short_axis.get("score"), "unit": "score", "tone": short_axis.get("tone")},
                    {"label": "단기 점수 위치", "value": short_axis.get("score_visual", {}).get("band", {}).get("label"), "unit": "label", "tone": short_axis.get("tone")},
                    {"label": "코스피 1주일", "value": short_axis.get("weekly", {}).get("kospi_5d_ret_pct"), "unit": "%"},
                    {"label": "코스닥 1주일", "value": short_axis.get("weekly", {}).get("kosdaq_5d_ret_pct"), "unit": "%"},
                    {"label": "오늘 장중 상태", "value": short_axis.get("today", {}).get("intraday_state_label"), "unit": "label"},
                    {"label": "선물 변화율", "value": short_axis.get("today", {}).get("futures_change_pct"), "unit": "%"},
                    {"label": "외국인 순매수", "value": short_axis.get("today", {}).get("foreigner_net"), "unit": "억원"},
                    {"label": "프로그램 순매수", "value": short_axis.get("today", {}).get("program_total_net"), "unit": "억원"},
                    {"label": "20일선 위 종목", "value": _pct(features.above_20dma_ratio), "unit": "%"},
                ],
            },
        ],
    }


def _consideration(label: str, body: str, tone: str, basis: list[str]) -> dict:
    return {"label": label, "body": body, "tone": tone, "basis": basis}


def _build_investment_considerations(env_axis: dict, medium_axis: dict, short_axis: dict, model_row: dict) -> list[dict]:
    items = []
    if env_axis.get("score") is not None and env_axis["score"] < -0.3:
        items.append(_consideration(
            "환경 리스크 확인",
            "금리·달러·원자재 부담이 기회 요인보다 우세하면 공격적인 해석보다 위험 점검을 우선합니다.",
            "warning",
            [f"환경점수 {env_axis.get('score')}", f"리스크 부담 {env_axis.get('risk_pressure_score')}"],
        ))
    elif env_axis.get("score") is not None and env_axis["score"] > 0.3:
        items.append(_consideration(
            "환경 기회 요인 확인",
            "글로벌 위험선호가 살아 있으면 국내 모델 신호가 회복될 때 반응 여지가 커집니다.",
            "positive",
            [f"환경점수 {env_axis.get('score')}", f"기회 점수 {env_axis.get('opportunity_score')}"],
        ))
    else:
        items.append(_consideration(
            "환경은 혼재",
            "기회와 리스크가 엇갈릴 때는 한 방향 결론보다 지표 변화 방향을 함께 봅니다.",
            "neutral",
            [f"VIX {_round(_float(model_row.get('vix_level')), 2)}", f"미국 10년 {_round(_float(model_row.get('us_10y_rate')), 2)}%"],
        ))

    if medium_axis.get("score") is not None and medium_axis["score"] >= 1.0:
        items.append(_consideration(
            "중기 모델은 우호적",
            "중기 모델 점수가 상승권이면 단기 조정은 추세 훼손 여부를 확인하는 방식으로 봅니다.",
            "positive",
            [f"7단계 {medium_axis.get('state_label')}", f"시장상태 점수 {medium_axis.get('score')}"],
        ))
    elif medium_axis.get("score") is not None and medium_axis["score"] <= -1.0:
        items.append(_consideration(
            "중기 모델은 방어 우위",
            "중기 모델 점수가 하락권이면 반등보다 리스크 축소 여부를 먼저 확인합니다.",
            "warning",
            [f"7단계 {medium_axis.get('state_label')}", f"시장상태 점수 {medium_axis.get('score')}"],
        ))
    else:
        items.append(_consideration(
            "중기 모델은 중립권",
            "중립권에서는 종목 확산, 변동성, 수급이 다음 방향을 정하는 핵심 확인 지표입니다.",
            "neutral",
            [f"7단계 {medium_axis.get('state_label')}", f"시장상태 점수 {medium_axis.get('score')}"],
        ))

    if short_axis.get("score") is not None and short_axis["score"] <= -0.3:
        items.append(_consideration(
            "단기 약세는 별도 확인",
            "중기 전망과 별개로 최근 1주일과 오늘 수급이 약하면 진입·추격 판단은 보수적으로 봅니다.",
            "warning",
            [f"단기점수 {short_axis.get('score')}", f"장중상태 {short_axis.get('today', {}).get('intraday_state_label')}"],
        ))
    elif short_axis.get("score") is not None and short_axis["score"] >= 0.3:
        items.append(_consideration(
            "단기 흐름은 우호적",
            "단기 흐름이 중기 모델과 같은 방향이면 시장 해석의 신뢰도가 높아집니다.",
            "positive",
            [f"단기점수 {short_axis.get('score')}", f"코스피 1주일 {short_axis.get('weekly', {}).get('kospi_5d_ret_pct')}%"],
        ))
    else:
        items.append(_consideration(
            "단기 흐름은 혼조",
            "방향성이 약할 때는 선물, 외국인, 프로그램 수급이 개선되는지 확인합니다.",
            "neutral",
            [f"단기점수 {short_axis.get('score')}", f"외국인 {short_axis.get('today', {}).get('foreigner_net')}억원"],
        ))
    return items


def _series_visual(chart: dict, series_id: str) -> dict:
    series = next((item for item in chart.get("series", []) if item.get("series_id") == series_id), None)
    return (series or {}).get("latest_visual") or _score_visual(None)


def build_market_state_composite(
    *,
    features: MarketFeatures,
    scores: ComponentScores,
    state_intraday_bridge: dict | None,
) -> dict:
    model_row = _latest_model_input_row(features.asof_date)
    model_rows = _model_input_rows(features.asof_date)
    forecasts = _forecast_rows(features.asof_date)
    intraday_environment = _latest_intraday_environment(features.asof)
    short_axis = _build_short_axis(features, state_intraday_bridge)
    axes = [_build_environment_axis(model_row, intraday_environment), _build_medium_axis(scores, forecasts), short_axis]
    chart = _build_composite_chart(
        model_rows,
        asof=features.asof,
        asof_date=features.asof_date,
        current_environment_score=(intraday_environment or {}).get("score"),
        current_short_score=short_axis.get("score"),
    )
    indicators = _build_key_indicators(model_row, forecasts, features, short_axis, axes[0], axes[1])
    considerations = _build_investment_considerations(axes[0], axes[1], short_axis, model_row)
    env_visual = _series_visual(chart, "financial_environment")
    medium_visual = _series_visual(chart, "medium_term_model_outlook")
    short_visual = _series_visual(chart, "short_term_market_condition")
    return {
        "enabled": True,
        "schema_version": "market_state_composite.v2",
        "title": "시장 상태 종합판",
        "subtitle": "세 개의 막대가 아니라 세 개의 흐름선을 한 그래프에서 비교합니다.",
        "display_policy": {
            "preferred_layout": "multi_line_chart_with_indicator_panel",
            "mobile_layout": "chart_first_then_indicator_cards",
            "primary_visual": "one_chart_three_colored_lines",
            "keep_legacy_state_intraday_bridge": True,
            "avoid_three_separate_bar_charts": True,
        },
        "market": features.market,
        "asof": features.asof,
        "composite_chart": chart,
        "key_indicators": indicators,
        "investment_considerations": considerations,
        "axes": axes,
        "summary": {
            "environment": axes[0]["status_label"],
            "medium_term": scores.state_label,
            "short_term": axes[2]["status_label"],
            "one_line": f"환경은 {axes[0]['status_label']}, 중기 모델은 {scores.state_label}, 단기는 {axes[2]['status_label']}로 나누어 해석합니다.",
            "visual_line": (
                f"금융시장 환경은 {env_visual['display_text']}, "
                f"퀀트모델 시장전망은 {medium_visual['display_text']}, "
                f"단기 시장상황은 {short_visual['display_text']}입니다."
            ),
        },
        "score_scale_guide": {
            "min": -3.0,
            "max": 3.0,
            "neutral_band": "-0.3 ~ +0.3",
            "bands": [
                {"label": "매우 나쁨", "range": "-3.0 ~ -2.0", "tone": "strong_bad", "color": "#1e3a8a"},
                {"label": "나쁨", "range": "-2.0 ~ -1.0", "tone": "bad", "color": "#2563eb"},
                {"label": "다소 나쁨", "range": "-1.0 ~ -0.3", "tone": "weak_bad", "color": "#60a5fa"},
                {"label": "중립", "range": "-0.3 ~ +0.3", "tone": "neutral", "color": "#94a3b8"},
                {"label": "다소 좋음", "range": "+0.3 ~ +1.0", "tone": "weak_good", "color": "#fca5a5"},
                {"label": "좋음", "range": "+1.0 ~ +2.0", "tone": "good", "color": "#ef4444"},
                {"label": "매우 좋음", "range": "+2.0 ~ +3.0", "tone": "strong_good", "color": "#b91c1c"},
            ],
            "rendering_hint": "Use a horizontal score ruler or colored legend so users can see whether each latest value is good, neutral, or bad.",
        },
        "interpretation_rules": [
            "금융시장 환경은 기회/리스크 배경이며, 모델 상태를 직접 덮어쓰지 않습니다.",
            "퀀트모델 시장 전망은 기존 7단계 시장분석을 유지합니다.",
            "단기 시장 상황은 최근 1주일과 오늘 장중 흐름을 보여 주는 참고 레이어입니다.",
        ],
    }
