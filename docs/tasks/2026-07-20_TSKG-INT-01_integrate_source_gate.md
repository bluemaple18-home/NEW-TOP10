---
card_id: TSKG-INT-01
chain_id: TSKG-INT
title: Integrate accepted TSKG source gate branch
status: DELIVERED_CANDIDATE
type: integration
owner: Codex 主線
assignee: TSKG-INT-01 visible implementation thread
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 需把落後共同祖先 205 個 main commits 的 20-commit TSKG 稽核鏈整合成單一候選 merge commit，並辨識基線測試失敗與真實 regression
source_kind: branch
source_branch: codex/tskg-integration-cards
source_sha: bc452e75cf2c847df40c9f6c3bdb6e52e0a77184
target_branch: origin/codex/tskg-source-gate
target_sha: 7f472be548c79a0b8d9758dcb3a4cfaca83751ff
mainline_dispatcher: TSKG root thread
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-INT-01/integration.md
---

# TSKG-INT-01：整合 accepted TSKG source gate branch

## Root question

能否在不碰現有 production API、排名、模型與 public source approval 邊界的前提下，把 `origin/codex/tskg-source-gate` 的完整 20-commit 稽核鏈整合到最新 main 基線，形成可獨立 Review 的單一 merge candidate？

## Known evidence

- Bootstrap base：`bc452e75cf2c847df40c9f6c3bdb6e52e0a77184`。
- Target：`7f472be548c79a0b8d9758dcb3a4cfaca83751ff`。
- Merge base：`d922e3f05decc4e397eb1132db55f0d601eaf6d3`。
- 先前唯讀試驗：34 個新增檔、6,010 insertions、無 merge conflict。
- TSKG focused suite：39 passed、154 subtests passed。
- Clean Git merge simulation full suite：367 passed、1 baseline failure；同一 research component ledger failure 在 merge 前 main 可重現。

## Dependencies and frontier

- 本卡是目前唯一 frontier。
- `REVIEW-TSKG-INT-01` 必須等本卡交付完整 candidate SHA 才可啟動。
- `REPAIR-TSKG-INT-01` 只有 Review 判定 `REVIEW_NO_GO` 才可啟動。

## Allowed scope

- 以 `--no-ff --no-commit` 合併固定 target SHA，保留整條 branch history。
- 由 merge 帶入的 34 個 TSKG 新增檔。
- 新增 `docs/evidence/TSKG-INT-01/integration.md`。
- 只為記錄驗證證據而更新本卡 Result/status。

## Forbidden scope

- 不修改 target branch 帶入的 TSKG code、fixture、spec、review 或 acceptance artifact。
- 不修改既有 `app/api/main.py`，不得掛載 TSKG router。
- 不核准任何 PUBLIC source，不連外、不部署、不 push。
- 不修改 ranking、model、ETL、scheduler、production runtime 或主 worktree 的既有 WIP。
- 若發生 merge conflict，停止並回報，不可自行解衝突。

## Required workflow

1. 驗證 worktree clean、source/target full SHA、無 `index.lock`。
2. `git merge --no-ff --no-commit 7f472be548c79a0b8d9758dcb3a4cfaca83751ff`。
3. 建立 integration evidence，記錄 exact changed files、merge parents、focused/full tests 與 baseline comparison。
4. 跑完驗證後才建立單一 merge candidate commit。
5. 只回報 `DELIVERED_CANDIDATE` 與完整 SHA，不得自稱 accepted/integrated。

## Verification

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_tskg_slc01.py tests/test_tskg_src01.py
<repo-root>/.venv/bin/python -m pytest -q
git diff --check HEAD^1..HEAD
git status --short
git show --no-patch --format='%H%n%P' HEAD
```

Full suite 若仍只有 `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger` 失敗，必須在 merge parent 重跑同測試證明為 baseline；任何新增失敗一律停止。

## Acceptance criteria

- 產生恰有兩個 parents 的 merge candidate，第二 parent 等於固定 target SHA。
- TSKG focused suite 全綠。
- Full suite 無新增 regression；既有 baseline failure 有 parent-side reproduction。
- `git diff --check` 通過，worktree clean。
- exact allowlist 與證據保存完成。

## Stop conditions

- merge conflict、target SHA 漂移、新增測試失敗、需要手改 target code、需要碰 forbidden scope或同一 blocker 第 3 次失敗時停止。

## Result

`DELIVERED_CANDIDATE` — 固定 target 已無衝突合併；focused suite 為 39 passed / 154 subtests passed，full suite 為 367 passed / 1 baseline failure / 182 subtests passed，且該 ledger failure 已在固定 first parent 重現。完整證據見 `docs/evidence/TSKG-INT-01/integration.md`。
