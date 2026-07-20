---
card_id: TSKG-OSS-ACCEPT-02
status: DELIVERED_CANDIDATE
verified_on: 2026-07-20
acceptance_source_sha: 938f583eeb361692976c123b12bf5bd134f42848
original_cleanup_card_commit: ab4595be037bebf28e201010440dc9bc0aa3f84e
original_candidate_sha: e0bfe6712dc1af1e3558e124f10a7d03632471de
original_candidate_parent: ab4595be037bebf28e201010440dc9bc0aa3f84e
repair_card_commit: a6e7b9dd4c34d3cb6aba6203d5e4724e8bb3ddc3
expected_repair_candidate_parent: a6e7b9dd4c34d3cb6aba6203d5e4724e8bb3ddc3
repair_candidate_sha_binding: final receipt and same-reviewer re-review evidence
---

# TSKG-OSS-ACCEPT-02 verification

## Scope

- 本卡只處理 `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md` 的主機資訊與會自我命中的掃描命令字面值。
- review verdict、reviewed SHA、findings、Spec／Standards axes、研究內容與 exit code 語意均維持不變。
- 其餘變更僅限本卡狀態與新增本 verification evidence。

## Preflight

| Check | Result |
|---|---|
| Independent worktree | pass |
| Original delivered candidate lineage: `e0bfe6712dc1af1e3558e124f10a7d03632471de^ == ab4595be037bebf28e201010440dc9bc0aa3f84e` | pass |
| Repair preflight lineage: `HEAD == a6e7b9dd4c34d3cb6aba6203d5e4724e8bb3ddc3` and `HEAD^ == e0bfe6712dc1af1e3558e124f10a7d03632471de` | pass |
| `git status --short` before edits | empty |
| `git rev-parse --git-dir` shape | `<repo-gitdir>/worktrees/<worktree-id>` |
| `.git/index.lock` present | no |
| `unrelated_dirty_paths` | `[]` |

## Sanitization performed

- Replaced the independent worktree cwd with `<local-only-worktree>`.
- Replaced the git metadata path with `<repo-gitdir>/worktrees/<worktree-id>`.
- Replaced the host-path scan command literals with `<host-path-scan>`.

## Verification results

| Check | Exit | Result |
|---|---:|---|
| `git diff -- docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md docs/evidence/TSKG-OSS-ACCEPT-02/verification.md` | 0 | Only allowlist files changed |
| `git diff --word-diff=porcelain HEAD^ -- docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md docs/evidence/TSKG-OSS-ACCEPT-02/verification.md` | 0 | Word diff limited to placeholder cleanup plus new evidence |
| `<host-path-scan>` | 1 | Broader TSKG OSS shared-file gate passed with no matches |
| `git diff --check` | 0 | Whitespace and patch hygiene passed |

## Original ACCEPT-02 candidate allowlist

- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`
- `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md`
- `docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-02_review_evidence_path_cleanup.md`

## Repair candidate exact changed files

- `docs/evidence/TSKG-OSS-ACCEPT-02/verification.md`
- `docs/tasks/2026-07-20_REPAIR-TSKG-OSS-ACCEPT-02_lineage_evidence.md`
