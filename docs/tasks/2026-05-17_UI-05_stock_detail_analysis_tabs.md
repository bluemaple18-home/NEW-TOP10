# UI-05：個股頁下方分析 tabs

任務ID：`UI-05`
卡片類型｜派工對象：Frontend / 個股頁資訊架構｜Codex
請讀：`docs/architecture/MOMENTUM_UI_SPEC.md`、`docs/tasks/2026-05-16_UI-03_kline_range_controls.md`、`docs/tasks/2026-05-16_UI-04_kline_trade_overlay.md`、`web/frontend/src/features/stock-detail/StockDetailPanel.tsx`、`web/frontend/src/styles.css`
任務目的：重整個股頁 K 線下方資訊區，讓 K 線維持最大寬度，下方分析資訊用 tabs 呈現，不再左右擠壓或溢出畫面。
證據路徑：`web/frontend` build output、browser screenshot、console/network/DOM 驗收紀錄。

## 狀態

`completed`

## 背景

規格要求個股頁為上中下結構：

- 上：個股決策摘要。
- 中：超寬 K 線互動區。
- 下：詳細分析 tabs。

目前 `Show Case / 基本面 / 交易計畫 / 回測證據` 雖已放在 K 線下方，但仍以連續區塊與局部 grid 顯示，容易在寬螢幕或縮放時造成資訊卡橫向擠出，視覺上也難分辨哪些是長文字、哪些只是數字。

## 範圍

- 下方資訊改為 tabs。
- tabs 至少包含：
  - Show Case
  - 基本面
  - 交易計畫
  - 回測證據
- K 線寬度不可被下方資訊影響。
- 下方分析區寬度需與 K 線區塊對齊。
- 數字型資訊使用穩定小卡，長文字使用完整段落區。
- 桌機與手機都不得水平溢出。

## 不做

- 不新增盤中即時價。
- 不新增個股搜尋。
- 不新增持有股追蹤。
- 不做 ETF 成分 / 曝險分析。
- 不改交易計畫或基本面演算法。
- 不改 K 線資料視窗邏輯。

## 驗收計劃

- `pnpm build` 通過。
- Browser console 無 error / warn。
- 個股頁 K 線仍為單欄全寬。
- 下方分析 tabs 存在且可切換。
- 切換 `基本面 / 交易計畫 / 回測證據 / Show Case` 後：
  - active tab 正確。
  - 內容不水平溢出。
  - K 線容器寬度不改變。
- 桌機與手機 viewport 各截圖一張。

## 已知風險

- 本卡只整理資訊架構，不補尚未存在的大盤環境 / 產業族群資料。
- ETF 詳情頁仍待後續卡片處理。
- 手機版 K 線圖內部指標標籤仍偏密，這是 K 線 mobile readability 問題；本卡只保證下方 tabs 不造成水平溢出或壓縮 K 線寬度。

## 實作紀錄

- `web/frontend/src/features/stock-detail/StockDetailPanel.tsx` 新增 `AnalysisTabs`，將 `Show Case / 基本面 / 交易計畫 / 回測證據` 收斂為個股頁下方 tabs。
- `web/frontend/src/styles.css` 新增 tabs 版型，讓下方分析區與 K 線區塊同寬。
- 交易計畫改成 `執行價位` 與 `部位設定` 兩組，避免 8 個數字卡在同一列擠壓。
- 基本面與交易計畫 metric grid 改用可伸縮欄寬，避免寬螢幕或窄螢幕水平溢出。

## 驗收結果

- `pnpm build` 通過。
- Browser diagnostics：desktop / mobile console、page error、network failure 皆無異常。
- Desktop viewport `1920x1080`：
  - tabs 可切換 `基本面 / 交易計畫 / 回測證據 / K 線案例`。
  - K 線寬度維持 `1858px`，切換 tabs 後不變。
  - tabs 與 panel 左右邊界等於 K 線左 31 / 右 1889。
  - `documentOverflow=false`、`panelOverflow=false`。
- Mobile viewport `390x900`：
  - tabs 可切換。
  - K 線、tabs、panel 寬度皆為 `340px`。
  - `documentOverflow=false`、`panelOverflow=false`。
- 證據：
  - `artifacts/top10_ui05_analysis_tabs_acceptance_2026-05-17.json`
  - `artifacts/top10_ui05_analysis_tabs_desktop_2026-05-17.png`
  - `artifacts/top10_ui05_analysis_tabs_mobile_2026-05-17.png`
