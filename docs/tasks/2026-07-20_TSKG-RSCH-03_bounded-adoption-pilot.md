---
card_id: TSKG-RSCH-03
chain_id: TSKG-RSCH
title: Bounded TSKG concept adoption pilot
status: PENDING
type: pilot
owner: Codex 主線
assignee: TSKG-RSCH-03 pilot execution line
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 需依 inventory 與 accepted contract 選擇最多三項代表研究，驗證概念導入成本與誤阻擋風險，但不做正式 workflow mutation
source_kind: commit
source_sha: <accepted-sha-from-TSKG-RSCH-02>
mainline_dispatcher: TSKG root thread
previous_card: REVIEW-TSKG-RSCH-02
worktree_mode: independent-clean-worktree
main_cwd: <repo-root>
expected_worktree_cwd: not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-RSCH-03/
---

# TSKG-RSCH-03：最多三項研究的概念導入試行

## Dependency

只有 `REVIEW-TSKG-RSCH-02 = REVIEW_GO` 才能開始。

## Selection

從 accepted inventory 選最多三項：

1. 一項 active／queued／in-review 研究。
2. 一項已完成但明確會再次引用或 promotion-bound 的研究。
3. 可選一項 identity/source/time/conflict 不確定的 negative case。

不得為了湊數重跑 archived、rejected 或無 reuse intent 的研究。

## Pilot behavior

- 只建立 additive envelope、跑 verifier、記錄缺口與人工判斷。
- 若檢查足以改變研究結論，只產 `RESEARCH_REQUIRED` 後續卡候選，不執行重驗。
- 不修改原 artifact、verdict、queue status、ledger status 或 promotion decision。

## Deliverables

- `docs/evidence/TSKG-RSCH-03/pilot.json`
- `docs/evidence/TSKG-RSCH-03/pilot.md`
- `docs/evidence/TSKG-RSCH-03/verification.md`
- 後續 checkpoint 建議：`ADOPT/ADJUST/STOP`，不得自動接入 workflow。

## Acceptance criteria

- 最多三項、選擇理由可追溯 inventory。
- 歷史研究未被改寫；無未授權 rerun。
- 能量化 envelope 填寫成本、阻擋原因、unknown rate 與 false-positive risk。
- 只有 `ADOPT` 且獨立 Review 通過，才另開 PM queue／ledger checkpoint integration 卡。

## Result

`PENDING_CONTRACT_REVIEW`
