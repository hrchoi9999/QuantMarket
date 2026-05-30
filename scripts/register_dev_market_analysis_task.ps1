param(
    [string]$TaskName = "QuantMarket-Dev-Hourly",
    [string]$PythonExe = "D:\Quant\venv64\Scripts\python.exe",
    [switch]$SeedSample,
    [switch]$SyncToQuantService,
    [switch]$PublishRemote,
    [switch]$RemoteDryRun,
    [string]$QuantServiceTargetDir = "D:\QuantService\service_platform\web\public_data\market_analysis\current",
    [string]$RemoteProvider = "gcs",
    [string]$RemoteGcsBucket = "quantservice-489808-market-analysis",
    [string]$RemoteBaseUrl = "https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current",
    [string]$RemotePrefix = "market_analysis",
    [string]$RemoteAccessMode = "public",
    [string]$RemoteCredentials = "D:\QuantService\data\gcp\quantmarket-handoff-uploader.json"
)

$root = "D:\QuantMarket"
$runner = Join-Path $root "scripts\run_dev_market_analysis.ps1"
if ($PublishRemote -and $SyncToQuantService) {
    $publishRunner = Join-Path $root "scripts\run_dev_market_analysis_publish_remote.ps1"
    $taskCmd = "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$publishRunner`""
} else {
    $parts = @(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-WindowStyle", "Hidden",
        "-File", "`"$runner`"",
        "-PythonExe", "`"$PythonExe`""
    )
    if ($SeedSample) {
        $parts += "-SeedSample"
    }
    if ($SyncToQuantService) {
        $parts += "-SyncToQuantService"
        if ($QuantServiceTargetDir -ne "D:\QuantService\service_platform\web\public_data\market_analysis\current") {
            $parts += @("-QuantServiceTargetDir", "`"$QuantServiceTargetDir`"")
        }
    }
    if ($PublishRemote) {
        $parts += "-PublishRemote"
        if ($RemoteDryRun) { $parts += "-RemoteDryRun" }
        if ($RemoteProvider -ne "gcs") { $parts += @("-RemoteProvider", "`"$RemoteProvider`"") }
        if ($RemoteGcsBucket -ne "quantservice-489808-market-analysis") { $parts += @("-RemoteGcsBucket", "`"$RemoteGcsBucket`"") }
        if ($RemoteBaseUrl -ne "https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current") { $parts += @("-RemoteBaseUrl", "`"$RemoteBaseUrl`"") }
        if ($RemotePrefix -ne "market_analysis") { $parts += @("-RemotePrefix", "`"$RemotePrefix`"") }
        if ($RemoteAccessMode -ne "public") { $parts += @("-RemoteAccessMode", "`"$RemoteAccessMode`"") }
        if ($RemoteCredentials -ne "D:\QuantService\data\gcp\quantmarket-handoff-uploader.json") { $parts += @("-RemoteCredentials", "`"$RemoteCredentials`"") }
    }
    $taskCmd = ($parts -join " ")
}

schtasks /Create /F /TN $TaskName /SC HOURLY /MO 1 /ST 00:05 /TR $taskCmd
Write-Host "Registered task: $TaskName"
Write-Host "Command: $taskCmd"
