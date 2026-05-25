# UI-12：K 線型態訊號顯示優先級

任務ID：`UI-12`
卡片類型｜派工對象：Backend contract / K 線 signal display｜Codex
請讀：`app/signals/registry.py`、`app/services/stock_detail_service.py`、`scripts/verify_data_contracts.py`、`web/frontend/src/charts/KLineWorkbench.tsx`
任務目的：避免同一根 K 線同時顯示多個同分類型態名稱；用同一套 registry 顯示優先級決定 API 輸出的可見訊號，不在前端寫個別型態特例。
證據路徑：`artifacts/top10_ui12_kline_signal_priority_acceptance_2026-05-19.json`、`artifacts/top10_ui12_kline_signal_priority_2026-05-19.png`

## 狀態

`completed`

## 範圍

- `PatternSignalDefinition` 新增 `display_priority`。
- 同一日期、同一 `category` 若命中多個訊號，只輸出 `display_priority` 最高者。
- 若 priority 相同，依 registry 順序穩定決定，不做型態名稱特例。
- TD 計數仍維持獨立 `td_sequential` 類別，可與 K 線型態分上下標註。

## 不做

- 不改 K 線型態計算公式。
- 不改 ranking score / model features。
- 不用前端 CSS 位移掩蓋重複文字。
- 不為十字星或蜻蜓十字寫單點 if-else 特例。

## 驗收計劃

- `py_compile` 通過。
- `verify_data_contracts.py` 通過，含 `stock_detail_pattern_signal_priority=True`。
- Browser 直接打 `/api/stocks/3030/detail?limit=1200`，candlestick duplicates 為空。
- 個股頁重刷後無水平溢出，K 線案例正常顯示。

## 實作紀錄

- `app/signals/registry.py`：新增 `display_priority` 作為所有型態共用顯示裁決標準。
- `app/services/stock_detail_service.py`：新增 `_visible_pattern_signal_ids()`，依 `category + display_priority` 選出可見型態；補 `_signal_is_active()` 避免缺欄位 / NaN 被誤判為 active。
- `scripts/verify_data_contracts.py`：新增回歸案例，覆蓋蜻蜓十字 + 錘子線、墓碑十字、十字星 + 多方吞噬等同分類重疊情境。

## 驗收結果

- `uv run --with-requirements requirements.txt python -m py_compile app/signals/registry.py app/services/stock_detail_service.py scripts/verify_data_contracts.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py` 通過：
  - `stock_detail_pattern_signal_priority=True`
  - `dragonfly=['candle_dragonfly_doji']`
  - `tombstone=['candle_tombstone_doji']`
  - `engulfing=['candle_bull_engulfing']`
- Backend `8001` 已重啟。
- Browser API 驗收：
  - `status=200`
  - `candlestickDates=9`
  - `duplicates=[]`
- Browser UI 驗收：
  - 個股頁 `activeRange=30D`
  - `density=full`
  - 無水平溢出。

## Review 派工卡

任務ID：`REVIEW-UI-12`
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-19_UI-12_kline_signal_display_priority.md`、`app/signals/registry.py`、`app/services/stock_detail_service.py`、`scripts/verify_data_contracts.py`
任務目的：review K 線型態去重是否使用同一套 `category + display_priority` 標準，而不是針對十字星 / 蜻蜓十字寫特例；確認缺欄位 / NaN 不會被誤判為 active。
證據路徑：`artifacts/top10_ui12_kline_signal_priority_acceptance_2026-05-19.json`、`artifacts/top10_ui12_kline_signal_priority_2026-05-19.png`
