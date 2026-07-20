---
card_id: REVIEW-TSKG-RSCH-02
chain_id: TSKG-RSCH
title: Independently review additive research evidence contract
status: PENDING
type: review
owner: Codex 主線
assignee: REVIEW-TSKG-RSCH-02 independent reviewer
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 一般跨檔 contract review，重點是向後相容、fail-closed 邊界與避免未授權 workflow mutation
source_kind: commit
source_sha: <candidate-sha-from-TSKG-RSCH-02>
mainline_dispatcher: TSKG root thread
previous_card: TSKG-RSCH-02
worktree_mode: independent-clean-worktree
main_cwd: <repo-root>
expected_worktree_cwd: not-equal-to-main-cwd
evidence_path: docs/evidence/REVIEW-TSKG-RSCH-02/review.md
---

# REVIEW-TSKG-RSCH-02：獨立審查 research evidence contract

## Review scope

- Spec axis：是否真的做到概念採用而非 runtime 接入；是否避免全面重跑與歷史 migration。
- Standards axis：correctness、backward compatibility、closed schema、determinism、fail-closed、testing、maintainability。
- 確認 verifier 不寫 queue／ledger、不改 verdict、不觸發 research／promotion。
- 確認 `GRANDFATHERED` 不被誤判為失效，`REQUIRED_NOW` 缺關鍵 evidence 時確實阻擋。

## Verdict

- 只允許 `REVIEW_GO/REVIEW_NO_GO`。
- Findings 必須有 `path:line`、觸發條件、風險與修法。
- Reviewer 不修 candidate；NO-GO 由主線另開 Repair 卡，原 Reviewer re-review。

## Result

`PENDING_CANDIDATE`
