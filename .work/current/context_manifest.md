---
id: FOG-RUNTIME-TIME-AUTHORITY-01-I5-CONTEXT
status: GO_LIVE_ACCEPTANCE
type: mainline
---

# Context Manifest

## Read first

- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/live_acceptance.md`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/scheduler_cycles.txt`
- `docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_I5_live_acceptance.md`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/bounded_dry_repair_1.md`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/recovery_preflight.md`

## Runtime code

- `scripts/build_research_campaign_progress.py`
- `scripts/research_map_linkage_smoke.py`
- `tests/test_research_topic_date_wiring.py`
- Runtime code commit：
  `e6fc10a3251e61bb49ef0ae66e28d336f3a3adb1`

## Boundary

I5已完成三輪 acceptance。LaunchAgent保持 loaded；後續 interval run是正常
production schedule，不得回寫成第四次 acceptance probe。
