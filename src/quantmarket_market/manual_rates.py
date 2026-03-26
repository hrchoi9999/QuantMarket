from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .config import MANUAL_RATE_SEED_PATH

RATE_NAME_MAP = {
    "BASE": "Base Rate",
    "CD91": "CD 91D",
    "KTB3Y": "KTB 3Y",
    "KTB5Y": "KTB 5Y",
}
RATE_CODES = tuple(RATE_NAME_MAP.keys())


@dataclass
class ManualRateRow:
    date: str
    rate_code: str
    rate_name: str
    value: float
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date,
            "rate_code": self.rate_code,
            "rate_name": self.rate_name,
            "value": f"{self.value:.6f}".rstrip("0").rstrip("."),
            "source": self.source,
        }


def load_manual_rate_rows(path: Path | None = None) -> list[ManualRateRow]:
    path = path or MANUAL_RATE_SEED_PATH
    if not path.exists():
        return []
    out: list[ManualRateRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            value = (row.get("value") or "").strip()
            if not row.get("date") or not row.get("rate_code") or not value:
                continue
            out.append(
                ManualRateRow(
                    date=row["date"].strip(),
                    rate_code=row["rate_code"].strip(),
                    rate_name=(row.get("rate_name") or RATE_NAME_MAP.get(row["rate_code"].strip()) or row["rate_code"].strip()).strip(),
                    value=float(value),
                    source=(row.get("source") or "manual_seed").strip(),
                )
            )
    return out


def write_manual_rate_rows(rows: Iterable[ManualRateRow], path: Path | None = None) -> None:
    path = path or MANUAL_RATE_SEED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda x: (x.date, x.rate_code))
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["date", "rate_code", "rate_name", "value", "source"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())


def upsert_manual_rates(*, target_date: str, values: dict[str, float], source: str = "manual_seed", path: Path | None = None) -> list[ManualRateRow]:
    existing = load_manual_rate_rows(path)
    keep = [row for row in existing if row.date != target_date]
    new_rows = [
        ManualRateRow(
            date=target_date,
            rate_code=code,
            rate_name=RATE_NAME_MAP[code],
            value=float(values[code]),
            source=source,
        )
        for code in RATE_CODES
        if code in values
    ]
    merged = keep + new_rows
    write_manual_rate_rows(merged, path)
    return merged


def latest_manual_rate_map(path: Path | None = None) -> tuple[str | None, dict[str, float]]:
    rows = load_manual_rate_rows(path)
    if not rows:
        return None, {}
    latest_date = max(row.date for row in rows)
    latest = {row.rate_code: row.value for row in rows if row.date == latest_date}
    return latest_date, latest


def validate_manual_rates(*, required_date: str | None = None, path: Path | None = None) -> tuple[bool, list[str]]:
    rows = load_manual_rate_rows(path)
    if not rows:
        return False, ["manual rate seed is empty"]
    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        grouped.setdefault(row.date, {})[row.rate_code] = row.value

    target_date = required_date or max(grouped)
    values = grouped.get(target_date, {})
    errors: list[str] = []
    for code in RATE_CODES:
        if code not in values:
            errors.append(f"missing {code} for {target_date}")
        elif values[code] <= 0:
            errors.append(f"non-positive {code} for {target_date}")
    return len(errors) == 0, errors
