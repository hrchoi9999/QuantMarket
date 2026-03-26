from __future__ import annotations

from .analytics import sample_recent_dates
from .db import upsert_many


def seed_sample_official_data(con, *, market: str, asof_date: str, updated_at: str) -> None:
    dates = sample_recent_dates(asof_date, count=90)
    index_rows = []
    fx_rows = []
    rate_rows = []

    kospi_base = 2520.0
    kosdaq_base = 810.0
    kospi200_base = 335.0
    usdkrw_base = 1365.0
    cd91_base = 3.48
    ktb3y_base = 2.92

    for i, date in enumerate(dates):
        drift = i - len(dates) / 2
        swing = ((i % 6) - 2.5) * 3.2
        kospi_close = kospi_base + drift * 4.8 + swing
        kosdaq_close = kosdaq_base + drift * 1.35 + (((i + 2) % 5) - 2.0) * 2.8
        kospi200_close = kospi200_base + drift * 0.72 + (((i + 1) % 4) - 1.5) * 1.1
        for code, name, close in (
            ("1001", "KOSPI", kospi_close),
            ("2001", "KOSDAQ", kosdaq_close),
            ("1028", "KOSPI200", kospi200_close),
        ):
            index_rows.append(
                {
                    "market": market,
                    "index_code": code,
                    "index_name": name,
                    "date": date,
                    "open": round(close * 0.996, 4),
                    "high": round(close * 1.004, 4),
                    "low": round(close * 0.994, 4),
                    "close": round(close, 4),
                    "volume": round(1000000 + i * 1200, 4),
                    "value": round(close * 1000000, 4),
                    "source": "sample_seed",
                    "updated_at": updated_at,
                }
            )

        fx_rows.append(
            {
                "market": market,
                "series_code": "USDKRW",
                "series_name": "USD/KRW",
                "date": date,
                "close": round(usdkrw_base - drift * 1.1 + ((i % 3) - 1.0) * 2.0, 4),
                "source": "sample_seed",
                "updated_at": updated_at,
            }
        )

        for code, name, value in (
            ("BASE", "Base Rate", cd91_base + drift * 0.0018),
            ("CD91", "CD 91D", cd91_base + drift * 0.0030 + ((i % 4) - 1.5) * 0.003),
            ("KTB3Y", "KTB 3Y", ktb3y_base + drift * 0.0025 + ((i % 5) - 2.0) * 0.002),
            ("KTB5Y", "KTB 5Y", ktb3y_base + 0.18 + drift * 0.0020),
        ):
            rate_rows.append(
                {
                    "market": market,
                    "rate_code": code,
                    "rate_name": name,
                    "date": date,
                    "value": round(value, 4),
                    "source": "sample_seed",
                    "updated_at": updated_at,
                }
            )

    upsert_many(
        con,
        table="market_index_daily",
        columns=["market", "index_code", "index_name", "date", "open", "high", "low", "close", "volume", "value", "source", "updated_at"],
        rows=index_rows,
        conflict_columns=["market", "index_code", "date"],
    )
    upsert_many(
        con,
        table="market_fx_daily",
        columns=["market", "series_code", "series_name", "date", "close", "source", "updated_at"],
        rows=fx_rows,
        conflict_columns=["market", "series_code", "date"],
    )
    upsert_many(
        con,
        table="market_rates_daily",
        columns=["market", "rate_code", "rate_name", "date", "value", "source", "updated_at"],
        rows=rate_rows,
        conflict_columns=["market", "rate_code", "date"],
    )
