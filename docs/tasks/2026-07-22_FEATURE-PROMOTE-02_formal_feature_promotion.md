---
card_id: FEATURE-PROMOTE-02
chain_id: TOP10-NEXT-WAVE-20260722
status: CARD_DRAFTED
type: promotion-decision
owner: receiving Mini
model: receiving Mini
reasoning: medium
model_reason: 使用者指定 Mini；本卡只做固定證據的 deterministic GO/NO_GO，不修改 production。
thickness: strict
depends_on: [TSKG-MFO-GRAPH-01, CP-NEXT-WAVE-A]
worktree: receiving_host_must_provision
---

# FEATURE-PROMOTE-02 Formal Feature Promotion Decision

任務ID：FEATURE-PROMOTE-02
卡片類型｜派工對象：Promotion Evidence + Decision｜Mini
請讀：docs/architecture/MODEL_IMPROVEMENT_LOOP.md、scripts/build_feature_experiment_gate.py、scripts/build_model_promotion_review.py、app/modeling/model_runtime_promotion.py
任務目的：針對 Theme flow、graph diffusion 與既有 shadow candidates 產出固定 commit/data SHA 的正式 promotion GO/NO_GO
證據路徑：docs/evidence/FEATURE-PROMOTE-02/、artifacts/feature_promotion_decision_*.json

## Required evidence

- sealed OOS 與 time split/walk-forward。
- baseline 與 candidate 相同 universe/date/cost assumptions。
- leakage checks、stability、turnover、drawdown、concentration、venue/coverage attribution。
- missing/stale/late-data behavior。
- code Review、data manifest、candidate commit SHA 與 reproducible commands。

## Contract

- 缺任一 required evidence 即 NO_GO。
- decision artifact 必須 deterministic、schema-validated、fail closed。
- 本卡不得修改 RankingPolicy、模型權重、production runtime 或 deploy config。
- Reviewer 必須重算 decision，不只閱讀輸出文案。

## Verification

```bash
uv run pytest tests/test_model_runtime_promotion.py tests/test_daily_v2_promotion.py
uv run python scripts/verify_feature_experiment_gate.py
uv run python scripts/build_model_promotion_review.py --help
git diff --check
```

若既有 builder 介面不同，以實際 help/contract 命令替代並記錄。
