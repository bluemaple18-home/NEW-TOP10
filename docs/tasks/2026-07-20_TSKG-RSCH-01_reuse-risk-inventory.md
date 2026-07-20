---
card_id: TSKG-RSCH-01
chain_id: TSKG-RSCH
title: Inventory research reuse risk without rerunning studies
status: CARD_DRAFTED
type: implementation
owner: Codex 主線
assignee: TSKG-RSCH-01 inventory execution line
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 需跨 research component ledger、experiment ledger、PM queue、research map 與 task evidence 做語意分類，不是單純檔名盤點
source_kind: commit
source_sha: e0aca9e71c4664badce4f1657c9440ce638a4bb1
mainline_dispatcher: TSKG root thread
worktree_mode: independent-clean-worktree
main_cwd: <repo-root>
expected_worktree_cwd: not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-RSCH-01/
---

# TSKG-RSCH-01：既有研究再使用風險清冊

## Goal

建立可重現的唯讀 inventory，將既有與進行中研究分類成 `GRANDFATHERED`、`CHECK_ON_REUSE`、`REQUIRED_NOW` 或 `RESEARCH_REQUIRED`；不重跑研究、不改 verdict、不修改來源 artifacts。

## Read inputs

- `scripts/build_research_component_ledger.py` 與其既有資料來源。
- `scripts/model_experiment_ledger.py` 與 model experiment ledger schema。
- `scripts/build_pm_approved_work_queue.py` 的 queue contract。
- `app/research/map_contract.py` 的 research run／decision 狀態。
- repo 內已提交 research task／evidence；主 worktree 未提交 WIP 不得納入正式輸入。

## Required output schema

每列至少包含：

- `research_id`、`artifact_refs`、`current_status`、`reuse_intent`
- `adoption_class`
- `identity_risk`、`source_risk`、`temporal_risk`、`conflict_risk`
- `promotion_or_model_path`
- `trigger_reasons`、`missing_dimensions`、`next_action`

分類必須 deterministic；無法判定時不得猜測，標記 `UNKNOWN / MANUAL_REVIEW`。

## Allowed scope

- 新增 `scripts/build_tskg_research_adoption_inventory.py`。
- 新增 `tests/test_tskg_research_adoption_inventory.py`。
- 新增 `docs/evidence/TSKG-RSCH-01/inventory.json`、`inventory.md`、`verification.md`。
- 更新本卡 Result/status。

## Forbidden scope

- 不修改任何既有 research artifact、queue、ledger、map、verdict 或 status。
- 不執行 research／backtest／training／promotion。
- 不讀取主 worktree 未提交的 `RESEARCH-QUEUE-01` artifacts 作為正式 evidence。
- 不連外、不新增 dependency、不修改 TSKG runtime。

## TDD and verification

- RED：synthetic fixtures 覆蓋 completed-unused、completed-reused、active/promotion-bound、ambiguous/unknown。
- GREEN：最小 builder 產出 stable ordering 與 closed schema。
- 驗證重跑不改 bytes；四類加總等於 inventory；每個 `RESEARCH_REQUIRED` 至少一個可重現 trigger。

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_tskg_research_adoption_inventory.py
<repo-root>/.venv/bin/python scripts/build_tskg_research_adoption_inventory.py --output docs/evidence/TSKG-RSCH-01/inventory.json
git diff --check
```

## Acceptance criteria

- 不會因缺少新欄位把全部舊研究標成失效。
- `REQUIRED_NOW` 僅限 active／queued／review／promotion-bound。
- 重驗建議只產卡候選，不自動執行。
- exact input coverage、分類 counts、unknowns 與 excluded WIP 有 evidence。

## Stop conditions

- 需要修改既有 artifact、需要主觀猜測 reuse intent、來源狀態互相衝突或同一 blocker 第 3 次失敗時停止。

## Result

`PENDING`
