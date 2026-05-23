param(
    [string]$PythonExe = "D:\Quant\venv64\Scripts\python.exe",
    [switch]$SyncToQuantService,
    [switch]$PublishRemote,
    [string]$QuantServiceTargetDir = "D:\QuantService\service_platform\web\public_data\market_analysis\current"
)

$ErrorActionPreference = "Stop"
$root = "D:\QuantMarket"
$logDir = Join-Path $root "reports\market_environment_live\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "us_live_market_environment_$timestamp.log"
$asof = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")
$scriptPath = Join-Path $root "run_us_live_market_environment.py"

$argsList = @(
    $scriptPath,
    "--asof", $asof
)
if ($SyncToQuantService) {
    $argsList += "--sync-to-quantservice"
    $argsList += @("--quantservice-target-dir", $QuantServiceTargetDir)
}
if ($PublishRemote) {
    $argsList += "--publish-remote"
}

"[$(Get-Date -Format s)] Starting QuantMarket US live market environment refresh asof=$asof" | Tee-Object -FilePath $logPath
& $PythonExe @argsList 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "QuantMarket US live market environment refresh failed with exit code $LASTEXITCODE"
}
"[$(Get-Date -Format s)] Completed QuantMarket US live market environment refresh" | Tee-Object -FilePath $logPath -Append
