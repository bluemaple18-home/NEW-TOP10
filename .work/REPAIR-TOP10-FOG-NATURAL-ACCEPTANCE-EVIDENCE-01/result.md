---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01
status: candidate-green
type: result
---

# Result

完成 invocation-bound terminal artifact、Storage Guard receipt 回接與 archived-receipt cadence verifier 的 bounded repair。

- exact invocation evidence 以 atomic、immutable publish 寫入，並綁定 Fog time authority、run/event identity 與內容 hash。
- Storage Guard 只在 child exit 與 process-group final quiescence 後讀取 exact evidence；不使用 latest。
- natural provenance 由 plist cadence、`scheduled_at`、`invocation_id` 與既有 archived receipt 驗證；PPID=1 不直接視為 verified。
- counter 只有在 artifact、cadence、exit、quiescence、marker 與 locks 全部通過時累加；連續兩輪才 `ACCEPTED`。
- Round 1 的 `F-001`～`F-004` 已於 Repair 1 修復，兩名原 Reviewer 以固定新版 manifest 重審皆回 `GO`。
- Mainline：`139 passed, 38 subtests passed`；8 個 Fog shell regressions 全過；shell syntax、Python compile、`git diff --check` 全過。

交付狀態：`CANDIDATE_GREEN / DEPLOY_BLOCKED_BY_RESTART_DENIAL / NATURAL_ACCEPTANCE_PENDING`。Owner 已授權 commit／deploy，但 preflight 發現既有 runtime 的 Fog marker；因此未 deploy、未 kickstart、未清 marker、未回填舊 receipt、未 push。
