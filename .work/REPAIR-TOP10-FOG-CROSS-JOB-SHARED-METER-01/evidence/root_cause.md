---
id: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01
type: root-cause-evidence
---

# Root cause

- Fog natural invocation `fog-research-worker-20260907T090500Z-80610` 自 17:05 執行。
- `external-review-preflight-20260907T094000Z-1210` 於 17:40:01–17:40:05 執行；其 receipt 記錄 retention 刪除三個 2026-07-31 檔案，artifact mtimes 證明另寫入三個 17:40 probe/preflight 檔案。
- Fog 17:40:30 sample 比對全專案 snapshot，把同六條 `artifacts/external_review` 變化判為 `REGISTERED_WRITE_OUTSIDE_METER`，終止 child，留下 persistent marker。
- `registered_changed_paths_outside_meter()` 的 deterministic probe 已以 exit `1` 重現同一路徑分類。

Audit：job 入口、receipt、deterministic gates 與 rollback 可定位；缺口在 shared checkout 的 I/O contract 未把已合法並行變化納入 Fog 容量 meter。採 exact subtree policy repair，避免新增 workflow/runtime control plane。
