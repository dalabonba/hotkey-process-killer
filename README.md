# ⚡ Process Killer — 自訂快捷鍵進程終結器

## 🚀 第一次使用

1. 下載最新 release 中的 `ProcessKiller.exe`
2. 將 `ProcessKiller.exe` 放到一個專用資料夾中
3. 直接執行 `ProcessKiller.exe`
   - 程式會在同一個資料夾中自動建立 `config.json`

之後每次使用，直接執行資料夾中的 `ProcessKiller.exe` 即可。

---

## ✨ 功能

| 功能 | 說明 |
|------|------|
| 自訂快捷鍵 | 為任意進程綁定鍵盤快捷鍵 |
| 即時狀態 | 每 3 秒自動偵測進程是否執行中 |
| 手動終止 | 選取列表項目後點「立刻手動終止」 |
| 終止計數 | 記錄每個快捷鍵觸發了幾次 |
| 設定儲存 | 關閉後重新開啟，設定依然在 |

---

## ⌨ 快捷鍵格式範例

```
ctrl+shift+k
alt+F4
ctrl+alt+k
shift+F9
win+q
```

---

## ⚠ 注意事項

- **建議以管理員身分執行**，否則部分系統進程（如防毒軟體）無法終止
- 進程名稱需完整輸入，包含 `.exe`（例: `chrome.exe`）
- 若快捷鍵與其他程式衝突，請換一個組合
- 部分系統保留快捷鍵（例如 `Ctrl+Alt+Delete`）無法被程式攔截，請改用其他組合

---

## 🔧 常見進程名稱參考

| 程式 | 進程名稱 |
|------|---------|
| Google Chrome | chrome.exe |
| Microsoft Edge | msedge.exe |
| Firefox | firefox.exe |
| Notepad++ | notepad++.exe |
| Discord | Discord.exe |
| Steam | steam.exe |
| Spotify | Spotify.exe |
| 工作管理員 | Taskmgr.exe |

---

製作：Claude（Anthropic）& Github Copilot
