---
card_id: REVIEW-UI-MFR-01
chain_id: TOP10-NEXT-WAVE-20260722
status: REVIEW_GO
final_review_sha: 8b324275ba5a1544486c6d11b1a387d85a75c872
type: independent-api-ui-browser-review
reviewed_candidate: a8d11a26d4378992a4749bae2707f6961a8de8ff
base_sha: cdd4c42
reasoning: medium
thickness: strict
---

# REVIEW-UI-MFR-01

獨立 Reviewer，只審不修。固定 reviewed range：
`cdd4c42..a8d11a26d4378992a4749bae2707f6961a8de8ff`。

只能新增 `docs/evidence/REVIEW-UI-MFR-01/**` 與
`.work/REVIEW-UI-MFR-01/**`；不得修改 candidate、merge 或 deploy。

## Required review

- Spec：versioned read-only API、deterministic approved fixture、Theme metrics/freshness/coverage/source/evidence、loading/empty/error/stale/partial、research/Top10 separation、Graph research-only/unavailable、no production/ranking mutation。
- API correctness：closed response schema、invalid dates、determinism、CORS、error envelope、fixture path portability、no external I/O。
- Frontend：existing shell、dense analytical route、responsive table/detail, keyboard/focus、reduced motion、semantic states、no overflow/card-in-card/recommendation wording。
- Build：`pnpm --dir web/frontend build`。可離線重用 `<repo-root>/web/frontend/node_modules`，lockfile SHA 必須相同；不得下載。
- Browser：使用本機 `/Applications/Google Chrome.app` headless/CDP；listeners 必須在 navigation 前註冊。啟動 API `127.0.0.1:8001` 與 frontend `127.0.0.1:5173`，驗 desktop/mobile、keyboard activation、五種狀態、console/pageerror/requestfailed/HTTP errors，保存 screenshots。
- 必須區分 candidate radar endpoint 與既有 weekly/stock fixture 缺檔造成的 baseline 500；若 background baseline requests 讓 radar slice 無法 clean acceptance，也要列具體 finding。
- 重跑 25 affected tests、py_compile、diff/allowlist/privacy/non-mutation。

## Preflight fact to reproduce

Integrator 已用本機 Chrome/CDP 成功啟動 browser。首次 probe 聚焦「市場雷達」button，但 keyboard Enter 未切換 view；頁面初始 weekly/stock background fetch 因缺 `data/clean/features.parquet` 回 500，瀏覽器記錄 `MissingAllowOriginHeader` request failures。Reviewer 不可直接採信此結論，必須區分 probe 問題、既有 baseline 與 candidate regression，再給 verdict。

## Verdict

- `GO`：API/visual/runtime/keyboard/desktop/mobile/state evidence 全通過，無 P0/P1。
- `NO_GO`：任何核心 radar path 在正常 fixture mode 無法使用、browser gate 未完成、API/資料邊界錯誤或 visual/accessibility P1。
- `BLOCKED`：僅客觀環境阻斷；本機已有 node_modules 與 Chrome，不得再以缺工具直接 BLOCKED。

提交單一 review evidence commit；Findings 必須有 path:line、觸發條件、風險與最小修正。
