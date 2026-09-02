# R13-R5 R1 committed bundle authority re-review

👉 [假設與目標確認] 目標是 re-review 固定 repair SHA 的 R13 committed-bundle authority；邊界是只驗原 findings 與 regression、不新增球門、不修 code、不 commit、不 push、不准入任何下游；驗收是給出 reviewed SHA、原 findings 關閉狀態、實際驗證與 `REVIEW_GO/NO_GO`。

## Review target

- Re-review task：`docs/tasks/2026-09-02_REREVIEW-NEW-TOP10-BC-CP2-R13-R5-R1-COMMITTED-BUNDLE-AUTHORITY.md`
- Original candidate：`84cc32452889553f1c89f7aaac4e89382b8d9827`
- Repair parent：`015d6e9c97ff968e300f62ca870fdcde4f789598`
- Repair candidate：`a2fdfdf6ef0e14d244f0676f288f95d78e8a08a5`
- Original review：`docs/evidence/REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY/review.md`
- Repair card：`docs/tasks/2026-09-02_REPAIR-NEW-TOP10-BC-CP2-R13-R5-R1-COMMITTED-BUNDLE-AUTHORITY.md`

## Verdict

`REVIEW_GO`

R1 repair closes the original blocking authority findings. The verifier now pins a single
immutable `HEAD^{commit}` at start, uses that commit for `ls-tree` and `show`, rejects if
`HEAD` changes before return, fails closed on staged-state Git command failure, and rejects
lexical project-root symlinks before resolving. The real R13 bundle test no longer has the
`SOURCE_NOT_COMMITTED` early-return path.

This GO only accepts the R13-R5 R1 repair for committed-bundle authority. It does not
authorize R14, Entry-Regime capacity/split, preregistration, historical corpus admission,
B0 Phase 2, B1, C1, production, push, deploy, or any downstream write.

## Original findings status

- P1 `HEAD` movement false-register：CLOSED.
  - Rerun probe result：`HEAD_MOVEMENT status=REJECTED`;
    `HEAD_MOVEMENT errors=HEAD_CHANGED_DURING_VERIFICATION`;
    `HEAD_MOVEMENT extra_in_final_head=True`.
- P2 project-root symlink：CLOSED.
  - Rerun probe result：`ROOT_SYMLINK status=REJECTED`;
    `ROOT_SYMLINK errors=ROOT_SYMLINK`;
    `ROOT_SYMLINK root_is_symlink=True`.
- P2 staged-state Git command failure：CLOSED.
  - Rerun probe result：`GIT_FAILURE status=REJECTED`;
    `GIT_FAILURE errors=GIT_STAGED_STATE_UNAVAILABLE`.
- P2 full diff-check vs exact CSV bytes conflict：RESIDUAL, non-blocking under R1 repair card.
  - Repair changed only source/test files; exact bundle bytes remain unchanged and are verified by
    fixed size/SHA plus public bundle verifier.
- P3 real-bundle early-return branch：CLOSED.
  - `test_real_r13_bundle_is_registered_after_implementation_commit()` now directly asserts
    `STATUS_REGISTERED` and `errors == []`.

## Scope verification

- `git diff --name-status 015d6e9..a2fdfdf6ef0e14d244f0676f288f95d78e8a08a5`：
  only `app/research/r13_forward_receipt_authority.py` and
  `tests/test_r13_forward_receipt_authority.py` changed.
- `git diff --name-status 84cc32452889553f1c89f7aaac4e89382b8d9827..a2fdfdf6ef0e14d244f0676f288f95d78e8a08a5 -- artifacts/backtest/r13-r2-20260901-af9c32b/output`：
  no output; four bundle files unchanged.
- Fixed bundle bytes:
  - `COMPLETE.manifest.json`：`4263` bytes,
    `144777c9ea1aa8dcd944917820640a77866e3e4280549854549a98e3b90189c9`
  - `ranking_2026-09-01.receipt.json`：`8074` bytes,
    `dff85cb7028f3a664a5d96a0884f4f7e6d334c29ef2f8c23bd85e42cdcbc76ee`
  - `model-ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d.pkl`：
    `2798697` bytes,
    `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
  - `ranking_2026-09-01.csv`：`4546` bytes,
    `d17cf9202b83f626023a8ee18aff423b1508540e6c54f294c7253021350046b2`

## Verification performed

- CodeGraph context attempted first; current index did not surface the new R13 target, so review
  used scoped file reads for the fixed task, source, tests, and evidence.
- `git rev-parse HEAD`：`a2fdfdf6ef0e14d244f0676f288f95d78e8a08a5`.
- `.venv/bin/python -m pytest tests/test_r13_forward_receipt_authority.py tests/test_ranking_provenance_receipt.py tests/test_ranking_provenance_admission.py`：
  exit `0`, `55 passed`.
- `.venv/bin/python -m app.research.r13_forward_receipt_authority --verify`：
  exit `0`; status `REGISTERED_FORWARD_BUNDLE_VERIFIED`; errors `[]`; all four bundle files
  `commit_status=MATCHED`; `downstream_authority=NONE`.
- `git diff --check 015d6e9..a2fdfdf6ef0e14d244f0676f288f95d78e8a08a5 -- app/research/r13_forward_receipt_authority.py tests/test_r13_forward_receipt_authority.py`：
  exit `0`.
- `git status --porcelain=v1 artifacts/backtest/r13-r2-20260901-af9c32b/output app/research/r13_forward_receipt_authority.py tests/test_r13_forward_receipt_authority.py`：
  exit `0`, no output.
- HEAD movement probe under `/private/tmp`：exit `0`, rejected with
  `HEAD_CHANGED_DURING_VERIFICATION`.
- root symlink probe under `/private/tmp`：exit `0`, rejected with `ROOT_SYMLINK`.
- staged-state Git command failure probe under `/private/tmp`：exit `0`, rejected with
  `GIT_STAGED_STATE_UNAVAILABLE`.

## Spec axis

`PASS`

The repair addresses the original P1/P2/P3 findings without modifying the four exact bundle
files, old receipt verifier, historical admission, workflow, config, or production surface.

## Standards axis

`PASS`

The repair keeps the authority reader narrow and read-only, preserves the fixed public CLI/API
shape, and adds regression coverage for the exact original failure modes. Remaining CSV
whitespace is an immutable-artifact acceptance exception, not a source/test regression.

## Remaining risks

- The R13-R5 authority still proves only one exact committed R13-R2 bundle identity. It does not
  prove outcome quality, experiment admission, historical admission, or production readiness.
- Full-repo `git diff --check` remains incompatible with the fixed R13-R2 CSV evidence bytes;
  source/test scoped diff-check is clean, and bundle bytes are protected by fixed size/SHA.
