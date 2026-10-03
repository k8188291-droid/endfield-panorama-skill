@echo off
chcp 65001 >nul
echo 請先確認：相機模式、第一人稱、22 mm、水平視角、隱藏介面，並設定好 NPC 與隊友顯示。
echo 按任意鍵開始，接著在 8 秒內切回遊戲。拍攝時請勿操作，F8 可中止。
pause >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-Panorama.ps1" -Prepared
echo.
echo 執行結束。請查看上面的結果路徑或錯誤訊息。
pause
