---
id: ARCH-UPGRADE-06
status: blocked
type: acceptance
priority: P0
thickness: strict
model: gpt-5.6-sol
reasoning: xhigh
model_reason: production daily 切換或 NO-GO 判定，涉及正式排程、報牌與高回退成本。
---

# Daily V2 production promotion gate

## 目標

以實際 parity、failure injection、resume 與 wrapper evidence 判定 `GO/NO-GO`；不是預設一定切換。

## 依賴

- blocking edges：`ARCH-UPGRADE-03`、`ARCH-UPGRADE-04`、`ARCH-UPGRADE-05`。

## GO 必要條件

- 多個代表日期與 success/failure fixtures 無 unexplained mismatch。
- ranking/report/payload 日期與內容 contract 一致。
- timeout、partial output、stale input、resume 不會重複副作用。
- launchd/wrapper/status/publish guard 有可回滾切換計畫與 acceptance evidence。
- independent review `GO`。

任一條件不足即 `NO-GO`，維持現行 production，Daily V2 保留 shadow；`NO-GO` 是完整、安全的驗收結果，不得以進度壓力越過。

## 可改範圍

- promotion decision builder/verifier、tests、docs。
- 只有 gate `GO` 後才可修改 production entrypoint allowlist／wrapper；live notification 設定仍不可變更。

## Evidence

`.work/ARCH-UPGRADE-06/evidence/`
