# M4-02：LightGBM 改吃技術 + 事件 + 基本面，維持 walk-forward

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`M4-02`
卡片類型｜派工對象：模型訓練｜另一個 coding model
請讀：`docs/tasks/2026-05-12_M4-01_feature_contract.md`、`app/agent_b_modeling.py`、`app/labels.py`、`app/modeling/registry.py`、`app/monitoring/factor_monitor.py`
任務目的：讓 M4 報酬預測模型使用合併後特徵訓練，並保留 walk-forward、purge、交易日切分。
證據路徑：新增或更新 `scripts/verify_model_foundation.py` / `scripts/verify_review_fixes.py`，必要時新增 `scripts/verify_m4_full_features.py`。

## 前置依賴

- 必須先完成 `M4-01`。

## 範圍

- `prepare_train_data()` 必須可排除非 feature 欄位，但保留技術、事件、基本面數值欄位。
- walk-forward split、Optuna split、purge 全部繼續使用 `trade_date`。
- 模型 artifact metadata 必須記錄 feature groups 與實際使用欄位。
- 訓練資料若沒有基本面欄位，流程可以降級但要明確警告；若有欄位，必須被納入 candidate features。

## 不做

- 不調整 M7 ranking 權重。
- 不改 UI。
- 不新增即時外部資料抓取。

## 驗收

- LightGBM feature list 中可看到技術、事件、基本面三類欄位。
- walk-forward 驗證仍跑得動，且 train fold 尾端仍有 purge。
- label 仍使用 D+1 entry / D+N exit，不因基本面 join 改變。
- `scripts.run_automation daily --dry-run` 不壞。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile app/agent_b_modeling.py
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run
```

## 完成紀錄（2026-05-17）

- `app/agent_b_modeling.py` 已使用 M4 feature contract 的候選欄位邏輯。
- walk-forward / Optuna split / purge 仍以交易日切分。
- `scripts/verify_review_fixes.py` 覆蓋：
  - walk-forward purge。
  - walk-forward 使用 trade dates。
  - duplicate label key 拒絕。
  - candidate feature 排除非 feature 欄位。
  - ranking inference 使用 M4 feature contract。
- 基本面欄位受 UQ-11 model gate 管控：coverage 未達標時不得偷渡進 LightGBM。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
```

結果：通過。

重點輸出：

- `MODEL_FOUNDATION_OK specs=11`
- `REVIEW_FIXES_OK`

註：`verify_review_fixes.py` 會刻意觸發一次「找不到 features.parquet」的 ranking failure regression；最後輸出 `REVIEW_FIXES_OK` 代表該預期失敗已被正確攔截。

## Review 重點

- 是否有 row-based split 回潮。
- 是否把 `trade_date`、`target`、`future_return`、價格未來欄位誤當 feature。
- 是否讓缺基本面資料導致訓練 silently 只剩技術欄位但沒有 metadata。
