param(
    [string]$TaskName = "QuantMarket-Dev-US-Live"
)

$root = "D:\QuantMarket"
$runner = Join-Path $root "scripts\run_dev_us_live_market_environment.ps1"
$taskCmd = "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`" -SyncToQuantService -PublishRemote"

schtasks /Create /F /TN $TaskName /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 20:00 /RI 30 /DU 10:00 /TR $taskCmd
Write-Host "Registered task: $TaskName"
Write-Host "Command: $taskCmd"
Write-Host "Schedule: MON-FRI 20:00~06:00 KST, every 30 minutes"
