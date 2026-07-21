---
id: TSKG-TIDE-CONCEPT-HANDOFF-01
status: READY_FOR_REVIEW
type: handoff
date: 2026-07-20
source: https://tide-tw.app/
target_chain: TSKG
related_spec: docs/specs/TSKG_v1.1.md
frontend_backlog: docs/tasks/2026-07-20_UI-MFR-00_market_flow_radar_backlog.md
---

# Tide 市場資金概念 → TSKG 交接

## Goal

把 Tide 類產品中可沿用的市場資金概念整理成 TSKG 後續設計輸入；本交接只保存概念與邊界，不修改 TSKG v1.1、不加入排名權重，也不實作前端。

## Root Question

如何讓 TSKG 的公司、Theme、Product、Industry 與供應鏈關係，未來能安全承接每日法人資金流，提供可解釋的市場觀察，而不把短期訊號誤建模成穩定知識或投資結論？

## Blocker

- TSKG 目前只有 SLC-01 synthetic identity-to-company query 完成。
- SLC-02 真實 relationship claim 仍受來源治理核准阻擋。
- 尚未建立官方法人資料的每日 snapshot 契約、Theme 成分權威與 aggregation 規則。
- 尚未回測圖譜關係加上資金擴散是否具有增量預測價值。

## Candidate Fork

- `TSKG-MFO-01`：Market Flow Observation 契約，屬知識圖譜／資料設計候選。
- `UI-MFR-00`：市場資金雷達前端，已封存為 backlog；目前禁止進入 runtime 或現有前端。

## Constraints & Preferences

- Tide 只作產品概念參考；不大量抓取、不複製其資料、公式、程式或像素級介面。
- 真實市場資料應直接取自經治理核准的官方來源，例如臺灣證券交易所與櫃買中心。
- 每日法人買賣、資金加速度、異常倍數與市場情緒是時間序列觀測，不是 `RelationshipClaim`。
- TSKG 關係層只保存具 evidence 的穩定語意，例如公司屬於 Theme、公司生產 Product、公司供應另一組織。
- 圖譜輸出的「相關候選」不得轉寫為補漲、買進、賣出、報酬或其他交易判斷。
- 任何資金特徵進入 Top10 ranking 前，必須有公式版本、資料時間、walk-forward 回測及無 leakage 證據。

## 可吸收的核心概念

### 1. 結構與觀測分層

```text
TSKG 結構層（較慢變動）
Organization / Security / Theme / Product / Industry
RelationshipClaim + Evidence + valid_time + system_time

市場觀測層（每日變動）
SecurityFlowObservation
ThemeFlowObservation
MarketRegimeObservation

Top10 分析層（研究與回測）
既有模型特徵 + 市場觀測特徵 + graph context
```

市場觀測必須能刪除、重算與版本化；不得因每日值改變而改寫 TSKG canonical fact。

### 2. 建議觀測實體

#### `SecurityFlowObservation`

最低欄位候選：

- `observation_id`
- `security_id`
- `trade_date`
- `investor_type`：`FOREIGN/INVESTMENT_TRUST/DEALER/ALL_INSTITUTIONAL`
- `net_buy_value_1d`
- `net_buy_value_5d`
- `net_buy_value_20d`
- `price_change_5d`
- `flow_acceleration`
- `flow_force_ratio`
- `anomaly_type`
- `formula_version`
- `source_id/evidence_id`
- `observed_at/retrieved_at`
- `freshness/is_stale`

#### `ThemeFlowObservation`

最低欄位候選：

- `observation_id`
- `theme_id`
- `taxonomy_version`
- `membership_snapshot_id`
- `trade_date`
- `constituent_count/included_count/excluded_count`
- `aggregation_method`
- `net_buy_value_1d/5d/20d`
- `price_change_5d`
- `flow_acceleration`
- `formula_version`
- `input_snapshot_hash`
- `freshness/provenance`

Theme 聚合必須固定 membership snapshot，否則歷史回放會因今日分類改動而重寫過去。

### 3. 可解釋的資金擴散

TSKG 可提供一跳關係與證據，市場觀測層提供每日資金狀態，研究層才做組合：

```text
Top10 標的
  → 查一跳 Theme／Product／Supplier／Customer／Competitor
  → 對齊各 SecurityFlowObservation
  → 產生同步流入、領先／落後、分歧等研究特徵
  → walk-forward 回測
```

在通過回測以前，只能輸出：

- `related_observation_candidate`
- 關係路徑
- 關係 evidence
- 各節點的資金觀測值與資料日期

禁止輸出「補漲股」「即將上漲」「買進訊號」。

### 4. 可沿用的查詢入口

