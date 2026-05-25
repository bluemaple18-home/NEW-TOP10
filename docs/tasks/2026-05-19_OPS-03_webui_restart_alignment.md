# OPS-03：Web UI 重啟入口與文件對齊

任務ID：`OPS-03`
卡片類型：`Ops / Local Startup`
證據路徑：`artifacts/top10_ops03_webui_restart_alignment_2026-05-19.json`

## 背景

OPS-01 已把本地 API port 統一到 `8001`，但 `docs/WEBUI.md` 仍寫 `8000`。同時 repo 內已有 `com.new-top10.webui.plist`，但沒有單獨安裝 Web UI launchd agent 的入口，容易讓「重開後要怎麼恢復 APP」變成手動猜。

## 範圍

- 新增 `scripts/setup_webui_launchd.sh`。
- 更新 `docs/WEBUI.md`：API 改為 `8001`，補 healthcheck 與 frontend smoke 驗證。
- 更新 `README.md`：補選用 launchd Web UI 安裝命令。

## 非範圍

- 不自動安裝或修改使用者系統 launchd。
- 不改 daily / retrain / reference 排程。
- 不改 API、前端產品邏輯或 port 預設。

## 驗證命令

```bash
bash -n scripts/setup_webui_launchd.sh
rg -n "127.0.0.1:8000|127.0.0.1:8001|setup_webui_launchd|verify_frontend_smoke" docs/WEBUI.md README.md scripts
```

## 執行紀錄

- Review finding `P1 launchd agent 可能重開後起不來，因為沒有設定 PATH` 已修正：
  - `scripts/com.new-top10.webui.plist` 補 `EnvironmentVariables.PATH`。
  - `scripts/setup_webui_launchd.sh` 會把 `__HOME_DIR__` 替換成實際 `$HOME`。
  - `scripts/start_market_ui.sh` 自行補常見 PATH，並支援 `UV_BIN` / `PNPM_BIN` 明確路徑。
  - 找不到或指定了不存在的 `uv` / `pnpm` 時會直接停下並輸出提示，不會半啟動。
- `bash -n scripts/setup_webui_launchd.sh scripts/start_market_ui.sh scripts/start_ui.sh scripts/verify_local_dev_health.sh` 通過。
- `rg` 確認 `docs/WEBUI.md` / `README.md` / `scripts` 中的 Web UI API 文件已對齊 `127.0.0.1:8001`，沒有殘留 `127.0.0.1:8000`。
- `bash scripts/verify_local_dev_health.sh` 通過，API `8001` / frontend `5173` 皆為 `200`。
- `node scripts/verify_frontend_smoke.mjs` 通過，證據沿用 `artifacts/top10_ops02_frontend_smoke_2026-05-19.json` 與截圖。
- 本卡沒有執行 `scripts/setup_webui_launchd.sh`，避免自動修改使用者系統 launchd。
- `plutil -lint /private/tmp/com.new-top10.webui.plist` 通過，產出的 plist 沒有殘留 placeholder。
- `UV_BIN=/missing/uv bash scripts/start_market_ui.sh` 會直接輸出找不到 `uv` 並停止。
- `PNPM_BIN=/missing/pnpm bash scripts/start_market_ui.sh` 會直接輸出找不到 `pnpm` 並停止。
- `REVIEW-OPS-03-FIX` 結論：未發現阻塞問題；確認 plist PATH、setup placeholder replacement、`UV_BIN` / `PNPM_BIN` fast fail、以及未碰 daily / retrain / reference 排程。

## Review 交接

任務ID：REVIEW-OPS-03
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-19_OPS-03_webui_restart_alignment.md`、`scripts/setup_webui_launchd.sh`、`scripts/com.new-top10.webui.plist`、`docs/WEBUI.md`、`README.md`
任務目的：review Web UI 重啟文件與 launchd 安裝入口是否對齊 API 8001 / frontend 5173，且沒有自動改使用者系統或動到 daily 排程。
證據路徑：`artifacts/top10_ops03_webui_restart_alignment_2026-05-19.json`
