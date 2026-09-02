# R13-R5 committed bundle authority independent review

👉 [假設與目標確認] 目標是審查固定 candidate SHA 的 R13-only committed-bundle authority 是否可被主線接受；邊界是 maker/checker 分離、只審不修、不 commit、不 push、不准入任何下游；驗收是給出 P0-P3 findings、Spec／Standards axes、實際驗證與 REVIEW_GO/NO_GO verdict。

## Review target

- Task：`docs/tasks/2026-09-02_REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY.md`
- Candidate：`84cc32452889553f1c89f7aaac4e89382b8d9827`
- Parent：`af9ca5262b97e373519a96a8bfdfcdb1db2eb3c8`
- Governing contract：`docs/evidence/BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT/01-contract-decision.md`
- Review mode：independent fixed-SHA review；implementation 未修改。

## Verdict

`REVIEW_NO_GO`

主要 functional path 目前會在固定 candidate HEAD 回傳
`REGISTERED_FORWARD_BUNDLE_VERIFIED`，但 authority reader 沒有把整次 Git 檢查固定在同一
個 commit。若 `HEAD` 在 file-set 檢查後移動到含 extra tracked file 的 commit，reader 仍可
回 registered。這違反 R13-R4 對 Git `HEAD` file-set、extra tracked file 與 TOCTOU 的
critical contract，因此本次不可接受。

## Findings

### P1 — `HEAD` 可在驗證中途移動，導致 extra tracked file false-register

- File：`app/research/r13_forward_receipt_authority.py:195`、`app/research/r13_forward_receipt_authority.py:230`、`app/research/r13_forward_receipt_authority.py:345`
- Contract：R13-R4 要求以 Git `HEAD` 作 committed-byte authority，canonical root 下 tracked file set 必須精確等於 allowlist，任何 extra tracked file 都要拒絕。
- Problem：reader 多次用 literal `HEAD` 執行 `ls-tree` 與 `show`，但沒有先固定 `HEAD` commit，也沒有驗證結束時 `HEAD` 未變。`_verify_head_file_set()` 看到的是舊 HEAD file-set；之後 `_verify_expected_bytes()` 與 bundle verifier 可讀到新 HEAD／working tree。
- Reproduction：review probe 在 temporary repo 中讓 `HEAD` 於 `ls-tree HEAD` 後移到含 `regime_shadow_ranking.json` 的 commit，結果：
  - `status=REGISTERED_FORWARD_BUNDLE_VERIFIED`
  - `errors=`
  - `extra_in_final_head=True`
- Impact：在 concurrent HEAD movement 或自動化切換 commit 的情境，reader 可宣告「當前 HEAD 已註冊」，但當前 HEAD 實際含 contract 禁止的 extra tracked file。這是 authority false positive。
- Minimum repair：驗證開始先取得 immutable commit id，例如 `git rev-parse --verify HEAD^{commit}`；所有 `ls-tree`／`show` 都使用該 commit id，不再使用 floating `HEAD`；結束前再次確認 `HEAD` 仍為同一 commit，否則回 `REJECTED` 與 stable code `HEAD_CHANGED_DURING_VERIFICATION`。新增對應 regression test。

### P2 — `project_root` symlink 未依 contract fail closed

- File：`app/research/r13_forward_receipt_authority.py:111`、`app/research/r13_forward_receipt_authority.py:345`
- Problem：`_verify_with_contract()` 先做 `project_root.resolve()`，因此 `_safe_project_path()` 收到的 root 已經不是 symlink；`root.is_symlink()` 永遠看不到 caller 傳入的是 symlink root。
- Reproduction：以 symlink root 呼叫 private verifier，結果：
  - `status=REGISTERED_FORWARD_BUNDLE_VERIFIED`
  - `errors=`
  - `root_is_symlink=True`
- Impact：目前 public CLI 沒有 root override，風險低於 P1；但 public API 仍接受 `project_root`，且 R13-R4 明確要求 root/file symlink fail closed。
- Minimum repair：在 resolve 之前檢查 lexical root；若 `project_root.absolute().is_symlink()` 或 lexical absolute path 與 strict resolved path 不一致，回 `ROOT_SYMLINK`。補 root-symlink regression test。

### P2 — Git staged-state command failure 被忽略

- File：`app/research/r13_forward_receipt_authority.py:213`、`app/research/r13_forward_receipt_authority.py:220`
- Problem：`git diff --cached --name-only` 或其 `--diff-filter=A` 版本若 return code 非 0，目前不加入 error。這違反「Git command failure fail closed」的 review risk。
- Reproduction：review probe 將兩個 staged-state Git call 模擬為 return code `128`，clean fixture 仍回：
  - `status=REGISTERED_FORWARD_BUNDLE_VERIFIED`
  - `errors=`
- Impact：index/staged 檢查不可用時仍可能發出 registered state；雖然 expected file bytes 與 committed bytes仍會驗，但 staged boundary 未被證明。
- Minimum repair：任一 Git command 非 0 都必須加入 stable error，例如 `GIT_STAGED_STATE_UNAVAILABLE`／`GIT_HEAD_FILE_SET_UNAVAILABLE`，並維持 `REJECTED`。補 Git command failure regression test。

### P2 — 全量 `git diff --check` 未通過，且與 exact evidence bytes 契約衝突

