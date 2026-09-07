---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01
status: context-ready
type: context-manifest
---

# Context Manifest

- `AGENTS.md`
- `docs/tasks/2026-09-07_REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01.md`
- `docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md`（只讀 natural acceptance 契約段）
- `docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A5-NATURAL-20260905/storage-guard-independent-review-repair-309edab.md`（只讀既有 PPID/archive 邊界）
- `app/storage_safety.py`（receipt/archive/final quiescence seam）
- `scripts/run_with_storage_guard.sh`
- `scripts/run_fog_research_worker.sh`
- `scripts/com.new-top10.fog-research-worker.plist`
- `tests/test_storage_safety.py`
- `tests/test_fog_storage_validation.py`

CodeGraph source decision：`_receipt_payload` 與 `run_guarded_job` impact 已確認；主要 blast radius 為 `tests/test_storage_safety.py`，activation transaction 的同名 method 不在本卡修改範圍。
