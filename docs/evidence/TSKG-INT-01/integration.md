# TSKG-INT-01 Integration Evidence

## Root question

能否在不碰 production API、排名、模型、ETL、scheduler 與 PUBLIC source approval 邊界的前提下，將固定 TSKG target 完整合併到固定 main bootstrap，形成單一、可獨立 Review 的 merge candidate？

## Fixed inputs and preflight

- Bootstrap / first parent：`a9758aa91e95985b16ce154a65521d10df6544d1`
- Target / second parent：`7f472be548c79a0b8d9758dcb3a4cfaca83751ff`
- Merge base：`d922e3f05decc4e397eb1132db55f0d601eaf6d3`
- Worktree：platform-managed independent detached worktree；cwd 不等於主 worktree。
- Pre-merge status：clean。
- Git metadata：獨立 worktree git dir；`index.lock` 不存在。
- Target ref：`origin/codex/tskg-source-gate` 精確解析為固定 target SHA。
- Merge command：`git merge --no-ff --no-commit 7f472be548c79a0b8d9758dcb3a4cfaca83751ff`
- Merge result：無 conflict；target tree 帶入 34 個新增檔、6,010 insertions。

本 worktree 未配置 `.venv`；驗證沿用主專案既有 uv venv 的 Python 3.12.12 interpreter，但 cwd 與 import tree 均為本 integration worktree。未安裝或更新任何依賴。

## Exact changed files

### Target merge payload（34 個新增檔）

- `app/tskg/__init__.py`
- `app/tskg/identity.py`
- `app/tskg/repository.py`
- `app/tskg/router.py`
- `app/tskg/service.py`
- `app/tskg/source_policy.py`
- `data/fixtures/tskg/identity_v1.json`
- `data/fixtures/tskg/source_policy_v1.json`
- `docs/evidence/REPAIR-TSKG-01/repair.md`
- `docs/evidence/REPAIR-TSKG-SLC-01/repair.md`
- `docs/evidence/REPAIR-TSKG-SRC-01/repair.md`
- `docs/evidence/REVIEW-TSKG-01/review.md`
- `docs/evidence/REVIEW-TSKG-SLC-01/review.md`
- `docs/evidence/REVIEW-TSKG-SRC-01/review.md`
- `docs/evidence/TSKG-01/acceptance.md`
- `docs/evidence/TSKG-01/requirements_traceability.md`
- `docs/evidence/TSKG-01/verification.md`
- `docs/evidence/TSKG-SLC-01/acceptance.md`
- `docs/evidence/TSKG-SLC-01/verification.md`
- `docs/evidence/TSKG-SRC-01/acceptance.md`
- `docs/evidence/TSKG-SRC-01/verification.md`
- `docs/specs/TSKG_v1.1.md`
- `docs/tasks/2026-07-17_REPAIR-TSKG-01_executable_spec.md`
- `docs/tasks/2026-07-17_REVIEW-TSKG-01_executable_spec.md`
- `docs/tasks/2026-07-17_TSKG-01_executable_spec.md`
- `docs/tasks/2026-07-18_REPAIR-TSKG-SLC-01.md`
- `docs/tasks/2026-07-18_REPAIR-TSKG-SRC-01_source_gate.md`
- `docs/tasks/2026-07-18_REVIEW-TSKG-SLC-01.md`
- `docs/tasks/2026-07-18_REVIEW-TSKG-SRC-01_source_gate.md`
- `docs/tasks/2026-07-18_TSKG-SLC-01_offline_identity_company_query.md`
- `docs/tasks/2026-07-18_TSKG-SRC-01_source_gate.md`
- `tests/__init__.py`
- `tests/test_tskg_slc01.py`
- `tests/test_tskg_src01.py`

### Integration-owned evidence（2 個檔案）

- `docs/evidence/TSKG-INT-01/integration.md`（新增）
- `docs/tasks/2026-07-20_TSKG-INT-01_integrate_source_gate.md`（僅更新 status / Result）

## Verification evidence

### Focused suite

Command equivalent：

```bash
<existing-uv-venv>/bin/python -m pytest -q tests/test_tskg_slc01.py tests/test_tskg_src01.py
```

Result：`39 passed, 1 warning, 154 subtests passed in 0.83s`。

### Full suite

Command equivalent：

```bash
<existing-uv-venv>/bin/python -m pytest -q
```

Result：`1 failed, 367 passed, 4 warnings, 182 subtests passed in 56.63s`。

唯一 failure：

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
AssertionError: 'FAILED' != 'OK'
```

### Baseline comparison

為避免主 worktree 的既有 WIP 影響結果，將固定 first parent `a9758aa91e95985b16ce154a65521d10df6544d1` 的 committed tree 以 `git archive` 匯出到獨立 temporary directory，使用同一 interpreter、停用 bytecode 與 pytest cache，重跑唯一 failing test：

```bash
PYTHONDONTWRITEBYTECODE=1 <existing-uv-venv>/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

Parent result：`1 failed in 0.24s`，assertion 同為 `'FAILED' != 'OK'`。因此 full suite 沒有新增 regression。

## Boundary and acceptance mapping

- `app/api/main.py` 未變更；TSKG router 未掛 production API。
- ranking、model、ETL、scheduler 與 production runtime 均未變更。
- 未核准任何 PUBLIC source，未連外、未 deploy、未 push。
- target 帶入內容未手改；integration-owned 變更僅為本 evidence 與本卡 Result/status。
- Merge candidate 經 `git show --no-patch --format='%H%n%P' HEAD` 驗證恰有兩個 parents：first parent 為 `a9758aa91e95985b16ce154a65521d10df6544d1`，second parent 為固定 target `7f472be548c79a0b8d9758dcb3a4cfaca83751ff`。
- `git diff --check HEAD^1..HEAD` 通過；post-commit `git status --short` 無輸出。

## Current state

`DELIVERED_CANDIDATE`
