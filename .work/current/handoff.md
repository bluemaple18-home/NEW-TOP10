# Handoff: TOP10new Decision Evidence / Shadow Feature 主線

## Root Question

TOP10new 下一步要怎麼讓模型越來越準，同時避免把未驗證的入榜天數、market context、portfolio risk、regime 研究直接混進 production score？

## 目前狀態

主線已完成：

- `MARKET-CONTEXT-02-TW`：台灣國內市場情境 artifact。
- `DECISION-QUALITY-01`：每日 Top10 決策品質 artifact。
- `FEATURE-EXP-01`：shadow feature promotion gate。

遠端也已合入：

- production write guard / overlapping daily run guard。
- regime research diagnostics。
- weekend research matrix runner。

## Blocker

目前沒有實作 blocker。

主要等待的是 review 判斷：

- regime research 是否只讀 evidence。
- weekend matrix 是否不觸發重訓 / 不改 production ranking。
- 哪些 candidate 可以進下一張 shadow experiment 卡。

## Fork

推薦路線：

- 把 `candidate_persistence`、`market_context`、`portfolio_risk_overlay` 留在 shadow experiment。
- 對 regime research 先做 review / audit，不直接升 production。
- 所有 promotion 必須有 sealed OOS / replay / portfolio risk / review evidence。

禁止路線：

- 直接改 `RankingPolicy` 權重。
- 直接改 `risk_adjusted_score`。
- 把 market context 或 industry/regime 當 production signal。
- 用未成熟 ranking date 或未封存樣本做 promotion。

## 已驗證

- `scripts/verify_market_context_fetcher.py` 通過。
- `scripts/verify_decision_quality.py` 通過。
- `scripts/verify_feature_experiment_gate.py` 通過。
- `scripts/build_decision_quality.py` 會用本地 `data/reference` 做中性 reference annotation，但 contract 明確宣告不改 score / model / ranking。

## 下一步

建議開：

```text
任務ID：REVIEW-REGIME-RESEARCH-01
卡片類型｜派工對象：Research / Production Boundary Review｜Reviewer
請讀：scripts/build_market_regime_history.py、scripts/research_regime_shadow_ranking.py、scripts/research_feature_group_ablation_by_regime.py、scripts/run_weekend_research_matrix.py、scripts/audit_research_dataset_coverage.py
任務目的：複查 regime / weekend research 是否只讀 evidence、不改 production score/model/ranking，並判斷是否可進 shadow experiment
證據路徑：artifacts/research_*、artifacts/feature_experiment_gate_YYYY-MM-DD.json
```

## 限制

- 文件與派工卡使用 repo-relative path。
- runtime artifacts 預設不進 git。
- 若要跨機同步 artifacts，必須明確打包或在主機重跑，不要假設 git 會帶過去。
