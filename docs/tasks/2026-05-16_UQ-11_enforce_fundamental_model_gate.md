# UQ-11：Enforce Fundamental Model Gate

任務ID：`UQ-11`
卡片類型｜派工對象：Model Feature Gate / 回歸修復｜Codex
請讀：`docs/tasks/2026-05-16_UQ-04_fundamental_shadow_rerun.md`、`docs/tasks/2026-05-16_UQ-05_ranking_integration_gate.md`、`app/modeling/feature_contract.py`、`app/agent_b_modeling.py`
任務目的：避免 real universe 下低 coverage 的 `fundamental_*` 欄位進入 LightGBM 訓練與最新模型 artifact。
證據路徑：`app/modeling/feature_contract.py`、`scripts/verify_model_foundation.py`、`scripts/verify_review_fixes.py`、`models/latest_lgbm.pkl`。

狀態：`completed`

## 背景

UQ-04 / UQ-05 已確認 real universe 基本面 coverage 約 `1.17%`，不可作為 ranking 權重依據。UQ-10 已修 ranking policy，但模型 feature contract 仍會把 `fundamental_*` 納入 candidate features，導致新模型可能學到低 coverage 噪音。

## 範圍

- 在 feature contract 層加 coverage gate。
- coverage 未達門檻時，保留 fundamental metadata / 欄位，但不放入 candidate features。
- 保留 coverage 足夠時重新接入模型的路徑。
- 重新訓練 `models/latest_lgbm.pkl`，讓目前正式模型不再使用低 coverage fundamental features。

## 不做

- 不刪基本面 cache。
- 不刪基本面 feature metadata。
- 不調 label / threshold / ranking 權重。

## 驗收

- 低 coverage fundamental 欄位不進 `candidate_feature_columns()`。
- coverage 足夠的 fixture 仍可把 fundamental 欄位放入候選特徵。
- 最新 `models/latest_lgbm.pkl` 的 feature list 不含 `fundamental_*`。
- ranking smoke 成功載入重訓模型。

## 執行紀錄

- 更新 `app/modeling/feature_contract.py`
  - 新增 `MIN_FUNDAMENTAL_FEATURE_COVERAGE = 0.80`。
  - `candidate_feature_columns()` 在基本面 cache coverage 未達門檻時，跳過 `fundamental` feature group。
  - metadata 與 `fundamental_*` 欄位仍保留，供 shadow / UI / future gate 使用。
- 更新 `app/agent_b_modeling.py`
  - 模型訓練 log 明確顯示基本面 coverage 未達 gate 時，不使用 `fundamental_*` 欄位。
- 更新驗證：
  - `scripts/verify_review_fixes.py`：缺基本面 cache 時，fundamental 欄位不進候選特徵。
  - `scripts/verify_m4_full_features.py`：real universe 低 coverage 時，feature columns 不含 `fundamental_*`。

## 重訓紀錄

```bash
uv run --with-requirements requirements.txt python -m app.agent_b_modeling
```

結果：

- labeled samples：`95632`
- positive samples：`22633` (`23.7%`)
- fundamental cache coverage：`1.2%`
- training feature count：`86`
- fundamental feature count：`0`
- Optuna best AUC：`0.6951`
- walk-forward AUC：
  - Fold 1：`0.6136`
  - Fold 2：`0.5994`
  - Fold 3：`0.6752`
  - Fold 4：`0.7024`
  - Fold 5：`0.7178`
- walk-forward mean AUC：`0.6617`
- 已更新 `models/latest_lgbm.pkl`
- 已更新 `artifacts/feature_importance.png`

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python scripts/verify_m4_full_features.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
uv run --with-requirements requirements.txt python -c "import pickle; obj=pickle.load(open('models/latest_lgbm.pkl','rb')); names=obj['model'].feature_name(); print(len(names), [n for n in names if n.startswith('fundamental_')])"
```

結果：

- `MODEL_FOUNDATION_OK specs=11`
- `REVIEW_FIXES_OK`
- `M4_FULL_FEATURES_OK`
- `verify_data_contracts.py` 通過
- model feature count：`86`
- model `fundamental_*` features：`[]`
- ranking smoke 成功載入重訓模型並輸出 `artifacts/ranking_2026-05-15.csv`

## 結論

模型端與推薦端都已遵守同一個 fundamental gate：低 coverage 基本面資料可以保留在 shadow / 解釋層，但不會影響 LightGBM 訓練，也不會影響 ranking score。
