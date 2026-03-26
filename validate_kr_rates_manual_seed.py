from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.manual_rates import latest_manual_rate_map, validate_manual_rates


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate QuantMarket manual KR rates seed file.")
    p.add_argument("--date", default=None, help="Optional target date in YYYY-MM-DD")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ok, errors = validate_manual_rates(required_date=args.date)
    latest_date, latest = latest_manual_rate_map()
    print(json.dumps({
        "ok": ok,
        "errors": errors,
        "latest_date": latest_date,
        "latest": latest,
    }, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
