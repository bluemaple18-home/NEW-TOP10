---
id: TSKG-01-mainline-acceptance
status: INTEGRATED
accepted_at: 2026-07-18
accepted_by: Codex 主線
accepted_successor: 1d464d70eabb3139936999a31917979c5e7c20e9
review_artifact_commit: 2b7dbdc1a230f7fdb8e693d32c1778e1531a3ceb
integration_head_before_acceptance_record: 2b6bf97e4a0fad1052a48b1a239c60850a59c6f6
---

# TSKG-01 Mainline Acceptance

## Status

`GO_WITH_NOTES / INTEGRATED`

本狀態只接受 TSKG v1.1 executable-spec 與 SLC-01 current frontier，不代表任何 crawler、database、API、source compliance、benchmark 或 production runtime 已完成。

## Evidence

- 原 candidate：`fad395589c90254ffbf4f0e7292a36920d019298`。
- 初審：`REVIEW_NO_GO`，review commit `7ddb092b449af801a4c86fb051a7c98561b1a29b`。
- Repair successor：`1d464d70eabb3139936999a31917979c5e7c20e9`。
- 同一 reviewer re-review：`REVIEW_GO / GO_WITH_NOTES`，review commit `2b7dbdc1a230f7fdb8e693d32c1778e1531a3ceb`。
- F-01～F-05：reviewer 判定 resolved。
- F-06：baseline SHA-256 尚待可重現 capture；保留 P2，不影響 SLC-01。
- F-07：benchmark generator 尚未保證固定 queries 產生指定 exact response sizes；保留 P2，阻擋 SLC-07 SLO acceptance，不影響 SLC-01。

## Acceptance mapping

- Canonical supply/customer fact：接受。
- Conflict set、resolution decision 與 lineage：接受為可實作契約；runtime 尚未執行。
- Temporal discriminator 與 round-trip matrix：接受為可實作契約；runtime 尚未執行。
- Verification integrity：接受；未執行項目不再標示 runtime PASS。
- Confidence API boundary：接受；public truth filter 不使用 extraction confidence。
- Baseline provenance closure：`PARTIAL/BLOCKED`，不可宣稱完成。
- Cache-hit `<300ms` SLO：`BLOCKED_FOR_SLO_ACCEPTANCE`，不可宣稱通過。

## Mainline integration proof

- 整合前主線 base：`d922e3f05decc4e397eb1132db55f0d601eaf6d3`。
- 規格、Repair、Review 七個 commits 依序 cherry-pick，無衝突；integration head 為 `2b6bf97e4a0fad1052a48b1a239c60850a59c6f6`。
- 整合檔案只位於 `docs/specs/**`、`docs/evidence/**`、`docs/tasks/**`。
- 使用者原有 `.gitignore`、research config/scripts 與元大輔助檔未被修改或納入整合。
- `git diff --check` 與 commit changed-file inspection 均通過。

## Next frontier

只有 SLC-01 可開工：synthetic/offline identity fixture → parse/normalize → local `/company/3017` contract response。SLC-02 之後仍受來源治理、universe authority、ADR 與對應 blocking edges 限制。
