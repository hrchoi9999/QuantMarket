param(
    [string]$TaskName = "QuantMarket-Dev-US-Live"
)

schtasks /Delete /F /TN $TaskName
Write-Host "Unregistered task: $TaskName"
