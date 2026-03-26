param(
    [string]$TaskName = "QuantMarket-Dev-Intraday"
)

$root = "D:\QuantMarket"
$runner = Join-Path $root "scripts\run_dev_intraday_task.cmd"
$taskCmd = "`"$runner`""

schtasks /Create /F /TN $TaskName /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:05 /RI 15 /DU 06:30 /TR $taskCmd
Write-Host "Registered task: $TaskName"
Write-Host "Command: $taskCmd"
