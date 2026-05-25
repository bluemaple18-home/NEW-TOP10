# UI-03：K 線工作台區間切換與寬度驗收

任務ID：`UI-03`
卡片類型｜派工對象：Frontend / Browser 驗收｜Codex
請讀：`docs/architecture/MOMENTUM_UI_SPEC.md`、`docs/KLINE_UI_DECISION.md`、`web/frontend/src/charts/KLineWorkbench.tsx`、`web/frontend/src/api.ts`
任務目的：修正 K 線工作台 `30D / 3M / 6M / 1Y / 全部` 區間切換，確保 30D 預設與回切都是真正最近 30 根有開盤紀錄的日 K，且資訊區不影響 K 線寬度。
證據路徑：`artifacts/top10_kline_30d_exact_fixed_2026-05-16.png`、browser console/network 驗收紀錄、`pnpm build` output。

## 狀態

`completed`

## 背景

PM 回報 `3M / 6M / 1Y / 全部` 有用，但 `30D` 沒有觸發。前一輪驗收只看自訂 `barSpace` 狀態，沒有驗 KLineCharts 實際可視區，導致誤判。

根因：

- KLineCharts 內建 `barSpace` 最大值是 `50`。
- 先前 30D 在超寬畫面下計算出 `61.7`，超過套件上限，`setBarSpace` 會被忽略。
- 因此按鈕 active 有變，但圖表實際 visible range 沒有縮回 30D。

## 範圍

- `KLineWorkbench` 區間切換：
  - `30D`：最近 30 根日 K。
  - `3M`：最近 60 根日 K。
  - `6M`：最近 120 根日 K。
  - `1Y`：最近 240 根日 K。
  - `全部`：本地 API 回傳的全部 K 線。
- `30D` 需是資料視窗切換，不只靠縮放近似。
- 每次區間切換需回到最新資料。
- 區間切換需保留 K 線圖上案例 overlay，且只呈現目前資料視窗內的訊號。
- 個股頁 K 線寬度不可被右側資訊或下方資訊影響。
- 頁面滾動不觸發 K 線縮放；點擊圖表後才進入圖表操作狀態。

## 實作紀錄

- `web/frontend/src/charts/KLineWorkbench.tsx`
  - 新增 `activeWindowBars`、`activeVisibleBars`、`rangeRevision` 驗收狀態。
  - `focusWindow()` 依區間切出 `windowedData` 後重設 KLineCharts data loader。
  - 將 `barSpace` 上限限制在 KLineCharts 可接受的 `50`。
  - 用 `chart.getBarSpace().bar` 回寫實際套件狀態，不再只回報預估值。
  - 新增 `signalsForWindow()`，避免非目前視窗的 Show Case overlay 留在圖上。
- `web/frontend/src/api.ts`
  - 個股詳情與 OHLCV 預設 `limit=1200`，讓 `全部` 有足夠資料可切換。
- `app/api/routers/market.py`、`app/api/routers/stock_detail.py`
  - API 預設 `limit=1200`。
- `app/services/market_service.py`、`app/services/stock_detail_service.py`
  - service 預設 `limit=1200`。

## 不做

- 不新增盤中即時價。
- 不新增個股搜尋。
- 不新增持有股追蹤。
- 不做 ETF 成分 / 曝險分析。
- 不把基本面、交易計畫或回測資訊放到 K 線左右側影響寬度。

## 驗收

- `pnpm build` 通過。
- Browser console 無 error / warn。
- `/api/stocks/1110/detail?limit=1200` 回 200，且可取得 300 根本地 K 線。
- 桌機個股頁無水平溢出。
- K 線與下方 Show Case / 基本面 / 交易計畫 / 回測左右邊界一致。
- 區間切換驗收：

```text
初始 30D  -> windowBars 30 / visibleBars 30
3M        -> windowBars 60
再按 30D -> windowBars 30 / visibleBars 30
6M        -> windowBars 120
再按 30D -> windowBars 30 / visibleBars 30
全部      -> windowBars 300
再按 30D -> windowBars 30 / visibleBars 30
```

## 證據

- 截圖：`artifacts/top10_kline_30d_exact_fixed_2026-05-16.png`
- 前一輪規格驗收截圖：
  - `artifacts/top10_spec_verify_weekly_desktop_2026-05-16.png`
  - `artifacts/top10_spec_verify_stock_desktop_2026-05-16.png`
- 30D 修正前錯誤觀測：

```text
3M        -> visibleBars 59
再按 30D -> visibleBars 59
全部      -> visibleBars 291
再按 30D -> visibleBars 291
```

- 30D 修正後觀測：

```text
3M        -> windowBars 60
再按 30D -> windowBars 30 / visibleBars 30
全部      -> windowBars 300
再按 30D -> windowBars 30 / visibleBars 30
```

## 已知風險

- 目前下方詳細分析仍是直向區塊，不是 `MOMENTUM_UI_SPEC.md` 中原始描述的 tabs。
- 交易計畫仍顯示百分比權重，和「第一版只提供相對部位」的原始規格不完全一致。
- 買點區、停損線、停利區尚未完整 overlay 到 K 線圖上。

