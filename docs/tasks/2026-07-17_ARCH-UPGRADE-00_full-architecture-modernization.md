---
id: ARCH-UPGRADE-00
status: completed
type: program
priority: P0
thickness: strict
model: gpt-5.6-sol
reasoning: high
model_reason: 跨 production workflow、artifact schema、測試與腳本治理，且每日報牌具高回退成本。
---

# TOP10new 完整架構現代化總控卡

## Root question

如何在不破壞每日報牌的前提下，把 TOP10new 從大量 script 驅動的系統，完整升級成具 canonical control plane、可續跑 workflow、增量 impact planning、可驗證 promotion gate 與清楚模組邊界的正式架構？

## 使用者授權與邊界

- 完整做完，不採只覆蓋 happy path 的 MVP。
- 若每日 ranking、publish、通知或 launchd 有受影響風險，必須先維持 shadow，取得 parity 證據後才能切換。
- 不調整 ranking 權重，不覆蓋正式模型，不發送 live 訊息。
- 不修改任務開始前已存在的 unrelated dirty paths。

## 目標架構

```text
Source graph / registry
        ↓
Canonical architecture manifest
        ↓
Git diff → reverse impact → required tests / gates
        ↓
Versioned workflow contract → run manifest → parity evidence
        ↓
Promotion decision (GO / NO-GO) → explicit production switch or shadow retention
```

## 完整範圍

1. 全部 tracked `scripts/` 進入可重跑 lifecycle／reference／owner 清冊。
2. production entrypoint、workflow、artifact、producer、consumer、test/gate 具單一 machine-readable control plane。
3. Git diff 能輸出 reverse impact、受影響 workflow 與 required verification，不以固定品質分數代替證據。
4. Daily V2 與現行 production daily 有同輸入 parity harness、明確 mismatch taxonomy 與 promotion gate。
5. production-critical script 邏輯移入可測的 `app/` 模組；script 保持薄 CLI。
6. 完成獨立 review、repair/re-review 與主線 acceptance。

## 任務圖

| 卡片 | 目的 | Blocking edges |
|---|---|---|
| `ARCH-UPGRADE-01` | canonical control plane | 無 |
| `ARCH-UPGRADE-02` | incremental impact planner | 01 |
| `ARCH-UPGRADE-03` | daily parity contract/harness | 01 |
| `ARCH-UPGRADE-04` | production orchestration modularization | 01、03 |
| `ARCH-UPGRADE-05` | scripts 全量治理與共用邏輯收斂 | 01、02、04 |
| `ARCH-UPGRADE-06` | promotion gate 與安全切換判定 | 03、04、05 |
| `ARCH-UPGRADE-07` | independent review 與 acceptance | 01–06 |
| `ARCH-UPGRADE-08` | review findings repair 與雙軸 re-review | 07 |

最終狀態：01–08 已完成；Daily V2 production promotion 依 fail-closed 契約維持 `NO-GO / retain_current_production`。

## Checkpoints

- CP1：01–02 完成後，control plane 與 impact planner 可對 repo HEAD 重跑。
- CP2：03–04 完成後，正式入口仍未切換，parity harness 在隔離目錄可重跑。
- CP3：05 完成後，全 scripts 清冊無未分類、production dependency 無 unknown owner。
- CP4：06–07 完成後，只有 promotion gate `GO` 才允許 production switch；否則以 `NO-GO` 完整結案並保留 shadow。

## 全域驗收

- 所有 schema 都有版本、commit SHA、輸入 digest 與 fail-loud 驗證。
- 所有 lifecycle 都有 `pending/running/succeeded/failed/skipped` 或明確等價狀態。
- 禁止 workflow failure 後整條自動 fallback 重跑。
- required tests 由 dependency／contract evidence 推導，不以狀態文案自證。
- 受影響 unit／contract／integration tests、`git diff --check`、獨立 review 全部通過。

## Evidence

- `.work/ARCH-UPGRADE-00/evidence/`
- 各子卡指定的 result／evidence。
