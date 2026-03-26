from __future__ import annotations

import math
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .db import upsert_many
from .types import ComponentScores, MarketFeatures, StateHistory

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


def format_kst(dt: datetime) -> str:
    value = dt.astimezone(KST) if dt.tzinfo else dt.replace(tzinfo=KST)
    return value.isoformat(timespec="seconds")
STATE_BUCKETS = [
    (2.0, "강상승"),
    (1.0, "상승"),
    (0.3, "강보합"),
    (-0.3, "중립"),
    (-1.0, "약보합"),
    (-2.0, "하락"),
    (-999.0, "강하락"),
]


def _clamp(value: float, lo: float = -3.0, hi: float = 3.0) -> float:
    return max(lo, min(hi, float(value)))


def _safe_pct(curr: float, prev: float) -> float:
    if prev in (0.0, None):
        return 0.0
    return float(curr / prev - 1.0)


def _rolling_returns(series: list[float], lag: int) -> float:
    if len(series) <= lag:
        return 0.0
    return _safe_pct(series[-1], series[-(lag + 1)])


def _realized_vol_20d(closes: list[float]) -> float:
    if len(closes) < 21:
        return 0.0
    rets = [_safe_pct(closes[i], closes[i - 1]) for i in range(1, len(closes))]
    window = rets[-20:]
    mean = sum(window) / len(window)
    var = sum((x - mean) ** 2 for x in window) / len(window)
    return math.sqrt(var)


def _drawdown(series: list[float], window: int) -> float:
    if not series:
        return 0.0
    values = series[-window:] if len(series) >= window else series
    peak = max(values)
    if peak == 0:
        return 0.0
    return float(values[-1] / peak - 1.0)


def _latest_series(
    con: sqlite3.Connection,
    *,
    table: str,
    code_column: str,
    value_column: str,
    code: str,
    market: str,
    asof_date: str,
    limit: int = 120,
) -> list[sqlite3.Row]:
    cur = con.execute(
        f"""
        SELECT date, {value_column} AS value
        FROM {table}
        WHERE market = ? AND {code_column} = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
        """,
        (market, code, asof_date, limit),
    )
    return list(reversed(cur.fetchall()))


def _market_breadth_proxies(kospi: list[float], kosdaq: list[float], kospi200: list[float]) -> dict[str, float]:
    if not kospi or not kosdaq or not kospi200:
        return {
            "above_20dma_ratio": 0.5,
            "above_60dma_ratio": 0.5,
            "adv_dec_ratio": 1.0,
            "new_high_count": 0.0,
            "new_low_count": 0.0,
            "breadth_universe_count": 0,
            "breadth_proxy_flag": 1,
        }

    latest = [kospi[-1], kosdaq[-1], kospi200[-1]]
    ma20 = [sum(series[-20:]) / min(20, len(series)) for series in (kospi, kosdaq, kospi200)]
    ma60 = [sum(series[-60:]) / min(60, len(series)) for series in (kospi, kosdaq, kospi200)]
    above20 = sum(1 for curr, ma in zip(latest, ma20) if curr >= ma) / 3.0
    above60 = sum(1 for curr, ma in zip(latest, ma60) if curr >= ma) / 3.0
    adv_count = sum(1 for series in (kospi, kosdaq, kospi200) if len(series) >= 2 and series[-1] >= series[-2])
    dec_count = 3 - adv_count
    highs = sum(1 for series in (kospi, kosdaq, kospi200) if len(series) >= 20 and series[-1] >= max(series[-20:]))
    lows = sum(1 for series in (kospi, kosdaq, kospi200) if len(series) >= 20 and series[-1] <= min(series[-20:]))
    return {
        "above_20dma_ratio": above20,
        "above_60dma_ratio": above60,
        "adv_dec_ratio": (adv_count + 1) / (dec_count + 1),
        "new_high_count": float(highs),
        "new_low_count": float(lows),
        "breadth_universe_count": 3,
        "breadth_proxy_flag": 1,
    }


