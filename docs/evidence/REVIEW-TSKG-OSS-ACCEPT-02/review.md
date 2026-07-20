---
card_id: REVIEW-TSKG-OSS-ACCEPT-02
status: REVIEW_NO_GO
reviewed_on: 2026-07-20
reviewer_thread_id: 019f7e7a-241e-7412-86f6-9e69538c7e28
operation_level: independent_read_only_review
reviewed_candidate: e0bfe6712dc1af1e3558e124f10a7d03632471de
reviewed_parent: ab4595be037bebf28e201010440dc9bc0aa3f84e
verdict: NO_GO
---

# REVIEW-TSKG-OSS-ACCEPT-02 review

## Verdict

`NO_GO`

Candidate `e0bfe6712dc1af1e3558e124f10a7d03632471de` stays within the candidate card allowlist and the placeholder cleanup in `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md` is non-semantic. However, `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md` does not record the actual delivered candidate SHA/parent and therefore does not satisfy the review contract's evidence-integrity requirement.

## Reviewed SHA and parent

| Item | SHA | Result |
|---|---|---|
| Review card HEAD | `644afde12469bcdaf1cefd84cef7e75f3a46ce8c` | matches review card commit |
| Candidate | `e0bfe6712dc1af1e3558e124f10a7d03632471de` | commit object present |
| Candidate parent | `ab4595be037bebf28e201010440dc9bc0aa3f84e` | exact parent confirmed |

## Findings

- P0: none
- P1: candidate verification does not record the delivered candidate lineage in `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md:5-7` and `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md:23-24`
- P2: none
- P3: none

## Scope and diff checks

- `git rev-list --parents -n 1 e0bfe6712dc1af1e3558e124f10a7d03632471de` confirms the sole parent is `ab4595be037bebf28e201010440dc9bc0aa3f84e`.
- `git diff --name-only ab4595be..e0bfe671` shows exactly three changed files:
  - `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`
  - `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md`
  - `docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md`
- Those three files exactly match the candidate card allowlist.
- Exact diff and word diff confirm the existing review evidence only replaces local worktree/git metadata values and host-path scan literals with placeholders, while the acceptance card only updates delivery receipt fields and the new verification file.
- No original GO verdict, reviewed SHA, findings, Spec/Standards axes, exit-code meaning, or remaining-risk meaning changed inside `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`.

## Host-path and evidence checks

- Candidate allowlist host-path scan via `<host-path-scan>` exits `1`.
- Broader TSKG OSS shared-file scan, including this review card and this review evidence, via `<host-path-scan>` exits `1`.
- `git diff --check ab4595be037bebf28e201010440dc9bc0aa3f84e e0bfe6712dc1af1e3558e124f10a7d03632471de` exits `0`.
- The blocking issue is evidence integrity, not host-path leakage or diff hygiene.

## Preflight and git hygiene

- Independent worktree cwd was verified in preflight and kept out of shared artifacts as `<local-only-worktree>`.
- `git rev-parse --git-dir` resolved to a worktree gitdir and is represented in shared artifacts as `<repo-gitdir>/worktrees/<worktree-id>`.
- Review worktree `git status --porcelain` was empty before review edits.
- `test -e "$(git rev-parse --git-dir)/index.lock"` observed exit `1`; no `index.lock` was present.
- `unrelated_dirty_paths` remained effectively `[]`.

## Spec axis

`NO_GO`

- Required review items 1-4 and 6 passed: parent, allowlist, placeholder-only diff behavior, broader host-path gate, and `git diff --check` all matched the review contract.
- Required review item 5 failed because the candidate verification artifact does not record the actual delivered candidate SHA/parent.

## Standards axis

`NO_GO`

- The repo's evidence-first review standard requires verification artifacts to be materially trustworthy.
- Leaving `candidate_head` pending and `candidate_parent` tied to an older SHA makes the artifact ambiguous enough to block acceptance even though the content cleanup itself is narrowly scoped.

## Commands and exit codes

| Command | Exit | Purpose |
|---|---:|---|
| `git rev-parse HEAD` | 0 | Confirm review card HEAD |
| `git status --porcelain` | 0 | Confirm clean preflight state |
| `git rev-parse --git-dir` | 0 | Confirm worktree git metadata path |
| `test -e "$(git rev-parse --git-dir)/index.lock"` | 1 | Confirm no index lock present |
| `git rev-list --parents -n 1 e0bfe6712dc1af1e3558e124f10a7d03632471de` | 0 | Confirm exact candidate parent |
| `git diff --name-only ab4595be037bebf28e201010440dc9bc0aa3f84e e0bfe6712dc1af1e3558e124f10a7d03632471de` | 0 | Confirm changed file set |
| `git diff --stat ab4595be037bebf28e201010440dc9bc0aa3f84e e0bfe6712dc1af1e3558e124f10a7d03632471de` | 0 | Confirm diff scope summary |
| `git diff --unified=3 ab4595be037bebf28e201010440dc9bc0aa3f84e e0bfe6712dc1af1e3558e124f10a7d03632471de -- docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md docs/evidence/TSKG-OSS-ACCEPT-02/verification.md docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md` | 0 | Inspect exact candidate diff |
| `git diff --word-diff=porcelain ab4595be037bebf28e201010440dc9bc0aa3f84e e0bfe6712dc1af1e3558e124f10a7d03632471de -- docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md docs/evidence/TSKG-OSS-ACCEPT-02/verification.md docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md` | 0 | Confirm placeholder-only textual changes plus new evidence |
| `sed -n '1,220p' docs/evidence/TSKG-OSS-ACCEPT-02/verification.md` | 0 | Inspect candidate verification artifact |
| `<host-path-scan>` | 1 | No host-specific path match in broader TSKG OSS shared files including reviewer outputs |
| `git diff --check ab4595be037bebf28e201010440dc9bc0aa3f84e e0bfe6712dc1af1e3558e124f10a7d03632471de` | 0 | Confirm whitespace/check hygiene |

## Remaining risks

- This review did not modify the candidate, so acceptance remains blocked until a new candidate corrects the verification artifact.
- Once the candidate verification metadata is fixed, the same host-path and diff-hygiene gates should be re-run because any new review output becomes part of the shared-file surface.
- This verdict is limited to acceptance evidence integrity and does not re-open the already-sanitized semantics of `REVIEW-TSKG-OSS-ACCEPT-01`.

## Clarification

The original `P1` was based on an implementability assumption that the candidate verification artifact itself should carry the final delivered candidate SHA. That assumption is too strict for a Git commit artifact because writing the final commit SHA into the file content would change the commit object and create a self-reference loop.

Repair acceptance is therefore available under the following contract without modifying the current candidate:

- The candidate verification artifact may omit self-referential `candidate_head: pending` and may avoid ambiguous `source_candidate` wording.
- The candidate verification artifact should instead record immutable input lineage only, such as the acceptance source commit, the repair/card commit, and the delivered candidate parent.
- The final delivered candidate SHA may be fixed outside the candidate artifact by the task final receipt plus independent review evidence, where the reviewer records the actual reviewed repair SHA and parent.
- Under that contract, the evidence becomes reproducible and non-self-referential while still preserving a verifiable chain from source input to reviewed candidate.

If a follow-up candidate adopts that contract cleanly and still passes the same allowlist, host-path, and diff-hygiene gates, this review's `P1` can be considered repaired. No requirement remains to embed the candidate's own final SHA inside the same candidate commit content.
