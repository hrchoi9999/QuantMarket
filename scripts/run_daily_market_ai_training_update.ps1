param(
    [string]$Workspace = "D:\QuantMarket",
    [string]$Python = "D:\Quant\venv64\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$script = Join-Path $Workspace "run_daily_market_ai_training_update.py"
& $Python $script
