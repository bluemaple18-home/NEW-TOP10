# Repair 02 Evidence

## Context

- Fixed start HEAD: `4244a69d72c82df465e8e850b74acf2e175c9f72`.
- Rejected code candidate: `33309e921a6b460967c9c96f30da5fca5630b075`.
- Review receipt: `1c967b0539056d7b40ff353b82e57e5033ab3c40`.
- CodeGraph was prepared at the fixed start HEAD and queried for both repair seams. The
  semantic query returned unrelated lifecycle/TSKG symbols, so source localization used
  bounded inspection of the repair allowlist files.

## Ranked falsifiable hypotheses

1. `completed_default_v2_base_combo_id()` treats the default-v2 suffix as sufficient
   authorization. If raw `combo_id` is instead checked against the row's raw `topic_id`
   and dimensions, a mismatched row will retain its raw identity while valid default-v2
   and lifecycle rows still canonicalize.
2. `main()` has no durable pre-replay check of its per-date progress artifact. If the
   previous same-date terminal no-progress identity is compared with the current queue
   identity before the replay command, a second unchanged invocation will be blocked and
   an identity change will resume replay.

## RED commands

- P1-01:
  `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_representative_replay_lifecycle.py::RepresentativeReplayLifecycleTests::test_mismatched_topic_and_default_v2_combo_keeps_raw_identity`
  failed because raw `other|...|entry_filter_TOPIC_DEFAULT` became the target base combo.
- P1-02:
  `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_representative_replay_drain_worker.py::RepresentativeReplayDrainWorkerTest::test_no_progress_blocks_same_identity_across_invocations_and_recovers_on_change`
  failed because the identical second invocation produced a second replay call (`2 != 1`).

## GREEN and regression evidence

- Both P1 probes together: `2 passed`.
- Targeted map/drain/lifecycle suite: `17 passed, 2 subtests passed`.
- Direct lifecycle coverage includes child × default-v2, child × non-default-v2, and a
  mismatched child/raw combo that must not map to the parent.
- Cross-invocation coverage executes only temp paths and mocks: first invocation reaches
  `NO_PROGRESS`; second and third identical invocations are blocked before replay and preserve
  `blocked_by_previous_identity`; a fourth invocation with one changed identity is allowed to
  attempt replay.
- Affected weekend/Fog suite: `38 passed, 6 subtests passed`.
- Full suite: `633 passed, 254 subtests passed, 1 failed`.
- The only full-suite failure is
  `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`;
  it reproduces alone because the isolated worktree lacks the pre-existing evidence paths needed
  by `evidence_exists`. No runtime artifact was generated or copied to mask it.
- Changed Python `py_compile`: PASS.
- Debug audit for `DBG-`, `pdb`, and `breakpoint(`: PASS (no matches).
- Exact repair-card changed-file allowlist: PASS (nine paths, no output from `comm -3`).
- Review card/receipt read-only audit: PASS.
- `git diff --check`: PASS.

## Runtime and review boundary

- No live Fog run, real runtime artifact/log write, LaunchAgent, circuit, deploy, push, merge,
  ranking, model, weight, promotion, topic-supply, or production-setting change was performed.
- Review card and review receipt remained read-only.
- Remaining risk: runtime/live acceptance remains intentionally unperformed until the capacity
  safety gate permits it; this candidate therefore requires independent re-review.
