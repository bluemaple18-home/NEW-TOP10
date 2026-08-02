---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-phase0-red
status: RED_CONFIRMED
type: evidence
---

# Phase 0 RED

- Command: `.venv/bin/python -m pytest -q tests/test_representative_replay_lifecycle.py::RepresentativeReplayLifecycleTests::test_completed_default_v2_replay_closes_only_the_base_scenario`
- Exit: `1`
- Target symptom: completed default-v2 history retained its expanded `combo_id`; the corresponding base/default scenario therefore remained pending.
- Failure boundary: observable canonical history identity and base scenario status; no live artifact dependency.

- Command: `.venv/bin/python -m pytest -q tests/test_representative_replay_drain_worker.py::RepresentativeReplayDrainWorkerTest::test_drain_stops_after_first_successful_batch_without_new_evidence_or_identity_change`
- Exit: `1`
- Target symptom: six successful batches replayed the unchanged representative identity set, appended `0` history rows, and still terminated `OK / max_batches_reached`.
- Observed summary: `batch_count=6`, `completed_replay_count=144`, `appended_run_history_count=0`.

# Ranked hypotheses

1. If completed default-v2 evidence is mapped to the base combo, the base/default scenario becomes `low_information` and expansion count stays `0`.
2. If the history record were absent, canonicalization could not close the scenario; the fixture disproves this because the completed record and artifact reference are present.
3. If batch progress requires either non-forced appended evidence or a representative identity-set change, the unchanged fixture stops after batch `1` with a non-OK status.
