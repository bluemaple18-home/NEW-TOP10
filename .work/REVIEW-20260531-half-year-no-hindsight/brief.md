# REVIEW-20260531-half-year-no-hindsight

## 卡片類型
Review

## 任務目的
審查「半年 walk-forward 訓練前驗證」與「no-hindsight 研究治理契約」是否足以防止後照鏡調參，並確認它只作正式訓練前準備，不會覆蓋 production 模型或改動 ranking 主流程。

## 背景
PM 要求模型訓練不能只等未來 10 日結果，也不能在看到近半年輸在哪些盤勢後，立刻同一輪補規則或 filter 來修過去輸的地方。這次變更把近半年 walk-forward 驗證接進 training automation readiness，並新增 artifact contract 與 verifier，要求所有可升級結論都必須來自預先註冊的 baseline gate；盤勢拆解、負 fold、候選特徵診斷只能列為下一輪研究輸入。

## Scope
- Review `scripts/research_regime_feature_offline_ablation.py` 的 half-year walk-forward artifact 契約。
- Review `scripts/verify_half_year_walkforward_no_hindsight.py` 是否能擋住後照鏡漏洞。
- Review `scripts/verify_training_automation_readiness.py` 是否正確納入 half-year validation 與 governance self-test。
- Review `docs/architecture/MODEL_IMPROVEMENT_LOOP.md` 是否把研究治理規則寫清楚，且不誤導成正式模型 promotion。

## Out Of Scope
- 不重訓正式模型。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不改 `risk_adjusted_score` 或 production ranking 規則。
- 不把 diagnostic-only 結果直接升級成同輪 promotion filter。
- 不調整 Clawd 通知文案或 daily report 格式。

## 驗收條件
- `uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --self-test` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --artifact artifacts/model_experiments/half_year_walkforward_validation_2026-05-31.json` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900` 通過，且 half-year decision 只能是 `PROMOTE_CANDIDATE` / `MONITOR_ONLY` / `REJECTED`。
- `git diff --check` 通過。
- Review 確認 artifact 的 `decision` 不是由 diagnostic-only variants 或同輪 post-hoc filters 產生。

## Review Questions
- [P1] `no_hindsight_policy` 是否足以防止「看到哪個 fold 輸，就同輪新增 filter 讓它變贏」？
- [P1] `decision_policy` 是否有清楚區分 `PROMOTE_CANDIDATE`、`MONITOR_ONLY`、`REJECTED`，且預設夠保守？
- [P2] readiness 將 `MONITOR_ONLY` 當 warning 而不是 blocker 是否合理，還是正式自動化前應該 blocker？
- [P2] `diagnostics_not_for_promotion` 是否列得夠完整，避免 regime breakdown / negative folds 被誤用成 promotion 依據？
- [P2] 文件是否清楚說明這是訓練前治理閘門，不是正式 retrain 或模型升級？
