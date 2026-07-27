---
id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-2
status: READY_FOR_REVIEW
type: repair
chain_id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01
generation: 2
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 封閉 sealed trade-date 與 dataset-slice lineage 的最後信任邊界。
base_candidate_sha: 759dd7c76bf7ea3766fb67670c501be3a24ef2c4
review_evidence_sha: d4507353fdc21a28600524887cc30c4b067d5c13
reviewer_thread_id: 019fa367-851b-7402-bec7-6b11b68249de
evidence_path: docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-2/
---

# REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-2

## Finding F-02

Public CLI 已重算大部分 runtime lineage，但未比對：

- `sealed_trade_dates`
- `sealed_trade_date_hash`
- `sealed_dataset_slice_hash`

重新 content-address 且把 sealed dates 改成 `2099-01-01` 的 registration 仍得到
`EXPECTED_FAMILY_VALID`。

## Phase 0 與修復

1. 先建立上述 public-path red test，保存修前可通過證據。
2. 使用 Repair-1 已建立的 runtime authority 重算三欄並逐欄比對。
3. 任一不符 fail closed，輸出穩定 reason code。
4. 補三欄各自 mutation 測試；不得只擋單一 fixture。

## Allowlist

- `scripts/run_autonomous_research.py`
- `scripts/run_backtest_strategy_matrix.py`
- `scripts/verify_regime_research_autonomy.py`
- `scripts/run_regime_statistical_family_canary.py`
- `tests/test_regime_research_autonomy.py`
- `docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-2/**`
- 本卡狀態更新

## 禁止範圍

- 不改模型、ranking、權重、promotion、API、UI。
- 不降低統計或 sealed gate。
- 不 merge、push、deploy、自行 acceptance。

## 驗證

- forged sealed dates/slice public-path red→green
- targeted suite
- verifier（base 為本卡 base、candidate 為最終完整 SHA）
- full suite
- 四 canary 與 forged dataset/sealed attacks
- production hashes unchanged
- `git diff --check`

## Receipt

- Branch：`codex/regime-statistical-family-trust-boundary-repair-2`
- Worktree：`/private/tmp/top10new-regime-statistical-family-trust-boundary-repair-2`
- Source kind：`commit`
- Source SHA：`759dd7c76bf7ea3766fb67670c501be3a24ef2c4`
- Source clean：是
- unrelated dirty paths：`[]`
- Workflow：`REVIEW_NO_GO → REPAIR_READY → READY_FOR_REVIEW`
- Reviewer continuity：`019fa367-851b-7402-bec7-6b11b68249de`
- 本卡是此 chain 最後允許的 Repair generation；若仍 `NO_GO`，必須
  `BLOCKED / REVIEW_REPAIR_LIMIT`。

## 交付

`DELIVERED_CANDIDATE`、完整 SHA、red→green evidence、測試與 canary receipts，
交回同一 Reviewer 複審；Executor 不得自行接受。
