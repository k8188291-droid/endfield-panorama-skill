# 安裝與使用

## 目錄

- [這套工具做什麼](#這套工具做什麼)
- [第一次安裝](#第一次安裝)
- [每次重拍](#每次重拍)
- [輸出與重複執行](#輸出與重複執行)
- [常用命令](#常用命令)
- [給 Codex 操作／校正](#給-codex-操作校正)
- [故障排除](#故障排除)
- [安裝 SKILL](#安裝-skill)

## 這套工具做什麼

使用持續連線的虛擬 Xbox 360 手柄，旋轉《明日方舟：終末地》的第一人稱拍照相機；擷取遊戲視窗，再用實際影像匹配和球面投影製作全景。沒有遊戲注入，也沒有 AI 生成的景物。

預設拍 5 排共 69 張（每排包含起始畫面），輸出 4096×2048 的 360°×180° PNG，以及內嵌圖片、免連網的 HTML 環視器。拼接保留未拍到的位置為透明，不以假圖補洞。

對齊時會增強灰階副本的局部對比，以辨識水泥地等較淡的紋理；成品仍從原始彩色截圖取樣。已在花叢與工業廣場實測，廣場的 69 張在這項修正後全部對齊，輸出無缺口。

## 第一次安裝

先檢查使用者目前的工作目錄與依賴；不要假設電腦已裝好驅動。

換電腦時，從 SKILL 的 `assets\toolkit` 複製整個目錄至可寫位置，例如桌面的 `endfield-camera-control`。程式會在該目錄寫入截圖、佇列、日誌及輸出。需要 Windows x64、64 位元 Python 3.12 以上（本機實測 3.13.3），以及 ViGEmBus 驅動。

1. 安裝 [Python](https://www.python.org/downloads/windows/)，勾選加入 PATH。重新開啟 PowerShell，確認 `python --version` 能執行。
2. 在工具資料夾開 PowerShell，執行：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup.ps1
   ```

   程式先檢查現有環境；已可用就直接結束，否則建立本地 `.venv`。`install_vgamepad.py` 從 PyPI 的官方檔案主機下載固定版本的原始套件，驗證 SHA-256 後只打包 Python 程式、x64 用戶端 DLL 與授權文字，再安裝其他依賴。這能避免執行 vgamepad 原始安裝腳本附帶的舊版 MSI；驅動仍需依下一步手動安裝。只影響這個資料夾的 Python 環境。這裡的 Bypass 僅限此 PowerShell 程序，不修改全機執行原則。

3. 若檢查結果 `driver_installed` 是 false，從 [ViGEmBus 官方發布頁](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0) 下載並執行驅動安裝程式。驅動安裝需要 Windows 系統管理員確認；依安裝器要求重新開機。`Setup.ps1` 不會替你靜默啟動驅動安裝器。
4. 再執行 `Setup.ps1 -CheckOnly`，確認 `ok: true`。

[vgamepad](https://github.com/yannbouteiller/vgamepad) 是 Python 控制庫，ViGEmBus 是系統驅動，兩者都需要。ViGEmBus 已[停止維護](https://docs.nefarius.at/projects/ViGEm/End-of-Life/)；本工具沿用本機已驗證的方案。只使用官方驅動來源，不需要更改遊戲檔案。

若工作目錄已有 `deps`，程式會優先讀取其中的本地依賴。可攜式 SKILL 不打包這些二進位依賴，換電腦請重新執行 Setup。固定版本記錄在 requirements.txt；其他 Python／套件版本未保證能使用相同的 OpenCV 介面。

## 每次重拍

1. 在遊戲移到想拍的位置，開啟相機模式。
2. 切換第一人稱。維持 22 mm 焦距、傾斜 0、視線大致水平。位置和焦距會影響拼接，拍攝途中不要調整。
3. 設定隊友與 NPC 顯示：`顯示幹員 → 隱藏全部` 隱藏隊友；`環境顯示 → NPC` 勾選才保留 NPC。依自己需求設定，腳本不會修改這些項目。
4. 關閉設定面板，隱藏操作介面。左下 UID 不一定能隱藏，拼接器已排除底部 40 像素；原始截圖仍保留 UID，分享原始檔前請注意。
5. 雙擊 **Run-Panorama.cmd**，閱讀準備提示並按鍵，接著在 8 秒內切回遊戲。
6. 拍攝時保持遊戲在前景，請勿操作滑鼠／搖桿。拍攝約 2 分鐘，拼接另需數分鐘，依電腦速度而異。完成後主控台會顯示 HTML 路徑。

**F8 隨時中止手柄服務。** 切離遊戲視窗也會中止目前拍攝，已完成的截圖會保留。中止後不會自動續拍或自動回正；下一次需重新確認相機狀態。成功結束時會回到大致水平，朝向可能不同。

也可以使用 PowerShell：

```powershell
cd "$env:USERPROFILE\Desktop\endfield-camera-control"
.\Run-Panorama.ps1 -Prepared -Delay 8
```

`-Prepared` 表示你已確認上述相機狀態；程式本身沒有選單辨識能力。若 PowerShell 擋下腳本，可使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Panorama.ps1 -Prepared`。

## 輸出與重複執行

每次自動命名新的 session，無須刪除上一次資料：

| 路徑 | 內容 |
| --- | --- |
| `screenshots\*.png` | 原始遊戲截圖 |
| `captures-<session>\<row>\manifest.json` | 該排的來源截圖清單 |
| `captures-<session>\profile.json` | 該次使用的拍攝參數 |
| `captures-<session>\run.json` | 該次狀態與錯誤 |
| `output\<session>\panorama.png` | 全景原圖 |
| `output\<session>\view-panorama.html` | 可直接開啟或單獨分享的離線環視器 |
| `output\<session>\preview.jpg` | 平面預覽 |
| `output\<session>\coverage.png` | 白色有影像，黑色是缺口 |
| `output\<session>\report.json` | 解析度、成功配準數量與覆蓋率 |
| `last-run.json` | 最新一次執行的狀態與結果位置 |

HTML 支援拖曳環視、滾輪縮放與方向鍵，需要瀏覽器支援 WebGL。移動 NPC、蝴蝶、搖晃花草可能形成局部接縫；完整覆蓋不代表全景在同一瞬間拍成。

## 常用命令

```powershell
# 只檢查環境；不操作遊戲
.\Run-Panorama.ps1 -Check

# 看拍攝計畫；不啟動手柄，也不寫截圖
.\Run-Panorama.ps1 -DryRun

# 指定新名稱；重複名稱會被拒絕以免混入舊圖
.\Run-Panorama.ps1 -Prepared -Session garden-npc-02 -Delay 10

# 只拍攝，稍後再拼
.\Run-Panorama.ps1 -Prepared -CaptureOnly -Session garden-npc-03

# 只重拼既有的一組來源；不需要開啟遊戲
.\Run-Panorama.ps1 -StitchOnly .\captures-garden-npc-03 -Session garden-npc-03-render

# 指定輸出寬度，高度自動為一半；8192 更耗記憶體，也不會新增原始細節
.\Run-Panorama.ps1 -StitchOnly .\captures-garden-npc-03 -Session garden-npc-03-8k -Width 8192
```

等價 Python 入口：`python run_panorama.py --prepared --delay 8`。若依賴安裝在 `.venv`，用 `.\.venv\Scripts\python.exe`。結束碼 0 表示成功；1 表示中止／錯誤；2 表示全景已輸出但存在未拍到的像素。

## 給 Codex 操作／校正

先啟動一次常駐 `control.py serve`。需要背景程序時使用 `Start-Process -WindowStyle Hidden`，例如：

```powershell
$cameraPython = (Get-Command python).Source
if (Test-Path .\.venv\Scripts\python.exe) {
    $cameraPython = (Resolve-Path .\.venv\Scripts\python.exe).Path
}
Start-Process -FilePath $cameraPython -ArgumentList 'control.py','serve' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -RedirectStandardOutput '.\server.stdout.log' -RedirectStandardError '.\server.stderr.log'
```

啟動後讀 `status.json`，等 state 為 ready。若 Codex 沙箱禁止互動桌面程序，僅在相應工具允許的桌面權限下啟動服務；不繞過前景檢查。

```powershell
python control.py capture
python control.py look --x 0.6 --seconds 0.25
python control.py look --y 0.6 --seconds 0.1
python control.py button --button BACK --seconds 0.1
python control.py stop
```

正 y 向上，負 y 向下。每個 look、button、trigger 指令完成後回中立、等待穩定並截圖。從主控台操作可加 `--delay 5`，在倒數內切回遊戲。每次輸入最長 2 秒；只接受前景程式 `Endfield.exe`。

準備好畫面後用 `Run-Panorama.ps1 -Prepared -ExternalServer -Delay 0` 連接該服務。結束時會停止服務。不要同時啟動多個自動流程或在拍摄時另送指令。

預設 `capture-profile.json` 記錄這次成功的 22 mm 參數。`pitch_seconds` 是每排前相對前一排的仰俯旋轉時間，正上負下；`count` 是水平轉動次數，因此實際照片數為 count+1。`restore_pitch_seconds` 是最後回正的相對時間。這些是依本機遊戲靈敏度實測的時間，不是 API 提供的絕對角度。

換靈敏度後先備份 profile，以短 look 輸入拍照，確認相鄰照片仍有約三成以上重疊，一排足以繞完整一圈。若轉速變為原本兩倍，各旋轉時間約縮為一半，仍須實拍確認。改用更長焦距時，需要更多水平及垂直重疊；不要僅改焦距就沿用預設 69 張配置。自訂配置用 `-Profile .\my-profile.json`。

## 故障排除

| 現象 | 處理 |
| --- | --- |
| `Endfield must be the foreground window` | 中止並切回遊戲，重新確認相機，用新 session 重拍。 |
| `Cannot identify foreground process` | 檢查遊戲與服務的桌面工作階段和權限；Codex 可能需要允許桌面存取。不要移除前景防護。 |
| 缺少 DLL 或驅動錯誤 | 執行 Check；確認 x64 Python 與 ViGEmBus 已安裝，必要時依驅動安裝器指示重新開機。 |
| 操作模式未切換 | 在相機模式試一次很短的右搖桿輸入，檢視返回截圖；確認後重新調水平，勿盲按 Y／B。 |
| 手柄服務已執行 | 使用既有服務加 ExternalServer，或先 `control.py stop`。不要建立第二個裝置。 |
| 截圖有選單 | 停止，關閉面板並隱藏介面，再用新 session 拍攝。 |
| 天頂或地底有缺口 | 查看 coverage.png 和 profile；檢查起始仰俯、靈敏度及焦距，補足視角或重拍。 |
| 大片错位 | 確認第一人稱、固定位置；不要混用不同位置或焦距的來源。 |
| `No response`／F8 中止 | 查看 status.json、server.stderr.log。不要重送相機動作；確認狀態後重啟新 session。 |
| 配準照片少於 69 | 天空缺乏特徵時可丟棄少量照片；以 unobserved_pixels、預覽和接縫判斷結果。 |

原始 manifests 存的是絕對圖片路徑。若需要搬移來源後重拼，保留原始截圖並更新 manifest 中的 image 路徑；成品 HTML 已內嵌圖片，可以單獨搬移。

## 安裝 SKILL

在完整解壓縮後的專案根目錄（與 README.md 同層）執行 `Install-Skill.ps1`，將 `endfield-panorama` 安裝到 `$CODEX_HOME\skills`；未設定 CODEX_HOME 時使用 `$env:USERPROFILE\.codex\skills`。不覆蓋同名 skill。開啟新的 Codex 對話後可使用：

```text
$endfield-panorama 幫我在目前位置拍一張 360 全景，保留 NPC、隱藏隊友。
```

也可以把提供的 skill ZIP 解壓縮，將整個 `endfield-panorama` 資料夾放到上述 skills 目錄，確認 SKILL.md 就在該資料夾第一層。這裡安裝的是 Codex 操作指南；相機控制仍由工作目錄內的腳本與虛擬手柄執行。
