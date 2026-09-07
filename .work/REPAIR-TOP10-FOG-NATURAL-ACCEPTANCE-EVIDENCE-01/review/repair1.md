---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01-REPAIR-1
status: ready-for-re-review
type: repair-evidence
---

# Repair 1 result

- `F-001`：writer/reader 以既有 Fog time authority 驗證真實 market date；Mainline probe 由 `stale_date_verified True` 轉為 `stale_date_rejected ValueError`。
- `F-002`：acceptance-sensitive read/publish 改用 anchored dirfd、`O_NOFOLLOW/O_DIRECTORY` 與 same-fd `fstat`；補 atomic publication failure與 ancestor swap tests。
- `F-003`：cadence anchor 與 accepted chain qualification 分離；Mainline probe 由 `old_anchor False 0` 轉為 `old_anchor True 1`，第二個新合格週期才到 2。
- `F-004`：只有 Fog 強制 wrapper 自產 metadata；其他 job 保留既有 overrides。
- drift 由 300 秒縮為 60 秒，receipt 明示 `ARCHIVED_RECEIPT_CADENCE_V1`。
- Worker 驗證：focused `45 passed`；Storage Safety `94 passed, 38 subtests passed`；8 個 Fog shell regression、syntax、compile與 diff check 通過。

限制仍維持：不 kickstart、不清 marker、不 production、不 deploy、不 push、不 commit；live natural acceptance 尚未執行。
