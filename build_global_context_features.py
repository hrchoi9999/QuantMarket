from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.global_context_db import DEFAULT_GLOBAL_CONTEXT_DB_PATH  # noqa: E402
from quantmarket_market.global_context_features import build_and_store_global_context  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build QuantMarket global context daily features.")
    parser.add_argument("--db-path", default=str(DEFAULT_GLOBAL_CONTEXT_DB_PATH))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "service_platform" / "global_context" / "current"),
    )
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_and_store_global_context(
        db_path=Path(args.db_path),
        output_dir=Path(args.output_dir),
        start_date=args.start,
        end_date=args.end,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
