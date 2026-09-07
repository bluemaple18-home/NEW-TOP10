# REPAIR-TOP10-VALIDATION-CONFINEMENT-PROBE-01

- **objective**：修正 Fog 代表性驗證在 `TMPDIR` 已收斂到 sandbox 後，把 forbidden confinement probe 錯建於 sandbox 內而誤判失敗的問題。
- **scope**：只修改 `app/storage_safety.py` 的 validation-only probe temp 邊界、直接回歸測試與本卡 evidence；不改 production storage budget、Fog business logic、launchd、runtime 或 marker。
- **constraints**：forbidden probe 必須位於 sandbox 外、仍由同一 temporary-directory lifecycle 自動清理；不得放寬 Seatbelt profile、檔案數上限或任何 production gate。
- **acceptance**：回歸測試在 `TMPDIR` 指向 sandbox 且 `tempfile` cache 重建時仍通過；storage/Fog targeted tests、兩個代表性 validation cycles、shell/plist/diff checks 全綠後，才可進 production activation。
- **status / evidence**：`REVIEW_GO / COMMITTED / CONFINEMENT_ACCEPTED`；兩次 pre-spawn receipt 均為 `GUARD_INTERNAL_ERROR_RuntimeError`；精準 stage diagnostic 定位為 `_validation_spawn_command: VALIDATION_CONFINEMENT_PROBE_FAILED`；Mainline 回歸 102 tests 全綠，兩位 clean-context fixed-diff Reviewer 均為 `GO`、無 P0/P1。固定 commit R3 已成功 spawn 且保持 scope 收斂，後續停止原因另由 `REPAIR-TOP10-FOG-VALIDATION-LOCK-IDENTITY-01` 承接。
