from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.manual_rates import latest_manual_rate_map, upsert_manual_rates, validate_manual_rates


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update QuantMarket manual KR rates seed file.")
    p.add_argument("--date", required=True, help="Target date in YYYY-MM-DD")
    p.add_argument("--base", type=float, required=True, help="Base rate value")
    p.add_argument("--cd91", type=float, required=True, help="CD 91D rate value")
    p.add_argument("--ktb3y", type=float, required=True, help="KTB 3Y rate value")
    p.add_argument("--ktb5y", type=float, required=True, help="KTB 5Y rate value")
    p.add_argument("--source", default="manual_seed", help="Source label")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    upsert_manual_rates(
        target_date=args.date,
        values={
            "BASE": args.base,
            "CD91": args.cd91,
            "KTB3Y": args.ktb3y,
            "KTB5Y": args.ktb5y,
        },
        source=args.source,
    )
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
