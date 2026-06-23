# RESEARCH-MAP-V2-03｜Full Universe Fog Density Layer

## Root Question

星圖已升級到 V2，但視覺上仍主要像 `5,913` 顆 base scenario map。

使用者要看到完整宇宙的存在感：

```text
full universe: 662,256
目前完成: 6,057
剩餘未探索: 656,199
```

但不能把 `662,256` 顆全部做成 DOM 或可點假點。

## 任務目的

在主星圖新增 full universe fog density layer：

- 視覺上能看出未探索 V2 宇宙鋪滿。
- 可互動點仍只限真資料點與 active queue。
- 不讓 662,256 顆變成可 hover/click 的假點。
- zoom / drag 不明顯變慢。

## 設計方向

`dense ops game-map dashboard`

這是一個研究作戰地圖，不是 landing page。

新增 fog layer 應是背景資料層：

- 灰藍細點 / 密度雲，代表未探索 V2 universe。
- 亮色點仍代表真 scenario / completed artifact。
- active queue 用 mission / inspector / active status 呈現，不偽裝成 completed。

## 驗收標準

- `research_fog_map_latest.json` 包含 `full_universe_fog` metadata。
- HTML 具有獨立 fog canvas layer。
- canvas dataset 可驗證：
  - `fullUniverse`
  - `fogSampleCount`
  - `clickableScenarioCount`
- 不建立 `662,256` 個 DOM node。
- `scenario-canvas` 可點資料點數仍等於真 scenario point 數，不等於 full universe。
- `hide-fog` 會關閉 fog canvas。
- browser QA 無 console error / page error。
- zoom / drag 後 canvas 不空白。

## 禁止事項

- 不准改 production ranking。
- 不准改模型。
- 不准改 Clawd live push。
- 不准把 fog layer 當成已探索成果。
- 不准讓灰色迷霧點可點擊或回 artifact。

## 證據

- `artifacts/research_map/index.html`
- `artifacts/research_map/research_fog_map_latest.json`
- `artifacts/research_map/research_fog_map_verification_latest.json`
- `artifacts/research_map/research_fog_map_browser_qa_YYYY-MM-DD.json`
- `artifacts/research_map/evidence/research_map_desktop_YYYY-MM-DD.png`

## 2026-06-12 實作結果

狀態：`IMPLEMENTED_WITH_STATIC_AND_PAYLOAD_VERIFICATION`

已完成：

- `research_fog_map_latest.json` 已包含 `full_universe_fog`。
- `full_universe_fog.full_universe_count = 662256`。
- `full_universe_fog.processed_count = 6057`。
- `full_universe_fog.unexplored_count = 656199`。
- `full_universe_fog.sample_count = 23652`。
- `full_universe_fog.clickable = false`。
- `index.html` 已新增 `universe-fog-canvas`。
- `verify_research_fog_map.py` 已驗證 fog metadata、canvas layer、非 DOM 假點。
- `hide-fog` 會同時關閉背景 fog 與 full-universe canvas。

驗證：

```text
.venv/bin/python scripts/build_research_fog_map.py --date 2026-06-12：OK
.venv/bin/python scripts/verify_research_fog_map.py --date 2026-06-12：OK
.venv/bin/python scripts/verify_research_map_v2_schema.py：OK
.venv/bin/python -m py_compile scripts/build_research_fog_map.py scripts/verify_research_fog_map.py：OK
git diff --check：OK
```

瀏覽器證據：

- 既有 2026-06-12 browser QA / screenshot 可檢視目前 V2 星圖讀數：
  - `artifacts/research_map/research_fog_map_browser_qa_2026-06-12.json`
  - `artifacts/research_map/evidence/research_map_desktop_2026-06-12.png`
- 本輪嘗試重跑 headless / CDP browser QA 時，遇到本機瀏覽器自動化限制：
  - Playwright bundled Chromium headless shell 缺失。
  - system Chrome headless 啟動後 `SIGABRT`。
  - Chrome CDP 可啟動，但 sandbox 內 Node 連 localhost 被 `EPERM` 擋住。
- 因此本輪不宣稱完整 browser QA 已重新跑過；目前可驗證狀態以 payload / HTML / verifier 為準。

Production impact：`NO_PRODUCTION_CHANGE`
