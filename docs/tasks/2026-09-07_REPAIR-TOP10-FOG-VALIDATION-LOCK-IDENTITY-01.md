# REPAIR-TOP10-FOG-VALIDATION-LOCK-IDENTITY-01

- **objective**：讓 Fog 代表性 workload 在 macOS Seatbelt 內仍能建立具 PID-reuse 防護的 lock identity。
- **scope**：只新增 trusted validation entrypoint 的 Darwin `libproc` start-token 模式與 Fog runner 的明確 validation-only 分支；production 預設仍使用 `/bin/ps`。
- **constraints**：不得放寬 Seatbelt profile、不得退化成 `kill -0` 或 PID-only、不得新增第三方依賴；helper 必須來自 digest-pinned、sandbox 外唯讀 materialized entrypoint，查詢失敗仍 fail closed。
- **acceptance**：同一存活 PID token 穩定、不存在 PID 拒絕；targeted Python/shell tests 全綠；兩位 clean-context Reviewer 無 P0/P1；固定 commit 的兩輪 bounded Fog validation 都產生代表性 workload 與 `OK` receipt，才可啟用 runtime。
- **status / evidence**：`REVIEW_GO / COMMITTED / PUSHED / RUNTIME_VALIDATION_PASS / ACTIVATED / NATURAL_ACCEPTANCE_PENDING`；固定 commit `26c88343ccac08ce4701b785bfa2c2c82bfa446d`。第一輪雙盲為 A=`GO`、B=`NO_GO`；Repair 1 新增 established-state boundary，未確認 teardown 會保留鎖並回 exit 70。A/B re-review 均 `GO`，B 明確關閉原 P1。固定 SHA 的兩輪代表性 validation 均為 `OK`，正式 detached runtime 已切換；Fog runtime activation 後仍須兩次連續自然週期才能完成。這不是 Research Spine Card A5。