def build_market_features(
    con: sqlite3.Connection,
    *,
    market: str,
    asof: str,
    created_at: str,
    quant_inputs: dict | None = None,
) -> MarketFeatures:
    asof_date = asof[:10]
    quant_inputs = quant_inputs or {}
    kospi_rows = _latest_series(con, table="market_index_daily", code_column="index_code", value_column="close", code="1001", market=market, asof_date=asof_date)
    kosdaq_rows = _latest_series(con, table="market_index_daily", code_column="index_code", value_column="close", code="2001", market=market, asof_date=asof_date)
    kospi200_rows = _latest_series(con, table="market_index_daily", code_column="index_code", value_column="close", code="1028", market=market, asof_date=asof_date)
    usdkrw_rows = _latest_series(con, table="market_fx_daily", code_column="series_code", value_column="close", code="USDKRW", market=market, asof_date=asof_date)
    cd91_rows = _latest_series(con, table="market_rates_daily", code_column="rate_code", value_column="value", code="CD91", market=market, asof_date=asof_date)
    ktb3y_rows = _latest_series(con, table="market_rates_daily", code_column="rate_code", value_column="value", code="KTB3Y", market=market, asof_date=asof_date)

    kospi = [float(row["value"]) for row in kospi_rows]
    kosdaq = [float(row["value"]) for row in kosdaq_rows]
    kospi200 = [float(row["value"]) for row in kospi200_rows]
    usdkrw = [float(row["value"]) for row in usdkrw_rows]
    cd91 = [float(row["value"]) for row in cd91_rows]
    ktb3y = [float(row["value"]) for row in ktb3y_rows]

    if len(kospi) < 61 or len(kosdaq) < 61 or len(kospi200) < 21:
        raise ValueError("Not enough source history to compute P1 market features.")

    breadth = quant_inputs if quant_inputs.get("breadth_proxy_flag") == 0 else _market_breadth_proxies(kospi, kosdaq, kospi200)
    return MarketFeatures(
        market=market,
        asof=asof,
        asof_date=asof_date,
        kospi_1d_ret=_rolling_returns(kospi, 1),
        kospi_5d_ret=_rolling_returns(kospi, 5),
        kospi_20d_ret=_rolling_returns(kospi, 20),
        kospi_60d_ret=_rolling_returns(kospi, 60),
        kosdaq_1d_ret=_rolling_returns(kosdaq, 1),
        kosdaq_5d_ret=_rolling_returns(kosdaq, 5),
        kosdaq_20d_ret=_rolling_returns(kosdaq, 20),
        kosdaq_60d_ret=_rolling_returns(kosdaq, 60),
        kospi200_20d_ret=_rolling_returns(kospi200, 20),
        usdkrw_20d_ret=_rolling_returns(usdkrw, 20) if len(usdkrw) >= 21 else 0.0,
        rate_cd91_20d_chg=(cd91[-1] - cd91[-21]) if len(cd91) >= 21 else 0.0,
        rate_ktb3y_20d_chg=(ktb3y[-1] - ktb3y[-21]) if len(ktb3y) >= 21 else 0.0,
        above_20dma_ratio=float(breadth["above_20dma_ratio"]),
        above_60dma_ratio=float(breadth["above_60dma_ratio"]),
        adv_dec_ratio=float(breadth["adv_dec_ratio"]),
        new_high_count=float(breadth["new_high_count"]),
        new_low_count=float(breadth["new_low_count"]),
        breadth_universe_count=int(breadth.get("breadth_universe_count", 0)),
        realized_vol_20d=_realized_vol_20d(kospi),
        drawdown_5d=_drawdown(kospi, 5),
        drawdown_20d=_drawdown(kospi, 20),
        bond_20d_ret=float(quant_inputs.get("bond_20d_ret", max(-_rolling_returns(ktb3y, 20), -0.2) if len(ktb3y) >= 21 else 0.0)),
        gold_20d_ret=float(quant_inputs.get("gold_20d_ret", 0.0)),
        inverse_20d_ret=float(quant_inputs.get("inverse_20d_ret", max(-_rolling_returns(kospi200, 20), -0.2))),
        breadth_proxy_flag=int(breadth.get("breadth_proxy_flag", 1)),
        defensive_proxy_flag=int(quant_inputs.get("defensive_proxy_flag", 1)),
        regime_3m_score=quant_inputs.get("regime_3m_score"),
        created_at=created_at,
    )


