---
card_id: TOP10-RANK-PROMOTE-01
chain_id: TOP10-NEXT-WAVE-20260722
status: CLOSED_NO_GO_INSUFFICIENT_PRODUCTION_HISTORY
type: conditional-production-candidate
owner: receiving Mini
model: receiving Mini
reasoning: medium
model_reason: 使用者指定 Mini；只有固定 SHA promotion GO 才解除 mutation blocker。
thickness: strict
depends_on: [FEATURE-PROMOTE-02_GO]
worktree: receiving_host_must_provision
---

# TOP10-RANK-PROMOTE-01 Ranking / Weight Candidate

任務ID：TOP10-RANK-PROMOTE-01
卡片類型｜派工對象：Conditional Ranking Candidate｜Mini
請讀：app/trading/ranking_policy.py、app/agent_b_ranking.py、docs/tasks/2026-05-16_UQ-05_ranking_integration_gate.md、FEATURE-PROMOTE-02 decision
任務目的：只有 promotion GO 時，以最小可回退 diff 將核准 feature/weight 做成 production candidate
證據路徑：docs/evidence/TOP10-RANK-PROMOTE-01/、artifacts/top10_rank_promotion_*.json

## Hard gate

FEATURE-PROMOTE-02 不是 GO、reviewed SHA 不一致、資料 manifest 漂移或 required evidence 過期時，本卡保持 BLOCKED，禁止修改任何 ranking/weight。

## Contract when unblocked

- 先寫會失敗的 behavioral tests，再做最小 mutation。
- 權重總和、方向、範圍、fallback、feature missing behavior、kill switch 與 rollback 固定。
- candidate 與 baseline 做相同日期、universe、cost、sealed replay。
- 不用單一平均報酬判定；必須同時檢查 drawdown、turnover、concentration、stability 與 coverage。
- 不 deploy、不啟動 production scheduler、不執行真實交易。

## Likely allowlist

- app/trading/ranking_policy.py
- app/agent_b_ranking.py
- 對應 feature contract/config
- tests/test_*ranking*.py
- scripts/verify_production_ranking_overlay.py
- docs/tasks/、docs/evidence/、.work/ 本卡路徑

## Verification

執行受影響 ranking tests、sealed replay、production parity/rollback verifier、完整 targeted suite 與 git diff --check。Acceptance 必須記錄 baseline/candidate/integrated SHA。

## 2026-07-22 final disposition

第一版 proxy baseline 經獨立 Review 否決後，已改用 40 份真實 production ranking artifacts。26 個成熟可配對日期的 Top5 replay 為 return uplift `-0.0075`、hit-rate uplift `-0.0231`，且未達 60 日 promotion floor；決策為 `NO_GO_INSUFFICIENT_PRODUCTION_HISTORY`。本卡不是待執行 blocker，而是已完成且禁止 production mutation。固定 replay、input manifest、decision 與 verifier 均在 `docs/evidence/INDUSTRY-PROMOTION-20260722/`。

2026-07-23 補充 quick diagnostic：現行 `0.12` overlay 在 59／99／119／234 日窗口中只有最短窗弱正，長窗皆負且集中度均惡化，因此現行 candidate 結案為 `REJECT_CURRENT_OVERLAY`。這不等於產業 feature family 永久無效；family 狀態為 `UNRESOLVED_RESEARCH_CANDIDATE`，未來須以不同 formulation 另開 candidate。
