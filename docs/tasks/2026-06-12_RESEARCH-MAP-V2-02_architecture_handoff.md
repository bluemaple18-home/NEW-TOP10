# RESEARCH-MAP-V2-02｜星圖架構變更交接卡

## 任務ID

`RESEARCH-MAP-V2-02-architecture-handoff`

## 卡片類型｜派工對象

Architecture Handoff / Research Runner Integration｜Codex

## Root Question

星圖現在已經不是 `5913` 顆的 v1 base scan。

目前架構已升級為 v2 世界觀：

```text
base scan: 5913 / 5913
full universe: 5913 / 662256
active queue: LIQUIDITY-REPLAY-02 144 scenarios
```

後續任何研究、訓練、回測、shadow runner 都必須寫進同一張星圖，不准另開世界線。

## 請讀

- `docs/tasks/2026-06-12_RESEARCH-MAP-V2-01_worldview_schema_upgrade.md`
- `scripts/research_map_contract.py`
- `scripts/build_research_fog_map.py`
- `scripts/verify_research_map_v2_schema.py`
- `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-02_v2_component_batch.md`

## 新架構摘要

V2 dimensions：

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

總宇宙：

```text
73 topics × 81 base scenarios × 112 v2 expansion multiplier = 662256
```

v1 5913 已 migrate 到：

```text
regime_gate=ALL
risk_guard=NONE
entry_filter=TOPIC_DEFAULT
```

## Runner 接入契約

新的 runner 每完成一顆星，必須 append：

```text
artifacts/autonomous_research/run_history.jsonl
```

必要欄位：

```json
{
  "schema_version": "research-map-run-history.v2",
  "map_version": "v2",
  "combo_id": "...",
  "dimensions": {},
  "status": "completed",
  "decision": "...",
  "insight_level": "...",
  "return_delta": 0.0,
  "drawdown_delta": 0.0,
  "artifact_path": "...",
  "finished_at": "..."
}
```

## 禁止事項

- 不准再用 `5913 / 5913` 表示全貌完成。
- 不准把新研究寫到 map 以外的平行紀錄。
- 不准把缺 artifact 的 scenario 當成已完成。
- 不准讓 research runner 改 production ranking / model / live push。

## 交接短卡

```text
任務ID：LIQUIDITY-REPLAY-02
卡片類型｜派工對象：Research Replay / Codex
請讀：docs/tasks/2026-06-12_LIQUIDITY-REPLAY-02_v2_component_batch.md、scripts/research_map_contract.py、artifacts/research_map/research_fog_map_latest.json
任務目的：從 research map v2 active queue 跑 144 顆 liquidity component replay，完成後 append run_history 並刷新星圖
證據路徑：artifacts/research_reviews/liquidity_replay_v2_batch_YYYY-MM-DD.json、artifacts/autonomous_research/run_history.jsonl、artifacts/research_map/research_fog_map_latest.json
```

