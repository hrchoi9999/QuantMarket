# QuantService Market Analysis Integration Prep (2026-03-23)

## Goal
- QuantMarket must remain the producer of market-analysis data.
- QuantService must remain the UI/API consumer.
- Local development should support `hourly collect -> analyze -> handoff generate -> optional QuantService sync`.

## What QuantMarket now publishes
Source snapshot directory:
- `D:\QuantMarket\service_platform\web\public_data\current`

QuantService handoff directory:
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current`

Generated handoff files:
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`
- `api_v1_market_analysis_home.json`
- `api_v1_market_analysis_page.json`
- `api_v1_market_analysis_summary.json`
- `api_v1_market_analysis_detail.json`
- `api_v1_market_analysis_today_bridge.json`

## Recommended QuantService consumption points
Current QuantService read pattern was reviewed in:
- `D:\QuantService\service_platform\web\app.py`
- `D:\QuantService\service_platform\web\data_provider.py`
- `D:\QuantService\service_platform\shared\constants.py`

Recommended page slots:
- Home hero: `quantservice_market_home.json#hero`
- Home top signals: `quantservice_market_home.json#top_signals`
- Today recommendation market bridge: `quantservice_market_today.json#market_bridge`
- Market analysis header: `quantservice_market_page.json#header_state`
- Market analysis component cards: `quantservice_market_page.json#component_cards`
- Market analysis signal lists: `quantservice_market_page.json#signal_lists`

## Local development sync option
QuantMarket provides a sync helper script:
- `D:\QuantMarket\scripts\sync_market_analysis_to_quantservice.ps1`

Default target path for local QuantService development:
- `D:\QuantService\service_platform\web\public_data\market_analysis\current`

Example:
```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\sync_market_analysis_to_quantservice.ps1
```

## Local hourly runner option
The dev runner now supports optional handoff sync after each pipeline run.

Example:
```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\run_dev_market_analysis.ps1 -SyncToQuantService
```

Scheduler registration example:
```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\register_dev_market_analysis_task.ps1 -SyncToQuantService
```

## Validation
Validate handoff files:
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quantservice_handoff.py
```

## Important note
This preparation work creates QuantService-ready handoff artifacts and sync tooling inside QuantMarket.
It does not yet patch QuantService routes/templates directly. The next implementation step inside QuantService is to add:
- market-analysis file loader
- `/api/v1/market-analysis/*` routes
- template placement for home / today / market-analysis pages
