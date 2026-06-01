# AUTO-TRAINING-01 model governance review close

## 任務ID

`AUTO-TRAINING-01`

## 卡片類型｜派工對象

Review Close / Model Governance｜Codex

## 請讀

- `.work/REVIEW-20260601-model-gov-full/brief.md`
- `.work/REVIEW-20260601-model-gov-full/result.md`
- `docs/tasks/2026-05-31_MODEL-GOV-FULL_implementation_card.md`
- `docs/architecture/MODEL_EXPERIMENT_LEDGER.md`

## 任務目的

收掉 `MODEL-GOV-FULL` review，確認 ledger 只作長期狀態記憶與 promotion evidence adapter，不取代 sealed/replay/rollback/model acceptance。

## 要做

- 確認 5 個 review finding 都已修復。
- 確認 `PyYAML` 問題已歸類為執行方式問題，不是 dependency 缺口。
- 確認 `model_exp_result_report_2026-06-01.json` 已重建且 verifier 通過。
- 確認 readiness 回到 `READY_FOR_AUTOMATED_TRAINING_REVIEW`。
- 更新 `.work/REVIEW-20260601-model-gov-full/status.md` 與 `result.md`。
- 準備 commit / push，若 PM 要求才執行。

## 不可做

- 不修 daily report 缺 `ranking_2026-05-31.csv`。
- 不啟動正式 retrain。
- 不把 `LEDGER_EVIDENCE_OK` 當 promotion ready。

## 驗收

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_result_report.py --artifact artifacts/model_experiments/model_exp_result_report_2026-06-01.json
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 回報格式

```text
AUTO-TRAINING-01 status:
review findings:
result report verify:
readiness:
training_launch_ready:
promotion_ready:
commit/push:
errors:
```
