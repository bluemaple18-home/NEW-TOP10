---
id: ARCH-UPGRADE-04
status: completed
type: implementation
priority: P0
thickness: strict
model: gpt-5.6-sol
reasoning: high
model_reason: 拆解 production orchestration 共享邏輯，需維持 CLI、status 與 rollback invariant。
---

# Production orchestration modularization

## 目標

把 `scripts/run_automation.py` 中 production-critical 的純政策、step spec、runner/status 與 artifact 驗證移入可測 `app/automation/`，保持 CLI 與 production 行為等價。

## 依賴

- blocking edges：`ARCH-UPGRADE-01`、`ARCH-UPGRADE-03`。

## Invariants

- `python -m scripts.run_automation` CLI、mode、exit code 與 canonical status path 不變。
- daily step order、ranking/report/payload 日期語意不變。
- retrain rollback、resource profile、publish guard 不變。
- script 收斂為 composition root；不得同時切換 Daily V2 production。

## 可改範圍

- `app/automation/`
- `scripts/run_automation.py`
- 直接相關 tests/docs。

## 驗收

- 先補 characterization tests，再搬移邏輯。
- production dry-run/status contract、daily wrapper guards、retrain rollback 與 scheduler ownership 測試通過。
- parity harness 無新增 mismatch。

## Evidence

`.work/ARCH-UPGRADE-04/evidence/`

- 70 affected tests、15 subtests 通過；僅 3 個既有 SHAP colormap deprecation warnings。
- parity 2026-07-16 重算為 `GO`，production switch 維持 `NO-GO`。
- 2026-07-09 缺少完整 step evidence 的歷史樣本維持 `NO-GO`。
- 未修改 production model、ranking、publish、launchd 或 shell entrypoint。
