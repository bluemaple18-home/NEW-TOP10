---
id: ARCH-UPGRADE-08
status: in_progress
type: repair
parent: ARCH-UPGRADE-07
source_review: ARCH-UPGRADE-07A,ARCH-UPGRADE-07C
priority: P0
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