def _state_label(score: float) -> str:
    for threshold, label in STATE_BUCKETS:
        if score >= threshold:
            return label
    return "강하락"


def _score_to_direction(current: float, previous: float | None) -> str:
    if previous is None:
        return "unchanged"
    if current > previous + 1e-9:
        return "stronger"
    if current < previous - 1e-9:
        return "weaker"
    return "unchanged"


def score_market_state(features: MarketFeatures, created_at: str) -> ComponentScores:
    regime_boost = ((features.regime_3m_score or 0.5) - 0.5) * 0.6
    trend = _clamp(
        8.0 * features.kospi_20d_ret
        + 5.0 * features.kospi_60d_ret
        + 6.0 * features.kosdaq_20d_ret
        + 4.0 * features.kosdaq_60d_ret
        + 5.0 * features.kospi200_20d_ret
        + 3.0 * features.kospi_5d_ret
        + regime_boost
    )
    breadth = _clamp(
        (features.above_20dma_ratio - 0.5) * 3.2
        + (features.above_60dma_ratio - 0.5) * 2.8
        + math.log(max(features.adv_dec_ratio, 1e-6)) * 0.9
        + (features.new_high_count - features.new_low_count) / max(features.breadth_universe_count, 1) * 10.0
    )
    risk = _clamp(
        -features.realized_vol_20d * 55.0
        + features.drawdown_5d * 18.0
        + features.drawdown_20d * 10.0
    )
    defensive = _clamp(
        -features.usdkrw_20d_ret * 15.0
        -features.inverse_20d_ret * 4.5
        -features.bond_20d_ret * 6.0
        -features.gold_20d_ret * 5.0
        -features.rate_cd91_20d_chg * 1.5
        -features.rate_ktb3y_20d_chg * 1.2
    )
    total = _clamp(trend * 0.35 + breadth * 0.30 + risk * 0.20 + defensive * 0.15)
    return ComponentScores(
        market=features.market,
        asof=features.asof,
        trend_score=round(trend, 4),
        breadth_score=round(breadth, 4),
        risk_score=round(risk, 4),
        defensive_flow_score=round(defensive, 4),
        total_score=round(total, 4),
        state_label=_state_label(total),
        created_at=created_at,
    )


def load_previous_state(con: sqlite3.Connection, *, market: str, asof: str) -> sqlite3.Row | None:
    cur = con.execute(
        """
        SELECT asof, state_label, state_score
        FROM market_state_history
        WHERE market = ? AND asof < ?
        ORDER BY asof DESC
        LIMIT 1
        """,
        (market, asof),
    )
    return cur.fetchone()


def build_state_history(con: sqlite3.Connection, *, scores: ComponentScores, created_at: str) -> StateHistory:
    prev = load_previous_state(con, market=scores.market, asof=scores.asof)
    prev_label = prev["state_label"] if prev else None
    prev_score = float(prev["state_score"]) if prev else None
    return StateHistory(
        market=scores.market,
        asof=scores.asof,
        state_label=scores.state_label,
        state_score=scores.total_score,
        prev_state_label=prev_label,
        state_change_direction=_score_to_direction(scores.total_score, prev_score),
        created_at=created_at,
    )


def persist_feature_bundle(con: sqlite3.Connection, *, features: MarketFeatures, scores: ComponentScores, state: StateHistory) -> None:
    upsert_many(
        con,
        table="market_features_hourly",
        columns=list(asdict(features).keys()),
        rows=[features.to_record()],
        conflict_columns=["market", "asof"],
    )
    upsert_many(
        con,
        table="market_component_scores",
        columns=list(asdict(scores).keys()),
        rows=[scores.to_record()],
        conflict_columns=["market", "asof"],
    )
    upsert_many(
        con,
        table="market_state_history",
        columns=list(asdict(state).keys()),
        rows=[state.to_record()],
        conflict_columns=["market", "asof"],
    )


