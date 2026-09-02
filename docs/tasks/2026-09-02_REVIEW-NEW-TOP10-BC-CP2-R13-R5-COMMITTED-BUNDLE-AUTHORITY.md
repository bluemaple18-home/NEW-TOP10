---
id: REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: independent-fixed-sha-review
risk: critical
model: gpt-5.5
reasoning: high
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# R13-R5 committed bundle authority independent review

## 工作名稱 → 正在做什麼 → 現在狀態

`R13-R5 Independent Review` → 對固定 candidate SHA 的 committed-byte authority 做 maker/checker 分離審查 → `READY_FOR_REVIEW`

## Fixed scope

- Candidate：`84cc32452889553f1c89f7aaac4e89382b8d9827`。
- Parent：`af9ca52`。
- Governing contract：`docs/evidence/BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT/01-contract-decision.md`。
- Review candidate 六檔及其直接依賴；不得修改 implementation。
- 唯一允許新增：`docs/evidence/REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY/review.md`。

## 必查風險

- Git `HEAD` file-set、committed bytes與 working bytes判定是否可能 false-register，包括 HEAD/worktree TOCTOU、staged state、Git command failure、symlink/path escape與extra tracked files。
- Exact identity、hash、size、schema、canonical JSON、bundle verifier、ranking semantics、duplicate/conflict的組合是否真正 fail closed。
- Real canonical bundle test是否在 candidate commit上強制 registered，或可能用 pre-commit compatibility branch掩蓋 regression。
- CLI/API是否暴露 path/identity override，reject schema是否 deterministic，historical 50-record audit是否完全不變。
- 四個 artifact bytes/hash與 changed-files allowlist。

## Verdict／驗收

- Findings先列，只有 P0/P1 阻塞；P2/P3列 residual risk。
- Verdict只能 `REVIEW_GO` 或 `REVIEW_NO_GO`。
- 記錄 reviewed SHA/parent、Spec axis、Standards axis、實際 commands/exits/tests、remaining risks。
- 若 NO_GO，只提出最小 repair acceptance；不得自行修。
- 不 commit、不 push、不 merge、不 deploy、不准入 R14或任何下游。
