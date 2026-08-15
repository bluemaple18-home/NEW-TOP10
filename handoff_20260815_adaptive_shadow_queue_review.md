# Adaptive Shadow Queue Review 交接

## Goal

完成 Card B `Adaptive Research Shadow Queue` 的獨立 review；通過後 fast-forward merge，若有 P0／P1 則回同一 Repair thread 修復並 re-review。

## Root Question

Candidate `8915a382a93d512235915a5400edfc78e62ea238` 是否能只用 committed development-only evidence 產生 deterministic、可解釋、shadow-only priority，且完全不改 canonical queue、manager、scheduler或 production？

## Constraints & Preferences

- 同一 chain 的 Reviewer／Repair各只用原正式 thread，不建立 replacement。
- Reviewer thread：`019fff37-cb09-7403-bf98-332c37eeb8c5`。
- Repair thread：`019fffca-8949-7792-a3e8-5a4f249d75b6`。
- Implementation thread：`01a000d1-e6c9-7b51-89d0-f3198d0e2544`。
- 未核准 push、deploy、scheduler、live或 production write。
- 不得補造 `artifacts/autonomous_research/next_action_queue.json`。
- 保留使用者 dirty files與既有 `.work/**`。

## Completed Actions

- Replay bundle與兩個 P1 repair 已經 Reviewer `APPROVED`。
- Main 已 fast-forward 到 `f7c5791af11f44059103cca4f176197bb5ebd1ec`。
- Card B implementation 已交 candidate：`8915a382a93d512235915a5400edfc78e62ea238`。
- Candidate驗證：23 tests、builder、verifier self-test、projection verifier、replay verifier、py_compile、JSON validation、`git diff --check` 全綠。
- 建立 review card：`docs/tasks/2026-08-15_REVIEW-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1.md`。
- Review source commit：`d72dc49`；固定 diff：`f7c5791..8915a38`。
- 原 Reviewer已開始 full review；正向 tests／self-test／verifier／diff-check均通過。

## Active State

- Main HEAD：`7fa78a9`（`f7c5791` 加本交接快照）。
- Card B candidate：`8915a382a93d512235915a5400edfc78e62ea238`，candidate worktree clean。
- Review source：`d72dc49`，Reviewer worktree clean。
- Reviewer目前正在反證 builder output path、external JSON與 canonical alias。
- 使用者 dirty files：
  - `scripts/build_weekend_universe_inventory.py`
  - `tests/test_weekend_universe_inventory_snapshot.py`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`
  - `docs/tasks/2026-08-03_TOP10-AICORE-STORAGE-OWNERSHIP-BOUNDARY-01.md`
  - `.work/**`

## Blocker

不是外部 blocker；目前只等待 Reviewer正式 verdict。反例初步顯示 `--output-root`、external bundle／manifest與 canonical alias可能缺 fail-closed boundary，需以 Reviewer final finding為準。

## Candidate Fork

- `APPROVED`：核對 main dirty paths無重疊後，cherry-pick單一 candidate commit `8915a382...` 到 main；不合併 review card commit `d72dc49`。
- `CHANGES_REQUIRED`：建立實體 repair card；用同一 Repair thread `019fffca...`；修復後回 Reviewer `019fff37...` targeted re-review。

## In Progress / Remaining Work

1. 讀 Reviewer thread最新 turn，取得 `APPROVED`或`CHANGES_REQUIRED`。
2. 若有 finding，保留 severity、path:line、repro與validation gap；不要自行降級。
3. 依 Candidate Fork執行。
4. Merge後重跑受影響 gates與`git diff --check`，再決定下一張卡。

## Waiting Conditions

- Reviewer正式 final answer。
- 只有 Reviewer通過才可 merge。

## Blocked & Errors

- Review worktree CodeGraph未初始化；Reviewer依規範使用固定 git objects與限域 `rg` fallback。
- Canonical `next_action_queue.json`在 base與candidate都不存在，屬 PRE-EXISTING；不得為過 gate補造。

## Key Decisions & Resolved Questions

- Review Orchestrator因 clean worktree誤判 0 diff；已人工改判 full review。實際 diff為9檔、1113新增行。
- Card B只建立 shadow projection；canonical queue為 read-only parity lock。
- Review card commit與candidate分離，merge目標仍是 `8915a382...`。

## Next Step

新對話先讀本檔與 Reviewer thread `019fff37-cb09-7403-bf98-332c37eeb8c5` 最新 turn；不要重開 Reviewer，也不要先 merge。
