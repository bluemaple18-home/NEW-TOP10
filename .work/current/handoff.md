# Handoff: TOP10new Decision Evidence / Shadow Feature 主線

## Root Question

TOP10new 下一步要怎麼讓模型越來越準，同時避免把未驗證的入榜天數、market context、portfolio risk、regime 研究直接混進 production score？

## 目前狀態

主線已完成：

- `MARKET-CONTEXT-02-TW`：台灣國內市場情境 artifact。
- `DECISION-QUALITY-01`：每日 Top10 決策品質 artifact。
- `FEATURE-EXP-01`：shadow feature promotion gate。
- `REVIEW-REGIME-RESEARCH-01`：regime／weekend research production-boundary review，裁決 `GO_SHADOW_ONLY`。
- `REVIEW-TSKG-MFO-DAILY-01`：獨立 Review `REVIEW_GO`；`TSKG-MFO-DAILY-01` mainline acceptance `GO`。

遠端也已合入：

- production write guard / overlapping daily run guard。
- regime research diagnostics。
- weekend research matrix runner。

## Blocker

目前沒有 TSKG daily integration blocker或 cleanup 待辦；production ranking/model promotion 仍明確未獲准。

已修復原本可把 shadow ranking 輸出指向 production artifact 的邊界缺口。`BROAD_RISK_ON`、`CHOPPY_RANGE` 仍只有 generic fallback，不算獨立 candidate。

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

本鏈已關閉，無等待條件。若要繼續改善，只能針對單一 candidate 另開 sealed OOS shadow experiment；先鎖樣本、replay、portfolio risk 與 promotion contract，不直接改 production。

審查證據：`docs/evidence/REVIEW-REGIME-RESEARCH-01/review.md`。

TSKG evidence：`docs/evidence/REVIEW-TSKG-MFO-DAILY-01/review.md`、`docs/evidence/TSKG-MFO-DAILY-01/acceptance.md`。

Canonical cleanup：本機 main clean/synced，相關 branches/worktree 皆為 0；舊 thread 在權威主機無實體，按 absent cleanup 收尾。

## 限制

- 文件與派工卡使用 repo-relative path。
- runtime artifacts 預設不進 git。
- 若要跨機同步 artifacts，必須明確打包或在主機重跑，不要假設 git 會帶過去。
