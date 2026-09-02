---
id: REPAIR-NEW-TOP10-BC-CP2-R13-R5-R1-COMMITTED-BUNDLE-AUTHORITY
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: strict-core-bounded-repair
risk: critical
model: gpt-5.5
reasoning: high
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# R13-R5 R1 committed bundle authority repair

## 工作名稱 → 正在做什麼 → 現在狀態

`R13-R5 R1 Repair` → 關閉 fixed-SHA Review 的 HEAD TOCTOU 與 fail-closed findings → `READY_FOR_REPAIR`

## Fixed inputs

- Candidate：`84cc32452889553f1c89f7aaac4e89382b8d9827`。
- Review commit：`14f4fd6`。
- Review evidence：`docs/evidence/REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY/review.md`。
- Architecture contract：`docs/evidence/BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT/01-contract-decision.md`。

## Exact changed-files allowlist

只能修改：

1. `app/research/r13_forward_receipt_authority.py`
2. `tests/test_r13_forward_receipt_authority.py`

四個 bundle files與所有既有 evidence/task/config/workflow不得修改。

## Required repair

- 開始時以 fail-closed Git command取得單一 immutable `HEAD^{commit}`；所有 file-set與blob讀取只用該 pinned SHA，不再使用 floating `HEAD`。
- 驗證結束前再次取得 `HEAD^{commit}`；不同即 `REJECTED / HEAD_CHANGED_DURING_VERIFICATION`。
- `ls-tree`、`show`、staged-state與HEAD pinning任一 Git command非零都回 stable error，不可忽略。
- 在 resolve前拒絕 lexical project-root symlink；保留 file symlink/path escape fail closed。
- 補可重現 regression：HEAD在中途切換、staged-state Git command failure、root symlink；原 Reviewer probe必須轉為 REJECTED。
- real canonical bundle test在 committed implementation語境必須無條件 assert registered；刪除 `SOURCE_NOT_COMMITTED` early-return假綠分支。
- public API/CLI、two-state schema、fixed path/identity、`downstream_authority=NONE`與historical audit不變。

## Acceptance

- 聚焦 tests與 receipt/admission regressions全過；public API/CLI在 Repair fixed SHA registered且errors空。
- HEAD movement、Git command failure、root/file symlink皆REJECTED並有stable code。
- `git diff --check <repair-parent>..<repair-sha> -- app/research/r13_forward_receipt_authority.py tests/test_r13_forward_receipt_authority.py`必過。
- Immutable artifact exception：原四個 exact bundle bytes不得因CSV whitespace修改；以 fixed size/SHA與bundle verifier驗收，故全量 diff-check不作為 Repair code acceptance。
- 只提交兩個 changed files；不 push、不 merge、不 deploy、不准入 R14或任何下游。完成後回原 Reviewer re-review。
