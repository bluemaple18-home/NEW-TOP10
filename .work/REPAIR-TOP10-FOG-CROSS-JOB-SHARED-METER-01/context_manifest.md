---
id: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01
type: context-manifest
---

# Context manifest

- `AGENTS.md`
- `docs/tasks/2026-09-07_REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01.md`
- `docs/operations/top10-storage-policy.json`
- `docs/operations/top10-storage-safety.md`
- `app/storage_safety.py`
- `tests/test_storage_safety.py`
- `docs/evidence/REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-20260907.md`

Runtime evidence（唯讀）：

- `logs/storage_safety/restart_denied/fog-research-worker.json`
- `logs/storage_safety/fog-research-worker_latest.json`
- `logs/storage_safety/external-review-preflight_latest.json`

CodeGraph 對自然語句命中不佳，已依規則回退 `rg` 並由 `registered_changed_paths_outside_meter()`、production policy 與 receipts 確認 source seam。
