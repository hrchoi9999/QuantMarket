from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.ai_briefs import build_ai_brief_prompt, upsert_ai_brief
from quantmarket_market.payloads import write_payload_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update manual AI brief lines for market analysis handoff.")
    parser.add_argument("--market", default="KR")
    parser.add_argument("--asof", required=True)
    parser.add_argument("--provider", required=True, choices=["chatgpt", "gemini"])
    parser.add_argument("--line", action="append", dest="lines", default=[], help="One summary line. Repeat up to 4 times.")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--out", default=None, help="Optional output file for the merged AI briefs payload.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = upsert_ai_brief(
        market=args.market,
        asof=args.asof,
        provider=args.provider,
        summary_lines=args.lines,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        source=args.source,
    )
    if args.out:
        write_payload_file(Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
