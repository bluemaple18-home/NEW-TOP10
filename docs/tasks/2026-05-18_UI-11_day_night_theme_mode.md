# UI-11：白天 / 夜晚模式切換

任務ID：`UI-11`
卡片類型｜派工對象：Frontend / Theme mode｜Codex
請讀：`docs/architecture/MOMENTUM_UI_SPEC.md`、`web/frontend/src/app/AppShell.tsx`、`web/frontend/src/styles.css`
任務目的：新增全站白天 / 夜晚模式切換，讓使用者可依環境調整閱讀亮度；切換狀態需保存，不影響資料、模型、候補篩選與 K 線寬度。
證據路徑：`artifacts/top10_ui11_theme_mode_acceptance_2026-05-18.json`、`artifacts/top10_ui11_theme_mode_desktop_night_2026-05-18.png`、`artifacts/top10_ui11_theme_mode_mobile_day_2026-05-18.png`

## 狀態

`completed`

## 範圍

- 頁首右上新增 `白天 / 夜晚` 切換。
- 切換狀態寫入 `localStorage`，重開頁面仍保留。
- 未保存時依系統偏好預設白天或夜晚。
- 白天模式調整產品 UI 外框、文字、卡片、候補列、側欄與分析區塊。
- K 線圖本體維持深色底，避免既有指標線與紅綠 K 判讀失真。

## 不做

- 不新增第三套主題。
- 不改資料 API / ranking / model。
- 不讓 theme switcher 進入 K 線區域或影響 K 線寬度。
- 不重設使用者目前的候補篩選或選股狀態。

## 驗收計劃

- `pnpm build` 通過。
- Browser desktop：白天 / 夜晚按鈕可切換，`html[data-theme]` 與 `localStorage` 同步。
- Browser mobile：切換按鈕可見、可操作，無水平溢出。
- console 無錯誤，API request 正常。

## 實作紀錄

- `web/frontend/src/app/AppShell.tsx`：新增 `ThemeMode` state、`localStorage` 保存、系統色系 fallback，並在頁首加入白天 / 夜晚 segmented control。
- `web/frontend/src/styles.css`：新增 day theme token 與 light-mode override，保留 night mode 既有視覺；K 線工作台在白天模式仍維持深色圖表背景。

## 驗收結果

- `pnpm build` 通過。
- Browser desktop `1440x900`：
  - 切到夜晚後 `data-theme=night`。
  - `localStorage.top10-theme-mode=night`。
  - 無水平溢出。
- Browser mobile `390x900`：
  - 切到夜晚後 active button 為 `夜晚`。
  - 切回白天後 active button 為 `白天`。
  - `localStorage.top10-theme-mode=day`。
  - theme switcher 可見，hero 無溢出，頁面無水平溢出。
- Diagnostics：
  - console 無 error。
  - `weekly-candidates` 與 `stock detail` API request 均 200。

## Review 派工卡

任務ID：`REVIEW-UI-11`
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-18_UI-11_day_night_theme_mode.md`、`web/frontend/src/app/AppShell.tsx`、`web/frontend/src/styles.css`
任務目的：review 白天 / 夜晚模式是否能保存、切換後不影響候補篩選或 K 線寬度，且 desktop/mobile 無水平溢出。
證據路徑：`artifacts/top10_ui11_theme_mode_acceptance_2026-05-18.json`、`artifacts/top10_ui11_theme_mode_desktop_night_2026-05-18.png`、`artifacts/top10_ui11_theme_mode_mobile_day_2026-05-18.png`
