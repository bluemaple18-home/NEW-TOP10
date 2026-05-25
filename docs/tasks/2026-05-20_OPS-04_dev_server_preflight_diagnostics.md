# OPS-04：Dev Server Preflight 診斷

任務ID：`OPS-04`
卡片類型：`Ops / Developer Experience`
證據路徑：`artifacts/top10_ops04_dev_server_preflight_2026-05-20.json`

## 背景

REVIEW-OPS-02 未發現阻塞問題，但 review 端因本地 dev server 沒開，無法現場重跑完整 smoke。這不是產品 blocker，但原本失敗訊息容易被誤解成前端資料壞掉。

## 範圍

- `scripts/verify_local_dev_health.sh`：當 curl 回傳 `000` 時，明確提示先執行 `bash scripts/start_ui.sh` 或檢查 port。
- `scripts/verify_frontend_smoke.mjs`：啟動 Chrome 前先 fetch frontend URL；若前端沒開，輸出 `FRONTEND_NOT_READY` 與啟動提示。
- 回填 `OPS-02` review 結論與缺口。

## 非範圍

- 不自動啟動 dev server。
- 不更動 API / frontend runtime 行為。
- 不改產品 UI。

## 驗證命令

```bash
bash -n scripts/verify_local_dev_health.sh
node --check scripts/verify_frontend_smoke.mjs
bash scripts/verify_local_dev_health.sh
node scripts/verify_frontend_smoke.mjs
```

## 執行紀錄

- Review finding `P2 frontend preflight 還是先啟動 Chrome` 已修正：
  - `scripts/verify_frontend_smoke.mjs` 不再於頂層 `spawn()` Chrome。
  - Chrome 啟動被包進 `startChrome()`。
  - 主流程現在是 `await assertFrontendReady()` 後才 `startChrome()`。
- `bash -n scripts/verify_local_dev_health.sh` 通過。
- `node --check scripts/verify_frontend_smoke.mjs` 通過。
- 本機服務未開時：
  - `bash scripts/verify_local_dev_health.sh` 會輸出 `FAIL ... status=000` 與 `請先執行 bash scripts/start_ui.sh`。
  - `node scripts/verify_frontend_smoke.mjs` 會輸出 `FRONTEND_NOT_READY` 與啟動提示，不再等到 Chrome/CDP timeout。
- 錯 port 補測：`TOP10_FRONTEND_PORT=59999 node scripts/verify_frontend_smoke.mjs` 直接輸出 `FRONTEND_NOT_READY`；依程式順序尚未進入 `startChrome()`。
- 啟動 `bash scripts/start_ui.sh` 後：
  - `bash scripts/verify_local_dev_health.sh` 通過，API `8001` / frontend `5173` 皆 `200`。
  - `node scripts/verify_frontend_smoke.mjs` 通過：`candidateCount=10`、`selectedStockTitle=3030 德律`、`windowBars=30`、`canvasCount=18`、`tradeRailMarkCount=3`、`diagnostics=[]`。
- `REVIEW-OPS-04-FIX` 結論：未發現阻塞問題；確認主流程先 `await assertFrontendReady()` 才 `startChrome()`，且 `TOP10_FRONTEND_PORT=59999 CHROME_PATH=/missing/chrome` 會先回 `FRONTEND_NOT_READY`，不被 Chrome/CDP 問題遮蔽。

## Review 交接

任務ID：REVIEW-OPS-04
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-20_OPS-04_dev_server_preflight_diagnostics.md`、`scripts/verify_local_dev_health.sh`、`scripts/verify_frontend_smoke.mjs`
任務目的：review dev server 未啟動時是否會給出清楚診斷，且正常服務開啟時 health/smoke 仍通過。
證據路徑：`artifacts/top10_ops04_dev_server_preflight_2026-05-20.json`
