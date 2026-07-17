---
id: ARCH-UPGRADE-02
status: completed
type: implementation
priority: P0
thickness: standard
model: gpt-5.5
reasoning: high
model_reason: 需解析 Python/import/config/docs 關係並推導驗證範圍。
---

# Git diff incremental impact planner

## 目標

將 Git diff 轉成直接修改、reverse dependents、受影響 workflow/artifact 與 required tests/gates 的 deterministic plan。

## 依賴

- blocking edges：`ARCH-UPGRADE-01`。
- frontier：01 完成後。

## 契約

- 輸入：base/head 或明確 changed-file list、architecture manifest。
- 輸出：version、commit SHA、changed、impacted、workflows、artifacts、required_verification、unknown_edges、risk。
- Python graph、control-plane explicit edges 與 script reference audit 分開標示 provenance。
- heuristic/ambiguous edge 不得假裝確定；必須進 `needs_review`。
- 沒有受影響測試映射時，production path 必須 fail closed。

## 可改範圍

- `app/architecture/impact.py`
- `scripts/plan_incremental_verification.py`
- `scripts/verify_incremental_verification_plan.py`
- `tests/test_incremental_impact_planner.py`
- 必要 config/docs。

## 驗收

- synthetic diff 測試涵蓋 Python importer、workflow step、artifact consumer、config owner 與 docs-only change。
- 對 production entrypoint 修改能列出 daily contract/integration gates。
- deterministic、無網路、無 source tree write。

## Evidence

`.work/ARCH-UPGRADE-02/evidence/`
