---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-context
status: CARD_DRAFTED
type: context_manifest
---

# Read first

- `AGENTS.md`
- `docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01.md`
- `.work/FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01/status.md`

# Source seams

- `app/research/map_contract.py`
- `scripts/run_representative_replay_drain_worker.py`
- `scripts/build_weekend_universe_inventory.py`（唯讀，do not touch）
- `tests/test_research_map_contract_boundary.py`
- `tests/test_representative_replay_drain_worker.py`

# Runtime evidence

- `artifacts/weekend_training/representative_replay_drain_2026-08-01.json`（local-only、唯讀）
- `artifacts/weekend_training/weekend_frontier_queue_2026-08-01.json`（local-only、唯讀）
- `artifacts/autonomous_research/run_history.jsonl`（local-only、唯讀）
