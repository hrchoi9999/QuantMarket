param(
    [string]$PythonExe = "D:\Quant\venv64\Scripts\python.exe",
    [string]$Market = "KR",
    [string]$AdminSnapshotDir = "D:\QuantMarket\service_platform\web\public_data\admin_market\current",
    [string]$AdminHandoffDir = "D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\admin_market\current",
    [switch]$SyncToQuantService,
    [switch]$PublishRemote,
    [string]$QuantServiceTargetDir = "D:\QuantService\service_platform\web\public_data\market_analysis\current",
    [string]$RemoteProvider = "gcs",
    [string]$RemoteGcsBucket = "quantservice-489808-market-analysis",
    [string]$RemoteBaseUrl = "https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current",
    [string]$RemotePrefix = "market_analysis",
    [string]$RemoteAccessMode = "public",
    [string]$RemoteCredentials = "D:\QuantService\data\gcp\quantmarket-handoff-uploader.json"
)

$ErrorActionPreference = "Stop"
$root = "D:\QuantMarket"
$logDir = Join-Path $root "reports\market_analysis\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "intraday_market_run_$timestamp.log"
$asof = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")
$intradayScriptPath = Join-Path $root "run_intraday_market_snapshot.py"
$marketAnalysisScriptPath = Join-Path $root "run_market_analysis_pipeline.py"
$syncScript = Join-Path $root "scripts\sync_market_analysis_to_quantservice.ps1"
$lockRoot = Join-Path $logDir "locks"
$lockDir = Join-Path $lockRoot "public_publish.lock"
New-Item -ItemType Directory -Force -Path $lockRoot | Out-Null

function Acquire-PublicPublishLock {
    if (Test-Path -LiteralPath $lockDir) {
        $ageMinutes = ((Get-Date) - (Get-Item -LiteralPath $lockDir).LastWriteTime).TotalMinutes
        if ($ageMinutes -lt 90) {
            "[$(Get-Date -Format s)] Skipping QuantMarket intraday public refresh because public publish lock is active age_minutes=$([math]::Round($ageMinutes, 1)) lock=$lockDir" | Tee-Object -FilePath $logPath
            return $false
        }
        Remove-Item -LiteralPath $lockDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $lockDir -ErrorAction Stop | Out-Null
    return $true
}

$lockAcquired = $false

$intradayArgs = @(
    $intradayScriptPath,
    "--market", $Market,
    "--asof", $asof,
    "--admin-snapshot-dir", $AdminSnapshotDir,
    "--admin-handoff-dir", $AdminHandoffDir
)

"[$(Get-Date -Format s)] Starting QuantMarket intraday snapshot asof=$asof market=$Market python=$PythonExe" | Tee-Object -FilePath $logPath
& $PythonExe @intradayArgs 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "QuantMarket intraday snapshot failed with exit code $LASTEXITCODE"
}

try {
$lockAcquired = Acquire-PublicPublishLock
if (-not $lockAcquired) {
    "[$(Get-Date -Format s)] Completed QuantMarket intraday snapshot; public briefing refresh skipped due to active lock" | Tee-Object -FilePath $logPath -Append
    exit 0
}

$marketArgs = @(
    $marketAnalysisScriptPath,
    "--market", $Market,
    "--asof", $asof,
    "--skip-official-collect"
)
if ($PublishRemote) {
    $marketArgs += "--publish-remote"
    if ($RemoteProvider) { $marketArgs += @("--remote-provider", $RemoteProvider) }
    if ($RemoteGcsBucket) { $marketArgs += @("--remote-gcs-bucket", $RemoteGcsBucket) }
    if ($RemoteBaseUrl) { $marketArgs += @("--remote-base-url", $RemoteBaseUrl) }
    if ($RemotePrefix) { $marketArgs += @("--remote-prefix", $RemotePrefix) }
    if ($RemoteAccessMode) { $marketArgs += @("--remote-access-mode", $RemoteAccessMode) }
    if ($RemoteCredentials) { $marketArgs += @("--remote-credentials", $RemoteCredentials) }
}

"[$(Get-Date -Format s)] Refreshing QuantMarket public briefing payload asof=$asof skip_official_collect=true publish_remote=$PublishRemote" | Tee-Object -FilePath $logPath -Append
& $PythonExe @marketArgs 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "QuantMarket public briefing refresh failed with exit code $LASTEXITCODE"
}

if ($SyncToQuantService) {
    "[$(Get-Date -Format s)] Syncing QuantService handoff to $QuantServiceTargetDir" | Tee-Object -FilePath $logPath -Append
    powershell -ExecutionPolicy Bypass -File $syncScript -TargetDir $QuantServiceTargetDir 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "QuantService sync failed with exit code $LASTEXITCODE"
    }
}

"[$(Get-Date -Format s)] Completed QuantMarket intraday snapshot and public briefing refresh" | Tee-Object -FilePath $logPath -Append
} finally {
    if ($lockAcquired -and (Test-Path -LiteralPath $lockDir)) {
        Remove-Item -LiteralPath $lockDir -Recurse -Force
    }
}
