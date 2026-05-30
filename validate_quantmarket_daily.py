from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.config import (  # noqa: E402
    DEFAULT_DB_PATH,
    QUANTSERVICE_HANDOFF_DIR,
    REMOTE_BASE_URL,
    SNAPSHOT_DIR,
)
from validate_quant_model_handoff import DEFAULT_HANDOFF_DIR, validate_handoff  # noqa: E402
from validate_quantservice_handoff import validate_quantservice_handoff  # noqa: E402

REMOTE_SMOKE_FILES = [
    "quantservice_market_manifest.json",
    "quantservice_market_today.json",
    "api_v1_market_analysis_page.json",
    "quantservice_market_environment_indicators.json",
]
REMOTE_CORE_ASOF_FILES = {
    "quantservice_market_manifest.json",
    "quantservice_market_today.json",
    "api_v1_market_analysis_page.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the daily QuantMarket analysis release.")
    parser.add_argument("--expected-asof", required=True, help="Expected market forecast asof date, YYYY-MM-DD.")
    parser.add_argument("--market", default="KR")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--snapshot-dir", default=str(SNAPSHOT_DIR))
    parser.add_argument("--quantservice-handoff-dir", default=str(QUANTSERVICE_HANDOFF_DIR))
    parser.add_argument("--quant-model-handoff-dir", default=str(DEFAULT_HANDOFF_DIR))
    parser.add_argument("--check-remote", action="store_true")
    parser.add_argument("--remote-base-url", default=REMOTE_BASE_URL)
    return parser.parse_args()


def _validate_market_db(db_path: Path, market: str) -> dict:
    errors: list[str] = []
    if not db_path.exists():
        return {"ok": False, "db_path": str(db_path), "errors": [f"missing db: {db_path}"]}

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        latest = con.execute(
            """
            SELECT market, asof, state_label, state_score, prev_state_label, state_change_direction
            FROM market_state_history
            WHERE market = ?
            ORDER BY asof DESC
            LIMIT 1
            """,
            (market,),
        ).fetchone()
        if latest is None:
            errors.append(f"missing latest market_state_history row for market={market}")
            latest_dict = None
        else:
            latest_dict = dict(latest)

        counts = {}
        for table in [
            "market_index_daily",
            "market_fx_daily",
            "market_rates_daily",
            "market_features_hourly",
            "market_component_scores",
            "market_state_history",
            "market_analysis_payload",
        ]:
            try:
                counts[table] = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                if counts[table] <= 0:
                    errors.append(f"{table} is empty")
            except sqlite3.Error as exc:
                errors.append(f"{table}: {exc}")
    finally:
        con.close()

    return {
        "ok": not errors,
        "db_path": str(db_path),
        "latest_state": latest_dict,
        "table_counts": counts,
        "errors": errors,
    }


def _validate_snapshots(snapshot_dir: Path) -> dict:
    required = [
        "market_analysis_manifest.json",
        "market_analysis_summary.json",
        "market_analysis_detail.json",
        "market_analysis_today_bridge.json",
        "market_analysis_tabs.json",
    ]
    errors = [f"missing snapshot file: {snapshot_dir / name}" for name in required if not (snapshot_dir / name).exists()]
    return {
        "ok": not errors,
        "snapshot_dir": str(snapshot_dir),
        "required_files": required,
        "errors": errors,
    }


def _fetch_remote_json(url: str, timeout: int = 20) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "QuantMarketDailyValidator/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def _validate_remote(base_url: str, expected_local_asof: str | None, market: str) -> dict:
    errors: list[str] = []
    files: dict[str, dict] = {}
    clean_base = base_url.rstrip("/")
    for filename in REMOTE_SMOKE_FILES:
        url = f"{clean_base}/{filename}"
        try:
            payload = _fetch_remote_json(url)
            files[filename] = {
                "url": url,
                "asof": payload.get("asof"),
                "market": payload.get("market"),
            }
            if payload.get("market") and payload.get("market") != market:
                errors.append(f"{filename}: remote market {payload.get('market')} != {market}")
            if (
                filename in REMOTE_CORE_ASOF_FILES
                and expected_local_asof
                and payload.get("asof")
                and payload.get("asof") != expected_local_asof
            ):
                errors.append(f"{filename}: remote asof {payload.get('asof')} != local asof {expected_local_asof}")
        except Exception as exc:
            errors.append(f"{filename}: remote fetch failed: {type(exc).__name__}: {exc}")
    return {"ok": not errors, "base_url": clean_base, "files": files, "errors": errors}


def main() -> None:
    args = parse_args()
    errors: list[str] = []

    market_db = _validate_market_db(Path(args.db_path), args.market)
    snapshots = _validate_snapshots(Path(args.snapshot_dir))
    quantservice = validate_quantservice_handoff(Path(args.quantservice_handoff_dir))
    quant_model = validate_handoff(Path(args.quant_model_handoff_dir), expected_asof=args.expected_asof)

    for section_name, section in [
        ("market_db", market_db),
        ("snapshots", snapshots),
        ("quantservice_handoff", quantservice),
        ("quant_model_handoff", quant_model),
    ]:
        if not section.get("ok", False):
            for error in section.get("errors", []):
                errors.append(f"{section_name}: {error}")

    remote = None
    if args.check_remote:
        remote = _validate_remote(args.remote_base_url, quantservice.get("asof"), args.market)
        if not remote["ok"]:
            for error in remote["errors"]:
                errors.append(f"remote: {error}")

    result = {
        "ok": not errors,
        "expected_asof": args.expected_asof,
        "market": args.market,
        "checks": {
            "market_db": market_db,
            "snapshots": snapshots,
            "quantservice_handoff": quantservice,
            "quant_model_handoff": quant_model,
            "remote": remote,
        },
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
