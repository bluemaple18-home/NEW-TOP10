---
id: ARCH-UPGRADE-06
status: completed
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

- promotion decision：`NO-GO / retain_current_production`，可由來源 digest 重算。
- blockers：2026-07-09 代表日期 parity NO-GO、production-equivalent 日期 0/2、缺 persistent resume/failure/rollback acceptance、缺獨立 review。
- script governance：441/441 covered、94 production-reachable、0 contract gaps、0 unknown dynamic edges。
- promotion gate tests：36 passed；涵蓋 hypothetical GO、fixture relabel、單日期不足與任一代表日 NO-GO。
- production switch 未授權且未執行；`scripts/run_automation.py` 已做行為等價模組化，但 launchd target、live notification、ranking、model 均未切換。
