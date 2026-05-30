# FEATURE-EXP-01 Shadow Feature Promotion Gate

## 任務卡

任務ID：FEATURE-EXP-01
卡片類型｜派工對象：Model Experiment Gate｜Codex
請讀：docs/architecture/MODEL_IMPROVEMENT_LOOP.md、docs/tasks/2026-05-28_MODEL_IMPROVEMENT_CARDS.md、scripts/build_decision_quality.py、app/agent_b_modeling.py
任務目的：建立 shadow feature promotion gate，定義 streak / market context / portfolio risk / fundamentals / chip / industry 何時可進模型實驗，何時可 promote，不改 production score
證據路徑：artifacts/feature_experiment_gate_YYYY-MM-DD.json、artifacts/feature_experiment_gate_verification_latest.json

## 交付內容

- 新增 `scripts/build_feature_experiment_gate.py`。
- 新增 `scripts/verify_feature_experiment_gate.py`。
- Gate 只讀既有 evidence artifacts，不訓練模型、不重跑 ranking、不改 `RankingPolicy`。
- Gate 會輸出模型側可立即開始 shadow test 的候選清單，以及仍 blocked 的資料契約。

## 模型側可開始測試的邊界

- 可以開始：以最新 `feature_experiment_gate_YYYY-MM-DD.json` 為準；2026-05-30 狀態為 `candidate_persistence`、`portfolio_risk_overlay`、`regime_feature_group_ablation`。
- 不可以開始：`market_context` 在 fetcher verification / source status 補齊前維持 blocked。
- 不可以：直接改 `risk_adjusted_score`、直接把欄位塞進 production LightGBM、直接 promote。
- promote 前必須補 shadow experiment artifact、production replay、sealed OOS、walk-forward / time split、portfolio risk、code review evidence。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/build_feature_experiment_gate.py scripts/verify_feature_experiment_gate.py
uv run --with-requirements requirements.txt python scripts/verify_feature_experiment_gate.py
uv run --with-requirements requirements.txt python scripts/build_feature_experiment_gate.py
git diff --check -- scripts/build_feature_experiment_gate.py scripts/verify_feature_experiment_gate.py docs/tasks/2026-05-29_FEATURE-EXP-01_shadow_feature_promotion_gate.md
```
