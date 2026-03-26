param(
    [string]$PythonExe = "D:\Quant\venv64\Scripts\python.exe",
    [string]$Market = "KR",
    [string]$AdminSnapshotDir = "D:\QuantMarket\service_platform\web\public_data\admin_market\current",
    [string]$AdminHandoffDir = "D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\admin_market\current"
)

$ErrorActionPreference = "Stop"
$root = "D:\QuantMarket"
$logDir = Join-Path $root "reports\market_analysis\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "intraday_market_run_$timestamp.log"
$asof = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")
$scriptPath = Join-Path $root "run_intraday_market_snapshot.py"

$args = @(
    $scriptPath,
    "--market", $Market,
    "--asof", $asof,
    "--admin-snapshot-dir", $AdminSnapshotDir,
    "--admin-handoff-dir", $AdminHandoffDir
)

"[$(Get-Date -Format s)] Starting QuantMarket intraday snapshot asof=$asof market=$Market python=$PythonExe" | Tee-Object -FilePath $logPath
& $PythonExe @args 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "QuantMarket intraday snapshot failed with exit code $LASTEXITCODE"
}

"[$(Get-Date -Format s)] Completed QuantMarket intraday snapshot" | Tee-Object -FilePath $logPath -Append
