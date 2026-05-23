@echo off
powershell -ExecutionPolicy Bypass -File "D:\QuantMarket\scripts\run_dev_intraday_market_snapshot.ps1" -SyncToQuantService -PublishRemote
