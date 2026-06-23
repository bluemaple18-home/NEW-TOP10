# WEEKEND-TRAINING-01｜Universe Inventory and Equivalence Map

## 目的

建立 `662,256` 個 V2 combo 的全量 inventory，並找出哪些 combo 在目前 replay runner 下其實等價。

這張卡不跑昂貴 replay，只做 deterministic 分類。

## Input

- `artifacts/research_map/research_fog_map_latest.json`
- `scripts/research_map_contract.py`
- `artifacts/autonomous_research/run_history.jsonl`
- 已存在的 batch / stage2 artifact

## Output

- `scripts/build_weekend_universe_inventory.py`
- `scripts/verify_weekend_universe_inventory.py`
- `artifacts/weekend_training/weekend_universe_inventory_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_universe_inventory_YYYY-MM-DD.md`

## 必須分類

每個 combo 必須至少得到：

```text
combo_id
topic_id
dimensions
current_status
equivalence_key
equivalence_group_size
eligible_for_replay
prune_reason
source_artifact
```

## Equivalence Key

初版 equivalence key 應至少包含：

```text
topic_id
horizon
stop_loss
take_profit
group_exposure
regime_gate_effective_bucket
risk_guard_effective_bucket
entry_filter
rankings_dir_family
```

如果某些 `risk_guard` / `regime_gate` 在目前資料區間對 gross exposure 沒造成差異，必須被歸為同一 equivalence group，而不是重跑浪費。

## 驗收

- inventory count 必須等於 `662,256`。
- 已完成 count 必須等於目前 map 的 `expanded_processed`。
- remaining count 必須等於 `656,199` 或當日最新剩餘數。
- 每個 combo 都有 `equivalence_key`。
- 每個 non-replay combo 都有 deterministic reason。
- 不寫 production artifact。
- 不寫模型。

## Verification

```bash
.venv/bin/python scripts/build_weekend_universe_inventory.py --date 2026-06-13
.venv/bin/python scripts/verify_weekend_universe_inventory.py --date 2026-06-13
git diff --check
```
