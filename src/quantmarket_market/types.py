from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MarketFeatures:
    market: str
    asof: str
    asof_date: str
    kospi_1d_ret: float
    kospi_5d_ret: float
    kospi_20d_ret: float
    kospi_60d_ret: float
    kosdaq_1d_ret: float
    kosdaq_5d_ret: float
    kosdaq_20d_ret: float
    kosdaq_60d_ret: float
    kospi200_20d_ret: float
    usdkrw_20d_ret: float
    rate_cd91_20d_chg: float
    rate_ktb3y_20d_chg: float
    above_20dma_ratio: float
    above_60dma_ratio: float
    adv_dec_ratio: float
    new_high_count: float
    new_low_count: float
    breadth_universe_count: int
    realized_vol_20d: float
    drawdown_5d: float
    drawdown_20d: float
    bond_20d_ret: float
    gold_20d_ret: float
    inverse_20d_ret: float
    breadth_proxy_flag: int
    defensive_proxy_flag: int
    regime_3m_score: float | None
    created_at: str

    def to_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ComponentScores:
    market: str
    asof: str
    trend_score: float
    breadth_score: float
    risk_score: float
    defensive_flow_score: float
    total_score: float
    state_label: str
    created_at: str

    def to_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StateHistory:
    market: str
    asof: str
    state_label: str
    state_score: float
    prev_state_label: str | None
    state_change_direction: str
    created_at: str

    def to_record(self) -> dict:
        return asdict(self)
