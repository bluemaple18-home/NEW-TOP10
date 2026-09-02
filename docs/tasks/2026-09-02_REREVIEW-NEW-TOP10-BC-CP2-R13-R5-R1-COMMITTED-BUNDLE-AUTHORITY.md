---
id: REREVIEW-NEW-TOP10-BC-CP2-R13-R5-R1-COMMITTED-BUNDLE-AUTHORITY
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: fixed-sha-re-review
risk: critical
model: gpt-5.5
reasoning: high
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# R13-R5 R1 committed bundle authority re-review

## 工作名稱 → 正在做什麼 → 現在狀態

`R13-R5 R1 Re-review` → 原 Reviewer 驗證原 findings與Repair regression → `READY_FOR_REREVIEW`

## Fixed scope

- Original candidate：`84cc32452889553f1c89f7aaac4e89382b8d9827`。
- Repair parent：`015d6e9`。
- Repair candidate：`a2fdfdf6ef0e14d244f0676f288f95d78e8a08a5`。
- Original review：`docs/evidence/REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY/review.md`。
- Repair card：`docs/tasks/2026-09-02_REPAIR-NEW-TOP10-BC-CP2-R13-R5-R1-COMMITTED-BUNDLE-AUTHORITY.md`。
- 唯一允許新增：`docs/evidence/REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY/re-review-r1.md`。

## Re-review contract

- 只驗原 P1 HEAD movement、P2 root symlink、P2 Git command failure、P3 real-bundle test與兩檔 regression；不得以新建議移動球門。
- 重跑原 reproduction probes；確認 repair只改 source/test兩檔，四個 bundle bytes未變。
- CLI/API fixed SHA registered、errors空、`downstream_authority=NONE`；negative probes全部REJECTED/stable codes。
- scoped source/test diff-check與聚焦 regressions通過；immutable CSV whitespace依Repair card例外，不改 bytes。
- Verdict只能 `REVIEW_GO` 或 `REVIEW_NO_GO`；只剩P2/P3可列 residual，不得阻塞。
- 不修 code、不 commit、不 push、不 merge、不 deploy、不准入R14或下游。