- File：`artifacts/backtest/r13-r2-20260901-af9c32b/output/ranking_2026-09-01.csv:2`
- Problem：R13-R5 implementation card 要求 `git diff --check` 通過；但全量 diff check 對 committed exact CSV evidence 報 trailing whitespace。這些 bytes 同時又被 R13-R4 固定 SHA／size，不可直接修改。
- Evidence：`git diff --check af9ca52..84cc32452889553f1c89f7aaac4e89382b8d9827` exit `2`，多行 trailing whitespace；source/test scoped `git diff --check ... -- app/research/r13_forward_receipt_authority.py tests/test_r13_forward_receipt_authority.py` exit `0`。
- Impact：不是 authority false-register 的主因，但代表 implementation acceptance 與 immutable evidence bytes 有明文衝突。
- Minimum repair：不要改 R13-R2 bundle bytes。下一次 acceptance 應明確拆成 source/test diff-check 必過，exact evidence artifact 以 fixed SHA/size 與 bundle verifier 證明；或另卡修正 governing contract 的 diff-check 例外。

### P3 — real-bundle test 保留 pre-commit compatibility branch

- File：`tests/test_r13_forward_receipt_authority.py:181`
- Problem：real R13 test 若得到 `REJECTED` 且含 `SOURCE_NOT_COMMITTED`，會直接 return。這對 pre-commit 開發友善，但不能單獨證明 candidate commit 後的 real bundle 已 registered。
- Review mitigation：本次 review 已在 candidate HEAD 直接跑 public API／CLI，得到 registered；因此不是 blocker。
- Minimum repair：可新增固定 candidate／committed-mode smoke，或在 acceptance command 中明確保留 public CLI 固定 SHA 驗證，避免只看 pytest。

## Spec axis

`FAIL`

- Changed-files allowlist：PASS，candidate 相對 parent 只新增 R13-R4 指定六檔。
- Real R13 bundle public verifier：PASS，candidate HEAD 回 `REGISTERED_FORWARD_BUNDLE_VERIFIED`，四檔 `commit_status=MATCHED`，`downstream_authority=NONE`。
- Historical admission unchanged：PASS，相關 regression tests pass。
- Critical authority boundary：FAIL，floating `HEAD` TOCTOU 可讓 extra tracked file false-register。
- Git command failure fail-closed：FAIL，staged-state command failure 被忽略。
- Root symlink boundary：FAIL，symlink root 未拒絕。
- Implementation acceptance `git diff --check`：FAIL，全量 diff check 對 exact CSV bytes 報 trailing whitespace。

## Standards axis

`FAIL`

核心 reader 的 API/CLI 形狀夠窄，且重用 existing bundle verifier 是對的方向；但 critical authority gate 必須把「同一個 commit 的 file-set 與 bytes」作為原子事實處理。現在的 implementation 把多次 Git command 各自讀 floating `HEAD`，在 governance boundary 上不夠硬。

## Verification performed

- CodeGraph context/explore：review 前先定位 `r13_forward_receipt_authority.py`、`ranking_provenance_receipt.py`、`ranking_provenance_admission.py` 的相關入口。
- `git rev-parse HEAD`：`84cc32452889553f1c89f7aaac4e89382b8d9827`
- `git diff --name-status af9ca52..84cc32452889553f1c89f7aaac4e89382b8d9827`：exit `0`，只列六個 allowed added files。
- `git ls-tree -r --name-only 84cc32452889553f1c89f7aaac4e89382b8d9827 -- artifacts/backtest/r13-r2-20260901-af9c32b/output`：exit `0`，只列四個 allowed bundle files。
- `.venv/bin/python -m pytest tests/test_r13_forward_receipt_authority.py tests/test_ranking_provenance_receipt.py tests/test_ranking_provenance_admission.py`：exit `0`，`52 passed`。
- `.venv/bin/python -m app.research.r13_forward_receipt_authority --verify`：exit `0`，status `REGISTERED_FORWARD_BUNDLE_VERIFIED`，errors `[]`。
- `git status --porcelain=v1 artifacts/backtest/r13-r2-20260901-af9c32b/output app/research/r13_forward_receipt_authority.py tests/test_r13_forward_receipt_authority.py`：exit `0`，no output。
- `git diff --check af9ca52..84cc32452889553f1c89f7aaac4e89382b8d9827`：exit `2`，trailing whitespace in exact CSV evidence。
- `git diff --check af9ca52..84cc32452889553f1c89f7aaac4e89382b8d9827 -- app/research/r13_forward_receipt_authority.py tests/test_r13_forward_receipt_authority.py`：exit `0`。
- HEAD movement probe：exit `0`，demonstrated false registered state with extra tracked file in final HEAD。
- root symlink probe：exit `0`，demonstrated symlink root registered instead of rejected。
- Git command failure probe：exit `0`，demonstrated staged-state command failure registered instead of rejected。

## Minimum repair acceptance

1. Pin one immutable commit id at verifier start and use it for all Git object reads; reject if `HEAD` changes before returning.
2. Treat every Git command failure as a stable fail-closed error; no Git failure path may return registered.
3. Detect root symlink before resolving project root, and keep file symlink/path escape protections.
4. Add regression tests for HEAD movement, staged-state Git command failure, and root symlink.
5. Keep public CLI fixed-contract with no path override and `downstream_authority=NONE`.
6. Re-run focused tests plus public CLI at fixed candidate SHA.
7. Resolve the exact-data `git diff --check` conflict without modifying R13-R2 bundle bytes: either scope diff-check to source/test files and rely on SHA/size for exact evidence, or update the governing acceptance with an explicit immutable-artifact exception.

## Boundary reminder

This review does not authorize R14, Entry-Regime capacity/split, preregistration, historical corpus admission, B0 Phase 2, B1, C1, production, push, deploy, or external writes.
