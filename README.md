# 終末地全景拍攝 skill 與腳本

> [!WARNING]
> **此 repo 完全由 AI 建立，未經任何人類 review。請在執行前自行檢查所有腳本的安全性。**

本包只含拍攝、虛擬手柄控制、拼接、單張全景的離線檢視器，以及安裝與使用說明。

完整解壓縮後，在此資料夾開啟 PowerShell，執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Skill.ps1
```

預設安装到 `%CODEX_HOME%\skills`，未設定時為 `%USERPROFILE%\.codex\skills`。
若已有同名 skill，安裝器會停止、不覆寫。也可手動複製 `endfield-panorama` 到 skills 目錄。
開啟新的 Codex 對話後，使用 `$endfield-panorama`。

要手動執行，將 `endfield-panorama/assets/toolkit` 複製到新的可寫目錄，例如 `endfield-camera-control`。
需要 Windows x64、64 位元 Python 3.12 以上和 ViGEmBus 驅動。
在工作目錄執行 `Setup.ps1` 安裝 Python 依賴；驅動依提示從官方來源安裝。
遊戲相機切為第一人稱、22 mm，固定位置、設定 NPC 與隊友顯示並隱藏介面後，執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Run-Panorama.ps1 -Prepared -Delay 8
```

在倒數內切回遊戲。F8 可中止。完整安裝、參數、操作和校正方法見
[安裝與使用](endfield-panorama/references/usage.md)。

依賴與驅動需另行安装；ZIP 不含遊戲截图或全景圖片。

檢查範圍：Python 邏輯測試、固定版本的影像拼接與覆蓋率測試、Skill 格式與引用檢查。Windows 遊戲拍攝、PowerShell 執行與驅動連線仍需在目標電腦驗證；原始套件記錄的實拍結果不代表每台電腦都已測試。

`Setup.ps1` 會驗證 vgamepad 0.1.0 原始套件雜湊並安裝其中的執行檔案，不執行上游的驅動安裝腳本。ViGEmBus 請依使用說明從官方來源手動安裝。
