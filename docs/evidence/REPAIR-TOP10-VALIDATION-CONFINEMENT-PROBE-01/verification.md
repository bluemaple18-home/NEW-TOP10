# 驗證紀錄

## 根因

validation runtime 先把 `TMPDIR` 收斂到 sandbox；`tempfile` process-global cache 若在此後初始化，原本的 forbidden probe 也會建在 sandbox 內，造成 Seatbelt 正確允許寫入後被誤判為 `VALIDATION_CONFINEMENT_PROBE_FAILED`。

## 修復

forbidden probe 的 `TemporaryDirectory` 明確使用 `sandbox_root.parent`，保持在 sandbox 外；Seatbelt profile、production budget、Fog business logic 與 launchd 均未更動。

## 本機驗證

- 原始 bounded validation：`GUARD_INTERNAL_ERROR_RuntimeError`，child 未 spawn。
- 精準 stage diagnostic：`_validation_spawn_command RuntimeError: VALIDATION_CONFINEMENT_PROBE_FAILED`。
- 新 regression：1 test passed。
- Fog/storage affected suite：102 tests passed。
- Fog resource/wiring/signal/retry shell tests、plist lint、`git diff --check`：全部通過。
- 兩位獨立 Reviewer：均 `GO`，無 P0/P1。

固定 commit R3 已成功通過 confinement、spawn child 且保持 scope 收斂；後續因 Seatbelt 拒絕 Fog runner 的 `/bin/ps`，由 `REPAIR-TOP10-FOG-VALIDATION-LOCK-IDENTITY-01` 承接，不再歸因於 confinement probe。
