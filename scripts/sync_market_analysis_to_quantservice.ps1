param(
    [string]$SourceDir = "D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current",
    [string]$TargetDir = "D:\QuantService\service_platform\web\public_data\market_analysis\current"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SourceDir)) {
    throw "Source handoff directory does not exist: $SourceDir"
}

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
Get-ChildItem -Path $SourceDir -Filter *.json | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination (Join-Path $TargetDir $_.Name) -Force
}

Write-Host "Synced QuantMarket handoff files"
Write-Host "Source: $SourceDir"
Write-Host "Target: $TargetDir"
