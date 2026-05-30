param(
    [switch]$SeedSample,
    [switch]$SyncToQuantService,
    [switch]$PublishRemote,
    [switch]$RemoteDryRun,
    [string]$PythonExe = "D:\Quant\venv64\Scripts\python.exe",
    [string]$Market = "KR",
    [string]$QuantServiceTargetDir = "D:\QuantService\service_platform\web\public_data\market_analysis\current",
    [string]$RemoteProvider = "gcs",
    [string]$RemoteGcsBucket = "",
    [string]$RemoteBaseUrl = "",
    [string]$RemotePrefix = "market_analysis",
    [string]$RemoteAccessMode = "public",
    [string]$RemoteCredentials = "",
    [switch]$SkipQuantModelHandoff,
    [string]$QuantModelHandoffExpectedAsof = ""
)

$ErrorActionPreference = "Stop"
$root = "D:\QuantMarket"
$logDir = Join-Path $root "reports\market_analysis\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "market_analysis_run_$timestamp.log"
$asof = (Get-Date).ToString("yyyy-MM-ddTHH:00:00zzz")
$scriptPath = Join-Path $root "run_market_analysis_pipeline.py"
$syncScript = Join-Path $root "scripts\sync_market_analysis_to_quantservice.ps1"
$quantModelHandoffScript = Join-Path $root "run_quant_model_handoff_fast.py"
$lockRoot = Join-Path $logDir "locks"
$lockDir = Join-Path $lockRoot "public_publish.lock"
New-Item -ItemType Directory -Force -Path $lockRoot | Out-Null

function Acquire-PublicPublishLock {
    if (Test-Path -LiteralPath $lockDir) {
        $ageMinutes = ((Get-Date) - (Get-Item -LiteralPath $lockDir).LastWriteTime).TotalMinutes
        if ($ageMinutes -lt 90) {
            "[$(Get-Date -Format s)] Skipping QuantMarket full hourly pipeline because public publish lock is active age_minutes=$([math]::Round($ageMinutes, 1)) lock=$lockDir" | Tee-Object -FilePath $logPath
            return $false
        }
        Remove-Item -LiteralPath $lockDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $lockDir -ErrorAction Stop | Out-Null
    return $true
}

$lockAcquired = $false
try {
$lockAcquired = Acquire-PublicPublishLock
if (-not $lockAcquired) {
    exit 0
}

$args = @($scriptPath, "--market", $Market, "--asof", $asof)
if ($SeedSample) {
    $args += "--seed-sample"
}
if ($PublishRemote) {
    $args += "--publish-remote"
    if ($RemoteProvider) { $args += @("--remote-provider", $RemoteProvider) }
    if ($RemoteGcsBucket) { $args += @("--remote-gcs-bucket", $RemoteGcsBucket) }
    if ($RemoteBaseUrl) { $args += @("--remote-base-url", $RemoteBaseUrl) }
    if ($RemotePrefix) { $args += @("--remote-prefix", $RemotePrefix) }
    if ($RemoteAccessMode) { $args += @("--remote-access-mode", $RemoteAccessMode) }
    if ($RemoteCredentials) { $args += @("--remote-credentials", $RemoteCredentials) }
    if ($RemoteDryRun) { $args += "--remote-dry-run" }
}

"[$(Get-Date -Format s)] Starting QuantMarket full hourly pipeline asof=$asof market=$Market seed_sample=$SeedSample sync_to_quantservice=$SyncToQuantService publish_remote=$PublishRemote python=$PythonExe" | Tee-Object -FilePath $logPath
& $PythonExe @args 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "QuantMarket pipeline failed with exit code $LASTEXITCODE"
}

if ($SyncToQuantService) {
    "[$(Get-Date -Format s)] Syncing QuantService handoff to $QuantServiceTargetDir" | Tee-Object -FilePath $logPath -Append
    powershell -ExecutionPolicy Bypass -File $syncScript -TargetDir $QuantServiceTargetDir 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "QuantService sync failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipQuantModelHandoff) {
    $handoffExpectedAsof = $QuantModelHandoffExpectedAsof
    if (-not $handoffExpectedAsof) {
        $forecastPath = Join-Path $root "service_platform\ai_training\market_context\current\market_forecast_ai_calibrated_daily_current.csv"
        if (-not (Test-Path -LiteralPath $forecastPath)) {
            throw "Quant model handoff source forecast is missing: $forecastPath"
        }
        $latestForecastRow = Import-Csv -LiteralPath $forecastPath |
            Where-Object { $_.asof_date } |
            Sort-Object asof_date |
            Select-Object -Last 1
        if (-not $latestForecastRow) {
            throw "Quant model handoff source forecast has no asof_date rows: $forecastPath"
        }
        $handoffExpectedAsof = $latestForecastRow.asof_date
    }

    "[$(Get-Date -Format s)] Refreshing Quant model handoff expected_asof=$handoffExpectedAsof" | Tee-Object -FilePath $logPath -Append
    & $PythonExe $quantModelHandoffScript --expected-asof $handoffExpectedAsof 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Quant model handoff fast refresh failed with exit code $LASTEXITCODE"
    }
}

"[$(Get-Date -Format s)] Completed QuantMarket full hourly pipeline" | Tee-Object -FilePath $logPath -Append
} finally {
    if ($lockAcquired -and (Test-Path -LiteralPath $lockDir)) {
        Remove-Item -LiteralPath $lockDir -Recurse -Force
    }
}
