---
name: endfield-panorama
description: Capture and stitch real 360-degree panoramas from Arknights Endfield on Windows using photo mode, a virtual Xbox controller, and screenshots. Use for taking or retaking game panoramas and setting up this capture toolkit.
---

# 終末地實拍全景

以固定位置的第一人稱相機拍攝重疊影像，再拼成 2:1 等距柱狀全景與可離線環視的 HTML。
使用遊戲畫面實拍；不使用 AI 補景、遊戲注入或記憶體讀寫。

## 工具與位置

- 工具隨附於 [assets/toolkit](assets/toolkit)，含自動流程、手柄控制、拼接器與檢視器範本。
- 若使用者已有工作目錄，先使用該目錄；不要假設任何個人電腦路徑或既有依賴存在。
- 新環境將 `assets/toolkit` 複製到使用者可寫的獨立工作目錄，再執行；不要把截圖和依賴寫進已安裝的 skill。
- 安裝、手動使用、參數與校正請讀 [references/usage.md](references/usage.md)。安裝前先做 `run_panorama.py --check`，現有依賴正常就不重裝。

## 拍攝前必須看畫面

1. 確認遊戲在拍照模式，切成**第一人稱**，固定位置、焦距 **22 mm**，仰俯約水平、傾斜 0。第三人稱會繞人物移動視點而造成近景錯位。
2. 確認使用者要保留哪些角色。`顯示幹員` 控制隊友；`環境顯示` 下的 **NPC** 是另一個勾選項。若已勾选不要再按 A。不要因為要隱藏隊友而關掉 NPC。
3. 關掉設定面板，隱藏介面，再檢視一張截圖。工具不辨識相機模式或選單，`--prepared` 只是已人工確認的旗標。
4. 拍攝期間不移動角色、不改焦距、不切視窗；僅使用右搖桿旋轉。每次換地點或顯示設定都另開新 session。

已實测按鍵（操作前以當前畫面為準）：RT 開啟相機、Y 切換第一／第三人稱、BACK 隱藏介面；B 關閉當前面板，在主相機畫面再按 B 會退出相機。RIGHT_THUMB 重置會彈出確認框。第一人稱提示通常只有旋轉、重置、隱藏、退出，沒有移動相機或距離調整。

## 自動執行

工作目錄內：

```powershell
.\Run-Panorama.ps1 -Prepared -Delay 8
```

這會啟動持續連線的虛擬手柄、倒數、拍攝 5 排共 69 張、回復大致水平仰俯、停止手柄，再拼接。每次產生獨立來源與輸出資料夾。完成的朝向不保證與起始相同。

代理環境若無法在沙箱內存取互動桌面，可依當前工具的權限機制在桌面工作階段啟動 `control.py serve`，使用 `Start-Process -WindowStyle Hidden`，再以 `-ExternalServer -Prepared -Delay 0` 執行自動流程。服務持續存在才能保留同一手柄；不要每次指令都重建虛擬裝置。自動流程結束會停止外部服務。

長時間執行時維持進度更新。看到前景視窗錯誤、F8、解析度變動或使用者介入就停止；不要自動重試相機動作，也不要在失敗後補做回正。保留已拍影像，確認目前畫面後用新 session 重來。依賴或桌面權限錯誤的處理見 usage.md。

## 驗收與交付

- `last-run.json` 記錄最新 session、狀態及輸出位置；`report.json` 的 `unobserved_pixels` 必須是 0，才可稱完整 360°×180°。若不為 0，自動程式以結束碼 2 保留結果，不捏造缺失畫面。
- 檢视 `preview.jpg`，留意選單殘留、錯位、NPC／花草動態接縫。覆蓋完整不代表動態接縫完全消失。
- 提供 `view-panorama.html` 和 `panorama.png` 的可點連結，簡短說明已知接縫，確認 `status.json` 是 stopped。
- 舊來源可用 `-StitchOnly` 重拼。不要混用不同位置、焦距或 NPC 設定的 manifests。

本機驗證基準：Windows、Python 3.13.3、1600×900 遊戲畫面、22 mm、軸值 0.6、水平每步 0.25 秒。參數屬實測配置，不是讀取遊戲角度；換靈敏度、遊戲版本或焦距後先校正，再檢查覆蓋率。
