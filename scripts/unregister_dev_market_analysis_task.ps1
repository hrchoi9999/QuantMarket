param(
    [string]$TaskName = "QuantMarket-Dev-Hourly"
)

schtasks /Delete /F /TN $TaskName