def normalize_asof_kst(asof: str | None, now: datetime | None = None) -> str:
    current = now.astimezone(KST) if now and now.tzinfo else (now.replace(tzinfo=KST) if now else datetime.now(KST))
    if not asof:
        return current.isoformat(timespec="seconds")
    parsed = datetime.fromisoformat(asof.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    parsed = parsed.astimezone(KST)
    if parsed > current:
        parsed = current
    return parsed.isoformat(timespec="seconds")


def default_asof(now: datetime | None = None) -> str:
    return normalize_asof_kst(None, now=now)


def sample_recent_dates(asof_date: str, count: int = 80) -> list[str]:
    end = datetime.strptime(asof_date, "%Y-%m-%d").date()
    return [(end - timedelta(days=offset)).isoformat() for offset in range(count - 1, -1, -1)]


def pick_top_signals(features: MarketFeatures, scores: ComponentScores) -> tuple[list[str], list[str]]:
    positives: list[tuple[float, str]] = []
    warnings: list[tuple[float, str]] = []

    if features.kospi_20d_ret > 0:
        positives.append((features.kospi_20d_ret, "코스피 1개월 상승 흐름"))
    else:
        warnings.append((abs(features.kospi_20d_ret), "코스피 1개월 약세"))
    if features.kosdaq_20d_ret > 0:
        positives.append((features.kosdaq_20d_ret, "코스닥 추세 회복"))
    else:
        warnings.append((abs(features.kosdaq_20d_ret), "코스닥 약세"))
    if features.above_20dma_ratio >= 0.55:
        positives.append((features.above_20dma_ratio, "20일선 위 종목 비율 개선"))
    else:
        warnings.append((1.0 - features.above_20dma_ratio, "20일선 위 종목 비율 낮음"))
    if features.above_60dma_ratio >= 0.55:
        positives.append((features.above_60dma_ratio, "60일선 위 종목 비율 양호"))
    else:
        warnings.append((1.0 - features.above_60dma_ratio, "60일선 위 종목 비율 낮음"))
    if features.usdkrw_20d_ret > 0.01:
        warnings.append((features.usdkrw_20d_ret, "달러 강세"))
    else:
        positives.append((abs(features.usdkrw_20d_ret), "환율 안정"))
    if features.realized_vol_20d > 0.02:
        warnings.append((features.realized_vol_20d, "변동성 확대"))
    else:
        positives.append((0.02 - features.realized_vol_20d, "변동성 안정"))
    if scores.defensive_flow_score < -0.3:
        warnings.append((abs(scores.defensive_flow_score), "방어자산 선호"))

    positives = [text for _, text in sorted(positives, reverse=True)[:3]]
    warnings = [text for _, text in sorted(warnings, reverse=True)[:3]]
    return positives, warnings


def component_summary(name: str, score: float, features: MarketFeatures) -> str:
    if name == "trend":
        if score >= 0.5:
            return "코스피와 코스닥의 중기 수익률 흐름이 모두 우호적입니다."
        if score <= -0.5:
            return "중기 추세가 약하고 코스닥 회복도 아직 제한적입니다."
        return "대형주는 버티지만 추세 확산은 아직 뚜렷하지 않습니다."
    if name == "breadth":
        if score >= 0.5:
            return "상승 흐름이 개별 종목으로 비교적 넓게 확산되고 있습니다."
        if score <= -0.5:
            return "지수 대비 내부 종목 확산은 약한 편입니다."
        return "시장 건강도는 중립 수준으로 해석됩니다."
    if name == "risk":
        if score >= 0.5:
            return "최근 변동성이 과도하지 않아 흔들림은 비교적 안정적입니다."
        if score <= -0.5:
            return "최근 변동성과 낙폭이 커져 방어적 해석이 필요합니다."
        return "변동성은 관리 가능한 수준이지만 경계는 필요합니다."
    if score <= -0.5:
        return "달러와 방어 ETF가 강해 위험선호가 약해진 상태입니다."
    if score >= 0.5:
        return "방어 ETF 상대강도가 높지 않아 주식 선호가 상대적으로 유지됩니다."
    return "방어자산 선호도는 중립권입니다."
