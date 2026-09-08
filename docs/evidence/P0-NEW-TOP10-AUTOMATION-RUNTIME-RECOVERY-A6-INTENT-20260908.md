# Automation Recovery A6 — Disabled Job Intent Reconciliation

日期：2026-09-08

狀態：`A6_INTENT_RECONCILED / ACTIVATION_NOT_AUTHORIZED`

👉 [假設與目標確認] 目標：替五個 disabled launchd job 固定 canonical intent；邊界：只讀比對文件、plist、歷史 receipt 與現行 owner，不 enable、load、reload、kickstart、補跑、deploy 或外送；驗收：每個 job 都有 A6 允許的單一 verdict，且 `SHOULD_BE_PRODUCTION` 不被誤寫成已啟用或已驗收。

## 現況證據

- `launchctl print-disabled gui/501` 顯示五個 label 均為 disabled，`launchctl list` 沒有載入這五個 label。
- 五份 installed plist 都仍指向 active checkout `/Users/mattkuo/TOP10new`，不符合 A0 detached runtime boundary；不得原地 enable。
- repo 內五份 plist 都存在；存在 plist 只證明候選入口存在，不構成 production intent 或 activation readiness。
- 歷史 storage representative matrix 對五個 job 都是 `NO-GO`；該結果限制 activation readiness，不單獨否定 workflow intent。

## Canonical verdict

| Job | Verdict | 現行 workflow owner／理由 | Activation boundary |
| --- | --- | --- | --- |
| `reference` | `SHOULD_BE_PRODUCTION` | `docs/AUTOMATION.md` 固定每月 1 日 03:30 維護 reference；`config/script_lifecycle.yaml` 列為 production entrypoint；`scripts/setup_launchd.sh` 明確安裝並載入。 | 歷史 representative cycle 因 project file count 超限停止；需獨立 repair／capacity／activation slice，並切到 detached runtime。 |
| `retrain` | `SHOULD_BE_PRODUCTION` | 此 label 的 production intent 僅是每日 02:00 `monitor --trigger scheduled`；`docs/AUTOMATION.md` 與 plist 一致。`config/automation.yaml` 的 retrain schedule 仍為 `manual`，不得把本 verdict 擴成 scheduled model retraining。 | 需獨立 activation slice 驗證 exact monitor branch；不得藉此啟用自動訓練或 promotion。 |
| `pm-research-harness` | `SUPERSEDED` | plist 已固定 `TOP10_PM_RESEARCH_ENABLED=0`、`TOP10_RESEARCH_QUEUE_OWNER=fog_worker`；runtime revalidation 將它定義為 disabled standby；現行每日研究 quota 由 Fog worker 與 external-review handoff 承接，不再另開此排程。 | 維持 disabled；不得與 Fog worker 同時成為 queue writer。若未來要恢復，須新 measured-gap admission，而不是 A6 activation。 |
| `external-review` | `SHOULD_BE_PRODUCTION` | `docs/AUTOMATION.md` 與 `docs/architecture/external_review_workflow.md` 固定它為 17:50 host runner，daily OK 後才產 packet、呼叫既有 provider adapters，再交接 Fog Map。 | 需獨立 external authority、storage／provider preflight、detached runtime activation 與自然週期驗收；本 verdict 不授權送出外部 review。 |
| `baseline-harness` | `SHOULD_BE_PRODUCTION` | `WEEKEND-TRAINING-21` 明確把 host runner 推進到可安裝 launchd 的受控 medium-window research-only smoke；commit 歷史為 `Add guarded production baseline harness`，installed plist 亦存在。它不是 production ranking／promotion writer。 | 現行 `setup_launchd.sh` 未管理此 job，且最近 representative attempt 因 medium-window review artifact 非 OK 而 fail closed；需獨立 owner／capacity／fresh-policy activation slice。 |

## 八個 job 的 canonical intent

既有三個 enabled job 維持原判定：`daily`、`external-review-preflight`、`fog-research-worker` 均為 `SHOULD_BE_PRODUCTION`；其中 Fog 仍是 `NATURAL_ACCEPTANCE_PENDING`，不是健康完成宣告。

合併本次五個 verdict 後，八個正式 job 已都有 canonical intent：七個 `SHOULD_BE_PRODUCTION`，一個 `SUPERSEDED`。目前實際 enabled 仍只有三個；另外四個 activation candidates 不因本文件自動取得 activation authority。

## 後續切片

| Slice ID | traces_to | 狀態 | 驗收 |
| --- | --- | --- | --- |
| `A6-INTENT-REFERENCE` | `A6-DISABLED-JOB-INTENT-RECONCILIATION` | `VERDICT_COMPLETE` | intent 與 readiness 分離 |
| `A6-INTENT-RETRAIN-MONITOR` | `A6-DISABLED-JOB-INTENT-RECONCILIATION` | `VERDICT_COMPLETE` | 只涵蓋 monitor branch |
| `A6-INTENT-PM-HARNESS` | `A6-DISABLED-JOB-INTENT-RECONCILIATION` | `VERDICT_COMPLETE` | 維持 single queue owner |
| `A6-INTENT-EXTERNAL-REVIEW` | `A6-DISABLED-JOB-INTENT-RECONCILIATION` | `VERDICT_COMPLETE` | 未取得 external send authority |
| `A6-INTENT-BASELINE-HARNESS` | `A6-DISABLED-JOB-INTENT-RECONCILIATION` | `VERDICT_COMPLETE` | research-only，不碰 ranking／promotion |

四個 `SHOULD_BE_PRODUCTION` disabled jobs 必須分開建立 activation slice；共同前置條件是 detached runtime、storage capacity safety、rollback、自然週期 acceptance，以及各自 side-effect authority。沒有 bulk-enable 路徑。

Trace preflight 對本輪標記為 `not-applicable`：A6 是既有 recovery card 內已有穩定 ID 的 operational verdict，沒有新增產品需求、Jira 草稿或外部交接；上表直接追溯既有 `A6-DISABLED-JOB-INTENT-RECONCILIATION`。

## 結論

`A6-DISABLED-JOB-INTENT-RECONCILIATION = COMPLETE`

這只關閉 intent ambiguity。Automation Recovery program 仍未完成：Fog 自然週期 acceptance 仍由原對話觀察，四個 activation candidates 也尚未取得 activation authority。
