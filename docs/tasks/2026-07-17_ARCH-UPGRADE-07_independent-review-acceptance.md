---
id: ARCH-UPGRADE-07
status: blocked
type: acceptance
priority: P0
thickness: standard
model: gpt-5.5
reasoning: high
model_reason: 需獨立重算驗證、審查跨模組 diff 與 production regression surface。
---

# Independent review、repair 與主線驗收

## 目標

固定 base/candidate SHA，獨立檢查 correctness、production regression、schema compatibility、test sufficiency 與 scripts 清冊完整性。

## 依賴

- blocking edges：`ARCH-UPGRADE-01` 至 `ARCH-UPGRADE-06`。

## Review contract

- reviewer read-only，只看 diff、原始碼、tests 與 evidence。
- verdict 只能 `GO/NO-GO`，finding 含 severity、path/line、repro、required fix。
- `NO-GO` 由獨立 Repair 卡處理，原 reviewer re-review；最多兩輪 Repair。
- 主線重跑受影響測試與 `git diff --check`，核對 changed files allowlist。

## 完成定義

- control plane、impact planner、parity、script convergence 均有可重跑 evidence。
- production switch 若為 `GO`，有 rollback 與 acceptance；若為 `NO-GO`，確認 launchd target、正式通知、ranking/model 與 daily 行為契約未切換，並精確揭露 production entrypoint 原始碼變更。
- 文件、task status、result 與剩餘風險一致。

## Evidence

`.work/ARCH-UPGRADE-07/evidence/`
