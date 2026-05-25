# UI-14：候補到個股頁切換 Flow 回歸

任務ID：`UI-14`
卡片類型：`UI / Browser Acceptance`
證據路徑：`artifacts/top10_ui14_stock_switching_flow_2026-05-20.json`、`artifacts/top10_ui14_stock_switching_flow_2026-05-20.png`

## 背景

個股頁已加入左側候補欄與 K 線工作台。這條路徑最容易在重構後出現「回本週才能換股票」、「左側欄選了但個股資料沒換」、「K 線只剩骨架」等問題，因此補一個可重跑的 browser flow regression。

## 範圍

- 新增 `scripts/verify_stock_switching_flow.mjs`。
- 驗證：
  - 本週候補至少有 2 檔。
  - 從本週候補點第一檔會進入個股頁。
  - 個股頁左側欄存在。
  - 在左側欄點第二檔，個股標題會換到第二檔。
  - 第二檔候補列成為 active。
  - K 線仍是 30D 載入狀態，canvas 與交易 rail 都存在。
  - 無 horizontal overflow 與 browser diagnostics。

## 非範圍

- 不改 UI layout。
- 不改 API / ranking / model contract。
- 不新增 npm dependency。

## 驗證命令

```bash
node --check scripts/verify_stock_switching_flow.mjs
node scripts/verify_stock_switching_flow.mjs
```

## Review 交接

任務ID：REVIEW-UI-14
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-20_UI-14_stock_switching_flow_regression.md`、`scripts/verify_stock_switching_flow.mjs`、`web/frontend/src/app/MarketDeskApp.tsx`、`web/frontend/src/features/weekly-candidates/WeeklyCandidatesPanel.tsx`
任務目的：review 候補列表到個股頁、個股頁左側欄切換股票、K 線資料維持載入的 browser flow regression 是否足夠，且沒有新增 product 行為或 dependency。
證據路徑：`artifacts/top10_ui14_stock_switching_flow_2026-05-20.json`、`artifacts/top10_ui14_stock_switching_flow_2026-05-20.png`
