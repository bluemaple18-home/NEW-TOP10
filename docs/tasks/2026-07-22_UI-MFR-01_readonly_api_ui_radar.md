---
card_id: UI-MFR-01
chain_id: TOP10-NEXT-WAVE-20260722
status: INTEGRATED_READ_ONLY
type: vertical-api-ui-slice
owner: receiving Mini
model: receiving Mini
reasoning: medium
model_reason: 使用者指定 Mini；以 read-only fixture/API 與 evidence-first browser acceptance 控制產品風險。
thickness: strict
depends_on: [TSKG-MFO-THEME-01]
optional_dependency: TSKG-MFO-GRAPH-01_for_graph_drilldown
worktree: receiving_host_must_provision
---

# UI-MFR-01 Read-only Market Flow Radar

任務ID：UI-MFR-01
卡片類型｜派工對象：Read-only API + UI Vertical Slice｜Mini
請讀：docs/tasks/2026-07-20_UI-MFR-00_market_flow_radar_backlog.md、web/frontend/src/app/MarketDeskApp.tsx、web/frontend/src/api.ts、web/frontend/src/types.ts
任務目的：交付一條可驗收的 read-only 市場資金雷達路徑，顯示 Theme flow、日期、freshness、coverage、來源與證據
證據路徑：docs/evidence/UI-MFR-01/、artifacts/ui_mfr_01/

## Scope

- 後端提供 versioned read-only response；無核准 live source 時使用 approved deterministic fixture。
- 前端新增 radar 頁面/研究模式、Theme 排名或受控圖表、詳情與歷史資料狀態。
- 必須支援 loading、empty、error、stale、partial coverage。
- 關聯候選與 Top10 recommendation 清楚分層，不寫成買進建議。
- Graph drilldown 只有 TSKG-MFO-GRAPH-01 GO 時才啟用，否則明確隱藏或標為 unavailable。
- 不新增登入、付款、推播、watchlist external write 或 production feature mutation。

## Likely allowlist

- app/tskg/router.py
- app/tskg/service.py
- 對應 API contract/tests
- web/frontend/src/features/market-flow/**
- web/frontend/src/app/MarketDeskApp.tsx
- web/frontend/src/api.ts
- web/frontend/src/types.ts
- web/frontend/src/styles.css
- frontend tests
- docs/tasks/、docs/evidence/、.work/ 本卡路徑

## Verification

```bash
pnpm --dir web/frontend build
uv run pytest <affected-api-tests>
git diff --check
```

另需 desktop/mobile browser evidence、console/page error clean、keyboard path、reduced motion、無重疊/爆版，以及 loading/empty/error/stale/partial coverage screenshots。
