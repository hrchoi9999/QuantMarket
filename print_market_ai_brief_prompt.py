from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.ai_briefs import build_ai_brief_prompt
from quantmarket_market.config import QUANTSERVICE_HANDOFF_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a 4-line AI brief prompt from the latest market-analysis handoff.")
    parser.add_argument("--handoff-dir", default=str(QUANTSERVICE_HANDOFF_DIR))
    return parser.parse_args()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    args = parse_args()
    handoff_dir = Path(args.handoff_dir)
    summary = _load_json(handoff_dir / "api_v1_market_analysis_summary.json").get("data", {})
    detail = _load_json(handoff_dir / "api_v1_market_analysis_detail.json").get("data", {})
    prompt = build_ai_brief_prompt(
        market=summary.get("market") or detail.get("market") or "KR",
        asof=summary.get("asof") or detail.get("asof") or "",
        summary=summary,
        detail=detail,
    )
    print(prompt)


if __name__ == "__main__":
    main()
