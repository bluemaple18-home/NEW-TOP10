---
card_id: UI-MFR-00
chain_id: MARKET-FLOW-RADAR
title: 市場資金雷達前端概念 backlog
status: BACKLOG
type: frontend
owner: Codex 主線
assignee: UNASSIGNED
thickness: standard
risk: medium
source_kind: concept
source_reference: https://tide-tw.app/
related_handoff: docs/handoff/handoff_20260720_tide_tskg_concepts.md
evidence_first: true
implementation_authorized: false
---

# UI-MFR-00：市場資金雷達前端概念 backlog

## 任務目的

封存 Tide 類市場資金雷達的可用前端概念，供資料與 TSKG 契約成熟後重新評估。現在不實作、不掛路由、不在現有前端顯示。

## Root Question

當 Theme、法人資金 observation 與歷史 snapshot 都具備可驗證契約後，是否值得在 TOP10new 增加一個以市場探索為主、但不取代現有 Top10 決策工作台的市場資金雷達？

## Status

`BACKLOG / NOT SCHEDULED / NOT AUTHORIZED`

這張卡只有概念保存功能，不是派工卡，也不是下一張自動執行卡。

## Visual Route Contract

```text
visual_route:
  product_type: 台股研究型資料儀表板
  audience: 已理解基本籌碼與 Top10 排名的波段研究者
  primary_layout_move: 左側市場狀態＋中央探索圖＋右側觀察清單
  information_density: 高密度、可掃描、桌面優先，行動版改為分頁而非硬縮三欄
  type_scale: 緊湊 dashboard hierarchy，數值強、說明弱
  palette_strategy: 中性色為主；紅綠只表達漲跌／流入流出，另提供色盲與市場慣例切換
  asset_strategy: 真實市場資料圖、關係路徑與歷史軌跡；不使用裝飾性假圖
  anti_patterns_to_avoid: 泡泡標籤全面重疊、卡片套卡片、只靠顏色傳意、把關聯候選寫成買進建議
```

## 候選資訊架構

```text
市場狀態列
大盤狀態｜資料日期｜freshness｜搜尋｜檢視切換

左側市場摘要
漲潮／輪動／觀望／退潮
市場風險與資料異常

中央主區
Theme 資金泡泡圖／排行榜／歷史回放

右側研究清單
自選股／關聯公司／異常觀測

詳情 Drawer
Theme 成分、圖譜關係路徑、證據、資金時間序列、Top10 狀態
```

## 可重用的現有前端

- `web/frontend/src/app/AppShell.tsx`：應用 Shell、日夜模式。
- `web/frontend/src/app/MarketDeskApp.tsx`：現有工作台狀態與頁面切換模式。
- `web/frontend/src/components/Panel.tsx`、`Button.tsx`、`MetricPill.tsx`：基礎元件。
- `web/frontend/src/features/ranking/RankingPanel.tsx`：排行榜交互模式。
- `web/frontend/src/features/stock-detail/StockDetailPanel.tsx`：個股詳情與圖表承載。
- `web/frontend/src/charts/KLineWorkbench.tsx`：時間序列圖與 interaction lifecycle 經驗。

## 不直接重用／需新增

- 現有 `klinecharts` 不適合承擔板塊泡泡圖；未來需評估 ECharts、D3 或受控 Canvas/SVG 實作。
- 需新增 `ThemeFlowObservation`、歷史回放與 graph context API contract。
- 需處理泡泡碰撞、標籤裁切、zoom/pan、鍵盤操作、tooltip 與 reduced motion。
- 行動版應將三欄拆成 `摘要／圖表／清單` tabs，不做縮小版桌面畫面。

## Backlog Slices

| Slice | Input → Output | Blocking edges | Acceptance / Verification | Status |
|---|---|---|---|---|
| UI-MFR-01 Static concept | approved fixture → desktop/mobile static radar | Visual route approved、fixture contract fixed | desktop/mobile screenshots、無重疊/爆版、不接 production | blocked |
| UI-MFR-02 Interactive bubble prototype | fixture history → zoom/pan/filter/tooltip/replay | UI-MFR-01、chart library ADR | deterministic labels、keyboard path、reduced motion、canvas/SVG nonblank | blocked |
| UI-MFR-03 Read-only data integration | approved observation API → radar/rankings | TSKG-MFO-03、API contract、freshness semantics | loading/error/stale/empty paths、contract test、browser acceptance | blocked |
| CP-MFR-A Visual/data checkpoint | MFR-01..03 → review evidence | MFR-01..03 | desktop/mobile evidence、console clean、data date/provenance visible | checkpoint |
| UI-MFR-04 Graph drilldown | bubble/stock → evidence-backed relation drawer | TSKG SLC-09、MFR-03 | relation path/evidence/freshness visible；no unsupported claims | blocked |
| UI-MFR-05 Watchlist and alerts | user selection → persisted list/notification preferences | auth/privacy/notification contracts、MFR-04 | explicit consent、reversible settings、no accidental external write | blocked |
| UI-MFR-06 Growth/payment surfaces | plan/referral/payment state → account UI | separate business approval、legal/payment contracts | end-to-end sandbox acceptance and explicit confirmations | deferred |

## Blocking Edges

前端不可開始，直到至少符合：

1. TSKG Theme membership 具 evidence 與 versioned snapshot。
2. `SecurityFlowObservation`／`ThemeFlowObservation` 契約核准。
3. 資金加速度、異常門檻與聚合公式有 owner、版本及 deterministic fixture。
4. 主線決定市場雷達是新頁面、研究模式或現有工作台的一部分。

接 production 前還需：

5. 官方來源治理與 daily freshness/late-data 行為完成。
6. 圖譜＋資金特徵若要影響 Top10，必須另有 walk-forward 回測證據。

## Current Frontier

無。`UI-MFR-01` 仍等待 visual route、fixture 與主線優先級核准；本卡本身不解除 blocker。

## Acceptance Boundary

- 「畫面做得出來」不等於資料、公式或產品完成。
- 第一階段只能使用 synthetic/approved fixture，不可假裝為即時資料。
- 正式 UI 必須清楚顯示資料日期、freshness、來源與公式說明入口。
- 關聯觀察候選與 Top10 模型候補必須在視覺與文案上分層。
- 不做 Tide 像素級複製；只吸收資訊架構、探索流程與每日回訪機制。

## Verification When Activated

- `pnpm --dir web/frontend build`
- 受影響的 component/contract tests。
- desktop 與 mobile browser screenshots。
- 核心路徑：切換檢視、篩選、選泡泡、開關詳情、回放、empty/error/stale。
- console/page error 檢查。
- `git diff --check`。

## Likely Files When Activated

- `web/frontend/src/app/MarketDeskApp.tsx`
- `web/frontend/src/features/market-flow/**`
- `web/frontend/src/charts/**`
- `web/frontend/src/types.ts`
- `web/frontend/src/api.ts`
- `web/frontend/src/styles.css`
- 對應 API contract/router/service/tests；實際 allowlist 由未來正式卡決定。

## Explicitly Forbidden Now

- 不修改 `web/frontend/**`。
- 不新增 chart dependency。
- 不新增 route、API、資料表、排程、登入、推播或金流。
- 不把本 backlog 當作 TSKG 當前 frontier 或 implementation authorization。

## Reactivation Condition

只有在主線明確說「啟動 UI-MFR」並建立正式實作卡、鎖定 allowlist、資料 fixture、驗收與 browser evidence 路徑後，才能從 backlog 轉入 planning／implementation。
