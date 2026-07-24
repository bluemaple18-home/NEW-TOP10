---
task_id: SHADOW-RUN-01
status: INTEGRATED
card_type: implementation
ownership: receiving Mini
allowlist:
  - config/research_shadow_runs.yaml
  - scripts/run_research_shadow_runs.py
  - scripts/verify_research_shadow_runs.py
  - docs/tasks/2026-07-22_SHADOW-RUN-01_shadow_feature_experiments.md
  - docs/evidence/SHADOW-RUN-01/**
  - .work/SHADOW-RUN-01/**
thickness: standard
risk: research/production boundary
model: receiving Mini
reasoning: medium
model_reason: User selected Mini; scope is cross-file but bounded by an existing gate and verifier.
---

# SHADOW-RUN-01 Shadow Feature Experiments

任務ID：SHADOW-RUN-01
卡片類型｜派工對象：Implementation + Integration｜另一台電腦的 Mini
請讀：docs/tasks/2026-05-29_FEATURE-EXP-01_shadow_feature_promotion_gate.md、docs/architecture/MODEL_IMPROVEMENT_LOOP.md、config/research_shadow_runs.yaml、scripts/run_research_shadow_runs.py
任務目的：把既有 feature experiment gate 轉成 shadow-only experiment/run artifacts，不抓資料、不訓練模型、不改 production ranking
證據路徑：artifacts/research_shadow_runs_verification_latest.json、docs/evidence/SHADOW-RUN-01/

## 已帶入的 candidate

交接 branch 已包含以下未完成候選：

- config/research_shadow_runs.yaml 的 feature_experiments 設定。
- scripts/run_research_shadow_runs.py 的 --feature-experiments-only 路徑。
- scripts/verify_research_shadow_runs.py 的 synthetic verifier。

先 review 實際 diff，不得因已有程式碼就直接宣稱完成。

## Invariants

- research_only=true。
- does_not_fetch_data=true。
- does_not_train_model=true。
- does_not_change_production_ranking=true。
- production_score_change_allowed=false。
- production_promotion_allowed=false。
- market_context 本批明確 excluded。
- READY_FOR_SHADOW 與 BLOCKED_BY_GATE 必須保留來源 gate 判定，不可把 blocked candidate 當成功 promotion。

## Forbidden scope

- 不改 RankingPolicy、risk_adjusted_score、production LightGBM input/weights。
- 不觸發 data fetch、training 或 production ranking writes。
- 不把 runtime artifacts 當 source commit；只提交 task/evidence summary 與必要 verifier。

## 驗證

```bash
cd <repo-root>
uv run --with-requirements requirements.txt python -m py_compile scripts/run_research_shadow_runs.py scripts/verify_research_shadow_runs.py
uv run --with-requirements requirements.txt python scripts/verify_research_shadow_runs.py
uv run --with-requirements requirements.txt python scripts/verify_feature_experiment_gate.py
git diff --check
```

Reviewer 另檢查 correctness、production regression、artifact schema、path portability 與 deterministic synthetic test。

## Acceptance

- candidate commit 只含 allowlist。
- 獨立 Reviewer 對 candidate SHA 給 REVIEW_GO。
- mainline 從最新 origin/main 整合 candidate 後重跑上述驗證。
- docs/evidence/SHADOW-RUN-01/acceptance.md 記錄 base/candidate/integrated SHA、命令與結果。
