$root = "D:\QuantMarket"
$runner = Join-Path $root "scripts\run_dev_market_analysis.ps1"

powershell -ExecutionPolicy Bypass -File $runner `
    -PythonExe "D:\Quant\venv64\Scripts\python.exe" `
    -Market "KR" `
    -SyncToQuantService `
    -PublishRemote `
    -RemoteProvider "gcs" `
    -RemoteGcsBucket "quantservice-489808-market-analysis" `
    -RemoteBaseUrl "https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current" `
    -RemoteAccessMode "public" `
    -RemoteCredentials "D:\QuantService\data\gcp\quantmarket-handoff-uploader.json"
