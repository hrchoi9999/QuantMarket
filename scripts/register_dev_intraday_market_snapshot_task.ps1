param(
    [string]$TaskName = "QuantMarket-Dev-Intraday"
)

$root = "D:\QuantMarket"
$runner = Join-Path $root "scripts\run_dev_intraday_market_snapshot.ps1"
$taskCmd = "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`" -SyncToQuantService -PublishRemote"

schtasks /Create /F /TN $TaskName /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:00 /RI 30 /DU 06:40 /TR $taskCmd
Write-Host "Registered task: $TaskName"
Write-Host "Command: $taskCmd"
Write-Host "Schedule: MON-FRI 09:00~15:40 KST, every 30 minutes"