- Company：公司、Security、Theme、Product、供應鏈與最新資金觀測。
- Theme：成分關係及某交易日的聚合資金狀態。
- Related：具 evidence 的一跳候選，加上各候選的資金觀測；不排序成交易建議。
- History：依 `trade_date` 回查當時的 observation，並固定當時 taxonomy/membership snapshot。
- Daily diff：新增、修訂、缺漏、來源延遲及重算差異都需進 change report。

## 建議後續切片

| Slice | Input → Output | Blocking edges | Acceptance / Verification | Frontier |
|---|---|---|---|---|
| TSKG-MFO-01 Observation contract | synthetic official-shaped rows → validated `SecurityFlowObservation` | 需先決定欄位、單位、公式 ownership；不依賴 DB/UI | schema gate、日期/單位/null/重複鍵、公式版本、prohibited prediction fields | 候選 frontier，需主線核准新卡 |
| TSKG-MFO-02 Theme membership snapshot | evidence-backed Theme claims → immutable membership snapshot | TSKG SLC-02/03 完成、Theme source governance 核准 | membership hash、taxonomy version、as-of round-trip | blocked |
| TSKG-MFO-03 Theme aggregation | membership snapshot + Security observations → Theme observations | MFO-01/02 | deterministic recompute、coverage、excluded reasons、checksum | blocked |
| CP-MFO-A Contract checkpoint | MFO-01..03 → contract review | MFO-01..03 | identity/time/provenance 與 TSKG v1.1 相容 | checkpoint |
| TSKG-MFO-04 Graph-flow research export | Top10 IDs + one-hop graph + observations → offline research artifact | TSKG SLC-09、MFO-03 | 路徑/evidence/date 完整、禁止交易語句與線上 ranking mutation | blocked |
| TSKG-MFO-05 Predictive value evaluation | research artifact → walk-forward comparison | MFO-04、回測契約 | leakage gate、baseline comparison、IC/hit-rate/turnover、negative result retained | blocked |

目前只有 `TSKG-MFO-01` 可作候選 frontier，但仍需 TSKG 主線正式開卡；不得從本 handoff 自動續作。

## 不應沿用的部分

- Tide 的專有板塊分類、異常門檻、情緒分數與 AI 摘要公式，除非取得可核准來源與定義。
- 把圖上右上角直接視為最強標的或買進訊號。
- 用今日 Theme membership 重算歷史資金排行。
- 把 extraction confidence、模型分數或資金強弱當成 graph truth。
- 為了泡泡圖先擴充 production API 或現有前端。

## Completed Actions

- 唯讀研究 `https://tide-tw.app/` 的首頁、排行榜、今日摘要、定價、PWA 與公開政策。
- 對照 `docs/specs/TSKG_v1.1.md` 的 identity、claim/evidence、temporal、API 與 Top10 邊界。
- 確認目前 `docs/evidence/TSKG-SLC-01/verification.md` 只證明 synthetic identity path，不證明真實關係或市場資料。
- 將前端構想移至 `docs/tasks/2026-07-20_UI-MFR-00_market_flow_radar_backlog.md`。

## Active State

- 工作目錄：`<repo-root>`。
- 本次只新增 handoff 與 backlog 文件。
- 未修改 `app/**`、`web/frontend/**`、`config/**`、資料、模型、API 或 TSKG spec。
- 未啟動 server，未寫入外部服務。
- worktree 原有其他未提交修改，本次未觸碰。

## In Progress / Remaining Work

- TSKG 主線需重新判斷是否接受 `TSKG-MFO-01` 為新 fork。
- 若接受，先把 observation schema 與 deterministic fixture 寫成正式任務卡，再實作。
- 前端 backlog 維持封存，直到其 blocking edges 全部解除。

## Blocked & Errors

- 本次沒有執行錯誤。
- 記憶召回查無相關既有 Tide／TSKG market-flow 記錄；本 handoff 是目前主要交接來源。

## Key Decisions & Resolved Questions

- 已決定：Tide 類資金資料放在 observation layer，不放進 canonical relationship layer。
- 已決定：TSKG 只提供可解釋關聯；預測價值由 Top10 research/backtest 驗證。
- 已決定：前端不先出現，另列 backlog，不視為 TSKG 當前 frontier。
- 未決定：法人資料 source registry、Theme membership authority、aggregation 公式與 anomaly threshold。

## Next Step

TSKG 主線讀取本 handoff，判斷是否建立 `TSKG-MFO-01` 正式卡；若不建立，本文保留為 deferred concept，不觸發任何實作。

## Waiting Conditions

- 需要 TSKG 主線明確接受 fork 與 observation layer 邊界。
- 涉及真實來源前，需通過 Source Gate。
- 涉及排名前，需通過離線回測與 leakage gate。

## Limits

- 本文不是 TSKG v1.1 規格增補，也不是 implementation authorization。
- 本文不證明任何公式、板塊關係、資金訊號或預測有效。
- 本文不授權前端、API、外部來源、資料庫、排程或 production 變更。
