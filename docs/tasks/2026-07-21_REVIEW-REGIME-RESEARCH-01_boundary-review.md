---
id: REVIEW-REGIME-RESEARCH-01
status: COMPLETE
type: review
owner: Codex 主線
created_on: 2026-07-21
evidence_path: docs/evidence/REVIEW-REGIME-RESEARCH-01/review.md
---

# REVIEW-REGIME-RESEARCH-01：Regime／Weekend Research 邊界審查

## Root question

現有 regime diagnostics 與 weekend research matrix 是否只讀既有 evidence、只寫 research artifacts，且不觸發重訓、不改 production model／ranking／score；哪些輸出可成為後續 shadow experiment candidate？

## Review scope

- `scripts/build_market_regime_history.py`
- `scripts/research_regime_shadow_ranking.py`
- `scripts/research_feature_group_ablation_by_regime.py`
- `scripts/run_weekend_research_matrix.py`
- `scripts/audit_research_dataset_coverage.py`
- 直接 caller、tests、config、artifact contracts 與 production promotion boundary。

## Axes

1. Correctness：日期、資料來源、樣本成熟度、輸出 schema 與失敗路徑。
2. Production boundary：不得寫 model、ranking、score、promotion 或 production config。
3. Side effects：不得觸發 retrain、live send、外部 write 或無界迴圈。
4. Reproducibility：輸入／輸出可定位，dry-run 或 deterministic verifier 可重跑。
5. Shadow eligibility：只允許 evidence 完整、無 leakage、無 production mutation 的 candidate。

## Verification

- 來源與 caller 靜態掃描。
- 相關 unittest／verifier。
- 最小 dry-run 或 synthetic artifact 驗證；不得啟動正式重訓或 live send。
- `git diff --check`。

## Do not touch

- 不修改 `RankingPolicy`、`risk_adjusted_score`、模型權重或 production ranking。
- 不執行正式 retrain、promotion 或外部通知。
- Review 有 finding 時先寫 evidence；除非使用者另授權 repair，不順手改實作。

## Authorized minimal repair

- 使用者要求承接並完成前一台電腦留下的工作；審查確認 `research_regime_shadow_ranking.py` 缺少輸出隔離後，只補 research output guard 與回歸測試。
- 不新增盤勢權重；`BROAD_RISK_ON`、`CHOPPY_RANGE` 在沒有獨立 evidence 前維持既有 fallback，且不得宣稱為已驗證的專屬策略。

## Result

- Verdict：`GO_SHADOW_ONLY`；五支腳本與既有 caller 未發現 retrain、model write、live send 或 production promotion 路徑。
- 已封鎖 shadow ranking 寫到 `artifacts/`、`models/`、`data/`、`artifacts/backtest/` 根目錄或來源 ranking 目錄的可能性。
- `BROAD_RISK_ON`、`CHOPPY_RANGE` 尚無專屬 shadow scoring evidence；只能視為 fallback baseline。
- 完整 findings、資格矩陣與重跑證據見 `docs/evidence/REVIEW-REGIME-RESEARCH-01/review.md`。
