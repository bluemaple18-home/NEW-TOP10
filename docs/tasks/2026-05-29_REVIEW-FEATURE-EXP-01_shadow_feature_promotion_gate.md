# REVIEW-FEATURE-EXP-01 Shadow Feature Promotion Gate

## 任務卡

任務ID：REVIEW-FEATURE-EXP-01
卡片類型｜派工對象：Code Review / Model Experiment Gate｜Reviewer
請讀：docs/tasks/2026-05-29_FEATURE-EXP-01_shadow_feature_promotion_gate.md、scripts/build_feature_experiment_gate.py、scripts/verify_feature_experiment_gate.py、docs/architecture/MODEL_IMPROVEMENT_LOOP.md
任務目的：review FEATURE-EXP-01 是否只開放 shadow feature 測試、不允許 production score / ranking score / model promotion 被直接改動，並確認證據 gating 足以讓模型側開始測試
證據路徑：artifacts/feature_experiment_gate_YYYY-MM-DD.json、artifacts/feature_experiment_gate_verification_latest.json

## Review 重點

- `contract.production_score_change_allowed` 必須是 `false`。
- `contract.production_promotion_allowed` 必須是 `false`。
- `handoff_for_model_team.can_start_now` 只能代表 shadow test，不代表 production promote。
- `candidate_persistence`、`market_context`、`portfolio_risk_overlay` 的 READY 條件必須依賴 verifier / evidence artifact。
- `fundamentals`、`chip_flow`、`industry_rotation` 在缺資料契約或 replay evidence 時必須維持 BLOCKED。
- 不得新增或修改 `RankingPolicy`、`risk_adjusted_score`、production LightGBM training feature set。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/build_feature_experiment_gate.py scripts/verify_feature_experiment_gate.py
uv run --with-requirements requirements.txt python scripts/verify_feature_experiment_gate.py
uv run --with-requirements requirements.txt python scripts/build_feature_experiment_gate.py
git diff --check -- scripts/build_feature_experiment_gate.py scripts/verify_feature_experiment_gate.py docs/tasks/2026-05-29_FEATURE-EXP-01_shadow_feature_promotion_gate.md docs/tasks/2026-05-29_REVIEW-FEATURE-EXP-01_shadow_feature_promotion_gate.md
```

## 預期結論格式

- Findings：依 P0/P1/P2/P3 排序；若無阻塞，明確寫「未發現阻塞問題」。
- Testing Gaps：只列會影響 shadow gate / promotion gate 判定的缺口。
- Merge Recommendation：`approve` / `approve_with_followups` / `block`。
