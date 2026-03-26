param(
    [string]$TaskName = "QuantMarket-Dev-Intraday"
)

schtasks /Delete /F /TN $TaskName
Write-Host "Unregistered task: $TaskName"
