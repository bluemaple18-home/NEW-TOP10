# WEEKEND-TRAINING-00｜V2 Full Universe Burn-Down Plan

## Root Question

假日任務：把 research map V2 full universe 剩餘格子消耗完，不能蝦跑。

目前狀態：

```text
base scan: 5,913 / 5,913
full universe: 6,057 / 662,256
remaining: 656,199
active queue: 144 / 144
latest active verdict: 22 next_stage / 56 monitor / 66 rejected
```

## 完成定義

`消耗完 60 萬` 的定義不是每一格都跑昂貴 replay。

完成定義是：

```text
每一個 V2 combo 都必須有一個可驗證狀態：
- EXECUTED_REPLAY：真的跑過 replay
- EQUIVALENCE_INHERITED：與已跑代表組等價，繼承 verdict
- RULE_PRUNED：被 deterministic rule 剪枝
- UNSUPPORTED_INPUT：缺資料或目前 runner 不支援
- LOW_INFORMATION：跑了但資訊不足
- NEXT_STAGE_CANDIDATE：可進深度 replay
- REJECTED：淘汰並有原因
```

昂貴 replay 只跑代表組與晉級組；其餘用 deterministic equivalence / pruning 給狀態與證據。

## 原則

- 不准改 production ranking。
- 不准改模型。
- 不准改 Clawd live push。
- 不准把研究 winner 宣稱 production-ready。
- 不准只看 return，不看 drawdown / concentration / turnover / sample size。
- 不准讓星圖進度靠手灌數字。
- 每一階段都要能 refresh 到 research map。

## 工作流

```text
01 inventory/equivalence
  ↓
02 frontier queue builder
  ↓
03 representative replay runner
  ↓
checkpoint A: progress/map/verifier
  ↓
04 deep replay for survivors
  ↓
05 weekend rollup / map review / next queue
```

## 卡片

1. `docs/tasks/2026-06-13_WEEKEND-TRAINING-01_universe_inventory_equivalence.md`
2. `docs/tasks/2026-06-13_WEEKEND-TRAINING-02_frontier_queue_builder.md`
3. `docs/tasks/2026-06-13_WEEKEND-TRAINING-03_representative_replay_runner.md`
4. `docs/tasks/2026-06-13_WEEKEND-TRAINING-04_deep_replay_survivors.md`
5. `docs/tasks/2026-06-13_WEEKEND-TRAINING-05_rollup_and_map_progress.md`

## 假日目標

最小完成：

- 建立 `662,256` 全宇宙 inventory。
- 建立 equivalence class 與 pruning reason。
- 把 `656,199` remaining 至少全部分派到：
  - replay representative
  - inherited
  - pruned
  - unsupported
- 跑完第一批 representative replay。
- 產出 weekend rollup。
- 星圖能顯示 full universe burn-down 進度。

理想完成：

- 全部 representative replay 跑完。
- survivors 完成 deep replay。
- 產出下一週可研究假設與 next-stage queue。

## 驗證總閘門

收尾必跑：

```bash
.venv/bin/python scripts/verify_research_map_v2_schema.py
.venv/bin/python scripts/verify_research_fog_map.py --date 2026-06-13
git diff --check
```

若任一 runner 寫入 `run_history.jsonl`，必須再跑：

```bash
bash scripts/refresh_research_map_from_history.sh
```
