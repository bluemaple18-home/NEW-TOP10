---
card_id: REVIEW-TSKG-INT-01
chain_id: TSKG-INT
title: Independently review TSKG integration candidate
status: REVIEW_GO
type: review
owner: Codex 主線
assignee: REVIEW-TSKG-INT-01 visible reviewer thread
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 需獨立驗證大型歷史分支 merge candidate、兩軸契約、production isolation、source governance 與 baseline regression 證據
source_kind: commit
source_sha: 2a1e5d2493975fda32bb5f9ecdff5dbc5aa018ff
mainline_dispatcher: TSKG root thread
previous_card: TSKG-INT-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/REVIEW-TSKG-INT-01/review.md
---

# REVIEW-TSKG-INT-01：獨立審查 TSKG 整合候選

## Dependency

只有 `TSKG-INT-01` 交付完整 candidate SHA、candidate worktree clean，且 source 可固定到該 commit 後才能派工；此前維持 `PENDING`。

## Review scope

- 固定 base SHA、candidate SHA、兩個 merge parents 與 target SHA。
- Spec axis：確認整合完整保留 accepted TSKG v1.1、SLC-01、Source Gate、Repair/Review/Acceptance artifacts，且沒有把後續 SLC 或 public approval 誤標為完成。
- Standards axis：correctness、regression、security/privacy、maintainability、performance、testing。
- 特別驗證 production API isolation、PUBLIC source fail-closed、無新 dependency、無真實 source bytes、無交易／模型欄位。
- 重跑 focused/full tests，並獨立判斷唯一 baseline failure 的等價性。

## Allowed scope

- 唯讀審查 candidate。
- 新增 `docs/evidence/REVIEW-TSKG-INT-01/review.md` 與更新本卡 Result/status。

## Forbidden scope

- 不修改 candidate code、fixture、spec 或 merge topology。
- 不修 findings；`REVIEW_NO_GO` 必須退回主線建立 Repair thread。
- 不 merge、push、deploy、掛載 production API 或核准 PUBLIC source。

## Verification

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_tskg_slc01.py tests/test_tskg_src01.py
<repo-root>/.venv/bin/python -m pytest -q
git diff --check <base-sha>..<candidate-sha>
git diff --name-status <base-sha>..<candidate-sha>
git show --no-patch --format='%H%n%P' <candidate-sha>
```

## Verdict contract

- Findings 依 P0–P3 排序並含 `path:line`、觸發條件、風險與建議修法。
- 無阻塞問題才回 `REVIEW_GO`；否則回 `REVIEW_NO_GO`。
- 輸出必須包含 fixed reviewed commit、測試結果、remaining risk、evidence path。

## Result

`REVIEW_GO` — fixed reviewed commit `2a1e5d2493975fda32bb5f9ecdff5dbc5aa018ff`；Spec／Standards 雙軸皆 GO，P0–P3 findings 皆為 0。Focused suite 39 passed／154 subtests；full suite 367 passed／1 baseline failure／182 subtests，唯一 ledger failure 已在 fixed first parent 獨立重現。完整證據見 `docs/evidence/REVIEW-TSKG-INT-01/review.md`。
