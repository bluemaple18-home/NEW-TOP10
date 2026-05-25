# UQ-08：恢復 latest_lgbm 模型產物

任務ID：`UQ-08`
卡片類型｜派工對象：模型訓練 / 推論恢復｜Codex
請讀：`app/agent_b_modeling.py`、`app/agent_b_ranking.py`、`docs/tasks/2026-05-16_UQ-07_staged_real_universe_rebuild.md`
任務目的：在 real universe `data/clean` 已修復後，恢復 `models/latest_lgbm.pkl`，避免 ranking 長期使用 `model_prob=0.5` fallback。
證據路徑：`models/latest_lgbm.pkl`、必要驗證輸出、`artifacts/ranking_*.csv`。

## 背景

UQ-07 ranking smoke 可跑，但 `models/latest_lgbm.pkl` 不存在，ranking 使用 fallback model probability。這可以驗證 UI/規則流程，但不能代表正式模型推論。

## 範圍

- 使用現有 real universe features 訓練 LightGBM。
- 儲存 `models/latest_lgbm.pkl`。
- 跑 ranking smoke，確認可載入模型。

## 不做

- 不把 fundamental score 接 ranking。
- 不調 ranking 權重。
- 不用假模型檔替代訓練結果。

## 驗收

- `models/latest_lgbm.pkl` 存在。
- ranking smoke 不再印出「找不到模型檔案」。
- 若訓練失敗，需記錄 root cause 與下一步，不得製造假模型。

## 執行紀錄

- 狀態：`completed`
- 完成時間：`2026-05-16`
- 產物：
  - `models/latest_lgbm.pkl`
  - `artifacts/feature_importance.png`
  - `artifacts/ranking_2026-05-15.csv`

## 訓練結果

- 訓練資料：`data/clean/features.parquet`
- feature rows：`115283`
- labeled samples：`95632`
- positive samples：`22633` (`23.7%`)
- feature count：`95`
- fundamental cache coverage：`1.2%`
- Optuna best validation AUC：`0.6981`
- Walk-forward AUC：
  - Fold 1：`0.6164`
  - Fold 2：`0.6039`
  - Fold 3：`0.6786`
  - Fold 4：`0.7042`
  - Fold 5：`0.7188`
- 平均 AUC：`0.6644`

## Ranking Smoke

```bash
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
```

結果：

- 成功載入 `latest_lgbm.pkl` 與 calibrator。
- 不再使用 `model_prob=0.5` fallback。
- 成功輸出 `artifacts/ranking_2026-05-15.csv`。

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --data-dir data
```

結果：

- `verify_model_foundation.py` 通過。
- pipeline validate 通過，仍保留 `ma20 / bb_middle` latest coverage WARN。
