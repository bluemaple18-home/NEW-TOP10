# CARD-NEW-TOP10-ORPHAN-PRECREATE-RECOVERY-EXECUTION-V1

## 狀態

COMPLETED

## 目標

依使用者 2026-08-14 明確核准，只回收兩筆已由新版 ai-core `inspect` 證實為 `ORPHAN_PRECREATE_RECOVERY_REQUIRED` 的 Reviewer reservation，使其成為不可逆稽核終態 `ABORTED_PRECREATE`，釋放正式 Reviewer role slot。

## 精確範圍

1. `v1:2ec1dcec37ee6c97ae16c5c69b477b29b88bc5d22cf7c45b701928813b26ee32`
   - owner: `root-nea-review-retry1-20260814`
   - card: `CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-V1-RETRY-1`
2. `v1:ccf95a64301678390306e6c0308fdaebf29b1bd0785cb36b6f3daa001ca6ff96`
   - owner: `root-nea-checkpoint-review-retry1-20260814`
   - card: `CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-CHECKPOINT-1-REVIEW-RETRY-1`

共同 identity：

- repo: `local-git:666e4bae2d44e988876ea874ca43bfa3de5be8653049a89ef8972593c9d631f9`
- chain: `NEW-TOP10-RESEARCH-SPINE-V1`
- role: `reviewer`
- cycle: `0`

## 執行契約

1. 修改前建立 SQLite 一致性備份、SHA-256 與 `PRAGMA integrity_check`。
2. 只使用 exact owner 執行 `recover-precreate-orphan`；不得使用 legacy `acquire`。
3. 每筆執行後須為 `ABORTED_PRECREATE`，且含 recovery receipt。
4. 重複執行須回 idempotent，不得新增第二筆事實。
5. 修改後再次執行 DB integrity check，並證明其他 reservation 未被改動。

## 禁止事項

- 不修改研究資料、研究 candidate、production ranking、模型、signals、strategy config。
- 不刪除任何 reservation 或 immutable receipt。
- 不修改兩筆以外的正式 control-plane row。
- 本卡不授權合併 candidate，也不授權 live canary。

## 驗收

- 兩筆精確 dispatch 均為 `ABORTED_PRECREATE`。
- blocker/next action 符合新版 contract。
- recovery receipt owner 與 dispatch identity 完整一致。
- 官方 SQLite 與備份均通過 `integrity_check=ok`。
- 再次 recovery 為 idempotent。
- TOP10 使用者既有未提交變更保持不動。

## 執行結果

- 官方 DB schema 已用核准的 `bootstrap-v1` 補齊。
- 兩筆指定 reservation 均由 exact owner 轉為 `ABORTED_PRECREATE`。
- 兩筆重複 recovery 均回 `idempotent`。
- 修改前後 reservation row count 均為 `335`；無新增或刪除 row。
- common columns 只有兩筆指定 row 的 `state`、`blocker_code`、`blocker_detail` 改變。
- 新增 schema 欄位只有 `precreate_recovery_receipt_json`。
- 官方 DB 與修改前 SQLite 備份均通過 `PRAGMA integrity_check=ok`。
- 正式 Reviewer role slot 已釋放，後續由獨立 Retry-3 卡重新 `prepare-create`。
