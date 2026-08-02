---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-result
status: REPAIR_CANDIDATE_READY
type: result
---

# Result

Completed default-v2 replay evidence only closes the canonical base/default scenario when its
raw topic, dimensions, and expanded combo match exactly. Mismatched normal and lifecycle-child
records retain their raw combo identity; valid default-v2, non-default-v2, and lifecycle-parent
mapping contracts remain covered.

The drain now persists its no-progress identity in the per-date progress artifact. Later same-date
invocations with the same representative identity stop before replay as
`BLOCKED / unchanged_no_progress_identity`, including repeated blocked invocations. A changed
identity set restores replay eligibility.

Targeted and affected suites are green. The full suite has one pre-existing isolated-worktree
evidence availability failure unrelated to the changed seams; it reproduces alone and is recorded
in `evidence/repair-02.md`.

`READY_FOR_RE_REVIEW`
