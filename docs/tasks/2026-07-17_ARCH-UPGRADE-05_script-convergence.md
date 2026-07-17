---
id: ARCH-UPGRADE-05
status: blocked
type: implementation
priority: P1
thickness: strict
model: gpt-5.6-sol
reasoning: high
model_reason: 涵蓋 398 支 scripts、production reachability 與共用邏輯邊界，需逐批驗證。
---

# Scripts 全量治理與模組收斂

## 目標

不是刪檔式 cleanup；要讓每支 tracked script 都有 lifecycle、owner、reachability、artifact contract 與 candidate action，並把 production-critical 重複邏輯收回 `app/`。

## 依賴

- blocking edges：`ARCH-UPGRADE-01`、`ARCH-UPGRADE-02`、`ARCH-UPGRADE-04`。

## 批次順序

1. production entrypoints 與直接依賴。
2. production artifact builders/verifiers。
3. research runners、builders、verifiers。
4. maintenance 與 approved-unreferenced。
5. legacy/dead candidate；沒有獨立證據不得刪除。

## 完整驗收

- 398/398 tracked Python scripts 均被清冊覆蓋。
- `unclassified=[]`；production reachable path 的 `owner/contract/tests` 不得缺漏。
- 共用 path/schema/subprocess/manifest 邏輯不在多支 production scripts 各自漂移。
- 刪除或搬移只能在 reference audit、impact plan、tests 與 rollback 證據完整時進行。
- 每 2–3 批執行 checkpoint，不讓長重構跨越未驗證狀態。

## Evidence

`.work/ARCH-UPGRADE-05/evidence/`
