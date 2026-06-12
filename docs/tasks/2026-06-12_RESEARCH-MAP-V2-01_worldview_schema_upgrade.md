# RESEARCH-MAP-V2-01｜研究地圖世界觀 Schema 升級

## Root Question

目前 research fog map 已完成 `5913 / 5913` base scan，但這個完成度會誤導使用者以為整個研究宇宙已完成。

實際上，5913 只覆蓋：

```text
topic × horizon × stop_loss × take_profit × group_exposure
```

它沒有把 `regime_gate`、`risk_guard`、`entry_filter` 等使用者真正關心的策略維度標準化成地圖座標。

本卡要把地圖從「base scan 進度圖」升級成「可擴充的研究世界觀」，讓未來任何策略假設都必須落在同一張地圖裡。

## 使用者原則

地圖的目的不是好看，而是：

- 研究不要失憶
- 不要重跑已測過的東西
- 不要每次新研究都另開世界線
- 失敗也要點燈並留下原因
- 使用者要能靠格點與完成度判斷還有多少研究沒做
- 任何新假設都必須能回到同一張 map 的座標

## 現況問題

### 1. 5913 被誤讀成全宇宙

目前 summary 顯示：

```text
total_combos=5913
processed_combos=5913
progress_pct=1.0
```

這只代表 base scan 完成，不代表全研究宇宙完成。

### 2. 新研究差點變成另一條世界線

`LIQUIDITY-REPLAY-02` 原本被描述成 `+144 expansion scenarios`。

這種寫法容易讓人以為它是另一套地圖。正確做法應該是把地圖 schema 升級為 v2，讓這 144 顆只是 v2 全宇宙裡被選出來優先探索的一小塊。

### 3. 盤勢沒有成為正式座標

使用者一開始就強調 BIG_BULL / HIGH_CHOPPY 是優先盤勢。但 v1 map 沒有把 regime gate 做成正式 scenario axis，導致結果看似完成，實際上盤勢覆蓋不足。

## V2 世界觀

V1 base dimensions:

```text
topic
horizon
stop_loss
take_profit
group_exposure
```

V2 expanded dimensions:

```text
topic
horizon
stop_loss
take_profit
group_exposure
regime_gate
risk_guard
entry_filter
```

建議初版 v2 dimension values：

```text
regime_gate:
- ALL
- BIG_BULL_ONLY
- BIG_BULL_HIGH_CHOPPY
- EXCLUDE_RISK_OFF_PANIC
- RISK_OFF_ONLY
- PANIC_SELLING_ONLY
- NEUTRAL_ONLY

risk_guard:
- NONE
- RISK_OFF_CASH_RAISE
- RISK_OFF_DISABLE
- PANIC_DISABLE

entry_filter:
- TOPIC_DEFAULT
- LOG_GATE
- PERCENTILE_GATE
- LOG_GATE_NON_WORSENING
```

V2 universe count:

```text
73 topics
× 3 horizon
× 3 stop_loss
× 3 take_profit
× 3 group_exposure
× 7 regime_gate
× 4 risk_guard
× 4 entry_filter
= 662,256 scenarios
```

注意：這不代表要立刻跑 662,256 組。

它代表地圖誠實顯示「目前研究宇宙有多大、已探索多少」。

## Migration 規則

原本 5913 顆 v1 已探索 scenario 必須 migrate 到 v2 default coordinate：

```text
regime_gate=ALL
risk_guard=NONE
entry_filter=TOPIC_DEFAULT
```

所以 v2 初始狀態應該是：

```text
base_scan_total=5913
base_scan_processed=5913
expanded_universe_total=662256
expanded_universe_processed=5913
expanded_progress_pct≈0.0089
```

地圖 UI 不能再只顯示 `5913 / 5913 = 100%`。

應該分開顯示：

- Base scan progress: `5913 / 5913`
- Full universe progress: `5913 / 662256`
- Active next queue: 例如 LIQUIDITY-REPLAY-02 的 144 顆
- Dimension coverage by regime / risk_guard / entry_filter

## LIQUIDITY-REPLAY-02 接法

`LIQUIDITY-REPLAY-02` 不准另開新地圖。

它必須從 v2 universe 裡選出 144 顆待探索 coordinate，例如：

```text
topic = liquidity_quality_candidate_universe
horizon = selected from parent evidence
stop_loss = selected from parent evidence
take_profit = selected from parent evidence
group_exposure = selected from parent evidence
regime_gate = ...
risk_guard = ...
entry_filter = ...
```

每個新 run history row 必須包含：

```json
{
  "schema_version": "research-map-run-history.v2",
  "combo_id": "...",
  "map_version": "v2",
  "parent_evidence": "artifacts/research_reviews/liquidity_quality_strict_replay_2026-06-12.json",
  "dimensions": {
    "topic": "...",
    "horizon": "...",
    "stop_loss": "...",
    "take_profit": "...",
    "group_exposure": "...",
    "regime_gate": "...",
    "risk_guard": "...",
    "entry_filter": "..."
  },
  "status": "completed",
  "decision": "...",
  "failure_attribution": [],
  "artifact_path": "..."
}
```

