---
id: ARCH-UPGRADE-08
status: ready_for_review
type: repair
parent: ARCH-UPGRADE-07
source_review: ARCH-UPGRADE-07A,ARCH-UPGRADE-07C
priority: P0
code_candidate_sha: 3613dc0f71fbf5cb29d94c55bc7df68a3d7a2d25
---

# Review Repair-2

完整修復 `b325c7f` 的 review findings：

- dry-run 不得成為成功 promotion evidence。
- acceptance/review 必須綁定 typed evidence 與呼叫方固定 base/candidate SHA。
- 記憶體 payload 不得直接授權；正式 promotion 只接受 file-backed 重算。
- ranking comparison 必須由實體 baseline/shadow CSV 完整重算。
- manifest 自簽 attestation 不具 production-equivalent 授權力；未建立外部信任根前 fail closed。
- `daily_entrypoint_modified` 由固定 SHA Git diff 推導。
- portable paths 統一相對 repo root，不依賴 cwd。

每日報牌、launchd、通知、ranking、model 與 production switch 維持原狀。

## 驗證

- targeted contract tests：23 passed。
- full suite：324 passed、28 subtests passed。
- promotion evidence：file-backed 重算通過，決策維持 `NO-GO / retain_current_production`。
- repo root 外重算 parity/promotion：通過。
- `git diff --check`：通過。
