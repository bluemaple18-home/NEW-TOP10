# UI-02：個股頁四區 UI

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`UI-02`
卡片類型｜派工對象：Frontend｜另一個 coding model
請讀：`docs/tasks/2026-05-12_UI-01_stock_detail_api_contract.md`、`web/frontend/src/features/stock-detail/StockDetailPanel.tsx`、`web/frontend/src/charts/KLineWorkbench.tsx`、`web/frontend/src/components/`
任務目的：把個股頁重整成四區：K 線、基本面、交易計畫、回測證據，並盡量抽成共用元件。
證據路徑：`web/frontend` build output、browser screenshot 或 smoke notes。

## 前置依賴

- 必須先完成 `UI-01`。

## 範圍

- 個股頁四區：
  - K 線：沿用可拖拉/縮放的 K 線工作台。
  - 基本面：顯示 quality metrics、warnings、cache availability。
  - 交易計畫：entry、stop、target、risk_reward、suggested_weight、exposure note。
  - 回測證據：summary、equity/drawdown 狀態、artifact unavailable 狀態。
- 可共用元件要抽到 `web/frontend/src/components`，業務區塊放 `features/stock-detail`。
- API loader 不應放進低階 chart/component。

## 不做

- 不新增即時回測按鈕。
- 不把 K 線 chart 和基本面/回測邏輯耦合。
- 不大改整體 app shell，除非必要。

## 驗收

- `pnpm build` 通過。
- 個股頁在資料缺一區時仍能渲染其他區。
- K 線仍可拖拉/縮放。
- 基本面、交易計畫、回測證據是清楚分區，不混在排名列表。

## 建議驗證

```bash
cd web/frontend
pnpm build
```

如需 browser 驗收，開本機 API + Vite 後檢查：

```text
個股頁四區可見、切換股票正常、K 線拖拉/縮放正常、console 無明顯 runtime error。
```

## 完成紀錄（2026-05-17）

- `web/frontend/src/features/stock-detail/StockDetailPanel.tsx` 已改為個股頁工作台。
- 上方為個股摘要與決策欄位，中段為 K 線工作台，下方分析資訊已在後續 `UI-05` 收斂為 tabs。
- K 線資料由 stock detail API 載入，不把 API loader 塞進低階 chart。
- 基本面、交易計畫、回測證據有 unavailable / empty 狀態，不阻塞 K 線。
- 後續 `UI-03`、`UI-04`、`UI-05`、`UI-06` 已補齊 K 線區間、交易 overlay、下方 tabs、手機 readability。

### 驗證結果

```bash
cd web/frontend
pnpm build
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `pnpm build`：`✓ built`
- `stock_detail: status=200`
- `price / reference / fundamentals / trade_plan / backtest` 均有可渲染 contract。

## Review 重點

- 是否把 API 呼叫塞進低階共用元件。
- 是否把 unavailable 狀態當錯誤爆掉。
- 是否破壞既有 K 線互動。