## 任務目的

請完成 research map v2 schema upgrade，讓後續所有研究都落在同一張世界觀地圖。

## 建議修改範圍

- `scripts/research_map_contract.py`
- `scripts/build_research_campaign_progress.py`
- `scripts/build_research_fog_map.py`
- `scripts/verify_research_fog_map.py`
- `scripts/backfill_research_map_run_history.py`
- `artifacts/research_map/index.html` 產生邏輯

如需新增 verifier：

- `scripts/verify_research_map_v2_schema.py`

## 必做功能

1. 定義 v2 dimension schema。
2. 產生 v2 universe total count。
3. 將 v1 5913 migrate 成 v2 default coordinates。
4. `research_fog_map_latest.json` 同時輸出：
   - `base_universe_total`
   - `base_processed`
   - `expanded_universe_total`
   - `expanded_processed`
   - `expanded_progress_pct`
   - `dimension_schema_version`
   - `dimension_values`
5. run history 支援 v1 / v2 共存。
6. v2 combo_id 必須 deterministic。
7. fog map UI 必須能顯示 base progress 與 full universe progress，不得只顯示 100%。
8. LIQUIDITY-REPLAY-02 的 144 顆必須能掛在 v2 coordinate queue 中。

## 禁止事項

- 不准重跑 5913。
- 不准把 v2 當成另一張獨立地圖。
- 不准改 production ranking。
- 不准改模型。
- 不准改 Clawd live push。
- 不准把 `expanded_universe_total` 的完成度包裝成已接近完成。

## 驗證

Verifier 至少檢查：

- v2 universe count 正確。
- v1 migrated rows 為 5913。
- migrated rows 都有：
  - `regime_gate=ALL`
  - `risk_guard=NONE`
  - `entry_filter=TOPIC_DEFAULT`
- `base_processed == 5913`
- `expanded_processed >= 5913`
- `expanded_progress_pct < 0.02`
- `research_fog_map_latest.json` 不得只呈現 `5913 / 5913` 作為唯一完成度。
- `LIQUIDITY-REPLAY-02` queue 若存在，必須使用 v2 coordinate。

## 驗收回報

完成時請回報：

- map schema version
- base universe total / processed / pct
- expanded universe total / processed / pct
- v1 migration count
- active queue count
- dimension values
- LIQUIDITY-REPLAY-02 是否已能掛 v2 coordinate
- production impact
- errors

## 預期結論

完成後，地圖不再宣稱整體研究 100%。

正確語意應該是：

```text
Base scan: complete
Full research universe: early stage
Next actionable area: liquidity quality risk-capped coordinates
```

## 收尾結果｜2026-06-12

狀態：`COMPLETED`

本卡已把 research map 從 v1 base scan 升級為 v2 世界觀座標。

### 已完成

- v2 dimension schema 已定義。
- v1 `5913` 顆已探索 scenario 已 migrate 到 v2 default coordinate。
- fog map 同時顯示 base scan 與 full universe progress。
- `LIQUIDITY-REPLAY-02` 的 `144` 顆 active queue 已掛進 v2 coordinate，不另開世界線。
- run history 仍可保留 v1 row，但 map 生成時會補成 v2 default coordinates。

### 目前數字

```text
map schema version: research-fog-map.v1
dimension schema version: research-map-dimensions.v2
base universe: 5913 / 5913 = 100.0%
expanded universe: 5913 / 662256 = 0.8929%
expanded pending: 656343
active queue: 144
active queue stage: LIQUIDITY-REPLAY-02
```

### V2 維度

```text
regime_gate:
- ALL
- BIG_BULL_ONLY
- BIG_BULL_HIGH_CHOPPY
- EXCLUDE_RISK_OFF_PANIC
- RISK_OFF_ONLY
- PANIC_SELLING_ONLY
- NEUTRAL_ONLY

risk_guard:
- NONE
- RISK_OFF_CASH_RAISE
- RISK_OFF_DISABLE
- PANIC_DISABLE

entry_filter:
- TOPIC_DEFAULT
- LOG_GATE
- PERCENTILE_GATE
- LOG_GATE_NON_WORSENING
```

### 驗證

```text
py_compile: OK
build_research_campaign_progress.py --date 2026-06-12: OK
build_research_fog_map.py --date 2026-06-12: OK
verify_research_fog_map.py --date 2026-06-12: OK
verify_research_map_v2_schema.py: OK
verify_research_map_run_history_backfill.py: OK
git diff --check: OK
```

### Production impact

```text
production ranking changed: false
models/latest_lgbm.pkl changed: false
daily report changed: false
Clawd live push changed: false
```

### 下一步

`LIQUIDITY-REPLAY-02` 可直接從 active queue 的 `144` 顆 v2 coordinates 開始跑，跑完後 append run history，地圖會繼續點燈。
