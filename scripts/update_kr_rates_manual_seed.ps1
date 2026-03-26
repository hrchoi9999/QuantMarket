param(
    [string]$Date,
    [double]$Base,
    [double]$Cd91,
    [double]$Ktb3y,
    [double]$Ktb5y,
    [string]$PythonExe = "D:\Quant\venv64\Scripts\python.exe"
)

if (-not $Date) {
    $Date = (Get-Date).ToString('yyyy-MM-dd')
}

& $PythonExe "D:\QuantMarket\update_kr_rates_manual_seed.py" --date $Date --base $Base --cd91 $Cd91 --ktb3y $Ktb3y --ktb5y $Ktb5y
if ($LASTEXITCODE -ne 0) {
    throw "Failed to update manual rate seed"
}
