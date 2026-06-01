# AUTO-TRAINING-05 half-year negative fold diagnostics

## 任務ID

`AUTO-TRAINING-05`

## 卡片類型｜派工對象

No-Hindsight Diagnostics / Model Research｜Codex

## 請讀

- `artifacts/model_experiments/half_year_walkforward_validation_2026-05-31.json`
- `scripts/research_regime_feature_offline_ablation.py`
- `scripts/verify_half_year_walkforward_no_hindsight.py`
- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`

## 任務目的

針對半年 walk-forward 的負 fold 做下一輪診斷實驗，找出不穩定來源，但不得回頭修改同一輪 gate 或用 post-hoc filter 讓歷史結果變好看。

## 背景

半年 walk-forward 目前是 `MONITOR_ONLY`。整體有訊號，但存在負 uplift / flat folds：

- `2026-02-06~2026-03-17`
- `2026-04-17~2026-05-15`

這些只能作下一輪 hypothesis input。

## 要做

- 把負 fold 拆成可驗證假設：
  - 模型訊號不穩？
  - ranking rule 推太多假突破？
  - 盤勢 tag 需要 ranking 分流？
  - portfolio sizing / risk overlay 不穩？
- 每個假設都進 ledger。
- 新實驗必須使用新的 walk-forward / sealed / replay，不能修改原 artifact 結論。
- 輸出下一輪 research plan。

## 不可做

- 不調舊 artifact 的 gate。
- 不把 diagnostic-only result 變 promotion evidence。
- 不新增同輪 filter 回頭修過去。
- 不把 `MONITOR_ONLY` 改成 `PROMOTE_CANDIDATE`。

## 驗收

```bash
uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --artifact artifacts/model_experiments/half_year_walkforward_validation_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --self-test
uv run --with-requirements requirements.txt python scripts/model_experiment_ledger.py list --status pending
git diff --check
```

## 回報格式

```text
AUTO-TRAINING-05 status:
negative folds:
hypotheses:
ledger entries:
next experiment artifacts:
promotion allowed:
errors:
```
