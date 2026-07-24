---
card_id: TASK-STATUS-RECONCILE-01
status: COMPLETED
type: documentation-status-reconciliation
owner: mainline integrator
thickness: minimal
risk: low
model_reason: 只依既有 acceptance／re-review evidence 修正狀態，不改 implementation。
---

# Task Status Reconciliation

## Root question

哪些 Next Wave 卡片只是 frontmatter 過期，哪些才是真正仍需人工處理？

## Allowlist

- `docs/tasks/2026-07-22_*.md` 的 frontmatter status／decision receipt。
- `.work/current/*.md` 的 current-state 摘要。
- 新增 `REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01` 實體 Review 卡。
- 本卡。

## Evidence contract

- 只有已有 `docs/evidence/**/acceptance.md` 或最終 re-review `GO` 的 chain 才能改為終態。
- 不改 candidate、implementation、測試、模型、ranking、權重或 runtime。
- `WAITING_FOR_NEW_OOS_DATES`、資料 coverage blocker 與 Windows live 未驗證邊界不得改寫成完成。

## Verification

- 狀態 reconciliation matrix 必須逐卡連到 acceptance／final review。
- `git diff --check`
- shared docs 不得新增本機絕對路徑或 secret。

## Result

- 20 個 stale／missing status 已依 acceptance 或 final Review evidence 收斂。
- 4 個真正的 waiting／blocked research state 保持不變。
- 新增固定 `f716883..4deb726` 的獨立 Review 卡。
- frontmatter parse、task ledger build、secret／local-path diff scan、`git diff --check`：PASS。
