# TSKG Research adoption inventory

日期：2026-07-20

本清冊把既有 Research Component Ledger 的 21 個元件映射成 TSKG 概念採用時點；它不重跑研究、不改 verdict，也不觸發 promotion。

| 採用類別 | 數量 | 行為 |
|---|---:|---|
| `GRANDFATHERED` | 2 | 保留歷史結論，不補跑；只有改用途時才重新分類。 |
| `CHECK_ON_REUSE` | 9 | 目前不阻擋，進入 reuse／model-input／promotion checkpoint 時才驗證。 |
| `REQUIRED_NOW` | 10 | 從下一個研究 checkpoint 起附加 evidence envelope；研究階段只標 `NEEDS_EVIDENCE`。 |

人工分類數為 0。完整逐項資料在 `inventory.json`。

## 邊界

- 分類只依既有 ledger lifecycle 與已附加的 `tskg_adoption` 摘要，沒有推測研究內容。
- `artifact_refs` 是 ledger 中的可追溯參照，不等同於本 worktree 已存在的檔案。33 個參照中有 16 個不在此乾淨 worktree，因此仍維持 `NOT_EVALUATED`，沒有誤宣稱證據完整。
- 主 worktree 的未提交研究資料未納入正式輸入。
